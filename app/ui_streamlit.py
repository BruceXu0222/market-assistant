"""
Streamlit 演示界面
=================

功能：
1. 提供类似 ChatGPT/Claude 的对话界面
2. 展示查询结果和分析
3. 可选 Debug 信息展示

使用方式：
    streamlit run app/ui_streamlit.py --server.port 8501
"""

import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional, Dict, Any
import json

# ============================================================================
# 配置
# ============================================================================

# FastAPI 服务地址
API_BASE_URL = "http://localhost:8080"

# 页面配置
st.set_page_config(
    page_title="智能行情分析助手",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# 自定义样式
# ============================================================================

st.markdown("""
<style>
/* 对话消息样式 */
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

/* 输入框容器固定在底部 */
.stChatInput {
    position: fixed;
    bottom: 0;
    width: 100%;
}

/* 隐藏 Streamlit 默认的页脚 */
footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 会话状态初始化
# ============================================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False

# ============================================================================
# 辅助函数
# ============================================================================

def check_api_health() -> bool:
    """检查 API 服务是否可用"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def call_chat_api(message: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """调用 FastAPI /chat 接口"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "session_id": st.session_state.session_id,
                "debug": debug,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        # 更新 session_id
        st.session_state.session_id = data.get("session_id")

        return data

    except requests.exceptions.ConnectionError:
        return {"error": "无法连接到 API 服务，请确保已启动后端服务"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API 调用失败: {e}"}


def format_table(table_data: list) -> pd.DataFrame:
    """格式化结果表格"""
    if not table_data:
        return None

    df = pd.DataFrame(table_data)

    # 格式化数值列
    for col in df.columns:
        if df[col].dtype in ['float64']:
            if df[col].abs().max() > 1e8:
                df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")
            else:
                df[col] = df[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")

    return df


def render_debug_info(debug_info: Dict[str, Any]) -> None:
    """渲染 Debug 信息"""
    if not debug_info:
        return

    with st.expander("调试信息", expanded=False):
        if debug_info.get("validation_errors"):
            st.warning(f"验证警告: {debug_info['validation_errors']}")

        st.markdown("**查询计划 (QueryPlan)**")
        st.json(debug_info.get("plan", {}))

        st.markdown("**生成的 SQL**")
        st.code(debug_info.get("sql", ""), language="sql")

        st.markdown("**数据文件**")
        st.text(debug_info.get("parquet_paths", []))


def render_field_explanations(field_explanations: Dict[str, str]) -> None:
    """渲染字段解释（复杂分析时使用）"""
    if not field_explanations:
        return

    with st.expander("📖 字段说明", expanded=True):
        for field, explanation in field_explanations.items():
            st.markdown(f"**{field}**：{explanation}")


# ============================================================================
# 侧边栏配置
# ============================================================================

with st.sidebar:
    st.title("配置")

    # API 状态检查
    if st.button("检查 API 状态"):
        if check_api_health():
            st.success("API 服务正常")
        else:
            st.error("API 服务不可用")

    st.markdown("---")

    # Debug 模式开关
    st.session_state.debug_mode = st.checkbox(
        "Debug 模式",
        value=st.session_state.debug_mode,
        help="展示 QueryPlan、SQL 等调试信息",
    )

    # 默认配置
    st.markdown("### 默认配置")

    default_date = st.date_input(
        "默认交易日",
        value=datetime.now() - timedelta(days=1),
        help="如果用户没有指定日期，使用此默认值",
    )

    default_market = st.selectbox(
        "默认市场",
        options=["ALL", "XSHG", "XSHE", "US"],
        index=0,
        help="XSHG=上交所, XSHE=深交所, US=美股, ALL=A股全部",
    )

    st.markdown("---")

    # 清空对话按钮
    if st.button("清空对话"):
        st.session_state.session_id = None
        st.session_state.messages = []
        st.rerun()

    # 帮助信息
    st.markdown("---")
    st.markdown("### 帮助")
    st.markdown("""
    **启动后端服务:**
    ```bash
    python -m uvicorn app.api:app --port 8080
    ```

    **支持的查询类型:**
    - 涨幅/跌幅排名
    - 成交额/量筛选
    - 涨跌停统计
    - 振幅分析
    """)

# ============================================================================
# 主界面 - 对话式布局
# ============================================================================

st.title("智能行情分析助手")
st.caption("基于Qwen3-32B + DuckDB 的股票行情分析系统")

st.markdown("---")

# ============================================================================
# 显示对话历史
# ============================================================================

for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            # 查询结果（表格）
            if msg.get("table"):
                st.markdown("**查询结果**")
                df = format_table(msg["table"])
                if df is not None:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("无数据")

            # 字段解释（复杂分析时显示）
            if msg.get("field_explanations"):
                render_field_explanations(msg["field_explanations"])

            # 查询结果分析（LLM 生成的内容）
            if msg.get("analysis"):
                st.markdown("**查询结果分析**")
                st.markdown(msg["analysis"])

            # 错误信息
            if msg.get("error"):
                st.error(msg["error"])

            # Debug 信息
            if st.session_state.debug_mode and msg.get("debug"):
                render_debug_info(msg["debug"])

# ============================================================================
# 示例问题（仅在没有对话时显示）
# ============================================================================

if not st.session_state.messages:
    st.markdown("### 试试这些问题")

    col1, col2 = st.columns(2)

    example_queries = [
        "今天涨幅前10的股票",
        "成交额最高的5只股票",
        "今天涨停的股票有哪些",
        "统计今天上涨和下跌的股票数量",
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

# ============================================================================
# 处理待处理的查询（来自示例按钮）
# ============================================================================

if "pending_query" in st.session_state:
    query = st.session_state.pending_query
    del st.session_state.pending_query

    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": query})

    # 调用 API
    with st.spinner("正在分析..."):
        response = call_chat_api(query, debug=st.session_state.debug_mode)

    # 添加助手消息
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

# ============================================================================
# 输入框
# ============================================================================

if prompt := st.chat_input("请输入您的问题，例如：今天涨幅前10的股票有哪些？"):
    # 添加用户消息到历史
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 API 并显示响应
    with st.chat_message("assistant"):
        with st.spinner("正在分析..."):
            response = call_chat_api(prompt, debug=st.session_state.debug_mode)

        if response:
            assistant_msg = {"role": "assistant"}

            if response.get("error"):
                st.error(response["error"])
                assistant_msg["error"] = response["error"]
            else:
                # 查询结果
                if response.get("table"):
                    st.markdown("**查询结果**")
                    df = format_table(response["table"])
                    if df is not None:
                        st.dataframe(df, use_container_width=True)
                    assistant_msg["table"] = response["table"]

                # 字段解释（复杂分析时显示）
                if response.get("field_explanations"):
                    render_field_explanations(response["field_explanations"])
                    assistant_msg["field_explanations"] = response["field_explanations"]

                # 查询结果分析
                if response.get("commentary"):
                    st.markdown("**查询结果分析**")
                    st.markdown(response["commentary"])
                    assistant_msg["analysis"] = response["commentary"]

                # Debug 信息
                if st.session_state.debug_mode and response.get("debug"):
                    render_debug_info(response["debug"])
                    assistant_msg["debug"] = response["debug"]

            # 保存助手消息到历史
            st.session_state.messages.append(assistant_msg)
