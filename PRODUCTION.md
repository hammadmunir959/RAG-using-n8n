# Document Intelligence - Production Guide

## Quick Start (Development)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Production Deployment

### Option 1: Docker Compose (Recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env with your API keys
nano .env

# 3. Build and run
docker-compose up -d --build

# 4. Access the app
# Frontend: http://localhost
# Backend API: http://localhost:8000
# n8n: http://localhost:5678
```

### Option 2: Manual Production Setup

#### Backend (with Gunicorn)

```bash
cd backend
pip install gunicorn

# Run with 4 workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

#### Frontend (Static Build)

```bash
cd frontend
npm run build

# Serve with nginx or any static file server
# Copy dist/ contents to your web server
```

## Production Checklist

### Security
- [ ] Change all default passwords in `.env`
- [ ] Use HTTPS (add SSL certificates to nginx)
- [ ] Enable firewall, only expose ports 80/443
- [ ] Set secure CORS origins in `main.py`
- [ ] Use secrets manager for API keys (not .env files)

### Performance
- [ ] Enable gzip compression (done in nginx.conf)
- [ ] Set up CDN for static assets
- [ ] Configure PostgreSQL for large-scale deployments
- [ ] Add Redis for caching (optional)

### Monitoring
- [ ] Set up health check monitoring
- [ ] Configure log aggregation (ELK, Datadog, etc.)
- [ ] Set up error tracking (Sentry)
- [ ] Monitor API rate limits

### Scaling
- [ ] Use PostgreSQL instead of SQLite
- [ ] Add Redis for session/cache
- [ ] Use Kubernetes for orchestration
- [ ] Configure horizontal pod autoscaling

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq AI API key for LLM |
| `SCRAPER_ANT_API_KEY` | No | ScrapingAnt key for web search |
| `LLM_MODEL` | No | Groq model (default: llama-3.3-70b-versatile) |
| `N8N_BASE_URL` | No | n8n server URL |
| `N8N_UPLOAD_WEBHOOK_ID` | No | n8n upload workflow webhook |
| `N8N_CHAT_WEBHOOK_PATH` | No | n8n chat workflow path |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (Port 80/443)                       │
│  - Static files (React build)                                │
│  - API proxy to backend                                      │
│  - SSL termination                                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (Port 8000)                  │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   n8n Primary   │  │ LangGraph       │                   │
│  │   Workflows     │  │ Fallback        │                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │                    │                             │
│           ▼                    ▼                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │     n8n         │  │   ChromaDB      │                   │
│  │   (Port 5678)   │  │   (Vectors)     │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                │                             │
│                                ▼                             │
│                       ┌─────────────────┐                   │
│                       │   Groq LLM      │                   │
│                       │   (Cloud API)   │                   │
│                       └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## SSL/HTTPS Setup

Add to `docker-compose.yml`:

```yaml
frontend:
  ports:
    - "443:443"
  volumes:
    - ./certs:/etc/nginx/certs:ro
```

Update `nginx.conf`:

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;
    # ... rest of config
}
```
