"""
PostProcess 节点：后处理
========================

功能：
1. 格式化数值（保留小数位）
2. 处理空值（NaN → "-"）
3. 计算统计摘要（min/max/mean/分位数）
4. 转换为输出表格（List[Dict]）

统计摘要示例：
{
  "总记录数": 10,
  "涨幅最大": 15.32,
  "涨幅最小": 8.45,
  "涨幅均值": 11.23,
  "涨幅中位数": 10.98
}
"""

from typing import Dict, Any, List
import pandas as pd

# ============================================================================
# 后处理函数
# ============================================================================

def postprocess_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    后处理节点：格式化、统计摘要

    Args:
        state: LangGraph 状态

    Returns:
        state: 更新后的状态（包含 table, summary）

    TODO:
    1. 格式化数值（保留 2 位小数）
    2. 处理 NaN（替换为 "-"）
    3. 计算统计摘要
    4. 转换为 List[Dict] 格式
    5. 添加日志
    """

    dataframe = state.get("dataframe")

    if dataframe is None or (isinstance(dataframe, pd.DataFrame) and dataframe.empty):
        state["table"] = []
        state["summary"] = {"总记录数": 0}
        return state

    # ========================================================================
    # 1. 格式化数值
    # ========================================================================

    # TODO: 实现格式化逻辑
    # df_formatted = dataframe.copy()
    #
    # # 保留 2 位小数
    # numeric_cols = df_formatted.select_dtypes(include=['float64', 'float32']).columns
    # df_formatted[numeric_cols] = df_formatted[numeric_cols].round(2)
    #
    # # 处理 NaN
    # df_formatted = df_formatted.fillna("-")

    # 占位
    df_formatted = dataframe

    # ========================================================================
    # 2. 转换为 List[Dict]
    # ========================================================================

    # TODO: 实现转换
    # table = df_formatted.to_dict(orient="records")
    # state["table"] = table

    # 占位
    state["table"] = []

    # ========================================================================
    # 3. 计算统计摘要
    # ========================================================================

    # TODO: 实现统计摘要
    # summary = {"总记录数": len(dataframe)}
    #
    # # 对数值列计算统计量
    # query_plan = state.get("query_plan", {})
    # metrics = query_plan.get("metrics", [])
    #
    # for metric in metrics:
    #     if metric in dataframe.columns:
    #         col = dataframe[metric]
    #         if pd.api.types.is_numeric_dtype(col):
    #             summary[f"{metric}最大"] = round(col.max(), 2)
    #             summary[f"{metric}最小"] = round(col.min(), 2)
    #             summary[f"{metric}均值"] = round(col.mean(), 2)
    #             summary[f"{metric}中位数"] = round(col.median(), 2)
    #
    # state["summary"] = summary

    # 占位
    state["summary"] = {"总记录数": 0}

    # ========================================================================
    # 日志记录
    # ========================================================================

    # TODO: 添加日志
    # logger.info(f"[PostProcess] session={state['session_id']}, summary={summary}")

    return state
