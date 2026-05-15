# Market Intelligence Assistant

A FastAPI and Streamlit assistant for querying HK and US daily stock data stored in per-stock parquet files. The system uses an LLM to create a constrained QueryPlan, DuckDB to perform deterministic computation, and Streamlit to display tables, charts, and commentary.

## Stack

- FastAPI for the backend API
- Streamlit for the demo UI
- DuckDB and Parquet for local analytics
- LangGraph for workflow orchestration experiments
- OpenAI-compatible chat completions for planning and narration

## Data Layout

```text
data/
  hk/    # HK daily history, one parquet file per stock
  us/    # US daily history, one parquet file per stock
```

Supported markets are `HK`, `US`, and `ALL`. Supported user questions are expected to be in English.

## Query Flow

1. The user asks a market question in Streamlit or through `POST /chat`.
2. The planner converts the English question into a JSON QueryPlan.
3. The path resolver selects HK, US, or both parquet scan patterns.
4. The SQL compiler normalizes raw parquet columns and generates DuckDB SQL.
5. DuckDB executes the query.
6. The API converts stock display names to English where possible, returns a table, and the UI renders a chart when the result is chartable.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
python -m uvicorn app.api:app --port 8080
```

Start the UI:

```bash
streamlit run app/ui_streamlit.py --server.port 8501
```

## Example Questions

- Which HK stocks had the highest turnover today?
- Show the 10 biggest US stock decliners today
- Which stocks have turnover rate above 5% today?
- Show Tesla's price trend in January 2025

## Notes

The LLM does not perform numeric calculations. It only plans and narrates; all numbers are computed by DuckDB.
