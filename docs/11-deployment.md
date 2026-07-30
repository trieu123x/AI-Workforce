# 11 - HƯỚNG DẪN ĐÓNG GÓI & TRIỂN KHAI HẠ TẦNG (DEPLOYMENT GUIDE)

## 11.1 Kiến Trúc Đóng Gói Docker Compose (Container Stack)

Hệ thống được đóng gói hoàn chỉnh thành các Docker Container giúp dễ dàng triển khai trên môi trường Local Development cũng như Cloud Infrastructure (AWS EC2 / DigitalOcean App Platform).

```yaml
version: '3.8'

services:
  # 1. Frontend Next.js Workspace
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend-api

  # 2. FastAPI Gateway & LangGraph Core
  backend-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:SecretPass123@postgres:5432/ai_workforce_db
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  # 3. Celery Async Task Worker (OCR, RAG, File Export)
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.worker worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:SecretPass123@postgres:5432/ai_workforce_db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres

  # 4. PostgreSQL 16 DB với pgvector Extension
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=SecretPass123
      - POSTGRES_DB=ai_workforce_db
    volumes:
      - pgdata:/var/lib/postgresql/data

  # 5. Redis Server cho Session Memory & Pub/Sub
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

## 11.2 Biến Môi Trường Cần Thiết (.env.example)

```env
# Server Config
PORT=8000
ENVIRONMENT=production
JWT_SECRET=super_secret_jwt_key_ai_workforce_2026

# Database & Cache
DATABASE_URL=postgresql+asyncpg://postgres:SecretPass123@localhost:5432/ai_workforce_db
REDIS_URL=redis://localhost:6379/0

# LLM & AI Models Providers
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
BGE_M3_MODEL_PATH=BAAI/bge-m3
RERANKER_MODEL_PATH=BAAI/bge-reranker-v2-m3

# Storage Config
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```
