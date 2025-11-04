#!/bin/bash

# triB FastAPI V2 Deployment Script
# This script is executed on the EC2 server to deploy the application

set -e  # Exit on error

echo "========================================="
echo "triB FastAPI V2 Deployment Started"
echo "========================================="

# Configuration
APP_DIR="/home/ubuntu/triB_python"
DOCKER_COMPOSE_FILE="$APP_DIR/docker-compose.yml"

# Navigate to application directory
cd "$APP_DIR"

echo "Step 1: Pulling latest code from repository..."
git pull origin main

echo "Step 2: Creating .env file from GitHub Secrets..."
# .env file is created by GitHub Actions with secrets

echo "Step 3: Stopping existing containers..."
docker compose down || true

echo "Step 4: Removing old images..."
docker compose rm -f || true

echo "Step 5: Building new Docker image..."
docker compose build --no-cache

echo "Step 6: Starting containers..."
docker compose up -d

echo "Step 7: Waiting for container to be healthy..."
sleep 10

echo "Step 8: Checking container status..."
docker compose ps

echo "Step 9: Testing health endpoint..."
sleep 5
curl -f http://localhost:8000/ || {
    echo "Health check failed!"
    docker compose logs --tail=50
    exit 1
}

echo "Step 10: Showing recent logs..."
docker compose logs --tail=20

echo "========================================="
echo "Deployment completed successfully!"
echo "API is running at: http://localhost:8000"
echo "========================================="

# Cleanup old images
echo "Cleaning up old Docker images..."
docker image prune -f
