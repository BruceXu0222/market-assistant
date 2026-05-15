"""
Streamlit demo UI.

Run:
    streamlit run app/ui_streamlit.py --server.port 8501
"""

import streamlit as st
import requests
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional, Dict, Any
import json

st.set_page_config(
    page_title="Market Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def get_streamlit_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a root-level Streamlit secret without failing outside Streamlit Cloud."""
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def get_nested_streamlit_secret(section: str, name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a nested Streamlit secret such as [llm] api_key = ... ."""
    try:
        return st.secrets.get(section, {}).get(name, default)
    except Exception:
        return default


def configure_env_from_streamlit_secrets() -> None:
    """Expose Streamlit Cloud secrets to the backend subprocess."""
    secret_mappings = {
        "OPENAI_API_KEY": get_streamlit_secret("OPENAI_API_KEY") or get_nested_streamlit_secret("llm", "api_key"),
        "OPENAI_BASE_URL": get_streamlit_secret("OPENAI_BASE_URL") or get_nested_streamlit_secret("llm", "base_url"),
        "OPENAI_MODEL": get_streamlit_secret("OPENAI_MODEL") or get_nested_streamlit_secret("llm", "model"),
    }
    for key, value in secret_mappings.items():
        if value and not os.getenv(key):
            os.environ[key] = str(value)


configure_env_from_streamlit_secrets()

API_BASE_URL = (
    os.getenv("API_BASE_URL")
    or get_streamlit_secret("API_BASE_URL")
    or get_nested_streamlit_secret("streamlit", "api_base_url")
    or "http://localhost:8080"
).rstrip("/")


def is_local_api_url(url: str) -> bool:
    """Return whether the UI expects an API running in the same container."""
    return url.startswith("http://localhost") or url.startswith("http://127.0.0.1")


def api_health(api_base_url: str, timeout: int = 5) -> bool:
    """Check whether an API URL is reachable."""
    try:
        response = requests.get(f"{api_base_url}/health", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def ensure_local_api_started(api_base_url: str) -> bool:
    """Start FastAPI when Streamlit is the only launched process."""
    if not is_local_api_url(api_base_url):
        return True

    if api_health(api_base_url, timeout=2):
        return True

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
        ],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    for _ in range(30):
        if process.poll() is not None:
            return False
        if api_health(api_base_url, timeout=2):
            return True
        time.sleep(1)

    return False

st.markdown("""
<style>
.user-message {
    background-color: #f0f2f6;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
}

.assistant-message {
    background-color: #ffffff;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border: 1px solid #e0e0e0;
}

.stChatInput {
    position: fixed;
    bottom: 0;
    width: 100%;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False

local_api_ready = ensure_local_api_started(API_BASE_URL)

def check_api_health() -> bool:
    """Check whether the API service is reachable."""
    return api_health(API_BASE_URL)


def call_chat_api(
    message: str,
    debug: bool = False,
    default_date: Optional[datetime] = None,
    default_market: str = "ALL",
) -> Optional[Dict[str, Any]]:
    """Call the FastAPI /chat endpoint."""
    try:
        default_date_value = default_date.strftime("%Y%m%d") if default_date else None
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "session_id": st.session_state.session_id,
                "debug": debug,
                "default_date": default_date_value,
                "default_market": default_market,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        st.session_state.session_id = data.get("session_id")

        return data

    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "Cannot connect to the API service. If you are using Streamlit Cloud, "
                "set API_BASE_URL to your deployed backend URL or check that the local "
                "backend subprocess started successfully."
            )
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}"}


def format_table(table_data: list) -> pd.DataFrame:
    """Format a result table for display."""
    if not table_data:
        return None

    df = pd.DataFrame(table_data)

    for col in df.columns:
        if df[col].dtype in ['float64']:
            if df[col].abs().max() > 1e8:
                df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")
            else:
                df[col] = df[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")

    return df


def prepare_chart_data(table_data: list) -> Optional[Dict[str, Any]]:
    """Build chart data for time-series or ranked result tables."""
    if not table_data:
        return None

    df = pd.DataFrame(table_data)
    if df.empty:
        return None

    numeric_cols = [
        col for col in df.columns
        if pd.api.types.is_numeric_dtype(pd.to_numeric(df[col], errors="coerce"))
    ]

    if "MDDate" in df.columns and "ClosePx" in df.columns and len(df) >= 2:
        chart_df = df.copy()
        chart_df["Date"] = pd.to_datetime(chart_df["MDDate"].astype(str), format="%Y%m%d", errors="coerce")
        chart_df["ClosePx"] = pd.to_numeric(chart_df["ClosePx"], errors="coerce")
        chart_df = chart_df.dropna(subset=["Date", "ClosePx"]).sort_values("Date")
        if len(chart_df) >= 2:
            return {
                "type": "line",
                "title": "Close Price Trend",
                "data": chart_df.set_index("Date")[["ClosePx"]],
            }

    preferred_metrics = [
        "ChangePct", "TurnoverRate", "TotalValueTrade",
        "TotalVolumeTrade", "Amplitude", "ClosePx",
    ]
    metric = next((col for col in preferred_metrics if col in numeric_cols), None)
    if not metric:
        return None

    label_col = "Symbol" if "Symbol" in df.columns else "SecurityID" if "SecurityID" in df.columns else None
    if not label_col:
        return None

    chart_df = df[[label_col, metric]].copy()
    chart_df[metric] = pd.to_numeric(chart_df[metric], errors="coerce")
    chart_df = chart_df.dropna(subset=[metric]).head(20)
    if chart_df.empty:
        return None

    return {
        "type": "bar",
        "title": f"{metric} by Stock",
        "data": chart_df.set_index(label_col),
    }


def render_result_chart(table_data: list) -> None:
    """Render a chart when the query result has chartable data."""
    chart = prepare_chart_data(table_data)
    if not chart:
        return

    st.markdown("**Chart**")
    if chart["type"] == "line":
        st.line_chart(chart["data"], use_container_width=True)
    else:
        st.bar_chart(chart["data"], use_container_width=True)


def render_debug_info(debug_info: Dict[str, Any]) -> None:
    """Render debug information."""
    if not debug_info:
        return

    with st.expander("Debug Info", expanded=False):
        if debug_info.get("validation_errors"):
            st.warning(f"Validation warnings: {debug_info['validation_errors']}")

        st.markdown("**QueryPlan**")
        st.json(debug_info.get("plan", {}))

        st.markdown("**Generated SQL**")
        st.code(debug_info.get("sql", ""), language="sql")

        st.markdown("**Data Files**")
        st.text(debug_info.get("parquet_paths", []))


def render_field_explanations(field_explanations: Dict[str, str]) -> None:
    """Render field explanations."""
    if not field_explanations:
        return

    with st.expander("Field Notes", expanded=True):
        for field, explanation in field_explanations.items():
            st.markdown(f"**{field}**：{explanation}")


with st.sidebar:
    st.title("Settings")
    st.caption(f"API: {API_BASE_URL}")

    if not local_api_ready:
        st.warning("API backend is not reachable.")

    if st.button("Check API Status"):
        if check_api_health():
            st.success("API service is healthy")
        else:
            st.error("API service is unavailable")

    st.markdown("---")

    st.session_state.debug_mode = st.checkbox(
        "Debug Mode",
        value=st.session_state.debug_mode,
        help="Show QueryPlan, SQL, and data file paths",
    )

    st.markdown("### Defaults")

    default_date = st.date_input(
        "Default Trading Date",
        value=datetime.now() - timedelta(days=1),
        help="Used when your question does not specify an exact date",
    )

    default_market = st.selectbox(
        "Default Market",
        options=["ALL", "HK", "US"],
        index=0,
        help="HK = Hong Kong stocks, US = US stocks, ALL = HK + US",
    )

    st.markdown("---")

    if st.button("Clear Chat"):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("### Help")
    st.markdown("""
    **Start the backend:**
    ```bash
    python -m uvicorn app.api:app --port 8080
    ```

    **Supported question types:**
    - Top gainers / losers
    - Turnover and volume rankings
    - Filter queries
    - Historical price trends
    """)

st.title("Market Assistant")
st.caption("GPT-5.5 + DuckDB stock market analysis for HK and US daily data")

st.markdown("---")

for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            if msg.get("table"):
                render_result_chart(msg["table"])
                st.markdown("**Results**")
                df = format_table(msg["table"])
                if df is not None:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No data")

            if msg.get("field_explanations"):
                render_field_explanations(msg["field_explanations"])

            if msg.get("analysis"):
                st.markdown("**Analysis**")
                st.markdown(msg["analysis"])

            if msg.get("error"):
                st.error(msg["error"])

            if st.session_state.debug_mode and msg.get("debug"):
                render_debug_info(msg["debug"])

if not st.session_state.messages:
    st.markdown("### Try These Questions")

    col1, col2 = st.columns(2)

    example_queries = [
        "How many HK stocks rose and fell today?",
        "Show the 10 biggest US stock decliners today",
        "Which stocks have turnover rate above 5% today?",
        "Show Tesla's price trend in January 2025",
    ]

    with col1:
        if st.button(example_queries[0], use_container_width=True):
            st.session_state.pending_query = example_queries[0]
            st.rerun()
        if st.button(example_queries[2], use_container_width=True):
            st.session_state.pending_query = example_queries[2]
            st.rerun()

    with col2:
        if st.button(example_queries[1], use_container_width=True):
            st.session_state.pending_query = example_queries[1]
            st.rerun()
        if st.button(example_queries[3], use_container_width=True):
            st.session_state.pending_query = example_queries[3]
            st.rerun()

if "pending_query" in st.session_state:
    query = st.session_state.pending_query
    del st.session_state.pending_query

    st.session_state.messages.append({"role": "user", "content": query})

    with st.spinner("Analyzing..."):
        response = call_chat_api(
            query,
            debug=st.session_state.debug_mode,
            default_date=default_date,
            default_market=default_market,
        )

    if response:
        assistant_msg = {"role": "assistant"}
        if response.get("error"):
            assistant_msg["error"] = response["error"]
        else:
            assistant_msg["table"] = response.get("table")
            assistant_msg["field_explanations"] = response.get("field_explanations")
            assistant_msg["analysis"] = response.get("commentary")
            assistant_msg["debug"] = response.get("debug")
        st.session_state.messages.append(assistant_msg)

    st.rerun()

if prompt := st.chat_input("Ask a market question, e.g. Which US stocks fell the most today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = call_chat_api(
                prompt,
                debug=st.session_state.debug_mode,
                default_date=default_date,
                default_market=default_market,
            )

        if response:
            assistant_msg = {"role": "assistant"}

            if response.get("error"):
                st.error(response["error"])
                assistant_msg["error"] = response["error"]
            else:
                if response.get("table"):
                    render_result_chart(response["table"])
                    st.markdown("**Results**")
                    df = format_table(response["table"])
                    if df is not None:
                        st.dataframe(df, use_container_width=True)
                    assistant_msg["table"] = response["table"]

                if response.get("field_explanations"):
                    render_field_explanations(response["field_explanations"])
                    assistant_msg["field_explanations"] = response["field_explanations"]

                if response.get("commentary"):
                    st.markdown("**Analysis**")
                    st.markdown(response["commentary"])
                    assistant_msg["analysis"] = response["commentary"]

                if st.session_state.debug_mode and response.get("debug"):
                    render_debug_info(response["debug"])
                    assistant_msg["debug"] = response["debug"]

            st.session_state.messages.append(assistant_msg)
