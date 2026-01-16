# Content Automation Platform - Production Deployment Guide

## 🚀 Complete Production Deployment with Multi-Agent Orchestration

### Prerequisites

**System Requirements:**
- Linux server (Ubuntu 22.04 LTS recommended)
- 16GB RAM minimum (32GB recommended for HA setup)
- 4 CPU cores minimum (8 cores recommended)
- 100GB SSD storage
- Docker 24.0+
- Docker Compose 2.20+

**API Access Required:**
- YouTube Data API v3 credentials
- Twitter API v2 bearer token
- Facebook Graph API app credentials
- Instagram Graph API (uses Facebook credentials)
- LinkedIn API v2 OAuth credentials
- OpenAI API key (GPT-4 access)
- Anthropic API key (Claude access)
- AWS account with S3 bucket (for media storage)

---

## 📋 Step-by-Step Deployment

### Phase 1: Server Preparation (15 minutes)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version

# Reboot to apply group changes
sudo reboot
```

### Phase 2: Repository Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/eyeszik/headlessbrowsers.git
cd headlessbrowsers

# Checkout production branch
git checkout claude/content-automation-platform-2HFNc

# Verify files
ls -la
```

### Phase 3: Configuration (20 minutes)

#### 3.1 Environment Configuration

```bash
# Copy production environment template
cp .env.example .env.production

# Edit with your credentials
nano .env.production
```

**Required Configuration:**

```bash
# Domain and SSL
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
ENVIRONMENT=production

# Security
SECRET_KEY=<generate-with-openssl-rand-base64-32>
TRAEFIK_AUTH=<generate-with-htpasswd>

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong-password-32-chars>
POSTGRES_DB=content_automation

# Redis
REDIS_PASSWORD=<strong-password-32-chars>

# Social Media APIs
YOUTUBE_API_KEY=AIza...
YOUTUBE_CLIENT_ID=123456...
YOUTUBE_CLIENT_SECRET=GOCSPX-...

TWITTER_BEARER_TOKEN=AAAA...
TWITTER_API_KEY=xyz...
TWITTER_API_SECRET=abc...

FACEBOOK_APP_ID=123456...
FACEBOOK_APP_SECRET=abc123...

INSTAGRAM_APP_ID=<same-as-facebook>
INSTAGRAM_APP_SECRET=<same-as-facebook>

LINKEDIN_CLIENT_ID=78abc...
LINKEDIN_CLIENT_SECRET=def456...

# AI Services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# AWS S3
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=your-content-automation-bucket
AWS_REGION=us-east-1

# Monitoring
GRAFANA_PASSWORD=<admin-password>
```

#### 3.2 Generate Security Keys

```bash
# Generate SECRET_KEY
openssl rand -base64 32

# Generate TRAEFIK_AUTH (Basic Auth)
echo $(htpasswd -nb admin your-password-here)

# Generate database password
openssl rand -base64 32
```

#### 3.3 DNS Configuration

Point your domain to server IP:
```
A     yourdomain.com          -> YOUR_SERVER_IP
A     grafana.yourdomain.com  -> YOUR_SERVER_IP
A     traefik.yourdomain.com  -> YOUR_SERVER_IP
```

### Phase 4: Initial Deployment (30 minutes)

```bash
# Make deployment script executable
chmod +x deploy/scripts/deploy.sh

# Run deployment
./deploy/scripts/deploy.sh production yourdomain.com
```

**Deployment Process:**
1. Pre-flight checks (Docker, environment variables)
2. Network creation
3. Image building (10-15 minutes)
4. Database migrations
5. Service startup
6. Health checks
7. Monitoring setup
8. Final verification

**Expected Output:**
```
=========================================
Content Automation Platform Deployment
=========================================
Environment: production
Domain: yourdomain.com

[1/10] Running pre-flight checks...
✓ Pre-flight checks passed
[2/10] Creating Docker networks...
✓ Networks created
[3/10] Building Docker images...
✓ Images built
[4/10] Running database migrations...
✓ Migrations completed
[5/10] Starting all services...
✓ Services started
[6/10] Waiting for services to be healthy...
✓ Backend is healthy
[7/10] Checking superuser...
✓ Superuser check completed
[8/10] Setting up monitoring...
✓ Monitoring configured
[9/10] Configuring backups...
✓ Backup directory created
[10/10] Running final checks...
✓ All checks passed

=========================================
Deployment Complete!
=========================================

Access points:
  - API: https://yourdomain.com/api/v1
  - API Docs: https://yourdomain.com/docs
  - Grafana: https://grafana.yourdomain.com
  - Prometheus: http://yourdomain.com:9090
```

### Phase 5: Verification (15 minutes)

#### 5.1 Health Checks

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Expected output:
# All services should show "Up" and "healthy"

# Backend health check
curl https://yourdomain.com/api/v1/health

# Expected: {"status":"healthy","environment":"production"}
```

#### 5.2 SSL Certificate Verification

```bash
# Check SSL certificate
curl -I https://yourdomain.com

# Verify with SSL Labs
# https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
```

#### 5.3 Database Verification

```bash
# Connect to database
docker exec -it postgres_primary psql -U postgres -d content_automation

# List tables
\dt

# Expected: 9 tables (socialaccount, mediaasset, contenttemplate, campaign, content, contentvariant, contentanalytics, taskstate, assumptionlog)

# Exit
\q
```

#### 5.4 Monitoring Dashboard Access

```
Grafana: https://grafana.yourdomain.com
Login: admin / <GRAFANA_PASSWORD>

Expected Dashboards:
- System Overview
- API Performance
- Multi-Agent Orchestrator Metrics
- Social Media Platform Health
- Campaign Performance
```

---

## 🛡️ Security Hardening (30 minutes)

### Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
sudo ufw status
```

### SSH Hardening

```bash
# Disable password authentication
sudo nano /etc/ssh/sshd_config

# Set:
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart sshd
```

### Docker Security

```bash
# Run Docker daemon with userns-remap
sudo nano /etc/docker/daemon.json

{
  "userns-remap": "default",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart Docker
sudo systemctl restart docker
```

---

## 📊 Monitoring & Alerting Setup

### Grafana Dashboards

1. **System Overview Dashboard**
   - CPU, Memory, Disk usage
   - Network I/O
   - Container health status

2. **API Performance Dashboard**
   - Request rate
   - Response times (p50, p95, p99)
   - Error rates
   - Endpoint breakdown

3. **Multi-Agent Orchestrator Dashboard** ✨ NEW
   - Active agents
   - Task execution rates
   - Confidence scores distribution
   - Circuit breaker states
   - State verification metrics

4. **Social Media Platform Dashboard**
   - Platform-specific API health
   - Rate limit usage
   - Publishing success rates
   - Analytics collection status

5. **Campaign Performance Dashboard**
   - Campaign metrics vs KPI targets
   - Content performance rankings
   - Platform comparison
   - ROI tracking

### Alert Configuration

```yaml
# /etc/prometheus/rules/alerts.yml
groups:
  - name: content_automation_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      - alert: AgentConfidenceCollapse
        expr: avg(agent_confidence_score) < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Agent confidence below threshold"
          description: "Average confidence: {{ $value }}"

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker opened"
          description: "Service experiencing failures"

      - alert: StateCorruptionDetected
        expr: increase(state_corruption_events_total[1h]) > 0
        labels:
          severity: critical
        annotations:
          summary: "State corruption detected"
          description: "Check .state_corruption.jsonl for details"
```

---

## 🔄 Operational Procedures

### Daily Operations

**Morning Checklist:**
```bash
# Check system health
docker-compose -f docker-compose.prod.yml ps

# Review overnight logs
docker-compose -f docker-compose.prod.yml logs --since 12h --tail 100

# Check backup status
ls -lh deploy/scripts/backup/

# Verify monitoring dashboards
# Open Grafana and review all dashboards
```

### Backup & Recovery

#### Automated Backups

Backups run daily at 3 AM via Celery task:
- PostgreSQL dump to S3
- Redis snapshot to S3
- Media files already in S3
- Configuration files versioned in Git

#### Manual Backup

```bash
# Database backup
docker exec postgres_primary pg_dump -U postgres content_automation > backup_$(date +%Y%m%d).sql

# Upload to S3
aws s3 cp backup_$(date +%Y%m%d).sql s3://your-backup-bucket/manual/
```

#### Recovery Procedure

```bash
# Stop services
docker-compose -f docker-compose.prod.yml down

# Restore database
cat backup_20251228.sql | docker exec -i postgres_primary psql -U postgres -d content_automation

# Restart services
docker-compose -f docker-compose.prod.yml up -d

# Verify health
curl https://yourdomain.com/api/v1/health
```

### Scaling

#### Horizontal Scaling

```bash
# Scale backend replicas
docker-compose -f docker-compose.prod.yml up -d --scale backend=5

# Scale Celery workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=4
```

#### Vertical Scaling

Edit `docker-compose.prod.yml`:
```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2.0'       # Increase from 1.0
        memory: 4G        # Increase from 2G
      reservations:
        cpus: '1.0'
        memory: 2G
```

Apply changes:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🔧 Troubleshooting

### Common Issues

#### Issue: SSL Certificate Not Generating

**Symptoms:** HTTP works but HTTPS fails

**Solution:**
```bash
# Check Traefik logs
docker logs traefik

# Verify DNS
dig yourdomain.com

# Manually trigger cert generation
docker exec traefik traefik healthcheck
```

#### Issue: Database Connection Errors

**Symptoms:** Backend can't connect to PostgreSQL

**Solution:**
```bash
# Check PostgreSQL status
docker logs postgres_primary

# Verify credentials
docker exec postgres_primary psql -U postgres -c "\l"

# Check network
docker network inspect content-automation-network
```

#### Issue: Celery Tasks Not Executing

**Symptoms:** Scheduled posts not publishing

**Solution:**
```bash
# Check Celery worker logs
docker logs content_automation_worker

# Check Celery beat
docker logs content_automation_beat

# Verify Redis connection
docker exec content_automation_worker celery -A backend.app.worker.celery_app inspect active
```

#### Issue: High Memory Usage

**Symptoms:** System becoming slow, OOM errors

**Solution:**
```bash
# Check resource usage
docker stats

# Review Grafana system dashboard
# Identify memory-hungry containers

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

#### Issue: Agent Confidence Collapse ✨ NEW

**Symptoms:** Tasks failing with low confidence

**Solution:**
```bash
# Check decision logs
tail -n 100 .agent_audit.jsonl | jq '.confidence'

# Review orchestrator metrics
curl http://localhost:8000/api/v1/orchestrator/metrics

# Recalibrate agents if needed
# (Would trigger through admin API)
```

---

## 📈 Performance Optimization

### Database Optimization

```sql
-- Create indexes on frequently queried fields
CREATE INDEX idx_content_scheduled ON content(scheduled_time) WHERE status = 'scheduled';
CREATE INDEX idx_analytics_collected ON contentanalytics(collected_at);
CREATE INDEX idx_task_state_status ON taskstate(status);

-- Analyze tables
ANALYZE content;
ANALYZE contentanalytics;
ANALYZE taskstate;

-- Set autovacuum more aggressive
ALTER TABLE content SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE contentanalytics SET (autovacuum_vacuum_scale_factor = 0.05);
```

### Redis Optimization

```bash
# Edit redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### API Response Caching

```python
# Add to backend/app/main.py
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://redis:6379")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
```

---

## 🎯 Success Metrics & KPIs

### Platform Health KPIs

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| API Uptime | 99.9% | < 99% |
| API Response Time (p95) | < 200ms | > 500ms |
| Error Rate | < 0.1% | > 1% |
| Database Connection Pool | < 80% | > 90% |
| Celery Queue Depth | < 100 | > 1000 |

### Multi-Agent Orchestrator KPIs ✨ NEW

| Metric | Target | Action Threshold |
|--------|--------|-----------------|
| Average Confidence Score | > 0.8 | < 0.6 |
| State Corruption Events | 0 | > 0 |
| Circuit Breaker Opens | 0 | > 3/hour |
| Agent Disagreement Rate | 10-30% | < 5% or > 40% |
| Task Success Rate | > 95% | < 90% |

### Content Performance KPIs

| Metric | Target | Tracking |
|--------|--------|----------|
| Content Publishing Success | > 98% | Real-time |
| Analytics Collection Rate | > 95% | Hourly |
| Average Engagement Rate | > 3% | Daily |
| Campaign ROI | > 2.5x | Weekly |

---

## 🚨 Incident Response Plan

### Severity Levels

**P0 - Critical (Response: Immediate)**
- Platform completely down
- Data loss or corruption
- Security breach
- State corruption detected

**P1 - High (Response: < 30 minutes)**
- Major feature unavailable
- High error rates (> 5%)
- Circuit breakers open
- Database connection failures

**P2 - Medium (Response: < 2 hours)**
- Performance degradation
- Minor feature issues
- Agent confidence below threshold

**P3 - Low (Response: Next business day)**
- UI bugs
- Documentation issues
- Feature requests

### Incident Response Workflow

1. **Detection** (Automated alerts or manual report)
2. **Assessment** (Classify severity, gather logs)
3. **Mitigation** (Apply hotfix or rollback)
4. **Communication** (Notify stakeholders)
5. **Resolution** (Permanent fix)
6. **Post-Mortem** (Document learnings)

### Emergency Contacts

```yaml
on_call_schedule:
  primary: DevOps Lead
  secondary: Backend Lead
  escalation: CTO

alert_channels:
  critical: SMS + Email + Slack
  high: Email + Slack
  medium: Slack
  low: Email
```

---

## 🎓 Training & Onboarding

### Required Reading
1. Platform Architecture (PLATFORM_ARCHITECTURE.md)
2. API Reference (README_PLATFORM.md)
3. Multi-Agent Orchestration Guide (this document)

### Hands-On Exercises
1. Deploy to staging environment
2. Create test campaign
3. Trigger manual backup
4. Simulate incident and recover
5. Review monitoring dashboards

---

**Production Deployment Complete! 🎉**

Your Content Automation Platform with Advanced Multi-Agent Orchestration is now live and operational.

Next steps:
1. Monitor Grafana dashboards for 24 hours
2. Create first production campaign
3. Review decision audit logs
4. Schedule team training session
5. Plan first monthly review meeting
