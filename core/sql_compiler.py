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

from typing import List, Tuple, Dict, Any, Set

# ============================================================================
# 衍生指标定义（增强版）
# ============================================================================

METRIC_DEFINITIONS = {
    # 日线行情数据中已包含涨跌幅/振幅。对旧快照数据，ChangePct/Amplitude 会在源层兜底计算。
    "涨幅": "ChangePct",
    "跌幅": "-ChangePct",
    "振幅": "Amplitude",
    "换手率": "TurnoverRate",

    # 价格区间（使用 ClosePx）
    "价格区间": "CASE WHEN ClosePx < 10 THEN '<10元' WHEN ClosePx <= 30 THEN '10-30元' ELSE '>30元' END",
}

METRIC_DEPENDENCIES = {
    "涨幅": {"ChangePct"},
    "跌幅": {"ChangePct"},
    "振幅": {"Amplitude"},
    "换手率": {"TurnoverRate"},
    "价格区间": {"ClosePx"},
}

# 有效的基础字段白名单（与实际数据表结构匹配）
VALID_BASE_FIELDS = {
    # 基础信息
    "Market", "MDDate", "MDTime", "SecurityType", "SecuritySubType",
    "SecurityID", "SecurityIDSource", "Symbol", "TradingPhaseCode",
    "HTSCSecurityID", "ReceiveDateTime", "ChannelNo",
    # 价格字段
    "PreClosePx", "LastPx", "OpenPx", "ClosePx", "HighPx", "LowPx",
    "DiffPx1", "DiffPx2", "MaxPx", "MinPx",
    # 成交字段
    "NumTrades", "TotalVolumeTrade", "TotalValueTrade",
    "ChangePx", "ChangePct", "Amplitude", "TurnoverRate",
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
        self._normalize_plan_metrics(query_plan)

        # raw_data 查询不去重，保留所有快照
        # 如果 filters 中包含时间条件（Time/MDTime），也不去重
        use_latest_snapshot = query_type != "raw_data"
        if self._is_daily_history_source(parquet_paths):
            # HK/US 日线数据每只股票每天最多一条记录，日期过滤应直接作用于历史表。
            use_latest_snapshot = False
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
        filters = self._expand_plan_filters(query_plan)
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
                all_conditions.append(f"{field_expr} {op} {self._quote_sql_string(value)}")
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
        filters = self._expand_plan_filters(query_plan)
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
                required_base_fields.update(METRIC_DEPENDENCIES.get(metric, set()))

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
        filters = self._expand_plan_filters(query_plan)
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

    def _normalize_plan_metrics(self, query_plan: Dict[str, Any]) -> None:
        """把 select/order/filter 中出现的衍生指标补进 metrics，避免 LLM 漏填。"""
        metrics = list(query_plan.get("metrics", []))
        seen = set(metrics)

        candidate_fields = []
        candidate_fields.extend(query_plan.get("select_fields", []))
        candidate_fields.extend(query_plan.get("output_fields", []))
        candidate_fields.extend(item.get("field") for item in query_plan.get("order_by", []))
        candidate_fields.extend(item.get("field") for item in query_plan.get("filters", []))

        for field in candidate_fields:
            if field in METRIC_DEFINITIONS and field not in seen:
                metrics.append(field)
                seen.add(field)

        query_plan["metrics"] = metrics

    def _expand_plan_filters(self, query_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """添加日期过滤。新 HK/US 数据按股票文件存放，必须在 SQL 中过滤日期。"""
        filters = list(query_plan.get("filters", []))

        has_md_date_filter = any(f.get("field") in {"MDDate", "日期"} for f in filters)
        date_range = query_plan.get("date_range") or {}

        if date_range and not has_md_date_filter:
            start_date = date_range.get("start")
            end_date = date_range.get("end")
            if start_date:
                filters.append({"field": "MDDate", "op": ">=", "value": self._normalize_date_format(start_date)})
            if end_date:
                filters.append({"field": "MDDate", "op": "<=", "value": self._normalize_date_format(end_date)})
        elif query_plan.get("date") and not has_md_date_filter:
            filters.append({"field": "MDDate", "op": "=", "value": self._normalize_date_format(query_plan["date"])})

        return filters

    def _normalize_date_format(self, date_str: str) -> str:
        """标准化日期为 YYYYMMDD。"""
        return str(date_str).replace("-", "").replace("/", "")[:8]

    def _is_daily_history_source(self, parquet_paths: List[str]) -> bool:
        """判断是否为 data/hk 或 data/us 下的历史日线 parquet。"""
        for path in parquet_paths:
            normalized = path.replace("\\", "/").lower()
            if "/hk/" in normalized or normalized.endswith("/hk/*.parquet"):
                return True
            if "/us/" in normalized or normalized.endswith("/us/*.parquet"):
                return True
            if normalized.startswith("data/hk/") or normalized.startswith("data/us/"):
                return True
        return False

    def _path_market(self, path: str) -> str:
        normalized = path.replace("\\", "/").lower()
        if "/hk/" in normalized or normalized.endswith("/hk/*.parquet") or normalized.startswith("data/hk/"):
            return "HK"
        if "/us/" in normalized or normalized.endswith("/us/*.parquet") or normalized.startswith("data/us/"):
            return "US"
        return "UNKNOWN"

    def _quote_sql_string(self, value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _build_scan_call(self, paths: List[str], union_by_name: bool = False) -> str:
        options = ", union_by_name=true" if union_by_name else ""
        if len(paths) == 1:
            return f"parquet_scan({self._quote_sql_string(paths[0])}{options})"
        quoted_paths = ", ".join(self._quote_sql_string(path) for path in paths)
        return f"parquet_scan([{quoted_paths}]{options})"

    def _build_daily_history_base_query(self, parquet_paths: List[str]) -> str:
        """把 HK/US 日线数据归一化成查询层使用的逻辑字段。"""
        market_to_paths: Dict[str, List[str]] = {}
        for path in parquet_paths:
            market_to_paths.setdefault(self._path_market(path), []).append(path)

        source_queries = []
        for market, paths in market_to_paths.items():
            scan = self._build_scan_call(paths, union_by_name=(market == "US"))
            if market == "US":
                date_expr = "COALESCE(CAST(\"日期\" AS VARCHAR), CAST(\"date\" AS VARCHAR))"
                open_expr = "COALESCE(\"开盘\", \"open\")"
                close_expr = "COALESCE(\"收盘\", \"close\")"
                high_expr = "COALESCE(\"最高\", \"high\")"
                low_expr = "COALESCE(\"最低\", \"low\")"
                volume_expr = "COALESCE(CAST(\"成交量\" AS DOUBLE), CAST(\"volume\" AS DOUBLE))"
                value_expr = "CAST(\"成交额\" AS DOUBLE)"
                prev_close_expr = (
                    f"LAG({close_expr}) OVER (PARTITION BY symbol ORDER BY {date_expr})"
                )
                change_px_expr = f"COALESCE(CAST(\"涨跌额\" AS DOUBLE), {close_expr} - {prev_close_expr})"
                change_pct_expr = (
                    f"COALESCE(CAST(\"涨跌幅\" AS DOUBLE), "
                    f"({close_expr} - {prev_close_expr}) / NULLIF({prev_close_expr}, 0) * 100)"
                )
                amplitude_expr = (
                    f"COALESCE(CAST(\"振幅\" AS DOUBLE), "
                    f"({high_expr} - {low_expr}) / NULLIF({prev_close_expr}, 0) * 100)"
                )
                turnover_expr = "CAST(\"换手率\" AS DOUBLE)"
                pre_close_expr = f"COALESCE({close_expr} - ({change_px_expr}), {prev_close_expr})"
            else:
                date_expr = "CAST(\"日期\" AS VARCHAR)"
                open_expr = "\"开盘\""
                close_expr = "\"收盘\""
                high_expr = "\"最高\""
                low_expr = "\"最低\""
                volume_expr = "CAST(\"成交量\" AS DOUBLE)"
                value_expr = "CAST(\"成交额\" AS DOUBLE)"
                change_px_expr = "CAST(\"涨跌额\" AS DOUBLE)"
                change_pct_expr = "CAST(\"涨跌幅\" AS DOUBLE)"
                amplitude_expr = "CAST(\"振幅\" AS DOUBLE)"
                turnover_expr = "CAST(\"换手率\" AS DOUBLE)"
                pre_close_expr = "\"收盘\" - COALESCE(\"涨跌额\", 0)"

            source_queries.append(f"""
SELECT
    {self._quote_sql_string(market)} AS Market,
    CAST(symbol AS VARCHAR) AS SecurityID,
    CAST(stock_name AS VARCHAR) AS Symbol,
    REPLACE({date_expr}, '-', '') AS MDDate,
    '000000000' AS MDTime,
    CAST(NULL AS INTEGER) AS SecurityType,
    CAST(NULL AS VARCHAR) AS SecuritySubType,
    CAST(NULL AS INTEGER) AS SecurityIDSource,
    CAST(NULL AS VARCHAR) AS TradingPhaseCode,
    CASE WHEN symbol IS NOT NULL AND {self._quote_sql_string(market)} IN ('HK', 'US')
         THEN symbol || '.' || {self._quote_sql_string(market)}
         ELSE CAST(symbol AS VARCHAR)
    END AS HTSCSecurityID,
    CAST(NULL AS BIGINT) AS ReceiveDateTime,
    CAST(NULL AS INTEGER) AS ChannelNo,
    CAST({open_expr} AS DOUBLE) AS OpenPx,
    CAST({close_expr} AS DOUBLE) AS ClosePx,
    CAST({close_expr} AS DOUBLE) AS LastPx,
    CAST({high_expr} AS DOUBLE) AS HighPx,
    CAST({low_expr} AS DOUBLE) AS LowPx,
    CAST({change_px_expr} AS DOUBLE) AS ChangePx,
    CAST({change_pct_expr} AS DOUBLE) AS ChangePct,
    CAST({pre_close_expr} AS DOUBLE) AS PreClosePx,
    CAST({volume_expr} AS DOUBLE) AS TotalVolumeTrade,
    CAST({value_expr} AS DOUBLE) AS TotalValueTrade,
    CAST({amplitude_expr} AS DOUBLE) AS Amplitude,
    CAST({turnover_expr} AS DOUBLE) AS TurnoverRate,
    CAST(NULL AS BIGINT) AS NumTrades,
    CAST(NULL AS DOUBLE) AS DiffPx1,
    CAST(NULL AS DOUBLE) AS DiffPx2,
    CAST(NULL AS DOUBLE) AS MaxPx,
    CAST(NULL AS DOUBLE) AS MinPx,
    CAST(NULL AS DOUBLE) AS TotalBidQty,
    CAST(NULL AS DOUBLE) AS TotalOfferQty,
    CAST(NULL AS DOUBLE) AS WeightedAvgBidPx,
    CAST(NULL AS DOUBLE) AS WeightedAvgOfferPx,
    CAST(NULL AS DOUBLE) AS AfterHoursNumTrades,
    CAST(NULL AS DOUBLE) AS AfterHoursTotalVolumeTrade,
    CAST(NULL AS DOUBLE) AS AfterHoursTotalValueTrade,
    CAST(NULL AS DOUBLE) AS Buy1Price,
    CAST(NULL AS DOUBLE) AS Buy1OrderQty,
    CAST(NULL AS DOUBLE) AS Buy1NumOrders,
    CAST(NULL AS DOUBLE) AS Buy1NoOrders,
    CAST(NULL AS DOUBLE) AS Sell1Price,
    CAST(NULL AS DOUBLE) AS Sell1OrderQty,
    CAST(NULL AS DOUBLE) AS Sell1NumOrders,
    CAST(NULL AS DOUBLE) AS Sell1NoOrders
FROM {scan}
""")

        return " UNION ALL ".join(source_queries)

    def _build_snapshot_base_query(self, parquet_paths: List[str]) -> str:
        """旧快照数据源，补齐日线衍生字段以便统一查询。"""
        def snapshot_select(path: str) -> str:
            scan = self._build_scan_call([path])
            return f"""
SELECT
    *,
    CAST(COALESCE(DiffPx1, LastPx - PreClosePx) AS DOUBLE) AS ChangePx,
    CAST(COALESCE(DiffPx2, (ClosePx - PreClosePx) / NULLIF(PreClosePx, 0) * 100) AS DOUBLE) AS ChangePct,
    CAST((HighPx - LowPx) / NULLIF(PreClosePx, 0) * 100 AS DOUBLE) AS Amplitude,
    CAST(NULL AS DOUBLE) AS TurnoverRate,
    CAST(NULL AS VARCHAR) AS Market
FROM {scan}
"""

        return " UNION ALL ".join(snapshot_select(path) for path in parquet_paths)

    def _build_from_clause(self, parquet_paths: List[str], use_latest_snapshot: bool = True) -> str:
        """
        构建 FROM 子句

        Args:
            parquet_paths: Parquet 文件路径列表
            use_latest_snapshot: 是否只选择每个 SecurityID 的最新快照（默认 True）
        """

        is_daily_history = self._is_daily_history_source(parquet_paths)
        base_query = (
            self._build_daily_history_base_query(parquet_paths)
            if is_daily_history
            else self._build_snapshot_base_query(parquet_paths)
        )

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
            elif field == "日期":
                field = "MDDate"
                if isinstance(value, str):
                    value = self._normalize_date_format(value)

            # 如果字段是衍生指标，展开表达式
            if field in METRIC_DEFINITIONS:
                field_expr = f"({METRIC_DEFINITIONS[field]})"
            else:
                field_expr = field

            # 构建条件
            if isinstance(value, str):
                conditions.append(f"{field_expr} {op} {self._quote_sql_string(value)}")
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
                conditions.append(f"{field} {op} {self._quote_sql_string(value)}")
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
