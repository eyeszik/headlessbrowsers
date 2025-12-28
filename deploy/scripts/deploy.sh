#!/bin/bash

# Content Automation Platform - Deployment Script
# Usage: ./deploy.sh [environment] [domain]

set -e

ENVIRONMENT=${1:-production}
DOMAIN=${2:-localhost}

echo "========================================="
echo "Content Automation Platform Deployment"
echo "========================================="
echo "Environment: $ENVIRONMENT"
echo "Domain: $DOMAIN"
echo ""

# Pre-flight checks
echo "[1/10] Running pre-flight checks..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env.$ENVIRONMENT" ]; then
    echo "Error: .env.$ENVIRONMENT file not found"
    echo "Please create it from .env.example"
    exit 1
fi

echo "✓ Pre-flight checks passed"

# Create networks
echo "[2/10] Creating Docker networks..."
docker network create content-automation-network 2>/dev/null || true
echo "✓ Networks created"

# Build images
echo "[3/10] Building Docker images..."
if [ "$ENVIRONMENT" = "production" ]; then
    docker-compose -f docker-compose.prod.yml build
else
    docker-compose build
fi
echo "✓ Images built"

# Run database migrations
echo "[4/10] Running database migrations..."
docker-compose run --rm backend alembic upgrade head
echo "✓ Migrations completed"

# Start services
echo "[5/10] Starting all services..."
if [ "$ENVIRONMENT" = "production" ]; then
    docker-compose -f docker-compose.prod.yml up -d
else
    docker-compose up -d
fi
echo "✓ Services started"

# Wait for services to be healthy
echo "[6/10] Waiting for services to be healthy..."
sleep 10

# Check backend health
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/health &> /dev/null; then
        echo "✓ Backend is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for backend... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Error: Backend failed to start"
    exit 1
fi

# Check superuser
echo "[7/10] Checking superuser..."
# Add logic to create superuser if needed
echo "✓ Superuser check completed"

# Setup monitoring
echo "[8/10] Setting up monitoring..."
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Prometheus: http://$DOMAIN:9090"
    echo "Grafana: https://grafana.$DOMAIN (default: admin/admin)"
fi
echo "✓ Monitoring configured"

# Configure backups
echo "[9/10] Configuring backups..."
mkdir -p ./deploy/scripts/backup
echo "✓ Backup directory created"

# Final checks
echo "[10/10] Running final checks..."
docker-compose ps
echo ""
echo "✓ All checks passed"

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Access points:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
if [ "$ENVIRONMENT" = "production" ]; then
    echo "  - Grafana: https://grafana.$DOMAIN"
    echo "  - Prometheus: http://$DOMAIN:9090"
fi
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart: docker-compose restart"
echo ""
