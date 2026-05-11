# 智能行情分析助手 (Market Intelligence Assistant)

## 系统架构概述

**架构定义（一句话）：**
用 Qwen2.5 负责"理解意图、生成结构化查询计划、生成解读"，用 DuckDB 负责"从 Parquet 做确定性计算"，用 LangGraph 把多轮对话与纠错流程编排成可控状态机，通过 FastAPI 提供服务、Streamlit 做演示 UI。

## 技术栈

- **LLM**: Qwen2.5-7B-Instruct (via vLLM)
- **数据计算**: DuckDB + Parquet
- **工作流编排**: LangGraph
- **API服务**: FastAPI
- **前端演示**: Streamlit
- **日志**: Loguru
- **监控**: Prometheus (可选)

## 系统分层架构

### 1. 交互层 (UI)
- Streamlit 演示界面
- 自然语言输入
- 表格 + 解读文本输出
- Debug 信息展示（QueryPlan、SQL、耗时）

### 2. 服务层 (API)
- FastAPI 提供 RESTful API
- `/chat`: 主要对话接口
- `/health`: 健康检查
- `/metrics`: Prometheus 指标

### 3. 工作流编排层 (核心)
- LangGraph 状态机
- 8个核心节点：Router → PlanGen → Validate → Repair → Execute → PostProcess → Narrate → MemoryUpdate
- 多轮对话状态管理

### 4. 模型层
- vLLM 部署 Qwen2.5-7B-Instruct
- OpenAI-style API
- 低温度参数（0-0.3）保证输出稳定

### 5. 数据计算层
- DuckDB 直接扫描 Parquet
- 所有数值计算由 SQL 完成，杜绝 LLM 幻觉
- 字段白名单机制

### 6. 数据存储层
- Parquet 文件（上交所/深交所日快照数据）
- 会话状态存储（内存/SQLite）

## 数据流示例

用户问："今天涨幅前10的股票有哪些？"

```
1. Streamlit → FastAPI /chat
   输入: {text: "今天涨幅前10...", session_id: "abc"}

2. FastAPI → LangGraph.invoke()
   输入: state = {session memory + new user message}

3. LangGraph 节点执行:
   Router → PlanGen → Validate → Execute → PostProcess → Narrate → MemoryUpdate

4. DuckDB 执行 SQL
   输出: Top10 DataFrame (含计算的涨幅字段)

5. LLM Narrator 生成解读
   输出: 结构化结论（表格 + 文字）

6. FastAPI 返回 JSON
   {table: [...], commentary: "...", debug: {...}}

7. Streamlit 渲染结果
```

## 项目结构

```
market-assistant/
├── app/
│   ├── api.py                 # FastAPI 服务
│   └── ui_streamlit.py        # Streamlit 演示界面
├── workflow/
│   ├── graph.py               # LangGraph 图定义
│   └── nodes/
│       ├── router.py          # 路由节点
│       ├── plan_gen.py        # 计划生成
│       ├── validate.py        # 计划校验
│       ├── repair.py          # 计划修复
│       ├── execute.py         # SQL 执行
│       ├── postprocess.py     # 后处理
│       ├── narrate.py         # 结果解读
│       └── memory_update.py   # 记忆更新
├── core/
│   ├── llm_client.py          # vLLM 客户端
│   ├── plan_schema.py         # QueryPlan Pydantic 定义
│   ├── sql_compiler.py        # QueryPlan → SQL 编译器
│   ├── duckdb_engine.py       # DuckDB 执行引擎
│   ├── path_resolver.py       # 数据文件路径解析
│   └── configs/
│       ├── prompts/           # Prompt 模板
│       │   ├── plan_gen.txt
│       │   ├── plan_repair.txt
│       │   └── narrate.txt
│       └── settings.yaml      # 系统配置
├── tests/
│   ├── test_sql_compiler.py
│   └── test_plan_validate.py
├── data/                      # 数据目录（Parquet 文件）
│   ├── hk/                    # 港股历史日线，每只股票一个 parquet
│   └── us/                    # 美股历史日线，每只股票一个 parquet
└── requirements.txt
```

## 核心设计思想

### QueryPlan（可控性核心）
LLM 只输出 QueryPlan（JSON），不输出 SQL：
```json
{
  "date": "20250115",
  "market": "HK",
  "metrics": ["涨幅", "振幅"],
  "filters": [{"field": "TotalValueTrade", "op": ">", "value": 1000000}],
  "order_by": [{"field": "涨幅", "desc": true}],
  "limit": 10,
  "output_fields": ["Market", "SecurityID", "Symbol", "ClosePx", "涨幅"]
}
```

支持的市场代码：`HK`（港股）、`US`（美股）、`ALL`（港股+美股）。

### 字段白名单
- Market, MDDate, SecurityID, Symbol
- OpenPx, ClosePx, HighPx, LowPx
- TotalValueTrade, TotalVolumeTrade, ChangePct, Amplitude, TurnoverRate
- 防止注入和字段不存在错误

### DuckDB SQL 编译
- 列裁剪：只 SELECT 必要列
- 先过滤后排序：减少排序数据量
- TopK 优化：ORDER BY ... LIMIT k
- 衍生指标在 SQL 中 AS 计算

## 部署说明

### vLLM 部署
```bash
# 启动 vLLM 服务
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --temperature 0.2
```

### FastAPI 服务
```bash
# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
uvicorn app.api:app --host 0.0.0.0 --port 8080
```

### Streamlit UI
```bash
streamlit run app/ui_streamlit.py
```

## 关键问题回答

**Q: 为什么使用 LangGraph？**
A: 对话是状态机，节点可控、可回退、可重试，比"纯 prompt 链"稳定。

**Q: 为什么使用 DuckDB？**
A: 对 Parquet 原生支持、SQL 表达力强、无需全量加载、TopK/聚合快。

**Q: 如何避免幻觉？**
A: LLM 不做计算，只做计划与解释；所有数值来自 DuckDB，且 plan schema 校验 + 字段白名单。

## 开发路线图

- [ ] 核心组件开发
- [ ] LangGraph 工作流实现
- [ ] FastAPI 接口开发
- [ ] Streamlit UI 开发
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 文档完善

## 许可证

MIT License
