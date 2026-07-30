"""
AI Workforce — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.router import api_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai_workforce")


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown events
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI Workforce backend starting up...")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   Database    : {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    logger.info(f"   Debug mode  : {settings.APP_DEBUG}")
    try:
        import app.models.models  # Register all models on Base.metadata
        from app.models.models import Base
        from app.core.database import sync_engine
        from sqlalchemy import text
        Base.metadata.create_all(bind=sync_engine)

        migrations = [
            "ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS allowed_actions JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS disallowed_actions JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE ai_agents ADD COLUMN IF NOT EXISTS knowledge_access JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS document_id VARCHAR(100);",
            "ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS collection_name VARCHAR(100) DEFAULT 'General Knowledge';",
            "ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'MEDIUM';",
            "ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;",
            "ALTER TABLE workflow_approvals ADD COLUMN IF NOT EXISTS comments TEXT;",
            "ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS title VARCHAR(255) DEFAULT 'Workflow Execution';",
            "ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS dag_plan JSONB;",
            "ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255);",
            "ALTER TABLE agent_workflows ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS tool_name VARCHAR(100) DEFAULT 'general';",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS input_parameters JSONB;",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(50) DEFAULT 'ALL';",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;",
            "ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_department;",
            "ALTER TABLE llm_cost_logs ADD COLUMN IF NOT EXISTS user_id UUID;",
            "ALTER TABLE llm_cost_logs ADD COLUMN IF NOT EXISTS department VARCHAR(50);",
            "ALTER TABLE llm_cost_logs ADD COLUMN IF NOT EXISTS cached_prompt_tokens INTEGER NOT NULL DEFAULT 0;",
            "ALTER TABLE llm_cost_logs ADD COLUMN IF NOT EXISTS usage_source VARCHAR(30) NOT NULL DEFAULT 'LEGACY_ESTIMATE';",
            "ALTER TABLE llm_cost_logs ADD COLUMN IF NOT EXISTS pricing_version VARCHAR(30) NOT NULL DEFAULT 'legacy';",
            "ALTER TABLE llm_cost_logs ALTER COLUMN estimated_cost_usd TYPE NUMERIC(18, 9);",
            "ALTER TABLE llm_cost_logs ALTER COLUMN usage_source SET DEFAULT 'PROVIDER';",
            "ALTER TABLE llm_cost_logs ALTER COLUMN pricing_version SET DEFAULT '2026-07-31';",
            "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_prompt_tokens;",
            "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_prompt_tokens CHECK (prompt_tokens >= 0);",
            "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_completion_tokens;",
            "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_completion_tokens CHECK (completion_tokens >= 0);",
            "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_cached_tokens;",
            "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_cached_tokens CHECK (cached_prompt_tokens >= 0 AND cached_prompt_tokens <= prompt_tokens);",
            "ALTER TABLE llm_cost_logs DROP CONSTRAINT IF EXISTS ck_llm_cost_usage_source;",
            "ALTER TABLE llm_cost_logs ADD CONSTRAINT ck_llm_cost_usage_source CHECK (usage_source IN ('PROVIDER', 'MANUAL_IMPORT', 'LEGACY_ESTIMATE'));",
            "CREATE INDEX IF NOT EXISTS idx_llm_cost_tenant_created ON llm_cost_logs (tenant_id, created_at);",
        ]
        for statement in migrations:
            try:
                with sync_engine.begin() as conn:
                    conn.execute(text(statement))
            except Exception as stmt_err:
                logger.warning(f"Startup migration skipped statement: {stmt_err}")

        logger.info("✅ Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"⚠️ Error initializing database tables: {e}")
    yield
    logger.info("🛑 AI Workforce backend shutting down...")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Workforce — Enterprise Multi-Agent Platform",
    description=(
        "Backend API for AI Workforce: a platform with autonomous AI Employees "
        "(HR, Legal, IT, Finance, Sales, Knowledge, CEO) that orchestrate real enterprise workflows."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "AI Workforce Backend",
            "version": "1.0.0",
            "environment": settings.APP_ENV,
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )
