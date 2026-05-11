"""
Narrate 节点：结果解读
=====================

功能：
1. 调用 LLM 生成专业解读
2. 基于"已计算结果"，不让 LLM 做计算
3. 返回结构化解读文本

解读要求：
1. 专业术语准确
2. 基于数据事实（不要编造数字）
3. 简洁明了（3-5 句话）
4. 可选：提供洞察（例如："整体市场处于上涨趋势"）

Prompt 设计：
- 查询意图（用户原始问题）
- 查询结果（表格 + 统计摘要）
- 要求：生成专业解读
"""

from typing import Dict, Any
import json

# TODO: from core.llm_client import LLMClient
# TODO: from core.configs.prompts import load_prompt

# ============================================================================
# Prompt 模板（待移至 configs/prompts/narrate.txt）
# ============================================================================

NARRATE_SYSTEM_PROMPT = """
You are a professional stock-market analyst. Your task is to interpret query results in English.

Requirements:
1. Ground the explanation in the provided data only.
2. Do not invent figures.
3. Use clear professional language.
4. Keep it concise unless the user asks for more detail.

Important: do not perform new calculations; all numbers must come from the provided result.
"""


# ============================================================================
# 解读函数
# ============================================================================

def narrate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    解读节点：生成专业解读

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 commentary）

    TODO:
    1. 构建解读 Prompt
    2. 调用 LLM 生成解读
    3. 添加日志和延迟记录
    """

    user_message = state.get("user_message", "")
    table = state.get("table", [])
    summary = state.get("summary", {})

    # ========================================================================
    # 构建解读 Prompt
    # ========================================================================

    prompt = f"""
{NARRATE_SYSTEM_PROMPT}

User question:
{user_message}

Query result ({len(table)} rows shown):
{json.dumps(table, ensure_ascii=False, indent=2)}

Summary:
{json.dumps(summary, ensure_ascii=False, indent=2)}

Write a professional interpretation in English, 3-5 sentences:
"""

    # ========================================================================
    # 调用 LLM
    # ========================================================================

    # TODO: 实现 LLM 调用
    # llm_client = LLMClient()
    # commentary = llm_client.chat(
    #     prompt,
    #     temperature=0.3,  # 稍高温度增加表达多样性
    #     max_tokens=256,
    # )
    # state["commentary"] = commentary

    # 占位
    row_count = summary.get("row_count", summary.get("总记录数", 0))
    state["commentary"] = f"Query complete. Returned {row_count} rows. The detailed data is shown above."

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 记录延迟
    # state.setdefault("debug", {}).setdefault("latency_ms", {})["narrate"] = ...

    # TODO: 添加日志
    # logger.info(f"[Narrate] session={state['session_id']}, commentary_length={len(commentary)}")

    return state
