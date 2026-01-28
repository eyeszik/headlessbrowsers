# CLAUDE.md - Project Documentation for Claude Code

## Project Overview

This repository has two co-located components:

1. **Headless Browsers Catalog** (original) — A curated list of headless web browsers and browser automation tools, maintained in `README.md`. Community-resource, table-formatted, no code.

2. **Content Automation Platform** (added) — A production-grade, multi-agent social media automation platform. Full Python backend (FastAPI + SQLModel + Celery), Docker infrastructure, AI integrations, and orchestration framework. 64 files across `backend/`, `deploy/`, `tests/`, and supporting scripts.

When an AI assistant receives a task, determine which component is in scope before proceeding. Editing `README.md` to add a headless browser entry is unrelated to changes in `backend/`.

---

## Repository Information

- **Type**: Hybrid — curated list + production platform
- **Primary list file**: `README.md` (headless browsers)
- **Platform entry point**: `backend/app/main.py` (FastAPI app)
- **Owner**: dhamaniasad
- **License**: See LICENSE file
- **Python version**: 3.11
- **Platform version**: 1.0.0

---

## Headless Browsers Catalog

The `README.md` organizes browsers into 9 categories (Browser Engines, Multi Drivers, PhantomJS Drivers, Chromium Drivers, Webkit Drivers, Other Drivers, Fake Browser Engine, Runs in a Browser, Misc Tools). Each entry has four columns: Name, About, Supported Languages, License. Entries marked `[[Unmaintained]]` are no longer actively developed.

**Contributing to the catalog:**
- Keep entries alphabetically sorted within each category
- Include all four columns for new entries
- Verify links resolve before adding
- Mark unmaintained projects with `[[Unmaintained]]`

---

## Content Automation Platform — File Structure

```
headlessbrowsers/
├── README.md                              # Headless browsers catalog
├── CLAUDE.md                              # This file
├── LICENSE
├── .env.example                           # All required env vars with placeholders
├── requirements.txt                       # 75 pinned Python dependencies
├── Dockerfile / Dockerfile.prod           # Dev and production container images
├── docker-compose.yml                     # Dev: postgres, redis, backend, worker
├── docker-compose.prod.yml                # Prod: traefik, 3x backend, 2x worker, monitoring
│
├── backend/
│   ├── alembic.ini                        # Alembic migration config
│   ├── migrations/                        # Alembic migration scripts
│   │   ├── env.py
│   │   └── script.py.mako
│   └── app/
│       ├── main.py                        # FastAPI app, lifespan, CORS, router mount
│       ├── core/
│       │   └── config.py                  # Pydantic Settings (all env vars, DB URLs)
│       ├── db/
│       │   └── session.py                 # SQLAlchemy engine + SessionLocal factory
│       ├── models/
│       │   └── models.py                  # 9 SQLModel tables + 3 enums
│       ├── crud/
│       │   └── crud.py                    # Generic CRUD operations for each model
│       ├── api/
│       │   └── v1/
│       │       ├── __init__.py            # Router aggregation (all 6 sub-routers)
│       │       ├── content.py             # Content CRUD + publish + variants
│       │       ├── campaigns.py           # Campaign CRUD
│       │       ├── social_accounts.py     # Social account management
│       │       ├── templates.py           # Template CRUD + render
│       │       ├── analytics.py           # Analytics fetch + aggregate
│       │       └── media.py               # Media upload (S3) + list
│       ├── services/
│       │   ├── orchestrator.py            # Multi-agent orchestration (570 LOC)
│       │   ├── state_verifier.py          # Merkle-tree state checkpointing (400 LOC)
│       │   ├── scheduler.py               # DAG scheduler with topological sort (480 LOC)
│       │   ├── template_engine.py         # Jinja2 rendering with platform overrides
│       │   ├── content_formatter.py       # Platform-specific content formatting
│       │   ├── analytics_service.py       # Cross-platform analytics aggregation
│       │   ├── media_manager.py           # S3 upload, resize, dedup via SHA-256
│       │   ├── integrations/
│       │   │   ├── base.py                # BasePlatformIntegration (retry, rate limit)
│       │   │   ├── youtube.py             # YouTube Data API v3
│       │   │   ├── twitter.py             # Twitter API v2
│       │   │   ├── facebook.py            # Facebook Graph API
│       │   │   ├── instagram.py           # Instagram Graph API
│       │   │   └── linkedin.py            # LinkedIn API v2
│       │   └── ai/
│       │       └── ai_service.py          # OpenAI + Anthropic, guardrails, assumptions
│       ├── adapters/
│       │   ├── langchain_adapter.py       # LangChain tool-augmented agent adapter
│       │   └── crewai_adapter.py          # CrewAI 5-agent hierarchical crew
│       └── worker/
│           ├── celery_app.py              # Celery config + beat schedule
│           └── tasks.py                   # 4 scheduled tasks (see below)
│
├── deploy/
│   ├── scripts/deploy.sh                  # Production deployment script
│   └── monitoring/
│       ├── prometheus.yml                 # Prometheus scrape config
│       └── loki.yml                       # Loki log aggregation config
│
├── tests/
│   ├── unit/                              # Unit tests (pytest)
│   └── integration/                       # Integration tests
│
├── demo_automation.py                     # Standalone runnable demo (see below)
├── automation_report_*.json               # Generated report from demo run
│
├── PLATFORM_ARCHITECTURE.md               # Detailed architecture diagrams + guardrails
├── PRODUCTION_DEPLOYMENT_GUIDE.md         # Step-by-step production deployment
├── AGIM_X_ENHANCED_ORCHESTRATOR.md        # Advanced orchestration framework spec
├── AUTOMATION_CATALOG.md                  # Catalog of 25+ available automations
├── AUTOMATION_DEMONSTRATION_SUMMARY.md    # Results of demonstration run
└── README_PLATFORM.md                     # Platform-specific README
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Web Framework | FastAPI | 0.109.0 |
| ORM | SQLModel (SQLAlchemy) | 0.0.14 |
| Database | PostgreSQL | 16 |
| Cache / Broker | Redis | 7 |
| Task Queue | Celery | 5.3.6 |
| AI Providers | OpenAI SDK, Anthropic SDK | 1.10.0 / 0.18.0 |
| Agent Frameworks | LangChain, CrewAI | 0.1.0 / 0.1.0 |
| Template Engine | Jinja2 | 3.1.3 |
| Reverse Proxy | Traefik | v2.11 |
| Monitoring | Prometheus, Loki | — |
| Media Storage | AWS S3 (boto3) | 1.34.34 |
| HTTP Client | aiohttp | 3.9.3 |
| Testing | pytest, pytest-asyncio, httpx | 7.4.4 |
| Linting | black, flake8, mypy | 24.1.1 / 7.0.0 / 1.8.0 |

---

## Database Models (`backend/app/models/models.py`)

9 SQLModel tables. Key enums: `PlatformType` (YOUTUBE, TWITTER, FACEBOOK, INSTAGRAM, LINKEDIN), `ContentStatus` (DRAFT → SCHEDULED → PUBLISHING → PUBLISHED / FAILED / ARCHIVED), `TaskStatus` (PENDING → RUNNING → SUCCESS / FAILED / RETRYING / ROLLED_BACK).

| Model | Purpose | Key Fields |
|-------|---------|------------|
| SocialAccount | Platform OAuth credentials | platform, access_token, refresh_token, token_expires_at, rate_limit_per_hour |
| MediaAsset | S3-stored files | filename, file_type, s3_key, s3_url, content_hash (SHA-256) |
| ContentTemplate | Jinja2 templates | template_text, template_variables, platform_overrides (JSON) |
| Campaign | Content campaign container | name, start_date, end_date, status, target_platforms (JSON) |
| Content | Individual content items | title, body, media_ids, scheduled_for, status, depends_on (JSON array for DAG) |
| ContentVariant | Platform-specific versions | platform, optimized_content, platform_specific_data |
| ContentAnalytics | Performance metrics | views, likes, shares, comments, engagement_rate, reach |
| TaskState | DAG task tracking | task_id, status, dependencies (JSON), retry_count, state_data |
| AssumptionLog | AI decision transparency | assumption_text, confidence_level, reasoning, impact_assessment |

Relationships: SocialAccount 1→N Content, Campaign 1→N Content, Content 1→N ContentVariant, Content 1→N ContentAnalytics.

---

## API Endpoints (prefix: `/api/v1`)

| Router File | Key Endpoints |
|-------------|---------------|
| `content.py` | POST/GET/PUT/DELETE `/content`, POST `/content/{id}/publish`, POST `/content/{id}/variants` |
| `campaigns.py` | CRUD `/campaigns`, POST `/campaigns/{id}/publish-all` |
| `social_accounts.py` | CRUD `/social-accounts`, POST `/social-accounts/{id}/validate` |
| `templates.py` | CRUD `/templates`, POST `/templates/{id}/render` |
| `analytics.py` | GET `/analytics/content/{id}`, GET `/analytics/campaign/{id}`, POST `/analytics/aggregate` |
| `media.py` | POST `/media/upload`, GET `/media/{id}`, DELETE `/media/{id}` |

OpenAPI docs auto-generated at `http://localhost:8000/api/v1/openapi.json`.

---

## Background Tasks (Celery)

Defined in `backend/app/worker/tasks.py`. Scheduled via beat in `celery_app.py`.

| Task | Schedule | Purpose |
|------|----------|---------|
| `process_scheduled_posts` | Every 60s | Checks for content with `scheduled_for <= now`, triggers publish |
| `fetch_analytics_batch` | Every 1h | Polls all platforms for engagement metrics |
| `cleanup_old_data` | Daily 2:00 AM | Purges archived content older than retention period |
| `backup_database` | Daily 3:00 AM | Runs pg_dump to S3 |

Base class `DatabaseTask` handles session lifecycle (open on access, close after task).

---

## Core Service Patterns

### Integration Base Class (`services/integrations/base.py`)

All 5 platform integrations inherit from `BasePlatformIntegration`:
- `execute_with_retry(func)` — exponential backoff with delays `[2, 4, 8]` seconds
- `validate_payload_integrity(payload)` — SHA-256 hash verification before every API call
- Rate-limit awareness per platform

### Multi-Agent Orchestrator (`services/orchestrator.py`)

4 agent roles: COORDINATOR, WORKER, VALIDATOR, ADVERSARIAL.

`AgentPayload` is the inter-agent message format. Every payload carries:
- `payload_hash_sha256` for tamper detection
- `confidence_score` (0.0–1.0)
- `reasoning_trace` and `assumptions_made` for audit
- `alternatives_considered`

Circuit breaker wraps external calls (CLOSED → OPEN after threshold failures → HALF_OPEN for probe).

Adversarial validation: if `disagreement_score > 0.3`, the payload is flagged `requires_human_review = True`.

### State Verifier (`services/state_verifier.py`)

Creates `StateCheckpoint` with:
- SHA-256 state hash
- Merkle tree root (O(log n) single-item verification)
- TTL (default 300s) — stale checkpoints trigger forced refresh
- Predecessor hash for checkpoint chaining

### DAG Scheduler (`services/scheduler.py`)

Kahn's algorithm topological sort. Returns levels (tasks within a level execute in parallel). Detects circular dependencies. Supports per-task retry with exponential backoff and full state rollback on failure.

### AI Service (`services/ai/ai_service.py`)

Dual-provider: OpenAI (GPT-4) and Anthropic (Claude). For every generation:
1. Logs assumptions with confidence scores
2. Detects hallucination keywords (`guarantee`, `proven fact`, `scientifically proven`)
3. Enforces platform character limits and hashtag counts
4. Returns confidence score, guardrails triggered, assumption log

Platform constraints enforced:
| Platform | Max Chars | Max Hashtags | Tone |
|----------|-----------|--------------|------|
| Twitter | 280 | 2 | Concise |
| Facebook | 63206 | 5 | Conversational |
| Instagram | 2200 | 30 | Inspiring |
| LinkedIn | 3000 | 3 | Professional |
| YouTube | 5000 | 15 | Descriptive |

### Framework Adapters

- **LangChain** (`adapters/langchain_adapter.py`): Tool-augmented agents with memory and state checkpointing. Wraps content generation, publishing, and analytics as LangChain tools.
- **CrewAI** (`adapters/crewai_adapter.py`): 5 specialized agents (Strategist, Creator, Validator, Adversarial, Analyst) in a hierarchical crew process.

---

## 5 Advanced Guardrails

These are system-wide protections enforced across all services. Every guardrail has three components: detection signal, threshold, and mitigation.

| # | Guardrail | Detection | Threshold | Mitigation |
|---|-----------|-----------|-----------|------------|
| 1 | Sycophancy Prevention | Agent agreement rate > 0.7 without independent validation | disagreement < 0.3 → flag human review | Mandatory adversarial review |
| 2 | State Desynchronization | Cached state age > TTL | state_age > 300s | Force refresh + Merkle verify |
| 3 | Hallucinated Dependencies | dependency_id not in registry | Unregistered dep found | Reject task |
| 4 | Confidence Collapse | Chained confidence < 0.5 or chain depth > 3 | accumulated < 0.5 | Halt chain, circuit break |
| 5 | Tool Phantom Success | API call without response validation | Missing success indicator | Raise error, require schema check |

---

## Development Workflow

### Initial Setup

```bash
# Clone and enter
cd headlessbrowsers

# Virtual environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env — fill in API keys for any platforms you'll test

# Start backing services
docker-compose up -d postgres redis

# Migrate database
cd backend && alembic upgrade head && cd ..

# Start API server (terminal 1)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (terminal 2)
celery -A backend.app.worker.celery_app worker --loglevel=info

# Start Celery beat scheduler (terminal 3)
celery -A backend.app.worker.celery_app beat --loglevel=info
```

### Running Tests

```bash
pytest                                    # All tests
pytest tests/unit/                        # Unit only
pytest --cov=backend/app --cov-report=html  # With coverage report
```

### Code Quality

```bash
black backend/app                         # Format
flake8 backend/app --max-line-length=100  # Lint
mypy backend/app                          # Type check
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"  # Generate
alembic upgrade head                               # Apply
alembic downgrade -1                               # Rollback one
```

### Docker

```bash
docker-compose up --build                          # Dev (rebuild)
docker-compose -f docker-compose.prod.yml up -d    # Production HA
docker-compose logs -f backend                     # Tail logs
```

### Running the Demo

```bash
python3 demo_automation.py
# Generates platform variants, runs adversarial review,
# creates state checkpoint, outputs automation_report_*.json
```

---

## Conventions

**Naming**: files `snake_case.py`, classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_CASE`, private `_leading_underscore`, tables plural (`socialaccount`).

**Imports**: stdlib → third-party → local. Type hints on all function signatures.

**Async**: `async/await` throughout API and service layers. Celery tasks are sync (Celery manages its own event loop).

**Logging**: `logger = logging.getLogger(__name__)` in every module. Include structured context in log calls.

**Secrets**: Never in code. All credentials via `.env` loaded through `backend/app/core/config.py` Settings class. Never commit `.env`.

**Error handling**: Validate at API boundaries. Internal services may raise typed exceptions. HTTP responses use standard format:
```json
{"success": true/false, "data": {...}, "error": {"code": "...", "message": "..."}}
```

**New platform integration**: Subclass `BasePlatformIntegration` in `services/integrations/`, add `PlatformType` enum value, add env vars to `config.py` and `.env.example`, add constraints to `content_formatter.py`.

**New scheduled task**: Add function to `worker/tasks.py` with `@celery_app.task` decorator, register in `celery_app.py` `beat_schedule`.

---

## Production Deployment

Production compose (`docker-compose.prod.yml`) runs:
- Traefik reverse proxy with Let's Encrypt SSL
- PostgreSQL with persistence
- Redis with AOF persistence
- 3 backend replicas (1 CPU / 2 GB each, 2 uvicorn workers)
- Celery worker + beat scheduler
- Prometheus + Loki for metrics and logs

See `PRODUCTION_DEPLOYMENT_GUIDE.md` for step-by-step setup including secrets management, domain configuration, and monitoring dashboards.

---

## Key Documentation Files

| File | What it covers |
|------|----------------|
| `PLATFORM_ARCHITECTURE.md` | Agent topology, inter-agent protocol, guardrail implementations |
| `PRODUCTION_DEPLOYMENT_GUIDE.md` | Server prep, Docker, TLS, monitoring, troubleshooting |
| `AGIM_X_ENHANCED_ORCHESTRATOR.md` | Advanced orchestration framework, 7-stage pipeline, governance gates |
| `AUTOMATION_CATALOG.md` | 25+ automation workflows organized by category |
| `AUTOMATION_DEMONSTRATION_SUMMARY.md` | Full results of the demo automation run |
| `demo_automation.py` | Self-contained runnable demonstration script |

---

## What NOT to Do

- Do not edit `README.md` when the task is about the platform code (and vice versa)
- Do not hardcode API keys, tokens, or secrets anywhere in source
- Do not skip adversarial validation on high-confidence content (threshold is 0.3 disagreement)
- Do not ignore confidence collapse signals (< 0.5 halts the chain)
- Do not assume state is current — check checkpoint TTL (300s)
- Do not bypass retry logic on platform integrations — rate limits are real
- Do not commit `.env`, `*.log`, or `automation_report_*.json` files
