"""FastAPI service layer for the market assistant."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
import duckdb
import re
from pathlib import Path

from core.llm_client import LLMClient
from core.llm_planner import LLMQueryPlanner
from core.sql_compiler import SQLCompilerEnhanced
from core.path_resolver import PathResolver
from core.stock_names import english_stock_name

app = FastAPI(
    title="Market Assistant API",
    description="LLM + DuckDB stock market analysis for HK and US daily data",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_client: Optional[LLMClient] = None
planner: Optional[LLMQueryPlanner] = None
compiler: Optional[SQLCompilerEnhanced] = None
path_resolver: Optional[PathResolver] = None

sessions: Dict[str, Dict[str, Any]] = {}
DATA_ROOT = Path("data")


def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get or create a session."""
    if session_id is None:
        session_id = str(uuid.uuid4())

    if session_id not in sessions:
        latest_date = path_resolver.latest_available_date("ALL") if path_resolver else None
        if not latest_date:
            # Fallback to yesterday if the data catalog cannot be read.
            yesterday = datetime.now() - timedelta(days=1)
            latest_date = yesterday.strftime("%Y%m%d")

        sessions[session_id] = {
            "created_at": datetime.now().isoformat(),
            "default_date": latest_date,
            "default_market": "ALL",
            "history": [],
        }
        print(f"[API] Created session: {session_id}")

    return session_id


def resolve_parquet_paths(date: str, market: str) -> List[str]:
    """Resolve parquet paths for a date and market."""
    resolver = path_resolver or PathResolver(DATA_ROOT)
    return resolver.resolve(date, market)


def normalize_request_date(date_value: Optional[str]) -> Optional[str]:
    """Normalize UI date values to YYYYMMDD."""
    if not date_value:
        return None
    normalized = re.sub(r"\D", "", str(date_value))
    return normalized[:8] if len(normalized) >= 8 else None


def normalize_request_market(market_value: Optional[str]) -> str:
    """Normalize UI market values to the supported HK/US universe."""
    market = (market_value or "ALL").upper()
    return market if market in {"HK", "US", "ALL"} else "ALL"


def infer_explicit_market(message: str) -> Optional[str]:
    """Return a market only when the user explicitly mentions one."""
    text = message.lower()
    if (
        " hk" in f" {text} "
        or "hong kong" in text
        or any(name in text for name in ["tencent", "alibaba"])
    ):
        return "HK"
    if any(
        token in text for token in [" us ", "usa", "u.s.", "nasdaq", "nyse", "tesla", "apple", "nvidia", "microsoft", "amazon"]
    ):
        return "US"
    if "all" in text:
        return "ALL"
    return None


def extract_explicit_absolute_date(message: str) -> Optional[str]:
    """Extract explicit calendar dates."""
    numeric_match = re.search(r"(\d{4})[-/]?(\d{1,2})[-/]?(\d{1,2})", message)
    if numeric_match:
        year, month, day = numeric_match.groups()
        return f"{year}{int(month):02d}{int(day):02d}"

    return None


def apply_ui_defaults_to_plan(plan: Dict[str, Any], message: str, default_date: str, default_market: str) -> Dict[str, Any]:
    """
    Keep sidebar defaults authoritative unless the user explicitly asks for another market/date.

    This protects the deterministic data query from LLM prompt drift.
    """
    explicit_market = infer_explicit_market(message)
    plan["market"] = explicit_market or default_market

    explicit_date = extract_explicit_absolute_date(message)
    if not plan.get("date_range"):
        plan["date"] = explicit_date or default_date

    return plan


def generate_commentary(query: str, plan: Dict, result_count: int, summary: Dict) -> str:
    """Generate a short English commentary for the query result."""
    global llm_client

    if not llm_client:
        return f"Query complete. Returned {result_count} rows."

    try:
        prompt = f"""User question: {query}

Query plan:
{plan}

Result summary:
- Rows returned: {result_count}
- Statistics: {summary}

Write a concise professional interpretation in English, 2-3 sentences.
Translate any stock names that appear in the result context into English.
Only use facts present in the summary/result metadata; do not invent numbers."""

        response = llm_client.chat(
            prompt=prompt,
            temperature=1,
            max_tokens=500,
        )
        return response.strip()
    except Exception as e:
        print(f"[API] Commentary generation failed: {e}")
        return f"Query complete. Returned {result_count} rows."


class ChatRequest(BaseModel):
    """Chat request."""
    message: str = Field(..., description="User question in natural language", min_length=1)
    session_id: Optional[str] = Field(None, description="Session ID; omitted creates a new session")
    debug: bool = Field(False, description="Whether to return debug information")
    default_date: Optional[str] = Field(None, description="Default trading date, YYYYMMDD")
    default_market: Optional[str] = Field(None, description="Default market: HK/US/ALL")


class ChatResponse(BaseModel):
    """Chat response."""
    session_id: str = Field(..., description="Session ID")
    table: Optional[List[Dict[str, Any]]] = Field(None, description="Result table")
    summary: Optional[Dict[str, Any]] = Field(None, description="Result summary")
    commentary: str = Field(..., description="LLM-generated commentary")
    field_explanations: Optional[Dict[str, str]] = Field(
        None, description="Optional field explanations"
    )
    debug: Optional[Dict[str, Any]] = Field(None, description="Debug information")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    llm_status: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle a chat request."""
    global planner, compiler

    try:
        session_id = get_or_create_session(request.session_id)
        session_state = sessions[session_id]
        requested_date = normalize_request_date(request.default_date)
        requested_market = normalize_request_market(request.default_market)

        if requested_date:
            session_state["default_date"] = requested_date
        session_state["default_market"] = requested_market

        print(f"[API] [{session_id[:8]}] Message: {request.message}")

        print("[API] Generating query plan...")
        plan, validation_errors = planner.generate_plan(
            user_query=request.message,
            default_date=session_state["default_date"],
            default_market=session_state["default_market"],
            context={"recent_queries": session_state["history"][-3:]} if session_state["history"] else None,
        )
        plan = apply_ui_defaults_to_plan(
            plan,
            request.message,
            session_state["default_date"],
            session_state["default_market"],
        )
        validation_errors = planner._validate_plan(plan)

        if validation_errors:
            print(f"[API] Plan validation warnings: {validation_errors}")

        if not plan.get("query_type"):
            if plan.get("aggregations"):
                plan["query_type"] = "stats"
            else:
                plan["query_type"] = "basic"

        if plan.get("query_type") in ["chat", "invalid"]:
            answer = plan.get(
                "answer",
                "Sorry, I did not understand the question. Try asking about HK/US stock data, "
                "such as 'Which US stocks fell the most today?' or 'Show Tesla in January 2025'."
            )

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

        if plan.get("query_type") == "stats" and plan.get("aggregations") and not plan.get("group_by"):
            plan["select_fields"] = []

        parquet_paths = resolve_parquet_paths(
            plan.get("date", session_state["default_date"]),
            plan.get("market", "ALL")
        )

        if not parquet_paths:
            raise HTTPException(status_code=404, detail="No matching data files found")

        print("[API] Compiling SQL...")
        sql = compiler.compile(plan, parquet_paths)

        print("[API] Executing query...")
        conn = duckdb.connect(":memory:")
        df = conn.execute(sql).fetchdf()
        conn.close()

        relevant_columns = set()

        relevant_columns.add("Market")
        relevant_columns.add("SecurityID")
        relevant_columns.add("Symbol")

        for field in plan.get("select_fields", []):
            relevant_columns.add(field)

        for metric in plan.get("metrics", []):
            relevant_columns.add(metric)

        for order in plan.get("order_by", []):
            relevant_columns.add(order.get("field", ""))

        for agg in plan.get("aggregations", []):
            relevant_columns.add(agg.get("alias", ""))

        available_columns = [col for col in df.columns if col in relevant_columns]
        if available_columns:
            df_filtered = df[available_columns]
        else:
            df_filtered = df

        if "SecurityID" in df_filtered.columns and "Symbol" in df_filtered.columns:
            df_filtered = df_filtered.copy()
            df_filtered["Symbol"] = df_filtered.apply(
                lambda row: english_stock_name(row.get("SecurityID"), row.get("Symbol")),
                axis=1,
            )
        table_data = df_filtered.to_dict(orient='records')
        summary = {
            "row_count": len(df_filtered),
            "column_count": len(df_filtered.columns),
        }

        for col in df_filtered.select_dtypes(include=['float64', 'int64']).columns[:3]:
            if col not in ["SecurityID"]:
                summary[f"{col}_mean"] = round(df_filtered[col].mean(), 2) if not df_filtered[col].isna().all() else None

        field_explanations = None

        commentary = generate_commentary(
            request.message,
            plan,
            len(df),
            summary
        )

        session_state["history"].append({
            "user": request.message,
            "assistant": commentary,
            "timestamp": datetime.now().isoformat(),
        })

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

        print(f"[API] Query complete, returned {len(table_data)} rows")
        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Request handling failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    global llm_client

    llm_status = "unknown"
    if llm_client:
        try:
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
    """Root endpoint."""
    return {
        "name": "Market Assistant API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.on_event("startup")
async def startup_event():
    """Initialize application dependencies on startup."""
    global llm_client, planner, compiler, path_resolver

    print("[API] Starting Market Assistant...")

    try:
        llm_client = LLMClient()
        print(f"[API] LLM client initialized: {llm_client.model}")
    except Exception as e:
        print(f"[API] LLM client initialization failed: {e}")
        llm_client = None

    planner = LLMQueryPlanner(llm_client)
    print("[API] Query planner initialized")

    compiler = SQLCompilerEnhanced()
    print("[API] SQL compiler initialized")

    path_resolver = PathResolver(DATA_ROOT)
    latest_date = path_resolver.latest_available_date("ALL")
    print(f"[API] Path resolver initialized, latest available trading date: {latest_date or 'unknown'}")

    print("[API] Service startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    print("[API] Shutting down Market Assistant...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
