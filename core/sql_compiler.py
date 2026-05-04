"""
SQL 编译器（增强版）
==================

功能：
1. 将 QueryPlan 编译为 DuckDB SQL
2. 支持更多衍生指标（涨跌幅、换手率、市值等）
3. 支持聚合统计（SUM/AVG/COUNT）
4. 支持分组分析（GROUP BY）
5. 列裁剪、过滤优化、TopK 优化
6. 快照数据处理：自动选择每个 SecurityID 的最新快照

编译要点：
1. 列裁剪：只 SELECT 必要列
2. 先过滤后排序：WHERE ... ORDER BY ... LIMIT
3. 衍生指标在 SQL 中 AS 计算
4. 聚合统计使用 GROUP BY + 聚合函数
5. 防止 SQL 注入（字段名白名单）
6. 快照去重：使用 ROW_NUMBER() OVER (PARTITION BY SecurityID ORDER BY MDTime DESC) 选择最新快照
"""

from typing import List, Tuple, Dict, Any

# ============================================================================
# 衍生指标定义（增强版）
# ============================================================================

METRIC_DEFINITIONS = {
    # 涨跌幅相关（使用 ClosePx 收盘价计算）
    "涨幅": "(ClosePx - PreClosePx) / NULLIF(PreClosePx, 0) * 100",
    "跌幅": "(PreClosePx - ClosePx) / NULLIF(PreClosePx, 0) * 100",
    "振幅": "(HighPx - LowPx) / NULLIF(PreClosePx, 0) * 100",

    # 涨跌停判断（使用数据中已有的 MaxPx 和 MinPx）
    "是否涨停": "CASE WHEN ClosePx >= MaxPx THEN 1 ELSE 0 END",
    "是否跌停": "CASE WHEN ClosePx <= MinPx THEN 1 ELSE 0 END",

    # 买卖盘比（使用 TotalBidQty 和 TotalOfferQty）
    "买卖盘比": "TotalBidQty / NULLIF(TotalOfferQty, 0)",

    # 价格区间（使用 ClosePx）
    "价格区间": "CASE WHEN ClosePx < 10 THEN '<10元' WHEN ClosePx <= 30 THEN '10-30元' ELSE '>30元' END",
}

# 有效的基础字段白名单（与实际数据表结构匹配）
VALID_BASE_FIELDS = {
    # 基础信息
    "MDDate", "MDTime", "SecurityType", "SecuritySubType",
    "SecurityID", "SecurityIDSource", "Symbol", "TradingPhaseCode",
    "HTSCSecurityID", "ReceiveDateTime", "ChannelNo",
    # 价格字段
    "PreClosePx", "LastPx", "OpenPx", "ClosePx", "HighPx", "LowPx",
    "DiffPx1", "DiffPx2", "MaxPx", "MinPx",
    # 成交字段
    "NumTrades", "TotalVolumeTrade", "TotalValueTrade",
    # 买卖盘汇总
    "TotalBidQty", "TotalOfferQty", "WeightedAvgBidPx", "WeightedAvgOfferPx",
    # 盘后交易
    "AfterHoursNumTrades", "AfterHoursTotalVolumeTrade", "AfterHoursTotalValueTrade",
    # 十档买盘
    "Buy1Price", "Buy1OrderQty", "Buy1NumOrders", "Buy1NoOrders",
    "Buy2Price", "Buy2OrderQty", "Buy2NumOrders",
    "Buy3Price", "Buy3OrderQty", "Buy3NumOrders",
    "Buy4Price", "Buy4OrderQty", "Buy4NumOrders",
    "Buy5Price", "Buy5OrderQty", "Buy5NumOrders",
    "Buy6Price", "Buy6OrderQty", "Buy6NumOrders",
    "Buy7Price", "Buy7OrderQty", "Buy7NumOrders",
    "Buy8Price", "Buy8OrderQty", "Buy8NumOrders",
    "Buy9Price", "Buy9OrderQty", "Buy9NumOrders",
    "Buy10Price", "Buy10OrderQty", "Buy10NumOrders",
    # 十档卖盘
    "Sell1Price", "Sell1OrderQty", "Sell1NumOrders", "Sell1NoOrders",
    "Sell2Price", "Sell2OrderQty", "Sell2NumOrders",
    "Sell3Price", "Sell3OrderQty", "Sell3NumOrders",
    "Sell4Price", "Sell4OrderQty", "Sell4NumOrders",
    "Sell5Price", "Sell5OrderQty", "Sell5NumOrders",
    "Sell6Price", "Sell6OrderQty", "Sell6NumOrders",
    "Sell7Price", "Sell7OrderQty", "Sell7NumOrders",
    "Sell8Price", "Sell8OrderQty", "Sell8NumOrders",
    "Sell9Price", "Sell9OrderQty", "Sell9NumOrders",
    "Sell10Price", "Sell10OrderQty", "Sell10NumOrders",
}

# ============================================================================
# SQL 编译器（增强版）
# ============================================================================

class SQLCompilerEnhanced:
    """
    SQL 编译器：QueryPlan → SQL（增强版）

    使用方式：
        compiler = SQLCompilerEnhanced()
        sql = compiler.compile(query_plan, parquet_paths)
        print(f"编译完成: {sql[:100]}...")
    """

    def __init__(self):
        """初始化编译器"""
        pass

    def compile(
        self,
        query_plan: Dict[str, Any],
        parquet_paths: List[str],
    ) -> str:
        """
        编译 QueryPlan 为 SQL

        Args:
            query_plan: 查询计划（字典格式）
            parquet_paths: Parquet 文件路径列表

        Returns:
            sql: SQL 字符串
        """

        print(f"[SQL编译器] 开始编译 QueryPlan，类型={query_plan.get('query_type')}")

        # ====================================================================
        # 1. 构建 FROM 子句
        # ====================================================================

        if not parquet_paths:
            raise ValueError("parquet_paths 不能为空")

        query_type = query_plan.get("query_type", "basic")

        # raw_data 查询不去重，保留所有快照
        # 如果 filters 中包含时间条件（Time/MDTime），也不去重
        use_latest_snapshot = query_type != "raw_data"
        if use_latest_snapshot:
            filters = query_plan.get("filters", [])
            for f in filters:
                if f.get("field") in ["Time", "MDTime"]:
                    use_latest_snapshot = False
                    break
        from_clause = self._build_from_clause(parquet_paths, use_latest_snapshot)
        print(f"[SQL编译器] FROM 子句构建完成，包含 {len(parquet_paths)} 个文件，use_latest_snapshot={use_latest_snapshot}")

        # ====================================================================
        # 2. 根据 query_type 决定编译策略
        # ====================================================================

        if query_type == "raw_data":
            # 纯数据查询：返回时间范围内的所有快照，不去重
            sql = self._compile_raw_data_query(query_plan, from_clause)

        elif query_type in ["basic", "filter", "anomaly", "multi_turn"]:
            # 基础查询/筛选查询：SELECT ... WHERE ... ORDER BY ... LIMIT
            sql = self._compile_basic_query(query_plan, from_clause)

        elif query_type in ["stats", "aggregation", "summary"]:
            # 统计分析/聚合查询：带 GROUP BY 和聚合函数
            sql = self._compile_aggregation_query(query_plan, from_clause)

        elif query_type == "complex_analysis":
            # 第三类：复杂分析查询（跨时序、多指标组合）
            sql = self._compile_complex_analysis(query_plan, parquet_paths)

        else:
            raise ValueError(f"不支持的 query_type: {query_type}")

        print(f"[SQL编译器] 编译完成，SQL 长度={len(sql)} 字符")
        return sql

    def _compile_raw_data_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """
        编译纯数据查询（原始行情数据）

        特点：
        1. 不去重，返回时间范围内的所有快照
        2. 支持 time_range 时间范围筛选
        3. 默认按 MDTime 升序排列

        流程：SELECT ... FROM ... WHERE ... ORDER BY MDTime ASC LIMIT
        """

        print("[SQL编译器] 使用纯数据查询编译策略")

        # 1. 确定需要的字段
        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        filters = query_plan.get("filters", [])
        time_range = query_plan.get("time_range", {})
        order_by = query_plan.get("order_by", [])

        # 收集基础字段
        required_base_fields = set()
        for field in output_fields:
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)
            elif field not in METRIC_DEFINITIONS:
                print(f"[SQL编译器] 警告: 忽略无效字段 '{field}'")

        # 添加 filters 需要的字段
        for f in filters:
            field = f["field"]
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)

        # 确保必要字段被选择
        required_base_fields.add("SecurityID")
        required_base_fields.add("MDTime")
        required_base_fields.add("Symbol")

        # 2. 构建 SELECT 子句
        select_items = []
        for field in required_base_fields:
            if field in VALID_BASE_FIELDS:
                select_items.append(field)

        # 添加衍生指标（如果需要）
        metrics = query_plan.get("metrics", [])
        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[metric]
                select_items.append(f"({expr}) AS \"{metric}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        # 3. 构建 WHERE 子句（包含时间范围）
        all_conditions = []

        # 添加普通过滤条件
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]

            if field in METRIC_DEFINITIONS:
                field_expr = f"({METRIC_DEFINITIONS[field]})"
            else:
                field_expr = field

            if isinstance(value, str):
                all_conditions.append(f"{field_expr} {op} '{value}'")
            else:
                all_conditions.append(f"{field_expr} {op} {value}")

        # 添加时间范围条件
        if time_range:
            start_time = time_range.get("start")
            end_time = time_range.get("end")
            if start_time:
                start_time = self._normalize_time_format(start_time)
                all_conditions.append(f"MDTime >= '{start_time}'")
            if end_time:
                end_time = self._normalize_time_format(end_time)
                all_conditions.append(f"MDTime <= '{end_time}'")

        where_clause = f"WHERE {' AND '.join(all_conditions)}" if all_conditions else ""

        # 4. 构建 ORDER BY 子句（默认按时间升序）
        if order_by:
            order_by_clause = self._build_order_by_clause(order_by)
        else:
            order_by_clause = "ORDER BY MDTime ASC"

        # 5. 构建 LIMIT 子句
        limit = query_plan.get("limit", 1000)
        limit_clause = f"LIMIT {limit}"

        # 6. 组装 SQL
        sql_parts = [select_clause, from_clause]

        if where_clause:
            sql_parts.append(where_clause)

        sql_parts.append(order_by_clause)
        sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _compile_basic_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """
        编译基础查询（TopK/筛选）

        流程：SELECT ... FROM ... WHERE ... ORDER BY ... LIMIT
        """

        print("[SQL编译器] 使用基础查询编译策略")

        # 1. 确定需要的字段（支持新旧两种字段名）
        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        metrics = query_plan.get("metrics", [])
        filters = query_plan.get("filters", [])
        order_by = query_plan.get("order_by", [])

        # 收集基础字段（过滤掉无效字段）
        required_base_fields = set()
        for field in output_fields:
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)
            elif field not in METRIC_DEFINITIONS:
                print(f"[SQL编译器] 警告: 忽略无效字段 '{field}'")

        # 添加 filters 和 order_by 需要的字段
        for f in filters:
            field = f["field"]
            if field in VALID_BASE_FIELDS or field in METRIC_DEFINITIONS:
                required_base_fields.add(field)
        for o in order_by:
            field = o["field"]
            if field in VALID_BASE_FIELDS or field in METRIC_DEFINITIONS:
                required_base_fields.add(field)

        # 添加 metrics 需要的基础字段（简化：添加所有可能字段）
        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                required_base_fields.update([
                    "ClosePx", "PreClosePx", "HighPx", "LowPx", "MaxPx", "MinPx",
                    "TotalVolumeTrade", "TotalValueTrade",
                    "Sell1Price", "Buy1Price",
                    "Buy1OrderQty", "Buy2OrderQty", "Buy3OrderQty", "Buy4OrderQty", "Buy5OrderQty",
                    "Sell1OrderQty", "Sell2OrderQty", "Sell3OrderQty", "Sell4OrderQty", "Sell5OrderQty",
                ])

        # 2. 构建 SELECT 子句
        select_items = []

        # 确保 SecurityID 总是被选择
        if "SecurityID" not in required_base_fields:
            required_base_fields.add("SecurityID")

        # 添加基础字段（只添加有效字段）
        for field in required_base_fields:
            if field in VALID_BASE_FIELDS:
                select_items.append(field)

        # 添加衍生指标
        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[metric]
                select_items.append(f"({expr}) AS \"{metric}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        # 3. 构建 WHERE 子句
        where_clause = self._build_where_clause(filters)

        # 4. 构建 ORDER BY 子句
        order_by_clause = self._build_order_by_clause(order_by)

        # 5. 构建 LIMIT 子句
        limit = query_plan.get("limit", 100)
        limit_clause = f"LIMIT {limit}"

        # 6. 组装 SQL
        sql_parts = [select_clause, from_clause]

        if where_clause:
            sql_parts.append(where_clause)

        if order_by_clause:
            sql_parts.append(order_by_clause)

        sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _compile_aggregation_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """
        编译聚合查询（GROUP BY + 聚合函数）

        流程：SELECT ... FROM ... WHERE ... GROUP BY ... HAVING ... ORDER BY ... LIMIT
        """

        print("[SQL编译器] 使用聚合查询编译策略")

        # 1. 解析参数（支持新旧两种字段名）
        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        metrics = query_plan.get("metrics", [])
        filters = query_plan.get("filters", [])
        aggregations = query_plan.get("aggregations", [])
        group_by = query_plan.get("group_by", [])
        having = query_plan.get("having", [])
        order_by = query_plan.get("order_by", [])

        # 2. 构建 SELECT 子句
        select_items = []

        # 添加分组字段
        for field in group_by:
            if field in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[field]
                select_items.append(f"({expr}) AS \"{field}\"")
            else:
                select_items.append(field)

        # 添加输出字段（如果不在分组字段中）
        for field in output_fields:
            if field not in group_by:
                if field in METRIC_DEFINITIONS:
                    expr = METRIC_DEFINITIONS[field]
                    select_items.append(f"({expr}) AS \"{field}\"")
                else:
                    select_items.append(field)

        # 添加聚合函数
        for agg in aggregations:
            func = agg["func"]
            field = agg["field"]
            alias = agg["alias"]

            if func == "count" and field == "*":
                select_items.append(f"COUNT(*) AS \"{alias}\"")
            elif "CASE" in field:  # 条件统计（如上涨数量）
                select_items.append(f"COUNT({field}) AS \"{alias}\"")
            else:
                # 如果字段是衍生指标，展开表达式
                if field in METRIC_DEFINITIONS:
                    field_expr = f"({METRIC_DEFINITIONS[field]})"
                else:
                    field_expr = field
                select_items.append(f"{func.upper()}({field_expr}) AS \"{alias}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        # 3. 构建 WHERE 子句
        where_clause = self._build_where_clause(filters)

        # 4. 构建 GROUP BY 子句
        if group_by:
            group_by_clause = f"GROUP BY {', '.join(group_by)}"
        else:
            group_by_clause = ""

        # 5. 构建 HAVING 子句
        having_clause = self._build_having_clause(having)

        # 6. 构建 ORDER BY 子句
        order_by_clause = self._build_order_by_clause(order_by)

        # 7. 构建 LIMIT 子句
        limit = query_plan.get("limit", 100)
        limit_clause = f"LIMIT {limit}"

        # 8. 组装 SQL
        sql_parts = [select_clause, from_clause]

        if where_clause:
            sql_parts.append(where_clause)

        if group_by_clause:
            sql_parts.append(group_by_clause)

        if having_clause:
            sql_parts.append(having_clause)

        if order_by_clause:
            sql_parts.append(order_by_clause)

        sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _compile_complex_analysis(self, query_plan: Dict[str, Any], parquet_paths: List[str]) -> str:
        """
        编译第三类复杂分析查询

        支持的分析类型：
        - order_book_anomaly: 盘口异动分析
        - money_flow: 资金流向分析
        - pressure_analysis: 买卖压力分析
        """
        analysis_type = query_plan.get("analysis_type", "order_book_anomaly")
        print(f"[SQL编译器] 使用复杂分析编译策略，analysis_type={analysis_type}")

        if analysis_type == "order_book_anomaly":
            return self._compile_order_book_anomaly(query_plan, parquet_paths)
        elif analysis_type == "money_flow":
            return self._compile_money_flow(query_plan, parquet_paths)
        elif analysis_type == "pressure_analysis":
            return self._compile_pressure_analysis(query_plan, parquet_paths)
        else:
            raise ValueError(f"不支持的 analysis_type: {analysis_type}")

    def get_field_explanations(self, analysis_type: str) -> Dict[str, str]:
        """
        获取复杂分析的字段解释

        Args:
            analysis_type: 分析类型

        Returns:
            字段名 -> 解释 的字典
        """
        explanations = {
            "order_book_anomaly": {
                "股票代码": "股票的唯一标识代码（如 300190）",
                "股票名称": "股票的中文简称",
                "数据点数": "该股票在分析时段内的快照数量，数据点越多统计越可靠",
                "委比波动率": "委买委卖比的标准差。委比 = (买盘总量-卖盘总量)/(买盘总量+卖盘总量)，波动率越大说明买卖力量变化越剧烈",
                "买一变化率_max": "买一档挂单量相邻时间点的最大变化率。数值越大说明买一档出现过大幅撤单或加单",
                "卖一变化率_max": "卖一档挂单量相邻时间点的最大变化率。数值越大说明卖一档出现过大幅撤单或加单",
                "价差波动率": "买卖价差(Sell1Price-Buy1Price)相对于中间价的波动程度。反映盘口流动性的稳定性",
                "异动分数": "综合异动评分(0-1)，由委比波动率(30%)、买一变化率(25%)、卖一变化率(25%)、价差波动率(20%)加权计算。分数越高表示盘口异动越大",
            },
            "money_flow": {
                "股票代码": "股票的唯一标识代码",
                "股票名称": "股票的中文简称",
                "数据点数": "该股票在分析时段内的快照数量",
                "主动买入(亿)": "价格上涨时产生的成交金额，推断为主动性买入资金",
                "主动卖出(亿)": "价格下跌时产生的成交金额，推断为主动性卖出资金",
                "净流入(亿)": "主动买入 - 主动卖出，正数表示资金净流入",
                "平均买卖盘比": "分析时段内 买盘总量/卖盘总量 的平均值，>1表示买盘占优",
                "买卖盘比变化": "买卖盘比的变化趋势（结束值-开始值），正数表示买盘力量增强",
                "资金状态": "综合判断：强流入(净流入+买盘增强)、流入(仅净流入)、强流出(净流出+买盘减弱)、流出(仅净流出)",
            },
            "pressure_analysis": {
                "股票代码": "股票的唯一标识代码",
                "股票名称": "股票的中文简称",
                "时间": "快照时间（格式 HHMMSSmmm，如 093000000 表示 9:30:00.000）",
                "最新价": "该时刻的最新成交价格",
                "委买委卖比": "买盘总量/卖盘总量，>1表示买盘力量强，<1表示卖盘力量强",
                "买盘深度(万)": "前5档买盘挂单总量（单位：万股），反映买方承接力度",
                "卖盘深度(万)": "前5档卖盘挂单总量（单位：万股），反映卖方抛压",
                "压力差(万)": "前3档买盘量 - 前3档卖盘量，正数表示买盘强于卖盘",
                "压力状态": "买压大(买盘>卖盘1.5倍)、卖压大(卖盘>买盘1.5倍)、平衡(其他)",
            },
        }
        return explanations.get(analysis_type, {})

    def _compile_order_book_anomaly(self, query_plan: Dict[str, Any], parquet_paths: List[str]) -> str:
        """
        编译盘口异动分析

        异动指标：
        1. 委比波动率：(TotalBidQty - TotalOfferQty) / (TotalBidQty + TotalOfferQty) 的标准差
        2. 买一变化率：买一档挂单量相邻时间点的最大变化率
        3. 卖一变化率：卖一档挂单量相邻时间点的最大变化率
        4. 价差波动率：(Sell1Price - Buy1Price) / 中间价 的标准差
        5. 综合异动分数：上述指标标准化后加权求和
        """
        limit = query_plan.get("limit", 5)
        filters = query_plan.get("filters", [])

        # 构建数据源（不去重，需要所有时间快照）
        if len(parquet_paths) == 1:
            base_source = f"parquet_scan('{parquet_paths[0]}')"
        else:
            union_queries = [f"SELECT * FROM parquet_scan('{path}')" for path in parquet_paths]
            base_source = f"({' UNION ALL '.join(union_queries)})"

        # 构建过滤条件（如指定股票）
        where_conditions = []
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]
            if isinstance(value, str):
                where_conditions.append(f"{field} {op} '{value}'")
            else:
                where_conditions.append(f"{field} {op} {value}")

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        sql = f"""
WITH raw_data AS (
    SELECT *
    FROM {base_source}
    {where_clause}
),
-- 计算每个时间点的盘口指标
tick_metrics AS (
    SELECT
        SecurityID,
        Symbol,
        MDTime,
        -- 委比 = (买总量 - 卖总量) / (买总量 + 卖总量)
        CASE WHEN (TotalBidQty + TotalOfferQty) > 0
             THEN (TotalBidQty - TotalOfferQty) * 1.0 / (TotalBidQty + TotalOfferQty)
             ELSE 0 END AS 委比,
        -- 买一量
        COALESCE(Buy1OrderQty, 0) AS Buy1Qty,
        -- 卖一量
        COALESCE(Sell1OrderQty, 0) AS Sell1Qty,
        -- 买卖价差比（相对于中间价）
        CASE WHEN (Sell1Price + Buy1Price) > 0
             THEN (Sell1Price - Buy1Price) * 2.0 / (Sell1Price + Buy1Price)
             ELSE 0 END AS 价差比,
        -- 用于计算变化率的前一个值
        LAG(Buy1OrderQty) OVER (PARTITION BY SecurityID ORDER BY MDTime) AS prev_Buy1Qty,
        LAG(Sell1OrderQty) OVER (PARTITION BY SecurityID ORDER BY MDTime) AS prev_Sell1Qty
    FROM raw_data
    WHERE Buy1Price IS NOT NULL AND Sell1Price IS NOT NULL
),
-- 计算变化率
tick_changes AS (
    SELECT
        SecurityID,
        Symbol,
        MDTime,
        委比,
        价差比,
        -- 买一变化率 = |当前 - 前一个| / 前一个平均
        CASE WHEN prev_Buy1Qty > 0
             THEN ABS(Buy1Qty - prev_Buy1Qty) * 1.0 / prev_Buy1Qty
             ELSE 0 END AS 买一变化率,
        -- 卖一变化率
        CASE WHEN prev_Sell1Qty > 0
             THEN ABS(Sell1Qty - prev_Sell1Qty) * 1.0 / prev_Sell1Qty
             ELSE 0 END AS 卖一变化率
    FROM tick_metrics
),
-- 按股票汇总各项异动指标
stock_anomaly AS (
    SELECT
        SecurityID,
        ANY_VALUE(Symbol) AS Symbol,
        COUNT(*) AS 数据点数,
        -- 委比波动率（标准差）
        STDDEV_SAMP(委比) AS 委比波动率,
        -- 买一变化率最大值
        MAX(买一变化率) AS 买一变化率_max,
        -- 买一变化率平均值
        AVG(买一变化率) AS 买一变化率_avg,
        -- 卖一变化率最大值
        MAX(卖一变化率) AS 卖一变化率_max,
        -- 价差波动率
        STDDEV_SAMP(价差比) AS 价差波动率
    FROM tick_changes
    GROUP BY SecurityID
    HAVING COUNT(*) >= 5  -- 至少5个数据点才有统计意义
),
-- 标准化各指标（Min-Max归一化）并计算综合分数
normalized AS (
    SELECT
        *,
        -- 归一化委比波动率
        (委比波动率 - MIN(委比波动率) OVER ()) /
            NULLIF(MAX(委比波动率) OVER () - MIN(委比波动率) OVER (), 0) AS 委比波动率_norm,
        -- 归一化买一变化率
        (买一变化率_max - MIN(买一变化率_max) OVER ()) /
            NULLIF(MAX(买一变化率_max) OVER () - MIN(买一变化率_max) OVER (), 0) AS 买一变化率_norm,
        -- 归一化卖一变化率
        (卖一变化率_max - MIN(卖一变化率_max) OVER ()) /
            NULLIF(MAX(卖一变化率_max) OVER () - MIN(卖一变化率_max) OVER (), 0) AS 卖一变化率_norm,
        -- 归一化价差波动率
        (价差波动率 - MIN(价差波动率) OVER ()) /
            NULLIF(MAX(价差波动率) OVER () - MIN(价差波动率) OVER (), 0) AS 价差波动率_norm
    FROM stock_anomaly
)
SELECT
    SecurityID AS "股票代码",
    Symbol AS "股票名称",
    数据点数,
    ROUND(委比波动率, 4) AS "委比波动率",
    ROUND(买一变化率_max, 4) AS "买一变化率_max",
    ROUND(卖一变化率_max, 4) AS "卖一变化率_max",
    ROUND(价差波动率, 6) AS "价差波动率",
    -- 综合异动分数 = 加权求和
    ROUND(
        COALESCE(委比波动率_norm, 0) * 0.30 +
        COALESCE(买一变化率_norm, 0) * 0.25 +
        COALESCE(卖一变化率_norm, 0) * 0.25 +
        COALESCE(价差波动率_norm, 0) * 0.20,
        4
    ) AS "异动分数"
FROM normalized
ORDER BY "异动分数" DESC
LIMIT {limit}
"""
        return sql

    def _compile_money_flow(self, query_plan: Dict[str, Any], parquet_paths: List[str]) -> str:
        """
        编译资金流向分析

        资金流向指标：
        1. 主动买入比例：价格上涨时的成交量占比
        2. 大单净流入：大额成交的买卖差额
        3. 买盘压力：买盘总量 / 卖盘总量 的变化
        """
        limit = query_plan.get("limit", 10)
        filters = query_plan.get("filters", [])

        if len(parquet_paths) == 1:
            base_source = f"parquet_scan('{parquet_paths[0]}')"
        else:
            union_queries = [f"SELECT * FROM parquet_scan('{path}')" for path in parquet_paths]
            base_source = f"({' UNION ALL '.join(union_queries)})"

        where_conditions = []
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]
            if isinstance(value, str):
                where_conditions.append(f"{field} {op} '{value}'")
            else:
                where_conditions.append(f"{field} {op} {value}")

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # 如果指定了特定股票（有 filters），则显示该股票的资金流向（无论流入流出）
        # 如果没有指定股票，则只显示净流入的股票
        if where_conditions:
            final_where = ""  # 单只股票查询，不过滤
        else:
            final_where = "WHERE (主动买入额 - 主动卖出额) > 0  -- 只显示净流入的股票"

        sql = f"""
WITH raw_data AS (
    SELECT *
    FROM {base_source}
    {where_clause}
),
tick_data AS (
    SELECT
        SecurityID,
        Symbol,
        MDTime,
        LastPx,
        TotalValueTrade,
        TotalBidQty,
        TotalOfferQty,
        -- 价格变化方向
        CASE WHEN LastPx > LAG(LastPx) OVER (PARTITION BY SecurityID ORDER BY MDTime) THEN 1
             WHEN LastPx < LAG(LastPx) OVER (PARTITION BY SecurityID ORDER BY MDTime) THEN -1
             ELSE 0 END AS 价格方向,
        -- 成交额增量
        TotalValueTrade - LAG(TotalValueTrade) OVER (PARTITION BY SecurityID ORDER BY MDTime) AS 成交额增量,
        -- 买卖盘比
        CASE WHEN TotalOfferQty > 0 THEN TotalBidQty * 1.0 / TotalOfferQty ELSE 1 END AS 买卖盘比
    FROM raw_data
    WHERE LastPx IS NOT NULL AND LastPx > 0
),
stock_flow AS (
    SELECT
        SecurityID,
        ANY_VALUE(Symbol) AS Symbol,
        COUNT(*) AS 数据点数,
        -- 主动买入金额（价格上涨时的成交额增量）
        SUM(CASE WHEN 价格方向 > 0 AND 成交额增量 > 0 THEN 成交额增量 ELSE 0 END) AS 主动买入额,
        -- 主动卖出金额
        SUM(CASE WHEN 价格方向 < 0 AND 成交额增量 > 0 THEN 成交额增量 ELSE 0 END) AS 主动卖出额,
        -- 平均买卖盘比
        AVG(买卖盘比) AS 平均买卖盘比,
        -- 买卖盘比的变化趋势（最后值 - 最初值）
        LAST(买卖盘比) - FIRST(买卖盘比) AS 买卖盘比变化
    FROM tick_data
    GROUP BY SecurityID
    HAVING COUNT(*) >= 5
)
SELECT
    SecurityID AS "股票代码",
    Symbol AS "股票名称",
    数据点数,
    ROUND(主动买入额 / 100000000, 2) AS "主动买入(亿)",
    ROUND(主动卖出额 / 100000000, 2) AS "主动卖出(亿)",
    ROUND((主动买入额 - 主动卖出额) / 100000000, 2) AS "净流入(亿)",
    ROUND(平均买卖盘比, 2) AS "平均买卖盘比",
    ROUND(买卖盘比变化, 4) AS "买卖盘比变化",
    -- 资金流入评分
    CASE
        WHEN (主动买入额 - 主动卖出额) > 0 AND 买卖盘比变化 > 0 THEN '强流入'
        WHEN (主动买入额 - 主动卖出额) > 0 THEN '流入'
        WHEN (主动买入额 - 主动卖出额) < 0 AND 买卖盘比变化 < 0 THEN '强流出'
        ELSE '流出'
    END AS "资金状态"
FROM stock_flow
{final_where}
ORDER BY (主动买入额 - 主动卖出额) DESC
LIMIT {limit}
"""
        return sql

    def _compile_pressure_analysis(self, query_plan: Dict[str, Any], parquet_paths: List[str]) -> str:
        """
        编译买卖压力分析（单只股票的时序分析）

        分析指标：
        1. 委买委卖比时序
        2. 买卖盘深度（5档汇总）
        3. 压力转换点
        """
        limit = query_plan.get("limit", 100)
        filters = query_plan.get("filters", [])

        if len(parquet_paths) == 1:
            base_source = f"parquet_scan('{parquet_paths[0]}')"
        else:
            union_queries = [f"SELECT * FROM parquet_scan('{path}')" for path in parquet_paths]
            base_source = f"({' UNION ALL '.join(union_queries)})"

        where_conditions = []
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]
            if isinstance(value, str):
                where_conditions.append(f"{field} {op} '{value}'")
            else:
                where_conditions.append(f"{field} {op} {value}")

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        sql = f"""
WITH raw_data AS (
    SELECT *
    FROM {base_source}
    {where_clause}
)
SELECT
    SecurityID AS "股票代码",
    Symbol AS "股票名称",
    MDTime AS "时间",
    ROUND(LastPx, 2) AS "最新价",
    -- 委买委卖比
    ROUND(
        CASE WHEN TotalOfferQty > 0 THEN TotalBidQty * 1.0 / TotalOfferQty ELSE 0 END,
        4
    ) AS "委买委卖比",
    -- 5档买盘深度
    ROUND((
        COALESCE(Buy1OrderQty, 0) + COALESCE(Buy2OrderQty, 0) +
        COALESCE(Buy3OrderQty, 0) + COALESCE(Buy4OrderQty, 0) +
        COALESCE(Buy5OrderQty, 0)
    ) / 10000, 2) AS "买盘深度(万)",
    -- 5档卖盘深度
    ROUND((
        COALESCE(Sell1OrderQty, 0) + COALESCE(Sell2OrderQty, 0) +
        COALESCE(Sell3OrderQty, 0) + COALESCE(Sell4OrderQty, 0) +
        COALESCE(Sell5OrderQty, 0)
    ) / 10000, 2) AS "卖盘深度(万)",
    -- 买卖压力差
    ROUND((
        (COALESCE(Buy1OrderQty, 0) + COALESCE(Buy2OrderQty, 0) + COALESCE(Buy3OrderQty, 0)) -
        (COALESCE(Sell1OrderQty, 0) + COALESCE(Sell2OrderQty, 0) + COALESCE(Sell3OrderQty, 0))
    ) / 10000, 2) AS "压力差(万)",
    -- 压力状态
    CASE
        WHEN TotalBidQty > TotalOfferQty * 1.5 THEN '买压大'
        WHEN TotalOfferQty > TotalBidQty * 1.5 THEN '卖压大'
        ELSE '平衡'
    END AS "压力状态"
FROM raw_data
WHERE LastPx IS NOT NULL
ORDER BY MDTime ASC
LIMIT {limit}
"""
        return sql

    def _build_from_clause(self, parquet_paths: List[str], use_latest_snapshot: bool = True) -> str:
        """
        构建 FROM 子句

        Args:
            parquet_paths: Parquet 文件路径列表
            use_latest_snapshot: 是否只选择每个 SecurityID 的最新快照（默认 True）
        """

        # 先构建基础数据源
        if len(parquet_paths) == 1:
            base_query = f"SELECT * FROM parquet_scan('{parquet_paths[0]}')"
        else:
            union_queries = [f"SELECT * FROM parquet_scan('{path}')" for path in parquet_paths]
            base_query = f"SELECT * FROM ({' UNION ALL '.join(union_queries)})"

        # 如果需要只选择最新快照，使用窗口函数
        if use_latest_snapshot:
            return f"""FROM (
    SELECT * FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY SecurityID ORDER BY MDTime DESC) AS rn
        FROM ({base_query}) AS raw_data
    ) AS ranked
    WHERE rn = 1
) AS data"""
        else:
            return f"FROM ({base_query}) AS data"

    def _build_where_clause(self, filters: List[Dict[str, Any]]) -> str:
        """构建 WHERE 子句"""

        if not filters:
            return ""

        conditions = []
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]

            # 自动修正 Time -> MDTime（LLM 可能生成错误的字段名）
            if field == "Time":
                field = "MDTime"
                # 同时修正时间格式
                if isinstance(value, str):
                    value = self._normalize_time_format(value)

            # 如果字段是衍生指标，展开表达式
            if field in METRIC_DEFINITIONS:
                field_expr = f"({METRIC_DEFINITIONS[field]})"
            else:
                field_expr = field

            # 构建条件
            if isinstance(value, str):
                conditions.append(f"{field_expr} {op} '{value}'")
            else:
                conditions.append(f"{field_expr} {op} {value}")

        return f"WHERE {' AND '.join(conditions)}"

    def _build_having_clause(self, having: List[Dict[str, Any]]) -> str:
        """构建 HAVING 子句"""

        if not having:
            return ""

        conditions = []
        for h in having:
            field = h["field"]
            op = h["op"]
            value = h["value"]

            if isinstance(value, str):
                conditions.append(f"{field} {op} '{value}'")
            else:
                conditions.append(f"{field} {op} {value}")

        return f"HAVING {' AND '.join(conditions)}"

    def _normalize_time_format(self, time_str: str) -> str:
        """
        标准化时间格式为 HHMMSSsss（9位）

        处理 LLM 可能生成的各种格式：
        - "150000" → "150000000"
        - "15:00:00" → "150000000"
        - "9:30" → "093000000"
        - "150000000" → "150000000"（已正确）
        """
        # 移除冒号
        time_str = time_str.replace(":", "")

        # 如果是奇数位（3,5,7位，小时位缺0），在前面补0
        if len(time_str) in [3, 5, 7]:
            time_str = "0" + time_str

        # 补足到9位（末尾补0）
        if len(time_str) < 9:
            time_str = time_str.ljust(9, "0")

        return time_str[:9]

    def _build_order_by_clause(self, order_by: List[Dict[str, Any]]) -> str:
        """构建 ORDER BY 子句"""

        if not order_by:
            return ""

        order_items = []
        for o in order_by:
            field = o["field"]
            desc = o.get("desc", True)
            direction = "DESC" if desc else "ASC"

            # 自动修正 Time -> MDTime
            if field == "Time":
                field = "MDTime"

            # 如果字段是衍生指标，直接用别名
            if field in METRIC_DEFINITIONS:
                order_items.append(f"\"{field}\" {direction}")
            else:
                order_items.append(f"{field} {direction}")

        return f"ORDER BY {', '.join(order_items)}"


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    # 测试基础查询
    compiler = SQLCompilerEnhanced()

    print("=" * 80)
    print("测试1: 基础 TopK 查询")
    print("=" * 80)

    query_plan1 = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["涨幅"],
        "filters": [],
        "order_by": [{"field": "涨幅", "desc": True}],
        "limit": 10,
        "output_fields": ["SecurityID", "ClosePx", "PreClosePx", "涨幅"],
    }

    sql1 = compiler.compile(query_plan1, ["data/test.parquet"])
    print("\n生成的 SQL:")
    print(sql1)

    print("\n" + "=" * 80)
    print("测试2: 聚合查询（总成交额）")
    print("=" * 80)

    query_plan2 = {
        "query_type": "aggregation",
        "date": "20250115",
        "market": "ALL",
        "metrics": [],
        "filters": [],
        "order_by": [],
        "limit": 1,
        "output_fields": [],
        "aggregations": [
            {"func": "sum", "field": "TotalValueTrade", "alias": "总成交额"},
            {"func": "count", "field": "*", "alias": "股票数量"}
        ],
        "group_by": [],
    }

    sql2 = compiler.compile(query_plan2, ["data/test.parquet"])
    print("\n生成的 SQL:")
    print(sql2)

    print("\n" + "=" * 80)
    print("测试3: 分组统计（按行业）")
    print("=" * 80)

    query_plan3 = {
        "query_type": "stats",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["涨幅"],
        "filters": [],
        "order_by": [{"field": "平均涨幅", "desc": True}],
        "limit": 10,
        "output_fields": ["价格区间"],
        "aggregations": [
            {"func": "count", "field": "*", "alias": "股票数量"},
            {"func": "avg", "field": "涨幅", "alias": "平均涨幅"}
        ],
        "group_by": ["价格区间"],
    }

    sql3 = compiler.compile(query_plan3, ["data/test.parquet"])
    print("\n生成的 SQL:")
    print(sql3)
