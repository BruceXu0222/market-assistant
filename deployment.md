# 智能行情分析助手 - 部署指南

## 环境要求

- Python 3.9+
- 依赖包：见 `requirements.txt`

```bash
pip install -r requirements.txt
```

## 配置

编辑 `core/configs/settings.yaml` 配置 LLM API：

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "your-api-key"
  model: "gpt-5.2"
```

## 启动服务

### 方式一：分步启动

**1. 启动 FastAPI 后端（终端 1）**

```bash
cd /Users/brucexu/Desktop/UCLA/Career/华泰/market-assistant
python -m uvicorn app.api:app --host 0.0.0.0 --port 8080
```

**2. 启动 Streamlit 前端（终端 2）**

```bash
cd /Users/brucexu/Desktop/UCLA/Career/华泰/market-assistant
streamlit run app/ui_streamlit.py --server.port 8501
```

### 方式二：后台启动

```bash
# 后台启动 API 服务
nohup python -m uvicorn app.api:app --host 0.0.0.0 --port 8080 > api.log 2>&1 &
echo $! > api.pid

# 后台启动 Streamlit
nohup streamlit run app/ui_streamlit.py --server.port 8501 > streamlit.log 2>&1 &
echo $! > streamlit.pid
```

## 关闭服务

### 方式一：前台进程

直接在终端按 `Ctrl+C` 即可停止。

### 方式二：后台进程

```bash
# 关闭 API 服务
kill $(cat api.pid) 2>/dev/null && rm api.pid

# 关闭 Streamlit 服务
kill $(cat streamlit.pid) 2>/dev/null && rm streamlit.pid
```

或者通过端口查找进程：

```bash
# 查找并关闭 8080 端口（API）
lsof -ti:8080 | xargs kill -9

# 查找并关闭 8501 端口（Streamlit）
lsof -ti:8501 | xargs kill -9
```

## 验证服务状态

```bash
# 检查 API 健康状态
curl http://localhost:8080/health

# 预期返回
# {"status":"healthy","timestamp":"...","version":"2.0.0","llm_status":"healthy"}
```

## 访问地址

| 服务 | 地址 |
|------|------|
| API 文档 | http://localhost:8080/docs |
| API 健康检查 | http://localhost:8080/health |
| Streamlit UI | http://localhost:8501 |

## 常见问题

### 1. API 连接失败

确保后端服务已启动，检查端口是否被占用：

```bash
lsof -i:8080
```

### 2. LLM 调用失败

检查 `settings.yaml` 中的 API Key 是否正确，确保网络可访问 OpenAI API。

### 3. 数据文件未找到

确保 `data/` 目录下有对应日期的 Parquet 文件，或使用 `data/test.parquet` 进行测试。
