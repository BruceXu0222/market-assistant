"""
Router 节点：路由判断
====================

功能：
1. 分析用户输入的自然语言
2. 判断查询类型：
   - market_query: 行情查询（TopK、筛选、排序等）
   - field_explain: 字段解释（"LastPx 是什么？"）
   - chitchat: 闲聊（"你好"、"谢谢"）
3. 设置 query_type，供后续节点使用

实现方式：
- 方案1：基于规则（关键词匹配）
- 方案2：调用 LLM 分类（更准确，但增加延迟）
- MVP 建议：先用方案1，后续优化为方案2
"""

from typing import Dict, Any
# TODO: from core.llm_client import LLMClient

# ============================================================================
# 路由规则（基于关键词）
# ============================================================================

MARKET_QUERY_KEYWORDS = [
    "涨幅", "跌幅", "排名", "前", "后", "TopK", "筛选", "成交额", "成交量",
    "买一", "卖一", "盘口", "股票", "振幅", "价格", "最高", "最低",
    "stock", "stocks", "market", "gainer", "gainers", "decliner", "decliners",
    "loser", "losers", "turnover", "volume", "price", "trend", "highest",
    "lowest", "top", "rank", "ranking", "filter", "amplitude",
]

FIELD_EXPLAIN_KEYWORDS = [
    "是什么", "什么意思", "解释", "含义", "定义", "字段",
    "what is", "what does", "meaning", "explain", "definition", "field",
]

CHITCHAT_KEYWORDS = [
    "你好", "谢谢", "再见", "帮助", "介绍", "你是谁",
    "hello", "hi", "thanks", "thank you", "bye", "help", "who are you",
]


# ============================================================================
# 路由函数
# ============================================================================

def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    路由节点：判断查询类型

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 query_type）

    TODO:
    1. 实现基于关键词的规则路由
    2. 可选：调用 LLM 进行分类（更准确）
    3. 添加日志记录
    """

    user_message = state.get("user_message", "")

    # ========================================================================
    # 方案1：基于关键词的规则路由（MVP）
    # ========================================================================

    # 判断是否为字段解释
    if any(keyword in user_message for keyword in FIELD_EXPLAIN_KEYWORDS):
        state["query_type"] = "field_explain"
        # TODO: 实现字段解释逻辑（从数据字典查询）
        return state

    # 判断是否为闲聊
    if any(keyword in user_message for keyword in CHITCHAT_KEYWORDS):
        state["query_type"] = "chitchat"
        # TODO: 实现闲聊响应（简单模板或调用 LLM）
        state["commentary"] = "Hello. I can help analyze HK and US daily stock data. What would you like to query?"
        return state

    # 判断是否为行情查询
    if any(keyword in user_message for keyword in MARKET_QUERY_KEYWORDS):
        state["query_type"] = "market_query"
        return state

    # 默认：行情查询
    state["query_type"] = "market_query"

    # ========================================================================
    # 方案2：调用 LLM 分类（可选优化）
    # ========================================================================

    # TODO: 实现 LLM 分类
    # llm_client = LLMClient()
    # prompt = f"""
    # 请判断用户输入的查询类型：
    # 用户输入：{user_message}
    #
    # 输出格式（JSON）：
    # {{"query_type": "market_query" | "field_explain" | "chitchat"}}
    # """
    # response = llm_client.chat(prompt, temperature=0.0)
    # query_type = parse_json(response)["query_type"]
    # state["query_type"] = query_type

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 添加日志
    # logger.info(f"[Router] session={state['session_id']}, query_type={state['query_type']}")

    return state
