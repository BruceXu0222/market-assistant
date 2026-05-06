"""
FastAPI 服务层
=============

功能：
1. 提供 RESTful API 接口
2. 管理会话状态
3. 调用 LLM 计划生成 + SQL 编译 + DuckDB 执行
4. 返回结构化结果

主要接口：
- POST /chat: 主要对话接口
- GET /health: 健康检查
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
import duckdb
from pathlib import Path

# 导入核心模块
from core.llm_client import LLMClient
from core.llm_planner import LLMQueryPlanner
from core.sql_compiler import SQLCompilerEnhanced

# ============================================================================
# FastAPI 应用初始化
# ============================================================================

app = FastAPI(
    title="智能行情分析助手 API",
    description="基于 LLM + DuckDB 的股票行情分析系统",
    version="2.0.0",
)

# CORS 中间件配置（允许 Streamlit 等前端调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 全局实例
# ============================================================================

llm_client: Optional[LLMClient] = None
planner: Optional[LLMQueryPlanner] = None
compiler: Optional[SQLCompilerEnhanced] = None

# 会话状态管理（MVP: 内存字典）
sessions: Dict[str, Dict[str, Any]] = {}

# 数据目录配置
DATA_ROOT = Path("data")


# ============================================================================
# 辅助函数
# ============================================================================

def get_or_create_session(session_id: Optional[str] = None) -> str:
    """获取或创建会话"""
    if session_id is None:
        session_id = str(uuid.uuid4())

    if session_id not in sessions:
        # 默认使用昨天作为默认日期
        yesterday = datetime.now() - timedelta(days=1)
        sessions[session_id] = {
            "created_at": datetime.now().isoformat(),
            "default_date": yesterday.strftime("%Y%m%d"),
            "default_market": "ALL",
            "history": [],
        }
        print(f"[API] 创建新会话: {session_id}")

    return session_id


def resolve_parquet_paths(date: str, market: str) -> List[str]:
    """
    解析 Parquet 文件路径

    Args:
        date: 日期（YYYYMMDD）
        market: 市场代码（XSHG/XSHE/US/ALL）

    Returns:
        parquet_paths: Parquet 文件路径列表
    """
    paths = []

    # 市场目录映射
    market_dirs = {
        "XSHG": "XSHG_Stock_Snapshot_Level2_Day",
        "XSHE": "XSHE_Stock_Snapshot_Level2_Day",
        "US": "US_Stock_Snapshot_Level2_Day",
    }

    if market == "ALL":
        markets = ["XSHG", "XSHE"]
    else:
        markets = [market]

    for m in markets:
        if m in market_dirs:
            found = list(DATA_ROOT.glob(f"{market_dirs[m]}/tradingday={date}/*.parquet"))
            if not found:
                found = list(DATA_ROOT.glob(f"{market_dirs[m]}/*{date}*.parquet"))
            paths.extend([str(p) for p in found])

    # 如果没找到真实数据，使用测试数据
    if not paths:
        test_path = DATA_ROOT / "test.parquet"
        if test_path.exists():
            paths = [str(test_path)]
            print(f"[API] 未找到 {date} 的数据，使用测试数据")

    return paths


def generate_commentary(query: str, plan: Dict, result_count: int, summary: Dict) -> str:
    """
    使用 LLM 生成结果解读

    Args:
        query: 用户查询
        plan: 查询计划
        result_count: 结果数量
        summary: 统计摘要

    Returns:
        commentary: 解读文本
    """
    global llm_client

    if not llm_client:
        return f"查询完成，共返回 {result_count} 条记录。"

    try:
        prompt = f"""用户查询：{query}

查询结果摘要：
- 返回记录数：{result_count}
- 统计信息：{summary}

请用简洁专业的语言解读这个查询结果（2-3句话）："""

        response = llm_client.chat(
            prompt=prompt,
            temperature=0.3,
            max_tokens=200,
        )
        return response.strip()
    except Exception as e:
        print(f"[API] 生成解读失败: {e}")
        return f"查询完成，共返回 {result_count} 条记录。"


# ============================================================================
# API 请求/响应模型
# ============================================================================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户输入的自然语言", min_length=1)
    session_id: Optional[str] = Field(None, description="会话 ID，不提供则创建新会话")
    debug: bool = Field(False, description="是否返回 Debug 信息")


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话 ID")
    table: Optional[List[Dict[str, Any]]] = Field(None, description="结果表格")
    summary: Optional[Dict[str, Any]] = Field(None, description="统计摘要")
    commentary: str = Field(..., description="LLM 生成的专业解读")
    field_explanations: Optional[Dict[str, str]] = Field(
        None, description="字段解释（复杂分析时提供）"
    )
    debug: Optional[Dict[str, Any]] = Field(None, description="调试信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    version: str
    llm_status: str


# ============================================================================
# API 路由
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    主要对话接口

    流程：
    1. 获取或创建会话
    2. 使用 LLM 生成查询计划
    3. 编译 SQL 并执行
    4. 生成解读并返回
    """
    global planner, compiler

    try:
        # 1. 获取或创建会话
        session_id = get_or_create_session(request.session_id)
        session_state = sessions[session_id]

        print(f"[API] [{session_id[:8]}] 收到消息: {request.message}")

        # 2. 使用 LLM 生成查询计划
        print(f"[API] 生成查询计划...")
        plan, validation_errors = planner.generate_plan(
            user_query=request.message,
            default_date=session_state["default_date"],
            default_market=session_state["default_market"],
            context={"recent_queries": session_state["history"][-3:]} if session_state["history"] else None,
        )

        if validation_errors:
            print(f"[API] 计划验证警告: {validation_errors}")

        # 确保 query_type 存在
        if not plan.get("query_type"):
            if plan.get("aggregations"):
                plan["query_type"] = "stats"
            else:
                plan["query_type"] = "basic"

        # 处理闲聊类型的查询（不需要查询数据库）
        if plan.get("query_type") in ["chat", "invalid"]:
            answer = plan.get(
                "answer",
                "抱歉，我不太理解您的问题。请尝试问一些关于股票行情的问题，"
                "例如「今天涨幅前10的股票」或「成交额超过10亿的股票有哪些」。"
            )

            # 更新会话历史
            session_state["history"].append({
                "user": request.message,
                "assistant": answer,
                "timestamp": datetime.now().isoformat(),
            })

            return ChatResponse(
                session_id=session_id,
                table=None,
                summary=None,
                commentary=answer,
                debug={"plan": plan} if request.debug else None,
            )

        # 对于纯聚合查询，清空 select_fields
        if plan.get("query_type") == "stats" and plan.get("aggregations") and not plan.get("group_by"):
            plan["select_fields"] = []

        # 3. 解析数据文件路径
        parquet_paths = resolve_parquet_paths(
            plan.get("date", session_state["default_date"]),
            plan.get("market", "ALL")
        )

        if not parquet_paths:
            raise HTTPException(status_code=404, detail="未找到对应日期的数据文件")

        # 4. 编译 SQL
        print(f"[API] 编译 SQL...")
        sql = compiler.compile(plan, parquet_paths)

        # 5. 执行 DuckDB 查询
        print(f"[API] 执行查询...")
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).fetchdf()
        conn.close()

        # 6. 处理结果 - 只保留相关列
        # 确定需要显示的列
        relevant_columns = set()

        # 始终显示股票标识
        relevant_columns.add("SecurityID")
        relevant_columns.add("Symbol")

        # 添加 select_fields 中的列
        for field in plan.get("select_fields", []):
            relevant_columns.add(field)

        # 添加 metrics 中的指标
        for metric in plan.get("metrics", []):
            relevant_columns.add(metric)

        # 添加排序字段
        for order in plan.get("order_by", []):
            relevant_columns.add(order.get("field", ""))

        # 添加聚合结果的别名
        for agg in plan.get("aggregations", []):
            relevant_columns.add(agg.get("alias", ""))

        # 过滤 DataFrame 只保留存在且相关的列
        available_columns = [col for col in df.columns if col in relevant_columns]
        if available_columns:
            df_filtered = df[available_columns]
        else:
            df_filtered = df  # 如果没有匹配的列，显示全部

        table_data = df_filtered.to_dict(orient='records')
        summary = {
            "总记录数": len(df_filtered),
            "列数": len(df_filtered.columns),
        }

        # 添加数值列的统计信息
        for col in df_filtered.select_dtypes(include=['float64', 'int64']).columns[:3]:
            if col not in ["SecurityID"]:
                summary[f"{col}_均值"] = round(df_filtered[col].mean(), 2) if not df_filtered[col].isna().all() else None

        # 7. 获取字段解释（复杂分析时）
        field_explanations = None
        if plan.get("query_type") == "complex_analysis":
            analysis_type = plan.get("analysis_type", "order_book_anomaly")
            field_explanations = compiler.get_field_explanations(analysis_type)

        # 8. 生成解读
        commentary = generate_commentary(
            request.message,
            plan,
            len(df),
            summary
        )

        # 9. 更新会话历史
        session_state["history"].append({
            "user": request.message,
            "assistant": commentary,
            "timestamp": datetime.now().isoformat(),
        })

        # 10. 构建响应（复杂分析时包含字段解释）
        response = ChatResponse(
            session_id=session_id,
            table=table_data,
            summary=summary,
            commentary=commentary,
            field_explanations=field_explanations,
            debug={
                "plan": plan,
                "sql": sql,
                "parquet_paths": parquet_paths,
                "validation_errors": validation_errors,
            } if request.debug else None,
        )

        print(f"[API] 查询完成，返回 {len(table_data)} 条记录")
        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] 处理请求时出错: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查接口"""
    global llm_client

    llm_status = "unknown"
    if llm_client:
        try:
            # 简单测试 LLM 连接
            llm_client.chat("test", max_tokens=5)
            llm_status = "healthy"
        except Exception:
            llm_status = "unhealthy"

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="2.0.0",
        llm_status=llm_status,
    )


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "智能行情分析助手 API",
        "version": "2.0.0",
        "docs": "/docs",
    }


# ============================================================================
# 应用启动/关闭事件
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global llm_client, planner, compiler

    print("[API] 启动智能行情分析助手...")

    # 初始化 LLM 客户端
    try:
        llm_client = LLMClient()
        print(f"[API] LLM 客户端初始化完成: {llm_client.model}")
    except Exception as e:
        print(f"[API] LLM 客户端初始化失败: {e}")
        llm_client = None

    # 初始化查询计划生成器
    planner = LLMQueryPlanner(llm_client)
    print("[API] 查询计划生成器初始化完成")

    # 初始化 SQL 编译器
    compiler = SQLCompilerEnhanced()
    print("[API] SQL 编译器初始化完成")

    print("[API] 服务启动完成!")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    print("[API] 关闭智能行情分析助手...")


# ============================================================================
# 主入口
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
