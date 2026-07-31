# AI Service architecture

## Service boundary

`apps/ai-service` owns stateless AI computation:

- semantic document cleaning and chunking;
- embedding providers and model lifecycle;
- dense/keyword fusion and reranking;
- prompt loading and LLM provider routing;
- agent definitions, state and routing;
- AI guardrails, memory contracts and evaluation helpers.

`backend` remains the system of record and owns:

- authentication, tenants and department/role ACL;
- PostgreSQL/pgvector persistence and lifecycle transactions;
- audit and cost records;
- notifications, approvals and business tool execution;
- filtering authorized chunks before sending candidates to AI service.

The AI service must not receive database credentials and must not decide tenant access.

## Runtime flow

```text
Frontend
   |
   v
Backend :8000 -- tenant/ACL/database/audit
   |
   | internal HTTP + X-AI-Service-Key
   v
AI Service :8100 -- chunk/embed/rerank/agent/LLM
```

## Rerank pipeline

```text
Authorized hybrid candidates (max 30)
   -> remove empty/duplicate chunks
   -> build metadata-aware document text
   -> Qwen3-Reranker-0.6B CrossEncoder (batch + sigmoid)
   -> 90% model score + 10% retrieval prior
   -> model score threshold
   -> top-k + model/latency/fallback metadata
```

The model is loaded lazily and inference is serialized per service process to keep
CPU/GPU memory predictable. A lexical provider is used only when explicitly
configured or when Qwen inference fails and fallback is enabled.

The development Compose profile reserves one NVIDIA GPU for the AI service and
loads both embedding and reranking models in FP16. `GET /health/accelerator`
reports the CUDA runtime and selected device so deployment checks can reject a
container that accidentally installed CPU-only PyTorch.

When `AI_SERVICE_URL` is empty, backend uses the existing in-process implementation
for local development and tests. Docker Compose sets it to `http://ai-service:8100`,
so deployed containers use the separated process.

## Failure policy

Production does not silently fall back after an AI service request fails. The request
raises an internal AI service error so an unavailable model cannot produce a different
embedding space or inconsistent retrieval result. Existing indexed content remains in
PostgreSQL and is not deleted until a replacement batch is ready.

## Security

- Configure the same `AI_SERVICE_INTERNAL_TOKEN` for backend and AI service.
- Pass AI settings through an explicit allowlist; never load `backend/.env` into the
  AI container because it also contains database and application secrets.
- Do not expose port 8100 publicly in production; use the internal container network.
- Backend applies ACL and governance filters before any candidate content leaves it.
- Tool mutations stay in backend and continue to use RBAC, approval and audit layers.
