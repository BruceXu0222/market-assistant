"""
基于 LLM 的查询计划生成器
========================

使用 LLM 替代固定的 Pydantic Schema 进行灵活的查询计划生成。

LLM 生成 JSON 格式的查询计划，结构更加灵活：
- LLM 理解用户意图并决定使用哪些字段/指标
- 通过字段白名单确保安全性（生成后检查）
- 支持复杂查询，不受预定义 query_type 限制
"""

from typing import Dict, Any, Optional, List, Tuple
import json
import re
from datetime import datetime, timedelta

from core.llm_client import LLMClient

# ============================================================================
# 字段和指标定义（用于安全校验和提示词引导）
# ============================================================================

# 完整字段定义，包含数据类型和说明
# 格式: {字段名: (数据类型, 中文说明)}
FIELD_SCHEMA = {
    # 基本信息字段
    "MDDate": ("string", "行情日期YYYYMMDD"),
    "MDTime": ("string", "行情时间HHMMSSsss"),
    "SecurityType": ("int32", "产品大类"),
    "SecuritySubType": ("string", "产品小类: 02001=主板A股, 02003=创业板, 02004=科创板"),
    "SecurityID": ("string", "产品代码（股票代码）"),
    "SecurityIDSource": ("int32", "产品代码源"),
    "Symbol": ("string", "产品名称（股票简称）"),
    "TradingPhaseCode": ("string", "交易阶段标志"),
    "HTSCSecurityID": ("string", "华泰证券代码（如600000.SH）"),

    # 价格字段
    "PreClosePx": ("double", "昨收价"),
    "LastPx": ("double", "最新价/现价"),
    "OpenPx": ("double", "开盘价"),
    "ClosePx": ("double", "收盘价"),
    "HighPx": ("double", "最高价"),
    "LowPx": ("double", "最低价"),
    "DiffPx1": ("double", "升跌1"),
    "DiffPx2": ("double", "升跌2"),
    "MaxPx": ("double", "涨停价"),
    "MinPx": ("double", "跌停价"),

    # 成交字段
    "NumTrades": ("int64", "成交笔数"),
    "TotalVolumeTrade": ("double", "成交总量（股数）"),
    "TotalValueTrade": ("double", "成交总金额（元）"),

    # 买卖盘汇总字段
    "TotalBidQty": ("double", "买入总量"),
    "TotalOfferQty": ("double", "卖出总量"),
    "WeightedAvgBidPx": ("double", "加权平均买入价"),
    "WeightedAvgOfferPx": ("double", "加权平均卖出价"),

    # 盘后交易字段
    "AfterHoursNumTrades": ("double", "盘后成交笔数"),
    "AfterHoursTotalVolumeTrade": ("double", "盘后成交量"),
    "AfterHoursTotalValueTrade": ("double", "盘后成交额"),

    # 十档买卖盘（常用前五档）
    "Buy1Price": ("double", "买一价"),
    "Buy1OrderQty": ("double", "买一量"),
    "Sell1Price": ("double", "卖一价"),
    "Sell1OrderQty": ("double", "卖一量"),
}

# 基础字段（用于向后兼容）
BASE_FIELDS = {k: v[1] for k, v in FIELD_SCHEMA.items()}

# 衍生指标（在 SQL 中计算）
DERIVED_METRICS = {
    "涨幅": "(ClosePx - PreClosePx) / NULLIF(PreClosePx, 0) * 100",
    "跌幅": "(PreClosePx - ClosePx) / NULLIF(PreClosePx, 0) * 100",
    "振幅": "(HighPx - LowPx) / NULLIF(PreClosePx, 0) * 100",
    "是否涨停": "CASE WHEN ClosePx >= MaxPx THEN 1 ELSE 0 END",
    "是否跌停": "CASE WHEN ClosePx <= MinPx THEN 1 ELSE 0 END",
    "盘口差": "Sell1Price - Buy1Price",
    "买卖盘比": "TotalBidQty / NULLIF(TotalOfferQty, 0)",
}

# 所有允许的字段（基础字段 + 衍生指标）
ALL_ALLOWED_FIELDS = set(BASE_FIELDS.keys()) | set(DERIVED_METRICS.keys())

# 允许的 SQL 操作符
ALLOWED_OPERATORS = {">", "<", "=", ">=", "<=", "!=", "LIKE", "IN", "BETWEEN"}

# 允许的聚合函数
ALLOWED_AGG_FUNCS = {"SUM", "AVG", "COUNT", "MAX", "MIN", "STDDEV", "VARIANCE"}


# ============================================================================
# LLM 系统提示词
# ============================================================================

PLANNER_SYSTEM_PROMPT = """你是一个股票行情查询计划生成器。你的任务是将用户的自然语言查询转换为结构化的 QueryPlan（JSON 格式）。

## 查询类型判断

首先判断用户的问题类型：

1. **数据查询类**：需要查询股票数据的问题（如"涨幅前10的股票"、"成交额超过10亿的股票"）
   - 返回包含 query_type 为 "basic"、"filter"、"stats" 等的查询计划

2. **闲聊/知识类**：关于股票知识、概念解释、闲聊等不需要查询数据的问题（如"什么是涨幅"、"股票怎么交易"、"你好"）
   - 返回 query_type 为 "chat" 的响应，并在 answer 字段中提供回答

## 可用数据字段

以下是数据表中的主要字段：

**基本信息**
| 字段名 | 说明 |
|--------|------|
| SecurityID | 股票代码（如 600000） |
| Symbol | 股票简称（如 浦发银行） |
| HTSCSecurityID | 完整代码（如 600000.SH） |
| SecuritySubType | 板块: 02001=主板A股, 02003=创业板, 02004=科创板 |

**价格字段**
| 字段名 | 说明 |
|--------|------|
| PreClosePx | 昨收价 |
| LastPx | 最新价/现价 |
| OpenPx | 开盘价 |
| ClosePx | 收盘价 |
| HighPx | 最高价 |
| LowPx | 最低价 |
| MaxPx | 涨停价 |
| MinPx | 跌停价 |

**成交字段**
| 字段名 | 说明 |
|--------|------|
| TotalVolumeTrade | 成交量（股） |
| TotalValueTrade | 成交额（元） |
| NumTrades | 成交笔数 |

**盘口字段**
| 字段名 | 说明 |
|--------|------|
| Buy1Price | 买一价 |
| Buy1OrderQty | 买一量 |
| Sell1Price | 卖一价 |
| Sell1OrderQty | 卖一量 |
| TotalBidQty | 买入总量 |
| TotalOfferQty | 卖出总量 |

**重要说明：**
- 使用 LastPx（最新价）或 ClosePx（收盘价）计算涨跌幅
- TotalValueTrade 是成交金额（单位：元）
- MaxPx 是涨停价，MinPx 是跌停价

## 可计算的衍生指标

以下指标会由系统自动计算，你只需在 metrics 字段中指定名称：

| 指标名 | 计算公式 | 说明 |
|-------|---------|------|
| 涨幅 | (ClosePx - PreClosePx) / PreClosePx * 100 | 涨跌幅百分比 |
| 跌幅 | (PreClosePx - ClosePx) / PreClosePx * 100 | 下跌幅度百分比 |
| 振幅 | (HighPx - LowPx) / PreClosePx * 100 | 日内振幅百分比 |
| 是否涨停 | ClosePx >= MaxPx ? 1 : 0 | 1=涨停, 0=未涨停 |
| 是否跌停 | ClosePx <= MinPx ? 1 : 0 | 1=跌停, 0=未跌停 |
| 买卖盘比 | TotalBidQty / TotalOfferQty | 买盘总量/卖盘总量 |

## 市场代码

- XSHG: 上海证券交易所
- XSHE: 深圳证券交易所
- US: 美国股票市场（当用户提到美股、US stocks、American stocks、NYSE/Nasdaq 时使用）
- ALL: A股全部市场（上海+深圳，默认）

## 输出格式

输出一个 JSON 对象，包含以下字段（根据查询需要选择性使用）：

```json
{
  "intent": "查询意图的简要描述",
  "date": "YYYYMMDD格式的日期",
  "market": "XSHG/XSHE/US/ALL",
  "select_fields": ["需要输出的字段列表"],
  "metrics": ["需要计算的衍生指标"],
  "filters": [
    {"field": "字段名", "op": "操作符", "value": "值"}
  ],
  "order_by": [
    {"field": "排序字段", "desc": true/false}
  ],
  "group_by": ["分组字段"],
  "aggregations": [
    {"func": "聚合函数", "field": "字段", "alias": "别名"}
  ],
  "having": [
    {"field": "字段", "op": "操作符", "value": "值"}
  ],
  "limit": 返回记录数
}
```

## 重要规则

1. **只输出 JSON**，不要有任何其他文字或解释
2. 日期格式必须是 YYYYMMDD（如 20250115）
3. 如果用户没有指定日期，使用提供的默认日期
4. 如果用户没有指定数量限制，默认 limit=100
5. 根据查询类型选择合适的字段组合：
   - TopK 查询：使用 order_by + limit
   - 条件筛选：使用 filters
   - 统计分析：使用 aggregations + group_by
   - 异动发现：结合 filters 和 order_by
6. **select_fields 只包含与查询相关的必要字段**，不要返回不相关的列：
   - 涨幅查询：SecurityID, Symbol, PreClosePx, LastPx/ClosePx
   - 成交额查询：SecurityID, Symbol, TotalValueTrade
   - 涨跌停查询：SecurityID, Symbol, LastPx/ClosePx, MaxPx/MinPx
   - 盘口查询：SecurityID, Symbol, Buy1Price, Sell1Price
7. 始终包含 SecurityID 和 Symbol 字段以便识别股票
8. **原始数据查询**：对于需要查看指定时间段内的行情数据序列，使用 query_type="raw_data"
   - 适用于：查看某只股票某时间段的行情、分时数据等
   - 使用 time_range 指定时间范围：{"start": "150000", "end": "153000"}（格式 HHMMSSsss）
   - 数据按时间顺序返回，不去重
9. **复杂分析查询**：对于需要跨时序计算、多指标组合分析的查询，使用 query_type="complex_analysis"
   - 盘口异动分析 (analysis_type="order_book_anomaly")：计算委比波动率、挂单变化率等
   - 资金流向分析 (analysis_type="money_flow")：分析主力资金流入流出，支持单只股票分析
   - 买卖压力分析 (analysis_type="pressure_analysis")：分析买卖盘深度变化
"""

FEW_SHOT_EXAMPLES = """
## 示例

**示例1：涨幅排名查询**
用户：今天涨幅前10的股票
```json
{
  "intent": "查询涨幅最高的前10只股票",
  "date": "20250115",
  "market": "ALL",
  "select_fields": ["SecurityID", "Symbol", "PreClosePx", "LastPx"],
  "metrics": ["涨幅"],
  "filters": [],
  "order_by": [{"field": "涨幅", "desc": true}],
  "limit": 10,
  "query_type": "basic"
}
```

**示例2：成交额筛选**
用户：成交额超过10亿的股票
```json
{
  "intent": "筛选成交额超过10亿的股票",
  "date": "20250115",
  "market": "ALL",
  "select_fields": ["SecurityID", "Symbol", "TotalValueTrade", "LastPx"],
  "metrics": ["涨幅"],
  "filters": [{"field": "TotalValueTrade", "op": ">", "value": 10000000000}],
  "order_by": [{"field": "TotalValueTrade", "desc": true}],
  "limit": 100,
  "query_type": "filter"
}
```

**示例3：成交额排名**
用户：成交额最高的5只股票
```json
{
  "intent": "查询成交额最高的前5只股票",
  "date": "20250115",
  "market": "ALL",
  "select_fields": ["SecurityID", "Symbol", "TotalValueTrade", "LastPx"],
  "metrics": ["涨幅"],
  "filters": [],
  "order_by": [{"field": "TotalValueTrade", "desc": true}],
  "limit": 5,
  "query_type": "basic"
}
```

**示例4：涨跌统计**
用户：统计今天上涨和下跌的股票数量
```json
{
  "intent": "统计涨跌股票数量",
  "date": "20250115",
  "market": "ALL",
  "select_fields": [],
  "metrics": [],
  "aggregations": [
    {"func": "COUNT", "field": "CASE WHEN LastPx > PreClosePx THEN 1 END", "alias": "上涨数量"},
    {"func": "COUNT", "field": "CASE WHEN LastPx < PreClosePx THEN 1 END", "alias": "下跌数量"},
    {"func": "COUNT", "field": "*", "alias": "总数量"}
  ],
  "limit": 1,
  "query_type": "stats"
}
```

**示例5：涨停股查询**
用户：今天涨停的股票有哪些
```json
{
  "intent": "查询涨停股票",
  "date": "20250115",
  "market": "ALL",
  "select_fields": ["SecurityID", "Symbol", "LastPx", "PreClosePx", "MaxPx"],
  "metrics": ["涨幅"],
  "filters": [{"field": "是否涨停", "op": "=", "value": 1}],
  "order_by": [{"field": "TotalValueTrade", "desc": true}],
  "limit": 100,
  "query_type": "filter"
}
```

**示例6：跌幅排名**
用户：跌幅最大的10只股票
```json
{
  "intent": "查询跌幅最大的前10只股票",
  "date": "20250115",
  "market": "ALL",
  "select_fields": ["SecurityID", "Symbol", "PreClosePx", "LastPx"],
  "metrics": ["涨幅"],
  "filters": [],
  "order_by": [{"field": "涨幅", "desc": false}],
  "limit": 10,
  "query_type": "basic"
}
```

**示例7：闲聊/知识问答**
用户：股票中的涨幅是什么意思
```json
{
  "intent": "解释涨幅概念",
  "query_type": "chat",
  "answer": "涨幅是指股票价格相对于前一交易日收盘价的变化百分比。计算公式为：涨幅 = (当前价格 - 昨收价) / 昨收价 × 100%。例如，如果一只股票昨天收盘价是10元，今天涨到11元，涨幅就是10%。涨幅为正表示上涨，为负表示下跌。"
}
```

**示例8：简单问候**
用户：你好
```json
{
  "intent": "问候",
  "query_type": "chat",
  "answer": "你好！我是智能行情分析助手，可以帮你查询股票行情数据，例如涨幅排名、成交额筛选、涨跌停统计等。请问有什么可以帮你的？"
}
```

**示例9：复杂分析 - 盘口异动分析**
用户：找出今日盘口异动最大的5只股票
```json
{
  "intent": "分析盘口异动最大的股票",
  "date": "20250115",
  "market": "ALL",
  "query_type": "complex_analysis",
  "analysis_type": "order_book_anomaly",
  "description": "基于委比波动率、买卖盘挂单变化率、价差波动率计算综合异动分数",
  "limit": 5
}
```

**示例10：复杂分析 - 资金流向分析**
用户：分析哪些股票有主力资金流入迹象
```json
{
  "intent": "分析主力资金流入的股票",
  "date": "20250115",
  "market": "ALL",
  "query_type": "complex_analysis",
  "analysis_type": "money_flow",
  "description": "基于大单成交、买卖盘压力、价格变化分析资金流向",
  "limit": 10
}
```

**示例11：复杂分析 - 买卖压力分析**
用户：分析科大讯飞今天的买卖压力变化
```json
{
  "intent": "分析单只股票的买卖压力变化",
  "date": "20250115",
  "market": "ALL",
  "query_type": "complex_analysis",
  "analysis_type": "pressure_analysis",
  "filters": [{"field": "Symbol", "op": "=", "value": "科大讯飞"}],
  "description": "分析买卖盘深度变化、委买委卖比时序变化",
  "limit": 100
}
```

**示例12：时间段行情数据查询（原始数据）**
用户：展示中兴通讯今天从15:00到15:30的行情数据
```json
{
  "intent": "查询指定股票在特定时间段内的行情数据",
  "date": "20250115",
  "market": "ALL",
  "query_type": "raw_data",
  "select_fields": ["SecurityID", "Symbol", "MDTime", "LastPx", "TotalVolumeTrade", "TotalValueTrade", "Buy1Price", "Sell1Price"],
  "metrics": ["涨幅"],
  "filters": [{"field": "Symbol", "op": "=", "value": "中兴通讯"}],
  "time_range": {"start": "150000", "end": "153000"},
  "order_by": [{"field": "MDTime", "desc": false}],
  "limit": 1000
}
```

**示例13：单只股票资金流向分析**
用户：中兴通讯今天有主力资金流入迹象吗
```json
{
  "intent": "分析指定股票的主力资金流向",
  "date": "20250115",
  "market": "ALL",
  "query_type": "complex_analysis",
  "analysis_type": "money_flow",
  "filters": [{"field": "Symbol", "op": "=", "value": "中兴通讯"}],
  "description": "分析该股票的主动买入卖出、买卖盘比变化等资金流向指标",
  "limit": 10
}
```

**示例14：多轮对话 - 基于上一轮结果追问**
用户：[上轮结果显示中兴通讯成交额最高] 中兴通讯今天的盘口数据怎么样
```json
{
  "intent": "查询指定股票的盘口数据",
  "date": "20250115",
  "market": "ALL",
  "query_type": "raw_data",
  "select_fields": ["SecurityID", "Symbol", "MDTime", "LastPx", "Buy1Price", "Buy1OrderQty", "Sell1Price", "Sell1OrderQty", "TotalBidQty", "TotalOfferQty"],
  "metrics": ["买卖盘比"],
  "filters": [{"field": "Symbol", "op": "=", "value": "中兴通讯"}],
  "order_by": [{"field": "MDTime", "desc": true}],
  "limit": 100
}
```
"""


# ============================================================================
# LLM 查询计划生成器
# ============================================================================

class LLMQueryPlanner:
    """
    基于 LLM 的查询计划生成器

    使用 LLM 理解用户意图并生成灵活的查询计划。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化计划生成器。

        参数:
            llm_client: LLM 客户端实例。如果为 None，则创建新实例。
        """
        self.llm_client = llm_client or LLMClient()

    def generate_plan(
        self,
        user_query: str,
        default_date: Optional[str] = None,
        default_market: str = "ALL",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        从自然语言生成查询计划。

        参数:
            user_query: 用户的自然语言查询
            default_date: 默认日期（YYYYMMDD 格式）
            default_market: 默认市场代码
            context: 额外上下文（对话历史等）

        返回:
            (query_plan, validation_errors) 元组
            - query_plan: 生成的计划字典
            - validation_errors: 验证错误列表（如果有效则为空）
        """

        # 如果未提供默认日期，使用昨天
        if not default_date:
            yesterday = datetime.now() - timedelta(days=1)
            default_date = yesterday.strftime("%Y%m%d")

        # 构建提示词
        prompt = self._build_prompt(user_query, default_date, default_market, context)

        # 调用 LLM
        try:
            response = self.llm_client.chat(
                prompt=prompt,
                system_prompt=PLANNER_SYSTEM_PROMPT,
                temperature=0.1,  # 低温度保证输出稳定性
                max_tokens=1024,
            )

            # 从响应中解析 JSON
            query_plan = self._parse_json_response(response)

            # 验证计划
            validation_errors = self._validate_plan(query_plan)

            # 应用默认值
            query_plan = self._apply_defaults(query_plan, default_date, default_market)

            return query_plan, validation_errors

        except Exception as e:
            return {
                "error": str(e),
                "intent": "解析失败",
                "date": default_date,
                "market": default_market,
            }, [f"LLM调用或解析失败: {str(e)}"]

    def _build_prompt(
        self,
        user_query: str,
        default_date: str,
        default_market: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """构建 LLM 提示词。"""

        prompt_parts = [FEW_SHOT_EXAMPLES]

        # 如果有上下文，添加到提示词中
        if context:
            prompt_parts.append(f"\n## 上下文信息\n{json.dumps(context, ensure_ascii=False)}")

        # 添加当前查询
        prompt_parts.append(f"""
## 当前查询

**默认日期**: {default_date}
**默认市场**: {default_market}
**用户输入**: {user_query}

请输出 QueryPlan（纯 JSON）：
""")

        return "\n".join(prompt_parts)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """从 LLM 响应中解析 JSON。"""

        # 尝试从响应中提取 JSON
        response = response.strip()

        # 移除 markdown 代码块（如果存在）
        if response.startswith("```"):
            # 在代码块之间查找 JSON 内容
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                response = match.group(1)

        # 尝试解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试在响应中查找 JSON 对象
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"无法从响应中解析 JSON: {response[:200]}...")

    def _validate_plan(self, plan: Dict[str, Any]) -> List[str]:
        """
        验证查询计划的安全性。

        返回验证错误列表（如果有效则为空）。
        """
        errors = []

        # 检查日期格式
        date_str = plan.get("date")
        if date_str:
            try:
                datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                errors.append(f"日期格式错误（应为 YYYYMMDD）: {date_str}")

        # 检查市场代码
        market = plan.get("market")
        if market and market not in {"XSHG", "XSHE", "US", "ALL"}:
            errors.append(f"市场代码无效: {market}")

        # 检查 limit
        limit = plan.get("limit")
        if limit is not None:
            if not isinstance(limit, int) or limit < 1 or limit > 10000:
                errors.append(f"limit 必须是 1-10000 的整数: {limit}")

        # 检查 select_fields
        for field in plan.get("select_fields", []):
            if field not in ALL_ALLOWED_FIELDS:
                errors.append(f"字段不在白名单中: {field}")

        # 检查 metrics
        for metric in plan.get("metrics", []):
            if metric not in DERIVED_METRICS:
                errors.append(f"指标不在白名单中: {metric}")

        # 检查 filters
        for f in plan.get("filters", []):
            field = f.get("field")
            op = f.get("op", "").upper()
            # 允许衍生指标在过滤条件中使用
            if field and field not in ALL_ALLOWED_FIELDS:
                errors.append(f"过滤字段不在白名单中: {field}")
            if op and op not in ALLOWED_OPERATORS:
                errors.append(f"操作符不在白名单中: {op}")

        # 检查 order_by
        for o in plan.get("order_by", []):
            field = o.get("field")
            if field and field not in ALL_ALLOWED_FIELDS:
                errors.append(f"排序字段不在白名单中: {field}")

        # 检查 group_by
        for field in plan.get("group_by", []):
            if field not in ALL_ALLOWED_FIELDS:
                errors.append(f"分组字段不在白名单中: {field}")

        return errors

    def _apply_defaults(
        self,
        plan: Dict[str, Any],
        default_date: str,
        default_market: str,
    ) -> Dict[str, Any]:
        """为计划应用默认值。"""

        if "date" not in plan or not plan["date"]:
            plan["date"] = default_date

        if "market" not in plan or not plan["market"]:
            plan["market"] = default_market

        if "limit" not in plan or not plan["limit"]:
            plan["limit"] = 100

        if "select_fields" not in plan:
            plan["select_fields"] = ["SecurityID"]

        if "metrics" not in plan:
            plan["metrics"] = []

        if "filters" not in plan:
            plan["filters"] = []

        if "order_by" not in plan:
            plan["order_by"] = []

        return plan


# ============================================================================
# 便捷函数
# ============================================================================

def generate_query_plan(
    user_query: str,
    default_date: Optional[str] = None,
    default_market: str = "ALL",
    llm_client: Optional[LLMClient] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    生成查询计划的便捷函数。

    参数:
        user_query: 用户的自然语言查询
        default_date: 默认日期
        default_market: 默认市场代码
        llm_client: 可选的 LLM 客户端实例

    返回:
        (query_plan, validation_errors) 元组
    """
    planner = LLMQueryPlanner(llm_client)
    return planner.generate_plan(user_query, default_date, default_market)


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    print("LLM 查询计划生成器测试")
    print("=" * 60)

    # 测试（如果 vLLM 服务未运行会失败）
    planner = LLMQueryPlanner()

    test_queries = [
        "今天涨幅前10的股票",
        "成交额超过10亿的股票有哪些",
        "统计今天涨跌停的股票数量",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 40)
        try:
            plan, errors = planner.generate_plan(query)
            print(f"计划: {json.dumps(plan, ensure_ascii=False, indent=2)}")
            if errors:
                print(f"错误: {errors}")
        except Exception as e:
            print(f"错误: {e}")
            print("（提示：需要先启动 vLLM 服务）")
            break
