---
title: RAG Chatbot API
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# RAG Chatbot API

Production-ready FastAPI backend for a multi-user RAG (Retrieval-Augmented Generation) document intelligence chatbot. Features JWT authentication, per-user data isolation, PDF ingestion with background processing, FAISS vector search, Groq LLM streaming via SSE, and comprehensive security controls.

## Features

- **JWT Authentication**: Register, login, token refresh, account lockout after 5 failed attempts, rate limiting
- **Strict User Isolation**: All chats, messages, documents, and FAISS embeddings are scoped per `user_id`
- **PDF Ingestion**: MIME validation, magic bytes check, filename sanitization, size limit (10MB), background processing
- **RAG Pipeline**: Sentence-Transformers (`all-MiniLM-L6-v2`) for 384-dim embeddings, FAISS per-user indices, top-k retrieval
- **LLM Streaming**: Groq API with `llama-3.1-8b-instant`, real SSE token streaming
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **Structured JSON Logging** and optional Sentry error monitoring
- **CORS**: Locked to configured frontend origin only
- **FastAPI Background Tasks**: PDF ingestion runs async after upload for instant UX
- **Comprehensive Tests**: Pytest backend tests with mocked RAGAS evaluation

## Tech Stack

- FastAPI + Uvicorn
- SQLAlchemy + SQLite (production: PostgreSQL compatible)
- FAISS + Sentence-Transformers
- Groq API (Llama 3.1-8B-Instant)
- python-jose + bcrypt
- slowapi (rate limiting)

## Environment Variables

Create a `.env` file in `backend/` or export variables in your deployment environment:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes (prod) | `your-super-secret-key-change-in-production` | JWT signing key |
| `GROQ_API_KEY` | Yes (prod) | `""` | Groq API key for LLM inference |
| `DATABASE_URL` | No | `sqlite:///./chats.db` | SQLAlchemy DB URL |
| `FRONTEND_URL` | No | `http://localhost:3000` | Allowed CORS origin |
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `SENTRY_DSN` | Recommended (prod) | `""` | Sentry error tracking DSN |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### HuggingFace Spaces Secrets

When deploying to HF Spaces, add these in **Settings > Secrets**:
- `SECRET_KEY` — strong random string (e.g., `openssl rand -hex 32`)
- `GROQ_API_KEY` — from [Groq Console](https://console.groq.com/keys)
- `SENTRY_DSN` — optional, from Sentry project settings

## Local Setup

```bash
cd backend

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file (see table above)
# Or export directly:
export SECRET_KEY="super-secret-key"
export GROQ_API_KEY="gsk_..."

# 4. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

API docs are auto-generated at:
- Swagger UI: `http://localhost:7860/docs`
- ReDoc: `http://localhost:7860/redoc`

## Running Tests

```bash
cd backend
pytest tests/ -v
```

- **14 backend tests** cover auth, chat isolation, upload validation, and RAG retrieval
- **RAGAS tests** are skipped if `GROQ_API_KEY` is not set (run with the key for full evaluation)

## Deployment

### HuggingFace Spaces (Backend)

1. Push the `backend/` folder to a new HF Space with SDK = Docker
2. Add secrets: `SECRET_KEY`, `GROQ_API_KEY`, `SENTRY_DSN`
3. Space will auto-build from the provided `Dockerfile`
4. API will be available at `https://<username>-<space-name>.hf.space`

### Vercel (Frontend)

Set the environment variable in Vercel:
- `REACT_APP_API_URL` = `https://<your-hf-space>.hf.space`

## Security & Compliance Mapping

### NIST Cybersecurity Framework (CSF 2.0)

| Function | Control | Implementation |
|----------|---------|----------------|
| **Identify** | Asset Management | Per-user SQLite rows, per-user FAISS directories |
| **Protect** | Access Control | JWT bearer tokens, bcrypt password hashing, `get_current_user` dependency on all routes |
| **Protect** | Data Security | PDF validation (MIME, magic bytes, size), filename sanitization, path traversal prevention |
| **Protect** | Protective Technology | Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), locked CORS |
| **Detect** | Anomalies & Events | Structured JSON logging with timestamp, level, module, request_id |
| **Respond** | Response Planning | Sentry integration for error tracking and alerting |
| **Recover** | Recovery Planning | FAISS indices persisted to disk per user; SQLite backups |

### ISO 27001:2022 Annex A

| Annex A Control | Implementation |
|-----------------|----------------|
| A.5.1 Policies for information security | Security headers, CORS policy, input validation |
| A.5.7 Threat intelligence | Structured logging, Sentry monitoring |
| A.5.18 Access control | JWT authentication, account lockout, rate limiting |
| A.5.20 Authentication information | bcrypt hashing, token expiry (24h access / 7d refresh) |
| A.5.23 Cloud services | HF Spaces deployment with secrets management |
| A.5.24 Planning & preparation for information security continuity | Persistent FAISS + SQLite storage |
| A.8.1 User endpoint devices | Frontend dark mode, auth context, protected routes |
| A.8.2 Privileged access rights | Strict user_id scoping on all DB queries |
| A.8.4 Removal of assets | Document deletion cascades, chat deletion with ownership check |
| A.8.12 Data leakage prevention | No user data exposed across isolation boundaries |
| A.8.14 Information transfer | PDF upload validation, sanitized filenames |

## API Endpoints Overview

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | Get access + refresh tokens |
| POST | `/auth/refresh` | No | Refresh access token |
| GET | `/auth/me` | Yes | Current user info |
| POST | `/chat/new` | Yes | Create chat session |
| GET | `/chat/` | Yes | List user's chats |
| POST | `/chat/{id}` | Yes | Send message (non-streaming) |
| POST | `/chat/{id}/stream` | Yes | Send message (SSE streaming) |
| GET | `/chat/{id}/messages` | Yes | Get chat history |
| DELETE | `/chat/{id}` | Yes | Delete chat |
| POST | `/upload` | Yes | Upload PDF (background ingestion) |
| GET | `/documents` | Yes | List user's uploaded documents |
| GET | `/health` | No | Health check |

## What You Need to Do

1. **Get a Groq API Key**
   - Sign up at [console.groq.com](https://console.groq.com/)
   - Create an API key and save it

2. **Set Environment Variables**
   - Local: create `backend/.env` with `GROQ_API_KEY` and `SECRET_KEY`
   - HF Spaces: add `GROQ_API_KEY`, `SECRET_KEY`, and `SENTRY_DSN` to Space Secrets
   - Vercel: add `REACT_APP_API_URL` pointing to your HF Space URL

3. **Generate a Strong SECRET_KEY**
   ```bash
   openssl rand -hex 32
   ```

4. **Deploy Backend to HuggingFace Spaces**
   - New Space → Docker SDK → upload `backend/` contents
   - Verify `/health` endpoint returns `{"status": "healthy"}`

5. **Deploy Frontend to Vercel**
   - Import the `frontend/` folder from GitHub
   - Set `REACT_APP_API_URL=https://<your-hf-space>.hf.space`
   - Build and deploy

6. **(Optional) Set Up Sentry**
   - Create a Sentry project, copy the DSN, add it to secrets

7. **(Optional) Switch to PostgreSQL**
   - Change `DATABASE_URL` to `postgresql://user:pass@host/db` for production scale

## Architecture Diagram

```
┌──────────────┐      JWT Bearer       ┌──────────────┐
│   React UI   │ ────────────────────> │  FastAPI     │
│  (Vercel)    │   SSE streaming <───── │  (HF Spaces) │
└──────────────┘                       └──────┬───────┘
                                              │
                     ┌──────────┐   ┌────────┴────────┐
                     │ SQLite   │   │  FAISS Index    │
                     │ (users,  │   │  per user       │
                     │  chats)  │   │  (vector_store) │
                     └──────────┘   └─────────────────┘
                                              │
                                        Groq API
                                     (Llama 3.1-8B)
```

## License

MIT