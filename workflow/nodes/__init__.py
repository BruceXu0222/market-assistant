"""
LangGraph 节点定义
=================

8 个核心节点：
1. router: 路由节点（判断查询类型）
2. plan_gen: 计划生成（NL → QueryPlan）
3. validate: 校验（Schema + 白名单 + 业务规则）
4. repair: 修复（校验失败时让 LLM 修复）
5. execute: 执行（QueryPlan → SQL → DuckDB）
6. postprocess: 后处理（格式化、统计摘要）
7. narrate: 解读（生成专业解读文本）
8. memory_update: 记忆更新（更新会话状态）
"""
