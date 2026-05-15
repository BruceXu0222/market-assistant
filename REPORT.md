# Market Intelligence Assistant: A Natural-Language Interface for HK and US Equity Data

**Author:** Bruce Xu  
**Project:** Market Assistant  
**Date:** May 2026

## Abstract

The Market Intelligence Assistant is an English-language stock data query system designed for interactive analysis of Hong Kong and United States equity markets. The system combines a large language model (LLM), a constrained query-planning layer, deterministic SQL execution through DuckDB, and a Streamlit-based user interface. Users can ask natural-language questions such as “Which HK stocks had the highest turnover today?”, “Show the 10 biggest US stock decliners today,” or “Show Tesla’s price trend in January 2025.” The assistant translates these questions into structured QueryPlans, validates them against an allowed schema, compiles them into SQL, executes the queries over local parquet files, and returns tables, charts, and concise English commentary.

The key design principle is separation of responsibility. The LLM is used for intent understanding, plan generation, and result narration, but it is not trusted to perform numerical computation. All filtering, sorting, aggregation, and time-series retrieval are executed by DuckDB over real parquet data. This approach reduces hallucination risk, improves debuggability, and makes the system more reliable for financial data exploration. The current implementation supports two markets, HK and US, with one parquet file per stock under `data/hk` and `data/us`. The system has been evaluated through unit tests, integration tests, static repository scans, and real-data DuckDB smoke tests. The result is a practical prototype for natural-language market analysis that balances LLM flexibility with deterministic computation.

## 1. Introduction

Financial market data is highly structured, but the questions analysts ask are often informal and exploratory. A user may want to know which stocks had the largest declines, which securities exceeded a turnover threshold, or how a particular stock moved over a month. These questions are simple to express in natural language but require knowledge of the data schema, file layout, SQL syntax, field names, and market conventions. Traditional query interfaces place that burden on the user.

The Market Intelligence Assistant addresses this gap by providing a conversational interface over local stock-market data. Instead of writing SQL manually, the user asks a question in English. The assistant interprets the intent, identifies relevant fields, generates a structured query plan, executes the corresponding computation, and presents the result in a user-friendly format. The current system is scoped to HK and US equities, because those are the two markets represented in the real data directories.

This project is motivated by a practical tension in LLM-based analytics. Modern language models are strong at language understanding and can map user intent to structured representations. However, they are not reliable calculators or database engines. In financial contexts, returning an invented number or silently applying an incorrect formula is unacceptable. The assistant therefore treats the LLM as a planning and explanation component, while DuckDB serves as the authoritative computation engine.

The prototype includes a FastAPI backend, a Streamlit frontend, a query planner, a SQL compiler, a parquet path resolver, and a small workflow layer. It also includes safeguards to keep the operating language English and to translate or sanitize stock names before output. When possible, the UI renders visualizations alongside result tables and text commentary.

The remainder of this report describes the background, system architecture, implementation details, evaluation results, limitations, and future work.

## 2. Background

### 2.1 Natural-Language Data Interfaces

Natural-language interfaces to databases have existed for decades, but LLMs have made them more practical by improving intent recognition and schema mapping. A user can express a request in ordinary language, and a model can infer whether the task requires filtering, ranking, aggregation, or time-series retrieval. This is particularly useful in exploratory analysis, where users may not know the exact schema in advance.

However, directly generating SQL from natural language can be risky. The generated query may reference invalid fields, use unsupported functions, or misinterpret market-specific concepts. An even greater risk appears when the LLM is asked to answer from memory or perform arithmetic directly. In market analysis, the assistant must avoid producing numbers that are not grounded in the data.

The approach in this project uses an intermediate representation called a QueryPlan. The LLM outputs JSON rather than SQL. The JSON is constrained to supported fields, operators, markets, dates, filters, sort orders, and aggregation structures. A deterministic compiler then turns this QueryPlan into SQL. This gives the system both flexibility and control.

### 2.2 DuckDB and Parquet for Local Analytics

DuckDB is well suited for embedded analytical workloads. It can query parquet files directly, supports SQL features such as filtering, aggregation, ordering, and window functions, and does not require a separate server process. For this project, the data is stored locally as parquet files, one file per stock. DuckDB can scan those files efficiently and apply column pruning and predicate filtering.

The current data layout is:

```text
data/
  hk/    # HK daily history, one parquet file per stock
  us/    # US daily history, one parquet file per stock
```

This layout differs from a date-partitioned market data warehouse. Since each file contains the history for one stock, the system cannot find a trading day by selecting a date-partitioned directory. Instead, it scans the relevant market files and applies the requested date or date range inside SQL.

### 2.3 Financial Query Safety

Financial applications require careful handling of facts, calculations, and language. A user might ask for “turnover,” “turnover rate,” “decliners,” or “price trend,” and each phrase maps to a different field or operation. The assistant therefore defines a limited but explicit field vocabulary:

- `Market`
- `MDDate`
- `SecurityID`
- `Symbol`
- `OpenPx`, `ClosePx`, `LastPx`, `HighPx`, `LowPx`, `PreClosePx`
- `TotalVolumeTrade`
- `TotalValueTrade`
- `ChangePx`
- `ChangePct`
- `Amplitude`
- `TurnoverRate`

The supported markets are `HK`, `US`, and `ALL`. The system intentionally removes irrelevant legacy concepts, such as A-share market codes and order-book-only fields, because the current dataset only contains HK and US historical daily bars.

## 3. System Design

### 3.1 Overview

The assistant is organized as a pipeline:

1. The user submits an English market question.
2. The backend receives the request through FastAPI.
3. The LLM planner generates a QueryPlan JSON object.
4. The API applies UI defaults for date and market unless the user explicitly specifies them.
5. The QueryPlan is validated against an allowlist.
6. The path resolver selects HK, US, or both parquet scan patterns.
7. The SQL compiler converts the QueryPlan into DuckDB SQL.
8. DuckDB executes the SQL and returns a DataFrame.
9. The API post-processes the result, including English stock-name display handling.
10. The UI renders tables, charts, and commentary.

This architecture makes the generated SQL inspectable in debug mode. If the answer is unexpected, the developer can examine the QueryPlan, SQL, parquet paths, and validation messages.

### 3.2 QueryPlan Representation

The QueryPlan is the central control object. A typical plan contains:

```json
{
  "intent": "Rank US stocks by worst daily percent change",
  "date": "20250115",
  "market": "US",
  "query_type": "basic",
  "select_fields": ["Market", "SecurityID", "Symbol", "ClosePx", "ChangePct"],
  "metrics": [],
  "filters": [],
  "order_by": [{"field": "ChangePct", "desc": false}],
  "limit": 10
}
```

The planner supports several query types. `basic` is used for rankings and simple sorted lists. `filter` is used when the user asks for records matching a condition. `raw_data` is used for historical series or trend questions. `stats` is used for aggregate summaries.

The model is prompted to output JSON only. It is instructed to use supported fields and avoid unsupported concepts. In addition to model prompting, deterministic query hints are applied for common user patterns. For example, “Tesla” maps to market `US` and ticker `TSLA`; “Tencent” maps to market `HK` and code `00700`; “turnover rate above 5%” maps to a `TurnoverRate > 5` filter; and month-based trend questions produce a `date_range`.

### 3.3 Date and Market Defaults

The Streamlit sidebar includes a default trading date and default market. These defaults are important because many natural-language questions contain relative terms such as “today” or omit the market entirely. Earlier behavior could ignore changed defaults and return the most recent data. The current API treats UI defaults as authoritative unless the user explicitly states another date or market.

For example, if the default market is set to `HK`, a query such as “Which stocks had the highest turnover today?” uses HK. If the user asks “Show Tesla’s price trend,” the explicit stock mention overrides the default market and uses US. This behavior improves predictability while preserving natural user intent.

### 3.4 English Output and Stock Names

The assistant is designed to operate in English. All user-facing interface text, prompt text, documentation, and tests have been converted to English, except for files whose filenames are Chinese as requested. The raw data may still contain non-English column headers or stock names. To preserve compatibility while keeping source text English, the SQL compiler uses escaped constants for raw source column names.

The output pipeline also sanitizes stock labels. Known tickers and local security IDs are mapped to English names, such as `TSLA` to “Tesla” and `00700` to “Tencent Holdings.” If a stock name cannot be translated reliably, the system falls back to the security code rather than displaying a non-English label. This affects tables, charts, and commentary context.

## 4. Implementation

### 4.1 Backend API

The backend is implemented in `app/api.py` using FastAPI. The primary endpoint is `POST /chat`. The request includes the user message, session ID, debug flag, default trading date, and default market. The response includes:

- `session_id`
- `table`
- `summary`
- `commentary`
- `field_explanations`
- `debug`

The endpoint performs several steps. It creates or retrieves session state, normalizes date and market defaults, generates a QueryPlan, applies UI defaults, validates the plan, resolves parquet paths, compiles SQL, executes DuckDB, filters result columns, translates stock display names, generates commentary, and stores the conversation history.

The backend also exposes a health endpoint at `/health`. This endpoint reports service health and attempts a small LLM request to check model connectivity.

### 4.2 LLM Planner

The planner in `core/llm_planner.py` defines the field schema, derived metrics, allowed operators, and model prompt. It uses an OpenAI-compatible client and returns a plan plus validation errors. The planner includes fallback behavior for parsing model responses that contain markdown code blocks or extra text around JSON.

The planner now uses English derived metric names:

- `GainPct`
- `LossPct`

In practice, many plans prefer direct fields such as `ChangePct`, `Amplitude`, and `TurnoverRate`, because those fields already exist in the normalized daily-bar schema. This reduces unnecessary metric expansion.

### 4.3 SQL Compiler

The SQL compiler in `core/sql_compiler.py` converts QueryPlans into SQL. It supports:

- basic ranking queries
- filter queries
- raw historical data queries
- aggregation queries
- group-by queries
- legacy snapshot de-duplication
- multi-file parquet scans

For HK and US daily history, the compiler normalizes different source schemas into a shared logical table. It produces fields such as `Market`, `SecurityID`, `Symbol`, `MDDate`, `OpenPx`, `ClosePx`, `ChangePct`, and `TurnoverRate`. Since the physical parquet columns may use non-English headers, the compiler references them through escaped constants rather than visible non-English source text.

### 4.4 Path Resolver

The path resolver in `core/path_resolver.py` maps markets to parquet scan patterns. For `HK`, it returns `data/hk/*.parquet`. For `US`, it returns `data/us/*.parquet`. For `ALL`, it returns both. It also supports listing available trading dates by scanning the date column in the parquet files.

This design is aligned with the current storage format: one parquet file per stock. It avoids constructing extremely long SQL statements that union every individual file path by returning glob patterns when possible.

### 4.5 Streamlit UI

The UI in `app/ui_streamlit.py` provides an interactive chat interface. The sidebar includes:

- API status check
- debug mode
- default trading date
- default market
- clear chat
- help text

The main panel displays example questions, conversation history, result tables, charts, commentary, and debug information. Chart rendering is automatic when the result shape supports it. If the result contains `MDDate` and `ClosePx` with multiple rows, the UI renders a line chart for close-price trend. Otherwise, it looks for a suitable numeric metric such as `ChangePct`, `TurnoverRate`, `TotalValueTrade`, `TotalVolumeTrade`, `Amplitude`, or `ClosePx` and renders a bar chart by stock.

## 5. Evaluation

### 5.1 Test Coverage

The system was evaluated with unit and integration tests covering the planner, plan validation, SQL compiler, and planner/compiler integration. The current test suite passes:

```text
33 passed
```

The tests cover:

- valid and invalid QueryPlans
- invalid date formats
- invalid market codes
- invalid operators
- invalid fields and metrics
- SQL generation for basic queries
- SQL generation for filters
- SQL generation for derived metrics
- SQL generation for aggregations
- SQL generation for group-by queries
- multi-file parquet scan SQL
- planner output compilation

These tests are not exhaustive, but they cover the core path from natural-language planning to executable SQL.

### 5.2 Static Checks

The repository was scanned for non-English text in tracked text files, excluding files whose names are Chinese and excluding binary assets such as parquet, png, and docx files. The scan returned no remaining matches. A separate scan for commented-out code and obsolete TODO scaffolding also returned no matches.

Python compilation was run across the main application modules, core modules, workflow nodes, and data retrieval scripts. This confirms that the codebase remains syntactically valid after the English-language cleanup and removal of commented-out prototype code.

### 5.3 Real-Data Smoke Test

A real-data DuckDB smoke test was run against US parquet data. The test resolved the latest available US trading date, compiled a query for the largest decliners, and executed it with DuckDB. This verified that the compiler can still query physical parquet files even though source-code references to raw non-English column names were converted to escaped constants.

The smoke test also exposed a robustness issue: `PathResolver` accepted `Path` objects but not string paths. This was fixed by normalizing string input to `Path` during initialization.

### 5.4 Limitations of Evaluation

The current evaluation is appropriate for a prototype but not sufficient for production financial software. The tests mostly verify structure, compilation, and representative behavior. They do not yet measure query latency over the full dataset, compare LLM plan quality across many natural-language variants, or validate every stock-name translation. They also do not include a large benchmark of real analyst questions.

## 6. Conclusion

The Market Intelligence Assistant demonstrates a practical architecture for natural-language market data analysis. By combining LLM-based planning with deterministic DuckDB execution, the system avoids the most dangerous failure mode of LLM analytics: invented numerical answers. The model is used where it is strongest, namely language understanding and explanation, while SQL handles all computation.

The assistant now supports English operation across the repository and interface, real HK and US parquet data, default market and date controls, chart rendering, English stock-name output handling, and a simplified two-market scope. The result is a usable prototype for querying market data through natural language while preserving transparency through QueryPlans, SQL debug output, and deterministic execution.

## 7. Future Work

Several improvements would make the assistant more useful and robust.

First, the English stock-name mapping should be expanded. The current system maps important and commonly queried securities, but the dataset contains many HK and US stocks. A complete mapping table would improve charts, tables, and commentary.

Second, the system should add richer visualizations. Current charts support close-price trends and simple bar charts. Future versions could support multi-stock comparison lines, distribution charts, sector-level summaries, and market breadth visualizations.

Third, multi-turn reasoning can be improved. The system stores conversation history, but follow-up questions could more precisely reference prior result sets. For example, after showing the top decliners, the user might ask, “Show their price trends over the last month.” Supporting that requires carrying result identifiers into the next QueryPlan.

Fourth, evaluation should be expanded with a benchmark of English financial questions. The benchmark should include expected QueryPlans, SQL patterns, and result checks over fixed parquet fixtures.

Fifth, performance optimization may be needed as the dataset grows. Repeated scans over all HK and US files could be improved through caching, materialized metadata tables, or optional partitioned storage by date.

Finally, production deployment would require authentication, rate limiting, stronger error handling, observability, and clearer user-facing explanations when a requested trading date is unavailable.
