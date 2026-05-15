# Deployment Guide

## Requirements

- Python 3.10 or newer
- Dependencies from `requirements.txt`
- HK and US parquet files under `data/hk` and `data/us`
- An OpenAI-compatible API key or local compatible service

## Configure

Create `.env` from `.env.example` or configure `core/configs/settings.yaml` if you use that file locally.

## Start Services

Backend:

```bash
python -m uvicorn app.api:app --port 8080
```

Frontend:

```bash
streamlit run app/ui_streamlit.py --server.port 8501
```

## Stop Services

For foreground processes, press `Ctrl+C` in each terminal. For background processes, stop the stored process IDs or find the processes by port:

```bash
lsof -ti :8080
lsof -ti :8501
```

## Health Check

```bash
curl http://localhost:8080/health
```

Expected response shape:

```json
{"status":"healthy","version":"2.0.0"}
```

## URLs

| Service | URL |
| --- | --- |
| Streamlit UI | http://localhost:8501 |
| API docs | http://localhost:8080/docs |
| API health | http://localhost:8080/health |

## Troubleshooting

If the UI cannot connect, make sure the backend is running on port 8080. If LLM calls fail, verify the API key, model name, and network access. If data files are missing, confirm that `data/hk` and `data/us` contain parquet files.
