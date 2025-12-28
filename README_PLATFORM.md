# Content Automation Platform

A production-ready content automation platform for multi-channel social media management with AI-powered content generation, DAG-based scheduling, and comprehensive analytics.

## Features

### 🎯 Core Capabilities

- **Multi-Platform Integration**: Native support for YouTube, Twitter, Facebook, Instagram, and LinkedIn
- **AI Content Generation**: OpenAI GPT-4 and Anthropic Claude integration with hallucination prevention
- **Template Engine**: Reusable content templates with variable substitution
- **DAG Scheduling**: Dependency-aware task orchestration with topological sorting
- **Analytics Aggregation**: Multi-platform analytics with KPI tracking
- **Media Management**: S3-backed storage with SHA-256 integrity validation
- **Production Deployment**: High-availability setup with Docker Compose

### 🔒 Enterprise Features

- **Guardrails**: Hallucination detection, rate limiting, payload integrity validation
- **Error Recovery**: Exponential backoff retry (2s, 4s, 8s) with rollback support
- **Monitoring**: Prometheus, Grafana, and Loki for comprehensive observability
- **Audit Logging**: Structured assumption logs with confidence scores
- **State Management**: Full lifecycle tracking with error boundaries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Traefik (Reverse Proxy)                  │
│                    SSL/TLS + Rate Limiting                   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────┬──────────────────┬──────────────────────┐
│   FastAPI x3     │   Celery x2      │   Celery Beat        │
│   (Backend API)  │   (Workers)      │   (Scheduler)        │
└──────────────────┴──────────────────┴──────────────────────┘
                             │
                             ▼
┌──────────────────┬──────────────────┬──────────────────────┐
│   PostgreSQL     │   Redis          │   S3 Storage         │
│   (Database)     │   (Cache/Queue)  │   (Media)            │
└──────────────────┴──────────────────┴──────────────────────┘
                             │
                             ▼
┌──────────────────┬──────────────────┬──────────────────────┐
│   Prometheus     │   Grafana        │   Loki               │
│   (Metrics)      │   (Dashboard)    │   (Logs)             │
└──────────────────┴──────────────────┴──────────────────────┘
```

## Database Schema

### 7 Core Models

1. **SocialAccount**: Platform credentials and configuration
2. **MediaAsset**: Media files with SHA-256 integrity
3. **ContentTemplate**: Reusable templates with variables
4. **Campaign**: Marketing campaigns with KPI targets
5. **Content**: Main content entity with DAG dependencies
6. **ContentVariant**: A/B testing variants
7. **ContentAnalytics**: Multi-platform metrics

### Supporting Models

- **TaskState**: DAG execution state with rollback
- **AssumptionLog**: AI decision audit trail

## Quick Start

### Prerequisites

- Docker & Docker Compose
- API keys for social platforms
- OpenAI and/or Anthropic API keys

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd headlessbrowsers

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env

# Start services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Access API
open http://localhost:8000/docs
```

### Production Deployment

```bash
# Configure production environment
cp .env.example .env.production
nano .env.production

# Run deployment script
chmod +x deploy/scripts/deploy.sh
./deploy/scripts/deploy.sh production yourdomain.com

# Access services
# - API: https://yourdomain.com/api
# - Grafana: https://grafana.yourdomain.com
# - Prometheus: https://prometheus.yourdomain.com
```

## API Endpoints

### Content Management

- `POST /api/v1/content/` - Create content
- `GET /api/v1/content/` - List content
- `GET /api/v1/content/{id}` - Get specific content
- `PUT /api/v1/content/{id}` - Update content
- `DELETE /api/v1/content/{id}` - Delete content
- `POST /api/v1/content/{id}/schedule` - Schedule content
- `POST /api/v1/content/publish-batch` - Publish with DAG

### Campaign Management

- `POST /api/v1/campaigns/` - Create campaign
- `GET /api/v1/campaigns/` - List campaigns
- `GET /api/v1/campaigns/{id}/analytics` - Campaign analytics

### Analytics

- `GET /api/v1/analytics/top-performing` - Top content by metric
- `POST /api/v1/analytics/collect` - Trigger collection

### Templates

- `POST /api/v1/templates/` - Create template
- `GET /api/v1/templates/` - List templates
- `POST /api/v1/templates/preview` - Preview with data

### Media

- `POST /api/v1/media/upload` - Upload media
- `GET /api/v1/media/{id}/url` - Get media URL

## Background Tasks

### Scheduled Tasks (Celery Beat)

1. **process_scheduled_posts** - Every minute
   - Checks for scheduled content
   - Triggers publishing

2. **fetch_analytics_batch** - Hourly
   - Collects analytics from platforms
   - Updates database

3. **cleanup_old_data** - Daily at 2 AM
   - Removes old analytics (>90 days)
   - Cleans failed content (>30 days)

4. **backup_database** - Daily at 3 AM
   - PostgreSQL dump to S3
   - Retention management

## Platform Integrations

### YouTube Data API v3
- Video upload with metadata
- Analytics: views, likes, comments
- Playlist management

### Twitter API v2
- Tweet posting (text + media)
- Engagement metrics
- Thread support

### Facebook Graph API
- Page post creation
- Insights and metrics
- Scheduled publishing

### Instagram Graph API
- Media publishing
- Story support
- Engagement analytics

### LinkedIn API v2
- Profile/company posts
- Article sharing
- Professional metrics

## AI Content Generation

### Providers

- **OpenAI GPT-4**: General-purpose generation
- **Anthropic Claude**: Long-form content

### Platform Optimization

Each platform has specific constraints:
- Twitter: 280 chars, concise tone
- LinkedIn: Professional, 3-5 hashtags
- Instagram: Visual-focused, up to 30 hashtags
- Facebook: Conversational, longer form
- YouTube: Searchable, descriptive

### Guardrails

1. **Hallucination Detection**: Keyword scanning
2. **Confidence Scoring**: 0-1 scale with thresholds
3. **Assumption Logging**: Audit trail in database
4. **Content Moderation**: Offensive language check

## DAG Scheduling

### Features

- Topological sort for dependency resolution
- Parallel execution within levels
- Error boundaries for fault isolation
- Rollback support

### Example

```python
# Content with dependencies
content_a = Content(id=1, depends_on=None)
content_b = Content(id=2, depends_on=[1])
content_c = Content(id=3, depends_on=[1])
content_d = Content(id=4, depends_on=[2, 3])

# Execution order
# Level 1: [A]
# Level 2: [B, C] (parallel)
# Level 3: [D]
```

## Monitoring

### Metrics (Prometheus)

- Request latency
- Error rates
- Task queue depth
- Database connection pool

### Dashboards (Grafana)

- System overview
- API performance
- Social media metrics
- Campaign ROI

### Logs (Loki)

- Centralized log aggregation
- Query by service/level
- Alert integration

## Configuration

### Environment Variables

```bash
# Core
SECRET_KEY=your-secret-key
ENVIRONMENT=production

# Database
POSTGRES_PASSWORD=secure-password
POSTGRES_DB=content_automation

# Social Media APIs
YOUTUBE_API_KEY=...
TWITTER_BEARER_TOKEN=...
FACEBOOK_APP_SECRET=...
INSTAGRAM_APP_SECRET=...
LINKEDIN_CLIENT_SECRET=...

# AI Services
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...

# AWS (Media Storage)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=...
```

## Security Checklist

### Pre-Deployment

- [ ] Generate strong SECRET_KEY (32+ chars)
- [ ] Set secure database password
- [ ] Configure firewall (ports 80, 443, 22)
- [ ] Enable SSL/TLS (automatic via Let's Encrypt)
- [ ] Review API scopes (minimum required)

### Post-Deployment

- [ ] Test SSL certificate
- [ ] Verify health checks
- [ ] Check monitoring dashboards
- [ ] Test backup system
- [ ] Enable 2FA for admin

### Ongoing

- [ ] Monitor audit logs
- [ ] Rotate API keys quarterly
- [ ] Update dependencies monthly
- [ ] Review access logs weekly

## Development

### Project Structure

```
headlessbrowsers/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API routes
│   │   ├── core/            # Configuration
│   │   ├── crud/            # CRUD operations
│   │   ├── db/              # Database setup
│   │   ├── models/          # SQLModel models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   │   ├── integrations/  # Platform APIs
│   │   │   ├── ai/            # AI services
│   │   │   └── ...
│   │   └── worker/          # Celery tasks
│   ├── migrations/          # Alembic migrations
│   └── tests/               # Test suite
├── deploy/
│   ├── docker/              # Docker configs
│   ├── monitoring/          # Prometheus/Grafana
│   └── scripts/             # Deployment scripts
├── docs/                    # Documentation
├── docker-compose.yml       # Development
├── docker-compose.prod.yml  # Production
├── requirements.txt         # Python deps
└── .env.example             # Config template
```

### Running Tests

```bash
# Unit tests
docker-compose exec backend pytest tests/unit

# Integration tests
docker-compose exec backend pytest tests/integration

# Coverage report
docker-compose exec backend pytest --cov=backend tests/
```

### Database Migrations

```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback
docker-compose exec backend alembic downgrade -1
```

## Troubleshooting

### Common Issues

**Database Connection Failed**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres
```

**Celery Worker Not Processing Tasks**
```bash
# Check worker status
docker-compose logs celery_worker

# Restart worker
docker-compose restart celery_worker
```

**API Returning 500 Errors**
```bash
# View backend logs
docker-compose logs backend

# Check health endpoint
curl http://localhost:8000/health
```

## Performance Tuning

### Backend

- Adjust Uvicorn workers: `--workers 4`
- Enable connection pooling (default)
- Use async endpoints where possible

### Celery

- Scale workers: `docker-compose scale celery_worker=4`
- Adjust concurrency: `--concurrency=8`
- Enable prefetch multiplier tuning

### Database

- Add indexes for frequent queries
- Enable connection pooling
- Configure autovacuum

## License

See LICENSE file.

## Support

For issues and questions:
- GitHub Issues: <repository-url>/issues
- Documentation: /docs

## Contributors

Built with the Claude Agent SDK.
