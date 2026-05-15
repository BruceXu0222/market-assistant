"""Compile structured QueryPlans into DuckDB SQL."""

from typing import List, Tuple, Dict, Any, Set

CN_DATE = "\u65e5\u671f"
CN_OPEN = "\u5f00\u76d8"
CN_CLOSE = "\u6536\u76d8"
CN_HIGH = "\u6700\u9ad8"
CN_LOW = "\u6700\u4f4e"
CN_VOLUME = "\u6210\u4ea4\u91cf"
CN_VALUE = "\u6210\u4ea4\u989d"
CN_CHANGE_PX = "\u6da8\u8dcc\u989d"
CN_CHANGE_PCT = "\u6da8\u8dcc\u5e45"
CN_AMPLITUDE = "\u632f\u5e45"
CN_TURNOVER_RATE = "\u6362\u624b\u7387"


METRIC_DEFINITIONS = {
    "GainPct": "ChangePct",
    "LossPct": "-ChangePct",
    "PriceBucket": "CASE WHEN ClosePx < 10 THEN 'Under 10' WHEN ClosePx <= 30 THEN '10 to 30' ELSE 'Above 30' END",
}

METRIC_DEPENDENCIES = {
    "GainPct": {"ChangePct"},
    "LossPct": {"ChangePct"},
    "PriceBucket": {"ClosePx"},
}

VALID_BASE_FIELDS = {
    "Market", "MDDate", "MDTime", "SecurityType", "SecuritySubType",
    "SecurityID", "SecurityIDSource", "Symbol", "TradingPhaseCode",
    "HTSCSecurityID", "ReceiveDateTime", "ChannelNo",
    "PreClosePx", "LastPx", "OpenPx", "ClosePx", "HighPx", "LowPx",
    "DiffPx1", "DiffPx2", "MaxPx", "MinPx",
    "NumTrades", "TotalVolumeTrade", "TotalValueTrade",
    "ChangePx", "ChangePct", "Amplitude", "TurnoverRate",
    "TotalBidQty", "TotalOfferQty", "WeightedAvgBidPx", "WeightedAvgOfferPx",
    "AfterHoursNumTrades", "AfterHoursTotalVolumeTrade", "AfterHoursTotalValueTrade",
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

class SQLCompilerEnhanced:
    """Compile QueryPlans into SQL for the normalized stock data schema."""

    def __init__(self):
        """Initialize the compiler."""
        pass

    def compile(
        self,
        query_plan: Dict[str, Any],
        parquet_paths: List[str],
    ) -> str:
        """Compile a QueryPlan dictionary into SQL."""

        print(f"[SQLCompiler] Compiling QueryPlan, type={query_plan.get('query_type')}")

        if not parquet_paths:
            raise ValueError("parquet_paths cannot be empty")

        query_type = query_plan.get("query_type", "basic")
        self._normalize_plan_metrics(query_plan)

        use_latest_snapshot = query_type != "raw_data"
        if self._is_daily_history_source(parquet_paths):
            use_latest_snapshot = False
        if use_latest_snapshot:
            filters = query_plan.get("filters", [])
            for f in filters:
                if f.get("field") in ["Time", "MDTime"]:
                    use_latest_snapshot = False
                    break
        from_clause = self._build_from_clause(parquet_paths, use_latest_snapshot)
        print(f"[SQLCompiler] FROM clause ready, files={len(parquet_paths)}, use_latest_snapshot={use_latest_snapshot}")

        if query_type == "raw_data":
            sql = self._compile_raw_data_query(query_plan, from_clause)

        elif query_type in ["basic", "filter", "anomaly", "multi_turn"]:
            sql = self._compile_basic_query(query_plan, from_clause)

        elif query_type in ["stats", "aggregation", "summary"]:
            sql = self._compile_aggregation_query(query_plan, from_clause)

        else:
            raise ValueError(f"Unsupported query_type: {query_type}")

        print(f"[SQLCompiler] SQL compiled, length={len(sql)} characters")
        return sql

    def _compile_raw_data_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """Compile a raw time-series query without snapshot de-duplication."""

        print("[SQLCompiler] Using raw-data query strategy")

        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        filters = self._expand_plan_filters(query_plan)
        time_range = query_plan.get("time_range", {})
        order_by = query_plan.get("order_by", [])

        required_base_fields = set()
        for field in output_fields:
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)
            elif field not in METRIC_DEFINITIONS:
                print(f"[SQLCompiler] Warning: ignoring invalid field '{field}'")

        for f in filters:
            field = f["field"]
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)

        required_base_fields.add("SecurityID")
        required_base_fields.add("MDTime")
        required_base_fields.add("Symbol")

        select_items = []
        for field in required_base_fields:
            if field in VALID_BASE_FIELDS:
                select_items.append(field)

        metrics = query_plan.get("metrics", [])
        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[metric]
                select_items.append(f"({expr}) AS \"{metric}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        all_conditions = []

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

        if order_by:
            order_by_clause = self._build_order_by_clause(order_by)
        else:
            order_by_clause = "ORDER BY MDTime ASC"

        limit = query_plan.get("limit", 1000)
        limit_clause = f"LIMIT {limit}"

        sql_parts = [select_clause, from_clause]

        if where_clause:
            sql_parts.append(where_clause)

        sql_parts.append(order_by_clause)
        sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _compile_basic_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """Compile a ranking or filter query."""

        print("[SQLCompiler] Using basic query strategy")

        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        metrics = query_plan.get("metrics", [])
        filters = self._expand_plan_filters(query_plan)
        order_by = query_plan.get("order_by", [])

        required_base_fields = set()
        for field in output_fields:
            if field in VALID_BASE_FIELDS:
                required_base_fields.add(field)
            elif field not in METRIC_DEFINITIONS:
                print(f"[SQLCompiler] Warning: ignoring invalid field '{field}'")

        for f in filters:
            field = f["field"]
            if field in VALID_BASE_FIELDS or field in METRIC_DEFINITIONS:
                required_base_fields.add(field)
        for o in order_by:
            field = o["field"]
            if field in VALID_BASE_FIELDS or field in METRIC_DEFINITIONS:
                required_base_fields.add(field)

        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                required_base_fields.update(METRIC_DEPENDENCIES.get(metric, set()))

        select_items = []

        if "SecurityID" not in required_base_fields:
            required_base_fields.add("SecurityID")

        for field in required_base_fields:
            if field in VALID_BASE_FIELDS:
                select_items.append(field)

        for metric in metrics:
            if metric in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[metric]
                select_items.append(f"({expr}) AS \"{metric}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        where_clause = self._build_where_clause(filters)

        order_by_clause = self._build_order_by_clause(order_by)

        limit = query_plan.get("limit", 100)
        limit_clause = f"LIMIT {limit}"

        sql_parts = [select_clause, from_clause]

        if where_clause:
            sql_parts.append(where_clause)

        if order_by_clause:
            sql_parts.append(order_by_clause)

        sql_parts.append(limit_clause)

        return "\n".join(sql_parts)

    def _compile_aggregation_query(self, query_plan: Dict[str, Any], from_clause: str) -> str:
        """Compile an aggregation query."""

        print("[SQLCompiler] Using aggregation query strategy")

        output_fields = query_plan.get("select_fields") or query_plan.get("output_fields", [])
        metrics = query_plan.get("metrics", [])
        filters = self._expand_plan_filters(query_plan)
        aggregations = query_plan.get("aggregations", [])
        group_by = query_plan.get("group_by", [])
        having = query_plan.get("having", [])
        order_by = query_plan.get("order_by", [])

        select_items = []

        for field in group_by:
            if field in METRIC_DEFINITIONS:
                expr = METRIC_DEFINITIONS[field]
                select_items.append(f"({expr}) AS \"{field}\"")
            else:
                select_items.append(field)

        for field in output_fields:
            if field not in group_by:
                if field in METRIC_DEFINITIONS:
                    expr = METRIC_DEFINITIONS[field]
                    select_items.append(f"({expr}) AS \"{field}\"")
                else:
                    select_items.append(field)

        for agg in aggregations:
            func = agg["func"]
            field = agg["field"]
            alias = agg["alias"]

            if func == "count" and field == "*":
                select_items.append(f"COUNT(*) AS \"{alias}\"")
            elif "CASE" in field:
                select_items.append(f"COUNT({field}) AS \"{alias}\"")
            else:
                if field in METRIC_DEFINITIONS:
                    field_expr = f"({METRIC_DEFINITIONS[field]})"
                else:
                    field_expr = field
                select_items.append(f"{func.upper()}({field_expr}) AS \"{alias}\"")

        select_clause = f"SELECT {', '.join(select_items)}"

        where_clause = self._build_where_clause(filters)

        if group_by:
            group_by_clause = f"GROUP BY {', '.join(group_by)}"
        else:
            group_by_clause = ""

        having_clause = self._build_having_clause(having)

        order_by_clause = self._build_order_by_clause(order_by)

        limit = query_plan.get("limit", 100)
        limit_clause = f"LIMIT {limit}"

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
        """Add referenced derived metrics to metrics when the model omitted them."""
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
        """Add date filters for per-stock HK/US daily-history parquet files."""
        filters = list(query_plan.get("filters", []))

        has_md_date_filter = any(f.get("field") in {"MDDate", CN_DATE} for f in filters)
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
        """Normalize a date to YYYYMMDD."""
        return str(date_str).replace("-", "").replace("/", "")[:8]

    def _is_daily_history_source(self, parquet_paths: List[str]) -> bool:
        """Return True for the current HK/US daily-history parquet layout."""
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
        """Normalize HK/US daily-history parquet columns into query fields."""
        market_to_paths: Dict[str, List[str]] = {}
        for path in parquet_paths:
            market_to_paths.setdefault(self._path_market(path), []).append(path)

        source_queries = []
        for market, paths in market_to_paths.items():
            scan = self._build_scan_call(paths, union_by_name=(market == "US"))
            if market == "US":
                date_expr = f'COALESCE(CAST("{CN_DATE}" AS VARCHAR), CAST("date" AS VARCHAR))'
                open_expr = f'COALESCE("{CN_OPEN}", "open")'
                close_expr = f'COALESCE("{CN_CLOSE}", "close")'
                high_expr = f'COALESCE("{CN_HIGH}", "high")'
                low_expr = f'COALESCE("{CN_LOW}", "low")'
                volume_expr = f'COALESCE(CAST("{CN_VOLUME}" AS DOUBLE), CAST("volume" AS DOUBLE))'
                value_expr = f'CAST("{CN_VALUE}" AS DOUBLE)'
                prev_close_expr = (
                    f"LAG({close_expr}) OVER (PARTITION BY symbol ORDER BY {date_expr})"
                )
                change_px_expr = f'COALESCE(CAST("{CN_CHANGE_PX}" AS DOUBLE), {close_expr} - {prev_close_expr})'
                change_pct_expr = (
                    f'COALESCE(CAST("{CN_CHANGE_PCT}" AS DOUBLE), '
                    f"({close_expr} - {prev_close_expr}) / NULLIF({prev_close_expr}, 0) * 100)"
                )
                amplitude_expr = (
                    f'COALESCE(CAST("{CN_AMPLITUDE}" AS DOUBLE), '
                    f"({high_expr} - {low_expr}) / NULLIF({prev_close_expr}, 0) * 100)"
                )
                turnover_expr = f'CAST("{CN_TURNOVER_RATE}" AS DOUBLE)'
                pre_close_expr = f"COALESCE({close_expr} - ({change_px_expr}), {prev_close_expr})"
            else:
                date_expr = f'CAST("{CN_DATE}" AS VARCHAR)'
                open_expr = f'"{CN_OPEN}"'
                close_expr = f'"{CN_CLOSE}"'
                high_expr = f'"{CN_HIGH}"'
                low_expr = f'"{CN_LOW}"'
                volume_expr = f'CAST("{CN_VOLUME}" AS DOUBLE)'
                value_expr = f'CAST("{CN_VALUE}" AS DOUBLE)'
                change_px_expr = f'CAST("{CN_CHANGE_PX}" AS DOUBLE)'
                change_pct_expr = f'CAST("{CN_CHANGE_PCT}" AS DOUBLE)'
                amplitude_expr = f'CAST("{CN_AMPLITUDE}" AS DOUBLE)'
                turnover_expr = f'CAST("{CN_TURNOVER_RATE}" AS DOUBLE)'
                pre_close_expr = f'"{CN_CLOSE}" - COALESCE("{CN_CHANGE_PX}", 0)'

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
        """Normalize legacy snapshot files into the same query fields."""
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
        """Build the FROM clause."""

        is_daily_history = self._is_daily_history_source(parquet_paths)
        base_query = (
            self._build_daily_history_base_query(parquet_paths)
            if is_daily_history
            else self._build_snapshot_base_query(parquet_paths)
        )

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
        """Build a WHERE clause."""

        if not filters:
            return ""

        conditions = []
        for f in filters:
            field = f["field"]
            op = f["op"]
            value = f["value"]

            if field == "Time":
                field = "MDTime"
                if isinstance(value, str):
                    value = self._normalize_time_format(value)
            elif field == CN_DATE:
                field = "MDDate"
                if isinstance(value, str):
                    value = self._normalize_date_format(value)

            if field in METRIC_DEFINITIONS:
                field_expr = f"({METRIC_DEFINITIONS[field]})"
            else:
                field_expr = field

            if isinstance(value, str):
                conditions.append(f"{field_expr} {op} {self._quote_sql_string(value)}")
            else:
                conditions.append(f"{field_expr} {op} {value}")

        return f"WHERE {' AND '.join(conditions)}"

    def _build_having_clause(self, having: List[Dict[str, Any]]) -> str:
        """Build a HAVING clause."""

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
        """Normalize common time strings to HHMMSSsss."""
        time_str = time_str.replace(":", "")

        if len(time_str) in [3, 5, 7]:
            time_str = "0" + time_str

        if len(time_str) < 9:
            time_str = time_str.ljust(9, "0")

        return time_str[:9]

    def _build_order_by_clause(self, order_by: List[Dict[str, Any]]) -> str:
        """Build an ORDER BY clause."""

        if not order_by:
            return ""

        order_items = []
        for o in order_by:
            field = o["field"]
            desc = o.get("desc", True)
            direction = "DESC" if desc else "ASC"

            if field == "Time":
                field = "MDTime"

            if field in METRIC_DEFINITIONS:
                order_items.append(f"\"{field}\" {direction}")
            else:
                order_items.append(f"{field} {direction}")

        return f"ORDER BY {', '.join(order_items)}"


# ============================================================================
# ============================================================================

if __name__ == "__main__":
    compiler = SQLCompilerEnhanced()
    demo_plan = {
        "query_type": "basic",
        "date": "20250115",
        "market": "ALL",
        "metrics": ["GainPct"],
        "filters": [],
        "order_by": [{"field": "GainPct", "desc": True}],
        "limit": 10,
        "output_fields": ["SecurityID", "ClosePx", "PreClosePx", "GainPct"],
    }
    print(compiler.compile(demo_plan, ["data/test.parquet"]))
