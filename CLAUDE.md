# CLAUDE.md - AI Assistant Guide for Content Automation Platform

## 📚 Repository Overview

### Dual Purpose Repository

This repository serves two distinct purposes:

1. **Original Purpose**: A curated list of headless web browsers (see README.md)
   - Comprehensive catalog of headless browser engines, drivers, and automation tools
   - Organized by engine type (Chromium, WebKit, PhantomJS, etc.)
   - Community-maintained resource for browser automation

2. **Content Automation Platform**: Enterprise-grade multi-agent content automation system
   - Built on top of the repository in subdirectories
   - Production-ready social media automation with AI integration
   - Advanced multi-agent orchestration with 5+ specialized agents
   - State verification and advanced guardrails

**Important**: When working on this repository, clarify with the user whether they're working on:
- The headless browsers list (README.md)
- The Content Automation Platform (backend/, frontend/, docs/)

---

## 🏗️ Project Structure

```
headlessbrowsers/
├── README.md                              # Original: Headless browsers list
├── CLAUDE.md                              # This file: AI assistant guide
├── requirements.txt                       # Python dependencies
│
├── backend/                               # Content Automation Platform backend
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py                  # Settings & environment variables
│   │   ├── models/
│   │   │   └── models.py                  # SQLModel database models (9 models)
│   │   ├── crud/
│   │   │   └── crud.py                    # Database CRUD operations
│   │   ├── api/
│   │   │   └── v1/                        # REST API endpoints
│   │   │       ├── content.py             # Content management
│   │   │       ├── campaigns.py           # Campaign operations
│   │   │       ├── social_accounts.py     # Social media account management
│   │   │       ├── templates.py           # Template management
│   │   │       ├── analytics.py           # Analytics endpoints
│   │   │       └── media.py               # Media upload/management
│   │   ├── services/
│   │   │   ├── orchestrator.py            # Multi-agent orchestration ⭐
│   │   │   ├── state_verifier.py          # Merkle tree state verification ⭐
│   │   │   ├── scheduler.py               # DAG-based task scheduler
│   │   │   ├── template_engine.py         # Jinja2 template rendering
│   │   │   ├── content_formatter.py       # Platform-specific formatting
│   │   │   ├── analytics_service.py       # Analytics aggregation
│   │   │   ├── media_manager.py           # S3 media management
│   │   │   ├── integrations/              # Platform integrations
│   │   │   │   ├── base.py                # Base integration class
│   │   │   │   ├── youtube.py             # YouTube Data API v3
│   │   │   │   ├── twitter.py             # Twitter API v2
│   │   │   │   ├── facebook.py            # Facebook Graph API
│   │   │   │   ├── instagram.py           # Instagram Graph API
│   │   │   │   └── linkedin.py            # LinkedIn API v2
│   │   │   └── ai/
│   │   │       └── ai_service.py          # OpenAI & Anthropic integration
│   │   ├── adapters/                      # Framework adapters ⭐
│   │   │   ├── langchain_adapter.py       # LangChain integration
│   │   │   └── crewai_adapter.py          # CrewAI multi-agent crews
│   │   ├── worker/
│   │   │   ├── celery_app.py              # Celery configuration
│   │   │   └── tasks.py                   # Background tasks (4 scheduled)
│   │   ├── db/
│   │   │   └── session.py                 # Database session management
│   │   └── main.py                        # FastAPI application entry
│   ├── migrations/                        # Alembic database migrations
│   └── scripts/                           # Utility scripts
│
├── frontend/                              # React frontend (placeholder)
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       └── utils/
│
├── deploy/                                # Deployment configuration
│   ├── docker/
│   ├── scripts/
│   └── monitoring/
│
├── tests/                                 # Test suite
│   ├── unit/
│   └── integration/
│
├── docs/                                  # Additional documentation
│
├── PLATFORM_ARCHITECTURE.md               # Detailed architecture (1000+ lines)
├── PRODUCTION_DEPLOYMENT_GUIDE.md         # Deployment guide (900+ lines)
├── AGIM_X_ENHANCED_ORCHESTRATOR.md        # Advanced orchestration framework
├── AUTOMATION_CATALOG.md                  # 25+ available automations
├── AUTOMATION_DEMONSTRATION_SUMMARY.md    # Demonstration results
├── demo_automation.py                     # Working automation demo
│
├── docker-compose.yml                     # Development Docker Compose
├── docker-compose.prod.yml                # Production HA Docker Compose (10 services)
├── .env.example                           # Environment variables template
└── .gitignore
```

---

## 🎯 Core Architecture Patterns

### 1. Multi-Agent Orchestration System

**Location**: `backend/app/services/orchestrator.py`

**Key Concepts**:
- **4 Agent Roles**: COORDINATOR, WORKER, VALIDATOR, ADVERSARIAL
- **Circuit Breaker Pattern**: Prevents cascade failures (CLOSED → OPEN → HALF_OPEN)
- **Confidence Propagation**: Decay factor = 0.9 ** chain_depth
- **Adversarial Validation**: 30% disagreement threshold triggers human review

**Agent Communication Protocol**:
```python
@dataclass
class AgentPayload:
    task_id: str
    agent_id: str
    timestamp: datetime
    payload_data: Dict[str, Any]
    payload_hash_sha256: str        # SHA-256 integrity validation
    confidence_score: float         # 0.0 - 1.0
    dependencies: List[str]
    outputs: Dict[str, Any]
    reasoning_trace: Optional[str]  # Decision audit trail
    assumptions_made: List[Dict]    # Logged assumptions
    alternatives_considered: List[str]
    metadata: Dict[str, Any]
```

**When to Use**:
- Complex workflows requiring coordination
- High-stakes decisions needing validation
- Workflows where assumptions must be challenged

### 2. State Verification System

**Location**: `backend/app/services/state_verifier.py`

**Key Concepts**:
- **Merkle Trees**: O(log n) verification performance
- **TTL Expiration**: Default 300 seconds (5 minutes)
- **Checkpoint Chaining**: Each checkpoint references predecessor
- **Corruption Detection**: SHA-256 hash comparison

**State Checkpoint Structure**:
```python
@dataclass
class StateCheckpoint:
    checkpoint_id: str
    state_hash: str                 # SHA-256 of entire state
    merkle_root: str                # Merkle tree root hash
    timestamp: datetime
    ttl_seconds: int = 300
    predecessor_hash: Optional[str] # For checkpoint chaining
```

**When to Use**:
- Before/after critical operations
- Multi-step workflows requiring rollback
- Distributed agent coordination
- State synchronization across services

### 3. Advanced Guardrail System

**5 Advanced Guardrails** (see PLATFORM_ARCHITECTURE.md for details):

1. **Sycophancy Prevention**
   - Detection: agent_agreement_rate > 0.7 without independent validation
   - Mitigation: Mandatory adversarial review
   - Threshold: disagreement_score < 0.3 → FLAG_HUMAN_REVIEW

2. **State Desynchronization Protection**
   - Detection: cached_state_age > TTL_SECONDS
   - Mitigation: Automatic expiration + Merkle verification
   - Threshold: state_age > 300s → FORCE_REFRESH

3. **Hallucinated Dependencies Prevention**
   - Detection: dependency_id NOT IN dependency_registry
   - Mitigation: Validate against source-of-truth
   - Threshold: unregistered_dep → REJECT_TASK

4. **Confidence Collapse Prevention**
   - Detection: chained_confidence < 0.5 OR chain_depth > 3
   - Mitigation: Propagate uncertainty bounds + circuit breaker
   - Threshold: accumulated_confidence < 0.5 → HALT_CHAIN

5. **Tool Call Phantom Success Prevention**
   - Detection: api_call_without_response_validation
   - Mitigation: Mandatory schema validation + explicit success check
   - Threshold: missing_success_indicator → RAISE_ERROR

### 4. DAG Task Scheduler

**Location**: `backend/app/services/scheduler.py`

**Key Concepts**:
- **Topological Sorting**: Kahn's algorithm for dependency resolution
- **Parallel Execution**: Tasks without dependencies run concurrently
- **Exponential Backoff**: Retry delays [2, 4, 8] seconds
- **Rollback Support**: Automatic state restoration on failure

**Task Dependency Graph**:
```python
# Example: Content publishing workflow
tasks = [
    Content(id=1, depends_on=[], parallelization_hint="CAN_PARALLELIZE"),
    Content(id=2, depends_on=[1], parallelization_hint="REQUIRED_SERIAL"),
    Content(id=3, depends_on=[1], parallelization_hint="CAN_PARALLELIZE"),
    Content(id=4, depends_on=[2, 3], parallelization_hint="REQUIRED_SERIAL")
]
# Result: [[1], [2, 3], [4]] - Three execution levels
```

### 5. Platform Integration Layer

**Location**: `backend/app/services/integrations/`

**Common Patterns**:
```python
class BasePlatformIntegration:
    async def execute_with_retry(self, func: Callable) -> Dict[str, Any]:
        """Execute with exponential backoff retry."""
        for attempt, delay in enumerate(self.retry_delays):
            try:
                return await func()
            except RateLimitError:
                await asyncio.sleep(delay)
        raise MaxRetriesExceeded()

    def validate_payload_integrity(self, payload: Dict) -> bool:
        """Verify SHA-256 hash."""
        computed_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return computed_hash == payload.get('hash')
```

**Platform-Specific Constraints**:
| Platform  | Max Length | Hashtag Limit | Rate Limit      |
|-----------|-----------|---------------|-----------------|
| Twitter   | 280       | 2             | 300/15min       |
| Facebook  | 63206     | 5             | 200/hour        |
| Instagram | 2200      | 30            | 200/hour        |
| LinkedIn  | 3000      | 3             | 100/day         |
| YouTube   | 5000      | 15            | 10000/day       |

---

## 🗄️ Database Models

**Location**: `backend/app/models/models.py`

### Core Models (9 total)

1. **SocialAccount**
   - Stores OAuth credentials for platforms
   - Fields: platform, account_identifier, access_token, refresh_token, expires_at
   - One-to-many: → Content, ContentAnalytics

2. **MediaAsset**
   - S3-stored media files (images, videos)
   - Fields: file_type, s3_key, s3_url, content_hash, metadata
   - Deduplication via SHA-256 content_hash

3. **ContentTemplate**
   - Jinja2 templates with variable substitution
   - Fields: template_text, template_variables, platform_overrides
   - Platform overrides: JSON dict with platform-specific versions

4. **Campaign**
   - Content campaign container
   - Fields: name, description, start_date, end_date, status, target_platforms
   - One-to-many: → Content

5. **Content**
   - Individual content items
   - Fields: title, body, media_ids, scheduled_for, status, depends_on
   - Status: DRAFT, SCHEDULED, PUBLISHED, FAILED
   - Many-to-one: → Campaign, SocialAccount
   - One-to-many: → ContentVariant, ContentAnalytics

6. **ContentVariant**
   - Platform-specific content versions
   - Fields: platform, optimized_content, platform_specific_data
   - Generated by content_formatter.py

7. **ContentAnalytics**
   - Performance metrics per platform
   - Fields: views, likes, shares, comments, engagement_rate, reach
   - Updated by analytics_service.py

8. **TaskState**
   - DAG scheduler task tracking
   - Fields: task_id, status, dependencies, retry_count, state_data
   - Status: PENDING, RUNNING, SUCCESS, FAILED, ROLLED_BACK

9. **AssumptionLog**
   - AI decision transparency
   - Fields: assumption_text, confidence_level, reasoning, impact_assessment
   - Linked to Content for audit trail

### Database Conventions

- **Primary Keys**: Auto-incrementing integers (`id`)
- **Timestamps**: `created_at`, `updated_at` on all models
- **Soft Deletes**: Use `deleted_at` instead of hard deletes
- **JSON Fields**: Use `sa.Column(JSON)` for flexible metadata
- **Indexes**: Add to frequently queried fields (platform, status, scheduled_for)

---

## 🔧 Development Workflows

### Setting Up Development Environment

```bash
# 1. Clone repository
git clone <repo-url>
cd headlessbrowsers

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Start PostgreSQL and Redis (Docker)
docker-compose up -d postgres redis

# 6. Run database migrations
cd backend
alembic upgrade head

# 7. Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 8. Start Celery worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info

# 9. Start Celery beat scheduler (separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend/app --cov-report=html

# Run specific test file
pytest tests/unit/test_orchestrator.py

# Run with output
pytest -v -s
```

### Code Quality Tools

```bash
# Format code with Black
black backend/app

# Lint with Flake8
flake8 backend/app --max-line-length=100

# Type checking with MyPy
mypy backend/app

# Pre-commit all checks
black . && flake8 . && mypy .
```

### Database Migrations

```bash
# Create new migration
cd backend
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Docker Development

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up backend

# View logs
docker-compose logs -f backend

# Rebuild after code changes
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🤖 AI-Specific Guidelines

### When Working with AI Content Generation

**File**: `backend/app/services/ai/ai_service.py`

**Best Practices**:
1. **Always log assumptions** with confidence scores
2. **Apply platform constraints** before returning content
3. **Trigger guardrails** for hallucination keywords
4. **Return confidence scores** in range [0.0, 1.0]
5. **Provide reasoning traces** for transparency

**Example Pattern**:
```python
async def generate_content(self, prompt: str, platform: PlatformType) -> Dict[str, Any]:
    # 1. Generate content
    content = await self._generate(prompt, platform)

    # 2. Log assumptions
    assumptions = [
        AssumptionLog(
            assumption_text="Assumed emoji usage increases engagement",
            confidence_level=0.75,
            reasoning="Based on platform best practices"
        )
    ]

    # 3. Apply guardrails
    guardrails_triggered = []
    if self._detect_hallucination(content):
        guardrails_triggered.append("hallucination_detected")
        content.confidence *= 0.8  # Reduce confidence

    # 4. Enforce platform constraints
    content = self._enforce_constraints(content, platform)

    return {
        "content": content,
        "assumptions": assumptions,
        "guardrails_triggered": guardrails_triggered,
        "confidence": content.confidence
    }
```

### When Working with Multi-Agent Systems

**File**: `backend/app/services/orchestrator.py`

**Best Practices**:
1. **Always create AgentPayload** with SHA-256 hash
2. **Verify payload integrity** before processing
3. **Create state checkpoints** at agent boundaries
4. **Use circuit breakers** for external calls
5. **Require adversarial review** for high-stakes decisions

**Adversarial Validation Pattern**:
```python
# When disagreement threshold (0.3) is met, flag for human review
if disagreement_score > 0.3:
    payload.metadata["requires_human_review"] = True
    payload.metadata["disagreement_details"] = {
        "score": disagreement_score,
        "primary_output": primary_result.outputs,
        "adversarial_output": adversarial_result.outputs,
        "risks_identified": adversarial_result.risks
    }
```

### Framework Integration Patterns

**LangChain** (`backend/app/adapters/langchain_adapter.py`):
```python
# Use for tool-augmented agents with memory
agent = LangChainContentAgent(agent_id="content_gen_1")
result = await agent.execute_task(
    task_description="Generate social media content",
    context={"campaign_id": 123}
)
```

**CrewAI** (`backend/app/adapters/crewai_adapter.py`):
```python
# Use for hierarchical multi-agent workflows
crew = ContentAutomationCrew()
result = crew.create_content_campaign(
    campaign_brief="Launch new product",
    platforms=["twitter", "linkedin"]
)
# Returns: Strategy → Content → Validation → Adversarial Review
```

---

## 📝 Key Conventions

### Code Style

- **Python**: PEP 8, enforced by Black (line length: 100)
- **Imports**: Grouped by stdlib, third-party, local
- **Type Hints**: Required for all function signatures
- **Docstrings**: Google style for all public functions
- **Async**: Prefer `async/await` over callbacks

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_CASE`
- **Private Members**: `_leading_underscore`
- **Database Tables**: Plural form (`social_accounts`)

### API Response Format

**Success Response**:
```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "timestamp": "2025-12-29T10:00:00Z",
    "request_id": "uuid-v4"
  }
}
```

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error message",
    "details": { ... }
  },
  "metadata": {
    "timestamp": "2025-12-29T10:00:00Z",
    "request_id": "uuid-v4"
  }
}
```

### Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

# Log levels:
logger.debug("Detailed information for debugging")
logger.info("General informational messages")
logger.warning("Warning messages for potentially harmful situations")
logger.error("Error messages for serious problems")
logger.critical("Critical messages for very serious problems")

# Include context
logger.info(f"Content published to {platform}", extra={
    "content_id": content.id,
    "platform": platform,
    "account_id": account.id
})
```

### Environment Variables

**Required**:
- `SECRET_KEY`: Application secret (change in production)
- `POSTGRES_*`: Database connection details
- `REDIS_HOST`, `REDIS_PORT`: Redis connection

**Optional but Recommended**:
- `OPENAI_API_KEY`: For AI content generation
- `ANTHROPIC_API_KEY`: Alternative AI provider
- `AWS_*`: For S3 media storage
- Platform API keys: `YOUTUBE_API_KEY`, `TWITTER_API_KEY`, etc.

**Never Commit**:
- API keys, secrets, tokens
- Production database credentials
- OAuth client secrets

---

## 🚀 Common Tasks for AI Assistants

### Task 1: Add a New Social Media Platform Integration

**Steps**:
1. Create new file: `backend/app/services/integrations/new_platform.py`
2. Inherit from `BasePlatformIntegration`
3. Implement required methods:
   - `publish_content(content, media_urls)`
   - `fetch_analytics(content_id)`
   - `validate_credentials(credentials)`
4. Add platform-specific constraints to `content_formatter.py`
5. Update `PlatformType` enum in `models.py`
6. Add API configuration to `core/config.py`
7. Create tests: `tests/unit/test_new_platform.py`

**Example Template**:
```python
from backend.app.services.integrations.base import BasePlatformIntegration

class NewPlatformIntegration(BasePlatformIntegration):
    PLATFORM_NAME = "newplatform"
    BASE_URL = "https://api.newplatform.com/v1"

    async def publish_content(
        self,
        content: Dict[str, Any],
        media_urls: List[str]
    ) -> Dict[str, Any]:
        async def _publish():
            # Implementation with rate limiting
            pass

        return await self.execute_with_retry(_publish)
```

### Task 2: Add a New Scheduled Background Task

**Steps**:
1. Add function to `backend/app/worker/tasks.py`
2. Decorate with `@celery_app.task`
3. Add schedule to `celery_app.py` `beat_schedule` dict
4. Test locally: `celery -A app.worker.celery_app worker -l info`

**Example**:
```python
from app.worker.celery_app import celery_app

@celery_app.task(name="tasks.generate_weekly_report")
def generate_weekly_report():
    """Generate weekly analytics report."""
    # Implementation
    logger.info("Weekly report generated")

# In celery_app.py beat_schedule:
"generate-weekly-report": {
    "task": "tasks.generate_weekly_report",
    "schedule": crontab(day_of_week=1, hour=9, minute=0),  # Monday 9 AM
}
```

### Task 3: Add a New API Endpoint

**Steps**:
1. Add function to appropriate file in `backend/app/api/v1/`
2. Use FastAPI decorators (`@router.post`, `@router.get`, etc.)
3. Add request/response models in `backend/app/schemas/` (if needed)
4. Update API documentation (auto-generated by FastAPI)
5. Add tests: `tests/integration/test_api.py`

**Example**:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from backend.app.db.session import get_db

router = APIRouter()

@router.post("/campaigns/{campaign_id}/publish")
async def publish_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Publish all content in campaign."""
    # Implementation
    return {"success": True, "data": {"published_count": 5}}
```

### Task 4: Add a New Database Model

**Steps**:
1. Add SQLModel class to `backend/app/models/models.py`
2. Create Alembic migration: `alembic revision --autogenerate -m "Add new model"`
3. Review generated migration in `backend/migrations/versions/`
4. Apply migration: `alembic upgrade head`
5. Add CRUD operations to `backend/app/crud/crud.py`
6. Add tests: `tests/unit/test_models.py`

**Example**:
```python
from sqlmodel import SQLModel, Field
from datetime import datetime

class NewModel(SQLModel, table=True):
    __tablename__ = "new_models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Task 5: Add a New Automation Workflow

**Steps**:
1. Review `AUTOMATION_CATALOG.md` for similar patterns
2. Create workflow class in `backend/app/services/`
3. Use `orchestrator.py` if multi-agent coordination needed
4. Use `scheduler.py` if DAG scheduling required
5. Create state checkpoints at critical boundaries
6. Log all assumptions with confidence scores
7. Add to automation catalog documentation
8. Create demo script in root directory (see `demo_automation.py`)

**Example Pattern**:
```python
from backend.app.services.orchestrator import MultiAgentOrchestrator
from backend.app.services.state_verifier import StateVerifier

class NewAutomationWorkflow:
    def __init__(self, db: Session):
        self.orchestrator = MultiAgentOrchestrator(db)
        self.state_verifier = StateVerifier()

    async def execute(self, workflow_input: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Create checkpoint
        checkpoint = self.state_verifier.create_checkpoint(
            checkpoint_id=f"workflow_{uuid.uuid4()}",
            state_data=workflow_input
        )

        # 2. Execute with orchestrator
        result = await self.orchestrator.execute_task_with_validation(
            task_payload=AgentPayload(...),
            executor_id="worker_1",
            adversarial_id="adversarial_1"
        )

        # 3. Verify state
        if not self.state_verifier.verify_checkpoint(checkpoint, workflow_input):
            # Rollback logic
            pass

        return result
```

---

## 🔍 Troubleshooting Common Issues

### Database Connection Errors

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
1. Verify PostgreSQL is running: `docker-compose ps postgres`
2. Check `.env` file has correct `POSTGRES_*` variables
3. Test connection: `psql -h localhost -U postgres -d content_automation`

### Celery Tasks Not Running

**Symptom**: Scheduled tasks not executing

**Solution**:
1. Verify Redis is running: `redis-cli ping` (should return "PONG")
2. Check Celery worker is running: `celery -A app.worker.celery_app status`
3. Check beat scheduler is running: `ps aux | grep celery`
4. Review logs: `celery -A app.worker.celery_app events`

### API Key Errors

**Symptom**: `401 Unauthorized` from social media platforms

**Solution**:
1. Verify API keys are set in `.env`
2. Check key expiration dates
3. Test with platform's API explorer
4. Verify OAuth scopes/permissions

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'backend'`

**Solution**:
1. Ensure you're in the correct directory
2. Verify virtual environment is activated
3. Set PYTHONPATH: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`
4. Reinstall dependencies: `pip install -r requirements.txt`

---

## 📖 Documentation Reference

### Primary Documentation Files

| File | Purpose | Lines |
|------|---------|-------|
| `README.md` | Original: Headless browsers list | 260+ |
| `CLAUDE.md` | This file: AI assistant guide | 900+ |
| `PLATFORM_ARCHITECTURE.md` | Technical architecture details | 1000+ |
| `PRODUCTION_DEPLOYMENT_GUIDE.md` | Production deployment steps | 900+ |
| `AGIM_X_ENHANCED_ORCHESTRATOR.md` | Advanced orchestration framework | 450+ |
| `AUTOMATION_CATALOG.md` | List of 25+ automations | 300+ |
| `AUTOMATION_DEMONSTRATION_SUMMARY.md` | Demo results & metrics | 400+ |

### Quick Reference Links

**In-Code Documentation**:
- `backend/app/services/orchestrator.py` - Multi-agent patterns
- `backend/app/services/state_verifier.py` - State management
- `backend/app/services/scheduler.py` - DAG scheduling
- `backend/app/models/models.py` - Database schema

**External Resources**:
- FastAPI: https://fastapi.tiangolo.com/
- SQLModel: https://sqlmodel.tiangolo.com/
- Celery: https://docs.celeryq.dev/
- LangChain: https://python.langchain.com/
- CrewAI: https://docs.crewai.com/

---

## 🎓 Learning Path for New AI Assistants

### Level 1: Basic Understanding (1-2 hours)
1. Read this CLAUDE.md file completely
2. Review `AUTOMATION_CATALOG.md` for available automations
3. Explore `backend/app/models/models.py` for data structure
4. Run `demo_automation.py` to see system in action

### Level 2: Architecture Comprehension (3-4 hours)
1. Study `PLATFORM_ARCHITECTURE.md` in detail
2. Trace multi-agent workflow in `orchestrator.py`
3. Understand state verification in `state_verifier.py`
4. Review all 5 advanced guardrails

### Level 3: Hands-On Development (5+ hours)
1. Set up development environment
2. Run tests: `pytest tests/`
3. Create a simple API endpoint
4. Add a scheduled Celery task
5. Implement a new automation workflow

### Level 4: Production Expertise (10+ hours)
1. Review `PRODUCTION_DEPLOYMENT_GUIDE.md`
2. Understand Docker Compose configuration
3. Study monitoring & observability setup
4. Review security & authentication patterns
5. Practice debugging with logs

---

## 🚨 Critical Reminders for AI Assistants

### Always Do ✅

1. **Check which part of repository** user is working on (headless browsers list vs. platform)
2. **Log assumptions** when making AI-generated content
3. **Create state checkpoints** before critical operations
4. **Verify payload integrity** with SHA-256 hashes
5. **Use adversarial validation** for high-stakes decisions
6. **Apply platform constraints** (character limits, hashtag counts)
7. **Handle rate limiting** with exponential backoff
8. **Write tests** for new features
9. **Update documentation** when adding features
10. **Never commit secrets** to version control

### Never Do ❌

1. **Don't skip adversarial review** for content > 0.7 confidence threshold
2. **Don't ignore circular dependencies** in DAG scheduler
3. **Don't bypass guardrails** even for "simple" cases
4. **Don't assume state is fresh** - always check TTL
5. **Don't hard-code API keys** - use environment variables
6. **Don't modify original README.md** without explicit permission
7. **Don't skip state verification** in multi-agent workflows
8. **Don't ignore confidence collapse** warnings (< 0.5)
9. **Don't forget to update AUTOMATION_CATALOG.md** when adding automations
10. **Don't deploy to production** without reviewing deployment guide

---

## 📊 Metrics & Monitoring

### Key Performance Indicators (KPIs)

**System Health**:
- API response time: < 200ms (p95)
- Database query time: < 50ms (p95)
- Task queue length: < 100
- Error rate: < 1%

**Content Performance**:
- Content generation time: < 5s
- Publishing success rate: > 95%
- Average confidence score: > 0.7
- Human review rate: < 30%

**Multi-Agent Metrics**:
- Agent execution time: < 10s per task
- Circuit breaker open rate: < 5%
- State verification pass rate: > 99%
- Adversarial disagreement rate: 20-30% (healthy skepticism)

### Monitoring Endpoints

- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (Prometheus format)
- **Celery Flower**: `http://localhost:5555`
- **API Docs**: `http://localhost:8000/docs`

---

## 🔐 Security Considerations

### Authentication & Authorization

- **API Keys**: Stored in environment variables, never in code
- **OAuth Tokens**: Encrypted in database with `expires_at` tracking
- **User Sessions**: JWT tokens with expiration
- **Rate Limiting**: Per-endpoint limits defined in config

### Data Protection

- **Sensitive Data**: Encrypted at rest (PostgreSQL encryption)
- **API Responses**: Never include secrets or internal IDs
- **Logs**: Redact sensitive information (tokens, passwords)
- **Audit Trail**: All state changes logged to `.audit_log.jsonl`

### Best Practices

1. **Validate all inputs** at API boundary
2. **Sanitize user content** before storage
3. **Use parameterized queries** (SQLModel does this)
4. **Implement CORS** properly (configured in `main.py`)
5. **Keep dependencies updated** (run `pip list --outdated`)

---

## 🎉 Conclusion

This repository is a unique dual-purpose project combining:

1. **Community Resource**: Comprehensive headless browser catalog
2. **Production Platform**: Enterprise content automation system

When working with this codebase:
- Clarify the scope with the user first
- Follow the architecture patterns documented here
- Apply all 5 advanced guardrails consistently
- Maintain high code quality and test coverage
- Document new features thoroughly

**Remember**: This platform is designed for safe, transparent, and reliable AI-powered automation. Every design decision prioritizes correctness over convenience.

---

**Last Updated**: 2025-12-29
**Platform Version**: 1.0.0
**Document Version**: 1.0
**Maintained By**: AI Assistants working with this codebase

For questions or clarifications, refer to the documentation files listed in the "Documentation Reference" section above.
