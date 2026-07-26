import sys
import json
import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.agent.orchestrator import process_query

API_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(
    page_title="Sentinel AML | Conversational Compliance Analyst",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .badge-high {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-medium {
        background-color: #FFEDD5;
        color: #9A3412;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-evidence {
        background-color: #F3E8FF;
        color: #6B21A8;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-low {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🛡️ Sentinel AML Intelligence Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Conversational Compliance Analyst | Auditable Agentic Risk Orchestration</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Agent Controls")
    session_id = st.text_input("Session ID", value="session_demo_01")
    use_api = st.checkbox("Connect via FastAPI Endpoint", value=False, help="Route requests through FastAPI backend (127.0.0.1:8000)")
    
    st.divider()
    st.subheader("💡 Demo Query Benchmarks")
    st.caption("Click any query to execute dynamic routing:")
    
    preset_query = None
    if st.button("🔍 Targeted: Structuring 30d"):
        preset_query = "Find structuring patterns in the last 30 days"
    if st.button("📊 Aggregation: 10+ txns under $10k"):
        preset_query = "Which customers made 10+ transactions under $10k?"
    if st.button("👤 Entity Lookup: Account 8000EBD30"):
        preset_query = "Is customer 8000EBD30 suspicious?"
    if st.button("🌐 Broad Scan: Full Dataset Analysis"):
        preset_query = "Analyze this entire dataset and give me top suspicious activities"

    st.divider()
    st.info("🔒 **Immutable Audit Hash-Chaining Enabled**\nEvery query & tool execution is recorded to `audit.db` with SHA-256 state hashing.")

# Chat Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "data" in msg:
            res_data = msg["data"]
            # Render execution summary
            with st.expander("🛠️ Query-Aware Execution Summary", expanded=False):
                st.json(res_data["execution_summary"])

# Input Handling
user_input = st.chat_input("Ask Sentinel (e.g., 'Find structuring patterns in last 30 days')...")
active_query = preset_query or user_input

if active_query:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": active_query})
    with st.chat_message("user"):
        st.write(active_query)

    # Process query
    with st.chat_message("assistant"):
        with st.spinner("Sentinel Orchestrator analyzing query & executing tool graph..."):
            response_json = None
            if use_api:
                try:
                    res = requests.post(API_URL, json={"query": active_query, "session_id": session_id}, timeout=15)
                    if res.status_code == 200:
                        response_json = res.json()
                    else:
                        st.error(f"API Error {res.status_code}: {res.text}")
                except Exception as e:
                    st.warning(f"FastAPI connection failed ({e}). Falling back to in-process orchestrator.")
            
            if not response_json:
                agent_res = process_query(active_query, session_id=session_id)
                response_json = agent_res.model_dump()

            exec_sum = response_json.get("execution_summary", {})
            flagged = response_json.get("flagged_items", [])
            metrics = response_json.get("supporting_metrics", {})
            audit_ref = response_json.get("audit_ref", "N/A")

            # 1. Execution Summary Card
            st.success(f"**Execution Complete** | Audit Ref: `{audit_ref}`")
            with st.expander("🛠️ Query-Aware Execution Plan & Summary", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Detected Intent:** `{exec_sum.get('detected_intent')}`")
                    st.markdown(f"**Invoked Tools:** `{', '.join(exec_sum.get('tools_invoked', []))}`")
                with col2:
                    st.markdown(f"**Skipped Tools:** `{', '.join(exec_sum.get('tools_skipped', []))}`")
                    st.markdown(f"**Filters:** `{json.dumps(exec_sum.get('filters_detected', {}))}`")
                st.caption(f"**Reasoning:** {exec_sum.get('reasoning')}")

            # 2. Flagged Items Summary
            st.subheader(f"🚨 Flagged Results ({len(flagged)} items)")
            
            if not flagged:
                st.info("No items met suspicious thresholds for this query.")
            else:
                for idx, item in enumerate(flagged):
                    level = item.get("risk_level", "low").lower()
                    
                    if level == "high":
                        badge_html = '<span class="badge-high">HIGH RISK</span>'
                    elif level == "medium":
                        badge_html = '<span class="badge-medium">MEDIUM RISK</span>'
                    elif level == "insufficient_evidence":
                        badge_html = '<span class="badge-evidence">INSUFFICIENT EVIDENCE</span>'
                    else:
                        badge_html = '<span class="badge-low">LOW RISK</span>'

                    title = f"Item #{idx+1}: {item.get('entity_type', '').title()} `{item.get('entity_id')}` | Score: {item.get('risk_score', 0):.2f}"
                    
                    with st.expander(f"{item.get('entity_id')} — {item.get('detected_pattern', 'unknown')} ({level.upper()})", expanded=(idx==0)):
                        st.markdown(f"### {badge_html} &nbsp; {title}", unsafe_allow_html=True)
                        st.markdown(f"**Pattern Detected:** `{item.get('detected_pattern')}`")
                        st.markdown(f"**Explanation:** {item.get('explanation')}")
                        st.markdown(f"**Recommended Action:** `{item.get('recommended_action', 'review').upper()}`")
                        
                        if item.get("evidence"):
                            st.json(item["evidence"], expanded=False)

                        if item.get("sar_draft"):
                            st.markdown("#### 📄 Draft Suspicious Activity Report (SAR)")
                            st.info(item["sar_draft"])

            # 3. Supporting Visualizations & Metrics
            if metrics:
                st.subheader("📊 Supporting Metrics & Evidence Visuals")

                # Graph Analysis Metrics
                if "graph" in metrics:
                    g = metrics["graph"]
                    st.markdown("#### 🌐 Graph Network Topology Analysis (NetworkX)")
                    gcol1, gcol2, gcol3, gcol4, gcol5 = st.columns(5)
                    gcol1.metric("Nodes", g.get("total_nodes", 0))
                    gcol2.metric("Edges", g.get("total_edges", 0))
                    gcol3.metric("Smurfing (Fan-Out)", g.get("fan_out_count", 0))
                    gcol4.metric("Aggregation (Fan-In)", g.get("fan_in_count", 0))
                    gcol5.metric("Layering Cycles", g.get("cycle_node_count", 0))

                # OFAC Sanctions Matches
                if "ofac_sanctions_matches" in metrics and metrics["ofac_sanctions_matches"]:
                    st.markdown("#### 🛡️ OFAC Sanctions Matches")
                    st.warning(f"Matches Found: {len(metrics['ofac_sanctions_matches'])}")
                    st.json(metrics["ofac_sanctions_matches"])

                # Population & EDA Stats
                if "risk_distribution" in metrics:
                    dist = metrics["risk_distribution"]
                    df_dist = pd.DataFrame(list(dist.items()), columns=["Risk Tier", "Count"])
                    fig = px.pie(df_dist, names="Risk Tier", values="Count", title="Risk Tier Distribution", color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig, use_container_width=True)

                if "amount_statistics" in metrics:
                    st.markdown("#### 💵 Monetary Distribution Statistics")
                    st.json(metrics["amount_statistics"])

            # Store message in chat history
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Processed query '{active_query}'. Flagged {len(flagged)} items. Audit Ref: `{audit_ref}`",
                "data": response_json
            })

