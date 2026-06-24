# pgvector News Research Agent

A self-hosted RAG (Retrieval-Augmented Generation) pipeline that embeds crypto news posts into a vector database, exposes a semantic search chatbot API, and publishes weekly AI-generated analysis articles to an Astro website.

Built on a VPS alongside an existing n8n setup.

---

## What it does

- Pulls markdown blog posts from a private GitHub repo every 6 hours
- Embeds them using `text-embedding-3-small` via OpenRouter
- Stores embeddings + sentiment + metadata in a self-hosted pgvector database
- Exposes a FastAPI endpoint (`/ask`) that answers questions grounded in your posts
- Publishes a weekly analysis article every Thursday to `src/content/analysis/`
- Powers a `/search` chatbot page on the Astro frontend

---

## Architecture Overview

```
GitHub Repo (markdown posts)
GitHub Repo (markdown posts)
        ↓ every 6 hours (ingest.py)
   text-embedding-3-small (OpenRouter)
        ↓
   pgvector (PostgreSQL + vector extension, Docker)
        ↓ on query (api.py)
   DeepSeek v4 Flash (OpenRouter)
        ↓
   FastAPI → https://your-website-api.com/ask
        ↓
   Astro /search page (chatbot)

   analyst.py (every Thursday 10am)
        ↓
   src/content/analysis/ (GitHub)
        ↓
   Astro blog page (weekly analysis carousel)
```

---

## Stack

| Component | Technology |
|---|---|
| Vector DB | pgvector (PostgreSQL 16, Docker) |
| Embeddings | `openai/text-embedding-3-small` via OpenRouter |
| Analysis & Chat | `deepseek/deepseek-v4-flash` via OpenRouter |
| API | FastAPI + Uvicorn (systemd service) |
| Reverse proxy | Caddy (Docker) |
| Runtime | Python 3.12, venv |
| Frontend | Astro, Cloudflare Pages |

---

## Prerequisites

- Ubuntu/Debian VPS
- Docker + an existing Docker network named `app-network`
- Caddy running in Docker on `app-network`
- Python 3.12
- OpenRouter account + API key
- GitHub Personal Access Token — read-only (for ingestion) and write access (for publishing analysis)
- Cloudflare managing your domain DNS

## Cost estimate

| Item | Cost |
|---|---|
| Embeddings (`text-embedding-3-small`) | ~$0.09/year |
| DeepSeek v4 Flash (analysis + chat) | <$1/month at this scale |
| pgvector (self-hosted) | Free |
| Caddy, FastAPI, systemd | Free |

---

## File structure

```
~/services/pgvector/
├── docker-compose.yml   # pgvector container
├── .env                 # all secrets
├── ingest.py            # GitHub → embed → store
├── search.py            # CLI semantic search tester
├── analyst.py           # weekly analysis generator + GitHub publisher
├── leaderboard.py       # entity leaderboard (disabled, kept for reference)
├── api.py               # FastAPI chatbot endpoint
├── ingest.log
├── analyst.log
└── venv/
```

---

## Step 1 — Fix Python environment

```bash
sudo apt install python3.12-venv python3-pip -y
```

---

## Step 2 — Create the pgvector container

```bash
mkdir ~/services/pgvector
nano ~/services/pgvector/docker-compose.yml
```

```yaml
services:
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: pgvector
    restart: unless-stopped
    environment:
      POSTGRES_USER: pgvector
      POSTGRES_PASSWORD: yourpassword
      POSTGRES_DB: newsresearch
    volumes:
      - pgvector_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    networks:
      - app-network

volumes:
  pgvector_data:

networks:
  app-network:
    external: true
```

```bash
docker compose -f ~/services/pgvector/docker-compose.yml up -d
```

---

## Step 3 — Create the database schema

```bash
docker exec -it pgvector psql -U pgvector -d newsresearch
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    category TEXT,
    published_at TIMESTAMPTZ,
    embedding vector(1536),
    sentiment TEXT,
    entities TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON posts USING ivfflat (embedding vector_cosine_ops);
```

```
\q
```

> The ivfflat warning on an empty table is harmless — ignore it.

---

## Step 4 — Python environment and dependencies

```bash
cd ~/services/pgvector
python3 -m venv venv
source venv/bin/activate
pip install openai pgvector psycopg2-binary PyGithub python-dotenv fastapi uvicorn
```

> If you get an `externally-managed-environment` error, make sure you activated the venv first with `source venv/bin/activate` before running pip.

---

## Step 5 — Create .env

```bash
nano ~/services/pgvector/.env
```

```env
OPENAI_API_KEY=your_openrouter_key
GITHUB_TOKEN=your_github_read_pat
GITHUB_WRITE_TOKEN=your_github_write_pat
DB_HOST=localhost
DB_PORT=5433
DB_NAME=newsresearch
DB_USER=pgvector
DB_PASSWORD=yourpassword
```

**GitHub tokens:**
- `GITHUB_TOKEN` — fine-grained PAT, read-only Contents access
- `GITHUB_WRITE_TOKEN` — classic PAT with `repo` scope (needed to push analysis files to private repo)

> Never paste tokens in chat or commit `.env` to GitHub.

---

## Step 6 — ingest.py

Pulls markdown files from GitHub, embeds them, stores in pgvector. Skips already-ingested posts.

```bash
nano ~/services/pgvector/ingest.py
```

Copy the code inside [this file](ingest.py) to your `ingest.py` file.

Run it:
```bash
python ingest.py
```

---

## Step 7 — search.py (CLI tester)

A test script. It searches in your vectorized database for similar results.

```bash
nano ~/services/pgvector/search.py
```

Copy the code inside [this file](search.py) to your `search.py` file.

Run it:
```bash
python search.py
```

---

## Step 8 — analyst.py (weekly analysis generator)

Analyzes the past week's news in ingest.py to create a relatively fact-based analysis report.

```bash
nano ~/services/pgvector/analyst.py
```

Copy the code inside [this file](analyst.py) to your `analyst.py` file.

Run it:
```bash
python analyst.py
```

---

## Step 9 — api.py (FastAPI chatbot endpoint)

An API edn-point you can curl from elsewhere.

```bash
nano ~/services/pgvector/api.py
```

Copy the code inside [this file](api.py) to your `api.py` file.

Run it:
```bash
python api.py
```

---

## Step 10 — Systemd service

```bash
nano /etc/systemd/system/pgvector-api.service
```

```ini
[Unit]
Description=pgvector News Chatbot API
After=network.target

[Service]
User=root
WorkingDirectory=/root/services/pgvector
ExecStart=/root/services/pgvector/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable pgvector-api
systemctl start pgvector-api
```

---

## Step 11 — Cron jobs

```bash
crontab -e
```

```bash
# Daily ingestion at 2am
0 2 * * * /root/services/pgvector/venv/bin/python /root/services/pgvector/ingest.py >> /root/services/pgvector/ingest.log 2>&1

# Weekly analysis every Monday at 3am
0 3 * * 1 /root/services/pgvector/venv/bin/python /root/services/pgvector/analyst.py >> /root/services/pgvector/analyst.log 2>&1
```

---

## Step 12 — Caddy reverse proxy

Add to your existing `Caddyfile`:
```
api.your-website.com {
    reverse_proxy host.docker.internal:8000
}
```

Add to your Caddy `docker-compose.yml` inside the `caddy` service:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Reload:
```bash
docker compose up -d --force-recreate
docker exec $(docker ps -qf "name=caddy") caddy reload --config /etc/caddy/Caddyfile
```

Add DNS A record in Cloudflare:
- Name: `api`
- Value: your VPS IP
- Proxy: DNS only (grey cloud)

---

## Step 13 — Frontend

Create a page that makes a `POST` to `https://api.your-website.com/ask`:

```javascript
const response = await fetch("https://api.your-website/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: userInput })
});
const data = await response.json();
// data.answer is a markdown string with **bold citations**
```

---

## Troubleshooting

**Caddy can't reach the API (`connection refused`):**
Make sure `host.docker.internal:host-gateway` is in your Caddy docker-compose and you're using `host.docker.internal:8000` in the Caddyfile, not `localhost`.

**ivfflat index warning on empty table:**
Harmless. Resolves automatically once posts are ingested.

**`externally-managed-environment` pip error:**
You ran pip outside the venv. Run `source venv/bin/activate` first.

**PyGithub deprecation warning:**
Use `Github(auth=Auth.Token(...))` instead of `Github(token)`.

**API returns empty answer:**
DeepSeek occasionally returns null responses. The `analyze_post` function handles this gracefully with a try/except fallback.

**DNS not resolving after adding Cloudflare record:**
Wait 1-2 minutes for propagation, then test again.