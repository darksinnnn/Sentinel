"""
Graph / Network Analysis Tool
==============================
Architecture ref: Sentinel_Architecture.md §5.3 (core tool) and §10 (differentiator #2)

Design:
  - Loads top-N suspicious senders from ml_scored.parquet (by ml_anomaly_score)
  - Expands 1 hop: pulls ALL transactions where sender OR receiver is in that seed set
  - Builds a directed NetworkX graph on the resulting edge list
  - Detects three structural AML patterns:
      * Fan-out   : one sender -> many unique receivers (structuring / smurfing distribution)
      * Fan-in    : many unique senders -> one receiver (aggregation before layering)
      * Cycle     : sender A -> B -> ... -> A (layering / round-tripping)
  - Returns List[FlaggedItem] + Plotly-ready JSON for the UI
  - Scoped to filtered subset only (country / segment / date window)

Performance:
  - Seed set capped at 500 high-risk senders => edge list typically 5K-50K rows in DuckDB
  - NetworkX graph stays <100K nodes — fast on any laptop
"""

import sys, math, logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import duckdb
import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.config import ML_SCORED_PATH
from src.schemas import ToolFilters, FlaggedItem
from src.audit.logger import log_event

logger = logging.getLogger(__name__)

# ── Thresholds (config-driven per §5.3) ──────────────────────────────────────
FAN_OUT_MIN_RECEIVERS   = 5    # sender -> N+ unique receivers  = potential structuring
FAN_IN_MIN_SENDERS      = 5    # N+ unique senders -> receiver  = aggregation / smurfing
CYCLE_MAX_LENGTH        = 6    # max cycle length to detect
SEED_LIMIT              = 500  # top-N anomalous senders to seed the graph
EDGE_LIMIT              = 50_000  # max edges pulled from DuckDB (safety cap)


def _build_date_clause(date_range: Optional[str]) -> str:
    """Converts '30d' / '7d' / '90d' to a DuckDB-compatible WHERE fragment."""
    if not date_range:
        return ""
    days_map = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}
    days = days_map.get(date_range.lower())
    if not days:
        return ""
    return f"AND CAST(txn_time AS DATE) >= (SELECT CAST(MAX(txn_time) AS DATE) - INTERVAL '{days}' DAY FROM read_parquet('{ML_SCORED_PATH}'))"


def run_graph_analysis(
    filters: ToolFilters,
    session_id: str = "default_session"
) -> Tuple[List[FlaggedItem], Dict[str, Any]]:
    """
    Entry point for the Graph/Network Analysis Tool.

    Returns:
        flagged_items   : List[FlaggedItem] with graph-structural risk flags
        graph_metrics   : Plotly-ready dict with nodes/edges for the UI
    """
    conn = duckdb.connect()

    # ── Step 1: Seed set — top anomalous senders ─────────────────────────────
    seed_query = f"""
        SELECT DISTINCT sender_id
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE ml_anomaly_score > 0.4
        ORDER BY ml_anomaly_score DESC
        LIMIT {SEED_LIMIT}
    """
    seed_df = conn.execute(seed_query).df()
    if seed_df.empty:
        logger.warning("Graph tool: no seed nodes found above threshold.")
        conn.close()
        return [], {}

    seed_ids = tuple(seed_df["sender_id"].tolist())
    seed_placeholder = ", ".join(f"'{s}'" for s in seed_ids)

    # ── Step 2: 1-hop expansion — all transactions touching any seed node ─────
    country_clause  = f"AND country = '{filters.country}'" if filters.country else ""
    segment_clause  = f"AND segment = '{filters.segment}'" if filters.segment else ""
    date_clause     = _build_date_clause(filters.date_range)

    edge_query = f"""
        SELECT sender_id, receiver_id, amount_paid, txn_time
        FROM read_parquet('{ML_SCORED_PATH}')
        WHERE (sender_id IN ({seed_placeholder}) OR receiver_id IN ({seed_placeholder}))
        {country_clause}
        {segment_clause}
        {date_clause}
        LIMIT {EDGE_LIMIT}
    """
    edge_df = conn.execute(edge_query).df()
    conn.close()


    if edge_df.empty:
        logger.warning("Graph tool: no edges found for seed set.")
        return [], {}

    logger.info("Graph tool: %d edges, %d unique nodes",
                len(edge_df),
                edge_df["sender_id"].nunique() + edge_df["receiver_id"].nunique())

    # ── Step 3: Build directed graph ──────────────────────────────────────────
    G = nx.DiGraph()
    for _, row in edge_df.iterrows():
        src, dst = str(row["sender_id"]), str(row["receiver_id"])
        amt = float(row.get("amount_paid", 0) or 0)
        if G.has_edge(src, dst):
            G[src][dst]["weight"] += amt
            G[src][dst]["count"] += 1
        else:
            G.add_edge(src, dst, weight=amt, count=1)

    # ── Step 4: Pattern Detection ─────────────────────────────────────────────
    flagged_items: List[FlaggedItem] = []
    graph_flags: Dict[str, Dict] = {}  # entity_id -> flag info

    # Fan-out: high out-degree = one sender distributing to many receivers
    for node in G.nodes():
        out_deg = G.out_degree(node)
        in_deg  = G.in_degree(node)
        total_out_amt = sum(d.get("weight", 0) for _, _, d in G.out_edges(node, data=True))

        if out_deg >= FAN_OUT_MIN_RECEIVERS:
            graph_flags[node] = {
                "pattern": "smurfing",
                "detail": f"Fan-out: {out_deg} unique receivers | Total outflow: ${total_out_amt:,.0f}",
                "out_degree": out_deg,
                "in_degree": in_deg,
                "total_out_amount": round(total_out_amt, 2),
            }

        if in_deg >= FAN_IN_MIN_SENDERS:
            total_in_amt = sum(d.get("weight", 0) for _, _, d in G.in_edges(node, data=True))
            existing = graph_flags.get(node, {})
            graph_flags[node] = {
                **existing,
                "pattern": "layering" if existing.get("pattern") == "smurfing" else "smurfing",
                "detail": (existing.get("detail", "") +
                           f" | Fan-in: {in_deg} unique senders | Total inflow: ${total_in_amt:,.0f}"),
                "in_degree": in_deg,
                "total_in_amount": round(total_in_amt, 2),
            }

    # Cycle detection (layering / round-trip)
    cycle_nodes: set = set()
    try:
        cycles = list(nx.simple_cycles(G))
        # Only count cycles up to CYCLE_MAX_LENGTH
        for cycle in cycles:
            if 2 <= len(cycle) <= CYCLE_MAX_LENGTH:
                for node in cycle:
                    cycle_nodes.add(node)
                    existing = graph_flags.get(node, {})
                    graph_flags[node] = {
                        **existing,
                        "pattern": "layering",
                        "cycle": True,
                        "cycle_length": len(cycle),
                        "detail": existing.get("detail", "") + f" | Cycle detected (len={len(cycle)})",
                    }
    except Exception as e:
        logger.warning("Cycle detection error (large graph): %s", e)

    # ── Step 5: Build FlaggedItems ────────────────────────────────────────────
    seed_set = set(seed_ids)
    for entity_id, flag in graph_flags.items():
        # Determine risk level: cycle or both fan-in+fan-out = high
        pattern = flag.get("pattern", "unspecified")
        is_cycle = flag.get("cycle", False)
        out_deg  = flag.get("out_degree", 0)
        in_deg   = flag.get("in_degree", 0)

        if is_cycle or (out_deg >= FAN_OUT_MIN_RECEIVERS and in_deg >= FAN_IN_MIN_SENDERS):
            risk_level = "high"
            action = "report"
        elif out_deg >= FAN_OUT_MIN_RECEIVERS or in_deg >= FAN_IN_MIN_SENDERS:
            risk_level = "medium"
            action = "review"
        else:
            risk_level = "low"
            action = "monitor"

        # Only include seed nodes (already anomalous by ML) or cycle nodes
        if entity_id not in seed_set and not is_cycle:
            continue

        sar = None
        if action == "report":
            sar = (
                f"SUSPICIOUS ACTIVITY REPORT DRAFT | Subject: {entity_id} | "
                f"Pattern: {pattern.upper()} (Graph-Structural) | "
                f"Detail: {flag.get('detail', '')} | "
                f"Recommended for immediate SAR filing and account freeze."
            )

        flagged_items.append(FlaggedItem(
            entity_type="customer",
            entity_id=entity_id,
            risk_level=risk_level,
            risk_score=round(
                min(1.0, (out_deg + in_deg) / (2 * max(FAN_OUT_MIN_RECEIVERS, 1))), 4
            ),
            detected_pattern=pattern,
            explanation=(
                f"Graph analysis flagged {entity_id} for {pattern} pattern. "
                f"{flag.get('detail', '')}. "
                f"{'Cycle detected — funds may be round-tripping through intermediaries (layering).' if is_cycle else ''}"
            ),
            evidence={
                "out_degree": out_deg,
                "in_degree": in_deg,
                "cycle_detected": is_cycle,
                "cycle_length": flag.get("cycle_length"),
                "total_out_amount": flag.get("total_out_amount"),
                "total_in_amount": flag.get("total_in_amount"),
                "graph_detail": flag.get("detail", ""),
            },
            recommended_action=action,
            sar_draft=sar,
        ))

    # Sort by risk_score descending
    flagged_items.sort(key=lambda x: x.risk_score, reverse=True)

    # ── Step 6: Build Plotly-ready graph JSON ─────────────────────────────────
    # Sample top 200 nodes for visualization (browser can't render 100K nodes)
    top_nodes = (
        sorted(graph_flags.keys(),
               key=lambda n: graph_flags[n].get("out_degree", 0) +
                             graph_flags[n].get("in_degree", 0),
               reverse=True)[:200]
    )
    top_nodes_set = set(top_nodes)

    # Build Plotly scatter + edge traces
    pos: Dict[str, Tuple] = {}
    try:
        subG = G.subgraph(top_nodes_set)
        pos_raw = nx.spring_layout(subG, seed=42, k=2.0)
        pos = {n: (float(xy[0]), float(xy[1])) for n, xy in pos_raw.items()}
    except Exception:
        pass

    nodes_data = []
    for n in top_nodes_set:
        flag = graph_flags.get(n, {})
        nodes_data.append({
            "id": n,
            "x": pos.get(n, (0, 0))[0],
            "y": pos.get(n, (0, 0))[1],
            "pattern": flag.get("pattern", "normal"),
            "out_degree": flag.get("out_degree", 0),
            "in_degree": flag.get("in_degree", 0),
            "cycle": flag.get("cycle", False),
        })

    edges_data = [
        {
            "source": u, "target": v,
            "weight": round(d.get("weight", 0), 2),
            "count": d.get("count", 1),
        }
        for u, v, d in G.edges(data=True)
        if u in top_nodes_set and v in top_nodes_set
    ]

    graph_metrics = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "fan_out_count": sum(1 for n, f in graph_flags.items() if f.get("out_degree", 0) >= FAN_OUT_MIN_RECEIVERS),
        "fan_in_count": sum(1 for n, f in graph_flags.items() if f.get("in_degree", 0) >= FAN_IN_MIN_SENDERS),
        "cycle_node_count": len(cycle_nodes),
        "nodes": nodes_data,
        "edges": edges_data,
    }

    log_event("graph_tool_executed", {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "flagged": len(flagged_items),
        "fan_out": graph_metrics["fan_out_count"],
        "fan_in": graph_metrics["fan_in_count"],
        "cycles": graph_metrics["cycle_node_count"],
    }, session_id=session_id)

    logger.info("Graph tool: flagged %d entities (%d fan-out, %d fan-in, %d cycle nodes)",
                len(flagged_items),
                graph_metrics["fan_out_count"],
                graph_metrics["fan_in_count"],
                graph_metrics["cycle_node_count"])

    return flagged_items, graph_metrics
