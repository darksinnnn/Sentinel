"""
Stretch Goals Demo UI — ISOLATED (port 8502)
=============================================
Runs independently of the main Sentinel UI (port 8501).
Does NOT import orchestrator, FastAPI, or any main-system tool.

Demonstrates:
  1. Accumulating Case Ledger (Priority 1):
     Stateless rule engine vs. trajectory-aware ledger score over 66 weeks.
  2. Insufficient Evidence (Priority 2):
     Population breakdown from the percentile-based classifier.

Launch:
    python -m streamlit run src/ui/stretch_goals_ui.py --server.port 8502
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# Import ONLY isolated stretch-goal modules — never orchestrator or main tools
from src.eval.synthetic_trajectory_generator import run as run_ledger_demo
from src.eval.test_insufficient_evidence import run as run_ie_report

st.set_page_config(
    page_title="Sentinel — Stretch Goals Demo",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header {
        font-size: 2rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem;
    }
    .sub-header { font-size: 1rem; color: #64748B; margin-bottom: 1.5rem; }
    .isolated-badge {
        display: inline-block; background: #FEF3C7; color: #92400E;
        padding: 3px 10px; border-radius: 5px; font-size: 0.8rem;
        font-weight: 600; margin-bottom: 1rem;
    }
    .insight-box {
        background: #F0FDF4; border-left: 4px solid #22C55E;
        padding: 12px 16px; border-radius: 6px; margin: 12px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🔬 Sentinel — Stretch Goals Demo</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Isolated from main system · Runs on port 8502</div>', unsafe_allow_html=True)
st.markdown('<div class="isolated-badge">⚠️ STRETCH GOAL — NOT IN PRODUCTION SYSTEM</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📈 Priority 1 — Accumulating Case Ledger", "⚖️ Priority 2 — Insufficient Evidence"])

# ── Priority 1: Accumulating Case Ledger ─────────────────────────────────────
with tab1:
    st.header("Temporal Trajectory Detection: Stateless vs. Ledger")

    st.markdown("""
    <div class="insight-box">
    <b>Structural argument:</b> A stateless point-in-time detector has a fundamental blind spot —
    an actor who spaces transactions further apart than the rolling window defeats it by construction,
    regardless of how many times they transact. The accumulating ledger catches what no single query can.
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Running synthetic trajectory demo and assertions…"):
        result = run_ledger_demo()

    df = pd.DataFrame(result["cycle_data"])
    threshold = result["alert_threshold"]
    breach_cycle = result["first_breach_cycle"]
    breach_week = df[df["cycle"] == breach_cycle]["week"].values[0]

    # ── Time-series chart ─────────────────────────────────────────────────
    fig = go.Figure()

    # Stateless baseline — flat
    fig.add_trace(go.Scatter(
        x=df["week"], y=df["stateless_score"],
        mode="lines+markers",
        name="Stateless Rule Engine Score",
        line=dict(color="#94A3B8", width=2.5, dash="dash"),
        marker=dict(size=7, color="#94A3B8"),
    ))

    # Ledger score — climbing
    fig.add_trace(go.Scatter(
        x=df["week"], y=df["ledger_score"],
        mode="lines+markers",
        name="Ledger Score (90-day decay)",
        line=dict(color="#3B82F6", width=3),
        marker=dict(size=8, color="#3B82F6"),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.08)",
    ))

    # Alert threshold line
    fig.add_hline(
        y=threshold, line_dash="dot", line_color="#EF4444", line_width=2,
        annotation_text=f"Alert Threshold ({threshold})",
        annotation_position="bottom right",
        annotation_font_color="#EF4444",
    )

    # Asymptotic ceiling
    fig.add_hline(
        y=1.087, line_dash="dot", line_color="#9CA3AF", line_width=1,
        annotation_text="Asymptotic ceiling (~1.09)",
        annotation_position="top right",
        annotation_font_color="#9CA3AF",
    )

    # Breach annotation
    breach_score = df[df["cycle"] == breach_cycle]["ledger_score"].values[0]
    fig.add_annotation(
        x=breach_week, y=breach_score,
        text=f"🚨 BREACH<br>Week {breach_week:.0f}",
        showarrow=True, arrowhead=2, arrowcolor="#EF4444",
        font=dict(color="#EF4444", size=12),
        bgcolor="white", bordercolor="#EF4444", borderwidth=1,
        ax=40, ay=-40,
    )

    fig.update_layout(
        title=dict(
            text="Stateless Rule Engine vs. Accumulating Ledger Score<br>"
                 "<sup>12 cycles · $7,500/42 days · 90-day decay half-life</sup>",
            font=dict(size=16)
        ),
        xaxis_title="Week (0 – 66)",
        yaxis_title="Risk Score",
        xaxis=dict(range=[0, 66], dtick=6),
        yaxis=dict(range=[-0.05, 1.2]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=480,
        plot_bgcolor="#FAFAFA",
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)

    # ── Comparison table ──────────────────────────────────────────────────
    st.subheader("Cycle-by-Cycle Comparison")
    df_display = df.copy()
    df_display["Stateless Verdict"] = "✅ CLEAN (no flags)"
    df_display["Ledger Verdict"] = df_display["ledger_score"].apply(
        lambda s: f"🚨 BREACH ({s:.3f})" if s >= threshold else f"accumulating ({s:.3f})"
    )
    df_display["Week"] = df_display["week"].apply(lambda w: f"Week {int(w)}")
    df_display["Day"] = df_display["day"]
    df_display["Ledger Score"] = df_display["ledger_score"].round(4)

    st.dataframe(
        df_display[["Cycle", "Week", "Day", "Stateless Verdict", "Ledger Score", "Ledger Verdict"]]
        .rename(columns={"cycle": "Cycle"}),
        use_container_width=True,
        hide_index=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("First Ledger Breach", f"Week {int(breach_week)}", f"Cycle {breach_cycle}")
    col2.metric("Stateless Detections", "0 / 12 cycles", "Misses actor completely")
    col3.metric("Alert Threshold", str(threshold), "Asymptotic ceiling ~1.09")

# ── Priority 2: Insufficient Evidence ────────────────────────────────────────
with tab2:
    st.header("Honest Uncertainty — Insufficient Evidence Classifier")

    st.markdown("""
    <div class="insight-box">
    <b>Why this matters:</b> Every team will output Low/Medium/High for every case.
    A fourth category — "insufficient evidence" — is a signal of <i>domain maturity</i>,
    not capability limitation. It flags the two populations a responsible system
    shouldn't pretend to know: extreme statistical outliers with no rule support,
    and accounts with too little history to baseline against.
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Computing insufficient evidence population from scored features…"):
        try:
            ie = run_ie_report()

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("p99.9 z-score Threshold", f"{ie['p999_threshold']:.3f}", "Computed from distribution")
            col2.metric("Criteria 1 (z-outlier, no flags)", f"{ie['c1_count']:,}", f"{100*ie['c1_count']/ie['total_rows']:.3f}% of dataset")
            col3.metric("Criteria 2 (< 3 txns)", f"{ie['c2_count']:,}", f"{100*ie['c2_count']/ie['total_rows']:.3f}% of dataset")
            col4.metric("Combined Unique", f"{ie['c1_count']+ie['c2_count']-ie['overlap']:,}", f"Overlap: {ie['overlap']:,}")

            st.info(f"**Note on merge readiness:** The p99.9 threshold computed here is **{ie['p999_threshold']:.4f}**. "
                    f"Before merging this classifier into the production anomaly_detector.py, verify this matches "
                    f"the threshold Phase 2 uses for the 'insufficient_evidence' tier.")

            # Visualization
            labels = ["Criteria 1 only\n(z-outlier, no rule flags)",
                      "Criteria 2 only\n(< 3 transactions)",
                      "Both criteria"]
            c1_only = ie["c1_count"] - ie["overlap"]
            c2_only = ie["c2_count"] - ie["overlap"]
            values  = [c1_only, c2_only, ie["overlap"]]

            fig2 = go.Figure(go.Bar(
                x=labels, y=values,
                marker_color=["#8B5CF6", "#3B82F6", "#EC4899"],
                text=[f"{v:,}" for v in values],
                textposition="outside",
            ))
            fig2.update_layout(
                title="Insufficient Evidence Population Breakdown",
                yaxis_title="Transaction Count",
                height=380,
                plot_bgcolor="#FAFAFA",
                paper_bgcolor="white",
            )
            st.plotly_chart(fig2, use_container_width=True)

        except FileNotFoundError:
            st.error(
                "scored_features.parquet not found. Run the Phase 1 rule engine pipeline first: "
                "`python src/features/rule_engine.py`"
            )
