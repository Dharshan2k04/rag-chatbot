# Industry-Standard Deployment Guide

## Executive Summary

Cloudflare **Pages** is excellent for your React frontend — arguably superior to Vercel for global CDN performance. However, Cloudflare alone cannot host your FastAPI backend (Python + SQLite + FAISS). Below are three deployment tiers from hobbyist to production-grade.

---

## Architecture Constraint

Your backend requires:
1. **Python runtime** (FastAPI)
2. **Persistent disk** (SQLite DB, FAISS indices)
3. **Long-running process** (background PDF ingestion, SSE streaming)

This rules out pure serverless/edge platforms (Cloudflare Workers, AWS Lambda, Vercel Functions) unless you re-architect significantly.

---

## Deployment Tiers

### Tier 1: Hobbyist / Demo (Current Plan)

| Layer | Service | Cost |
|-------|---------|------|
| Frontend | **Vercel** or **Cloudflare Pages** | Free |
| Backend | **HuggingFace Spaces** (Docker) | Free |
| Database | SQLite (ephemeral) | Free |
| Vector Store | FAISS (local disk) | Free |

**Verdict:** Fine for demos. **Not industry-standard** because:
- HF Spaces sleeps after inactivity (cold starts ~10-30s)
- SQLite data lost on container restart
- No horizontal scaling

---

### Tier 2: Indie / Small Product (Recommended)

| Layer | Service | Why |
|-------|---------|-----|
| Frontend | **Cloudflare Pages** | Global CDN, instant propagation, generous free tier |
| Backend | **Render** (Docker) or **Railway** | Persistent disk, native Docker, auto-HTTPS, sleeps on free tier |
| Database | **Neon** (PostgreSQL) or **Supabase** | Serverless Postgres, connection pooling, branching |
| Vector Store | **Pinecone** (free tier) or **pgvector** (in Postgres) | Managed vector search, no disk dependency |
| LLM | **Groq** (already using) | Keep as-is |

**Cloudflare Pages + Render/Railway** is the sweet spot for industry-standard without AWS complexity.

---

### Tier 3: Production / Enterprise

| Layer | Service | Why |
|-------|---------|-----|
| Frontend | **Cloudflare Pages** or **AWS S3 + CloudFront** | Edge caching, DDoS protection |
| Backend | **Google Cloud Run** or **AWS ECS Fargate** | Auto-scaling containers, pay-per-use |
| Database | **AWS RDS** or **Google Cloud SQL** (PostgreSQL) | Managed backups, monitoring, HA |
| Vector Store | **Pinecone**, **Weaviate Cloud**, or **Qdrant Cloud** | Managed vector DB with hybrid search |
| Secrets | **AWS Secrets Manager** or **Doppler** | Rotation, audit logs |
| Monitoring | **Datadog** or **Grafana Cloud** | APM, metrics, alerting |
| CI/CD | **GitHub Actions** → deploy to prod | Automated testing, staged rollouts |

---

## Why Cloudflare Pages for Frontend?

| Feature | Cloudflare Pages | Vercel |
|---------|------------------|--------|
| Global CDN | 300+ PoPs (fastest) | 100+ PoPs |
| Build speed | Fast | Fast |
| Custom domains | Free SSL | Free SSL |
| Functions | Yes (JS/TS only) | Yes (JS/TS/Go) |
| Analytics | Built-in | Built-in |
| **Bandwidth** | **Unlimited free** | 100GB/mo free |

**Cloudflare Pages wins on edge network density and bandwidth limits.**

---

## Recommended Migration Path

### Step 1: Frontend → Cloudflare Pages (Immediate)

1. Push `frontend/` to GitHub
2. Connect repo at [dash.cloudflare.com](https://dash.cloudflare.com) → Pages
3. Build settings:
   - Build command: `npm run build`
   - Build output: `build/`
4. Add environment variable: `REACT_APP_API_URL=https://<your-backend>.onrender.com`
5. Deploy → instant global CDN

### Step 2: Backend → Render (Week 1)

1. Create `render.yaml` or use Web UI
2. Choose **Docker** environment
3. Mount persistent disk (`/opt/render/project/src/data/` and `/opt/render/project/src/vector_store/`)
4. Add secrets: `GROQ_API_KEY`, `SECRET_KEY`, `DATABASE_URL`
5. Set `ENVIRONMENT=production`

```yaml
# render.yaml (optional IaC)
services:
  - type: web
    name: rag-chatbot-api
    runtime: docker
    plan: standard
    disk:
      name: data
      mountPath: /opt/render/project/src/data
      sizeGB: 2
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: DATABASE_URL
        value: sqlite:///./data/chats.db
      - key: SECRET_KEY
        generateValue: true
```

### Step 3: SQLite → PostgreSQL (Week 2)

```bash
# Sign up for Neon (neon.tech) — free tier: 500MB
# Get connection string:
DATABASE_URL="postgresql://user:pass@neon-host/db?sslmode=require"
```

Update `backend/app/config.py`:
```python
database_url: str = os.getenv("DATABASE_URL", "sqlite:///./chats.db")
```

No code changes needed — SQLAlchemy supports both.

### Step 4: FAISS → pgvector or Pinecone (Week 3)

**Option A: pgvector** (keeps everything in Postgres)
- Enable `pgvector` extension in Neon/Supabase
- Replace FAISS with SQL queries on `vector` columns
- Good for <100k chunks

**Option B: Pinecone** (managed vector DB)
- Sign up at [pinecone.io](https://pinecone.io)
- Free tier: 1 pod, ~100k vectors
- Replace `embedding_store.search()` with Pinecone SDK calls

---

## Cloudflare-Only Stack (If You Insist)

If you want to minimize vendors and use Cloudflare end-to-end:

| Component | Cloudflare Service | Limitation |
|-----------|-------------------|------------|
| Frontend | **Pages** | None |
| API Gateway | **Workers** (JS/TS) | Must proxy to external Python backend |
| Auth | **Workers KV** or **D1** | Stateless JWT validation only |
| Documents | **R2** (S3-compatible) | Good for PDF storage |
| LLM | **Workers AI** | Limited models; you'd drop Groq |

**Reality check:** You still need a Python host for FastAPI + FAISS/Sentence-Transformers. Cloudflare Workers doesn't run Python containers.

---

## My Opinion

**For your project, the best industry-standard setup is:**

> **Cloudflare Pages** (frontend) + **Render** or **Railway** (backend Docker) + **Neon** (PostgreSQL) + **Pinecone** (vector DB)

**Why not HF Spaces + Vercel for production?**
- HF Spaces cold starts kill UX
- SQLite on ephemeral storage is data-loss risk
- Vercel's 100GB bandwidth vs Cloudflare's unlimited matters at scale

**Why not AWS/GCP immediately?**
- Overkill for a solo project; $50-200/mo minimum
- Render/Railway gives 90% of the value at 10% of the complexity

**Migration order:**
1. Frontend to Cloudflare Pages (zero risk, immediate)
2. Backend to Render with persistent disk (moderate effort)
3. SQLite → Neon Postgres (low risk, better durability)
4. FAISS → Pinecone (only if you hit scaling limits)

---

## Security Checklist for Production

- [ ] `SECRET_KEY` generated with `openssl rand -hex 32`
- [ ] `ENVIRONMENT=production` (enables stricter validation)
- [ ] CORS `FRONTEND_URL` locked to your Cloudflare Pages domain only
- [ ] Database credentials in platform secrets (not `.env` in repo)
- [ ] HTTPS enforced (all platforms do this by default)
- [ ] Sentry DSN added for error tracking
- [ ] Rate limiting already implemented (slowapi)
- [ ] Document upload validation already implemented

---

## Estimated Monthly Costs

| Tier | Frontend | Backend | Database | Vector DB | Total |
|------|----------|---------|----------|-----------|-------|
| Hobby | Cloudflare Pages Free | Render Free / HF Spaces Free | SQLite | FAISS local | **$0** |
| Indie | Cloudflare Pages Free | Render Starter ($7) | Neon Free | Pinecone Free | **$7** |
| Pro | Cloudflare Pro ($20) | Render Standard ($25) | Neon Pro ($19) | Pinecone Std ($70) | **$134** |
| Enterprise | Custom | GCP/AWS ($200+) | RDS/Cloud SQL ($100+) | Pinecone Enterprise | **$500+** |

---

## Next Steps

1. **Today**: Move frontend to Cloudflare Pages (takes 5 minutes)
2. **This week**: Deploy backend to Render with persistent disk
3. **Update `FRONTEND_URL` in backend env** to your Cloudflare Pages domain
4. **Test end-to-end**: Register → Upload PDF → Chat → Streaming works
5. **Monitor**: Check Render logs, verify FAISS indices persist across deploys
