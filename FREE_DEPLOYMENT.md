# 100% Free Deployment Guide

## The Honest Truth

"Industry-standard + completely free" requires compromise. Here's what's actually possible at $0/month, ranked by quality.

---

## Option 1: "Pragmatic Free" — Best Balance (Recommended)

**Cost: $0/month | Cold starts: Yes | Persistence: Partial**

| Layer | Service | Why |
|-------|---------|-----|
| Frontend | **Cloudflare Pages** | Unlimited bandwidth, 300+ edge locations, $0 |
| Backend | **HuggingFace Spaces** (Docker) | Free container, persistent-ish storage |
| Database | **SQLite** (on HF Spaces disk) | Survives container restarts, backups recommended |
| Vector DB | **FAISS** (on HF Spaces disk) | Same as above |
| LLM | **Groq** | Free tier: check your dashboard for credits |

### HuggingFace Spaces Persistence Reality

HF Spaces **does** persist files in the container volume between restarts:
- `chats.db` survives restarts ✓
- `vector_store/` survives restarts ✓
- **BUT**: If Space crashes or rebuilds, data may reset

**Mitigation**: Add a startup check in `main.py`:

```python
# In app/main.py, add to startup:
import shutil

@app.on_event("startup")
async def backup_check():
    """Backup DB and FAISS to /tmp for extra safety"""
    if os.path.exists("chats.db"):
        shutil.copy2("chats.db", "/tmp/chats.db.backup")
```

### Groq Free Tier Limits

- Sign up at [console.groq.com](https://console.groq.com)
- Free tier: typically ~$5-10 in credits/month
- Monitor usage in dashboard
- **Fallback**: If credits run out, return "LLM service temporarily unavailable"

---

## Option 2: "Zero Cold Starts" — Best UX for Free

**Cost: $0/month | Cold starts: No | Setup: More complex**

| Layer | Service | Why |
|-------|---------|-----|
| Frontend | **Cloudflare Pages** | $0, unlimited bandwidth |
| Backend | **Oracle Cloud Free Tier** (ARM VM) | 24GB RAM, 4 cores, 200GB disk, **actually free forever** |
| Database | **PostgreSQL on same VM** | Full control, zero limits |
| Vector DB | **FAISS or pgvector** | Your choice |
| LLM | **Groq** | Same free tier |

### Oracle Cloud Free Tier Setup

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com) (requires credit card for verification, but **never charged**)
2. Create **Always Free** ARM instance (Ampere A1):
   - Shape: VM.Standard.A1.Flex
   - OCPUs: 4
   - Memory: 24GB
   - Boot volume: 200GB
3. SSH in, install Docker:
   ```bash
   sudo apt update && sudo apt install docker.io docker-compose -y
   sudo usermod -aG docker $USER
   ```
4. Clone your repo, build & run:
   ```bash
   cd ~/Rag\ Chatbot/backend
   docker build -t rag-backend .
   docker run -d -p 7860:7860 \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/vector_store:/app/vector_store \
     -e GROQ_API_KEY=your_key \
     -e SECRET_KEY=$(openssl rand -hex 32) \
     -e ENVIRONMENT=production \
     --restart unless-stopped \
     rag-backend
   ```
5. Open port 7860 in Oracle Security List (Ingress Rules)
6. Point Cloudflare Pages to `http://<oracle-ip>:7860`

**Pros**: Never sleeps, real persistent disk, 24GB RAM (more than Render's $25 plan)  
**Cons**: Oracle's UI is painful, occasional account reviews, need to manage VM yourself

---

## Option 3: "Serverless Free" — Modern Architecture

**Cost: $0/month | Cold starts: Minimal | Requires code changes**

| Layer | Service | Why |
|-------|---------|-----|
| Frontend | **Cloudflare Pages** | $0 |
| API | **Cloudflare Workers** (TypeScript) | JWT auth, routing, rate limiting |
| Database | **Supabase PostgreSQL** | 500MB free, pgvector extension |
| Vector Search | **Supabase pgvector** | Cosine similarity, 500MB limit |
| File Storage | **Cloudflare R2** | 10GB free, S3-compatible |
| LLM | **Groq** (from Workers) | Direct API calls |

### What You'd Need to Change

This requires **rewriting the backend** because Workers don't run Python containers:

```typescript
// workers/index.ts (new backend)
export default {
  async fetch(request: Request, env: Env) {
    // Auth via Supabase
    // Upload PDFs to R2
    // Call Groq API directly
    // Store embeddings in Supabase pgvector
  }
}
```

**Verdict**: Too much rewrite work. Only do this if you want to learn serverless.

---

## Option 4: "GitHub-Powered" — Minimal Vendors

**Cost: $0/month | Cold starts: Yes**

| Layer | Service |
|-------|---------|
| Frontend | **GitHub Pages** (static React build) |
| Backend | **GitHub Codespaces** (not for production, but interesting) |
| LLM | **GitHub Copilot Chat API** (limited) |

**Verdict**: Not suitable for production. Listed for completeness only.

---

## My Actual Recommendation for You

> **Use Option 1 (Cloudflare Pages + HuggingFace Spaces) for now.**

Here's why it's the smartest free choice:

1. **Zero migration work** — your code works as-is
2. **HF Spaces is genuinely free** — no credit card, no sleep-death (just cold starts)
3. **Cloudflare Pages is the best free CDN** — no bandwidth anxiety
4. **SQLite + FAISS persistence is adequate** — for a portfolio project, data loss risk is acceptable

### Upgrade Path When You Have Money

```
Phase 1 (Now, $0):     Cloudflare Pages + HF Spaces + SQLite + FAISS
Phase 2 ($7/mo):       Cloudflare Pages + Render + Neon + Pinecone
Phase 3 ($50/mo):      Cloudflare Pages + GCP Cloud Run + Cloud SQL + Pinecone
```

---

## Step-by-Step: Deploy for $0 Right Now

### 1. Frontend → Cloudflare Pages

```bash
cd frontend
npm run build
# This creates build/ folder
```

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Pages → "Create a project" → Connect GitHub
3. Select your repo
4. Build settings:
   - **Build command**: `cd frontend && npm install && npm run build`
   - **Build output directory**: `frontend/build`
5. Environment variable: `REACT_APP_API_URL=https://your-username-rag-chatbot-api.hf.space`
6. Save & Deploy

**Result**: `https://rag-chatbot.pages.dev` (free SSL, global CDN)

### 2. Backend → HuggingFace Spaces

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. New Space → Docker → Public or Private
3. Upload `backend/` contents (Dockerfile, app/, requirements.txt)
4. Go to **Settings → Secrets**:
   ```
   GROQ_API_KEY = your_groq_key
   SECRET_KEY = your_random_key
   ENVIRONMENT = production
   FRONTEND_URL = https://rag-chatbot.pages.dev
   ```
5. Space auto-builds and runs

### 3. Update CORS

In `backend/app/config.py`, update:
```python
frontend_url: str = "https://rag-chatbot.pages.dev"
```

Or add to HF Space secrets:
```
FRONTEND_URL = https://rag-chatbot.pages.dev
```

---

## Free Tier Limits You Should Know

| Service | Free Limit | What Happens When Exceeded |
|---------|-----------|---------------------------|
| Cloudflare Pages | Unlimited bandwidth | Nothing, stays free |
| HuggingFace Spaces | 2 vCPU, 16GB RAM, sleeps after inactivity | Cold start (~10-30s) |
| Groq API | ~$5-10 credits/month | Returns 429 error |
| SQLite | Single file, ~2GB max | Performance degrades |
| FAISS | Disk space on container | Search slows down |

---

## Monitoring Your Free Resources

### HuggingFace Spaces Uptime

Add a simple health ping to keep it warm:

```bash
# Add to your local crontab (Linux/Mac) or Task Scheduler (Windows)
# Every 10 minutes:
curl -s https://your-space.hf.space/health > /dev/null
```

Or use a free cron service like [UptimeRobot](https://uptimerobot.com) (free tier: 50 monitors, 5-min intervals).

### Groq API Usage

Check your Groq dashboard weekly. If approaching limits:
- Add caching for repeated questions
- Implement a "simple mode" that returns cached responses

---

## Security at $0

Your security features are **not compromised** by free hosting:

- ✅ JWT auth works the same
- ✅ bcrypt hashing works the same
- ✅ Rate limiting works the same
- ✅ PDF validation works the same
- ✅ Security headers work the same
- ✅ User isolation works the same

The only risk is **data persistence** on HF Spaces (mitigate with backups).

---

## Backup Strategy (Free)

Add to `backend/app/main.py`:

```python
import shutil
from datetime import datetime

@app.on_event("startup")
async def restore_from_backup():
    """Restore DB from backup if main file is missing/corrupt"""
    if not os.path.exists("chats.db") and os.path.exists("/tmp/chats.db.backup"):
        shutil.copy2("/tmp/chats.db.backup", "chats.db")
        print("✅ Restored database from backup")

# Add periodic backup (every hour via simple threading)
import threading

def backup_task():
    while True:
        if os.path.exists("chats.db"):
            shutil.copy2("chats.db", "/tmp/chats.db.backup")
        if os.path.exists("vector_store"):
            shutil.make_archive("/tmp/vector_store_backup", 'zip', "vector_store")
        threading.Event().wait(3600)  # Every hour

threading.Thread(target=backup_task, daemon=True).start()
```

---

## Summary

| Goal | Best Free Option | Trade-off |
|------|-----------------|-----------|
| Zero cost, zero code changes | **Cloudflare Pages + HF Spaces** | Cold starts on backend |
| Zero cold starts, still free | **Cloudflare Pages + Oracle Cloud VM** | Complex setup, Oracle UI pain |
| Modern serverless, free | **Cloudflare Pages + Workers + Supabase** | Rewrite backend to TypeScript |
| Maximum free RAM/disk | **Oracle Cloud Free Tier** | Manual VM management |

**My recommendation: Start with Option 1. It costs nothing, your code works today, and you can migrate to paid when you have users.**
