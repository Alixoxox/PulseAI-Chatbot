# CryptoBot 🤖

A LangChain-powered cryptocurrency assistant chatbot with FastAPI, Groq AI, MongoDB, and Upstash Redis.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Groq (llama-4-scout-17b-16e-instruct) via LangChain |
| Backend | FastAPI |
| Database | MongoDB (Motor async driver) |
| Cache | Upstash Redis (HTTP) |
| Deployment | Render (Docker, free tier) |

## Features

- 🔧 **Tool Calling** — 4 LangChain tools: coin info, market data, trending list, risk score
- 💬 **Streaming** — SSE-based real-time response streaming
- 🧠 **Memory** — Per-session conversation history (last 20 messages)
- ⚡ **Caching** — Redis caching with 5-minute TTL
- 🚀 **Eager Loading** — MongoDB, Redis, and LLM fully warmed up on startup

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env file and fill in your credentials
cp .env.example .env

# 3. Run locally
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key |
| `GROQ_MODEL` | Model name (default: `llama-4-scout-17b-16e-instruct`) |
| `MONGODB_URI` | MongoDB connection string |
| `MONGODB_DB` | Database name (default: `cryptodb`) |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token |

## Deploy to Render

1. Push to GitHub
2. Connect repo in Render dashboard
3. Set environment variables in Render
4. Deploy — uses `render.yaml` blueprint

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message, get full response |
| POST | `/api/chat/stream` | Send message, get SSE stream |
| GET | `/health` | Health check |
