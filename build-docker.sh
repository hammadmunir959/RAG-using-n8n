#!/bin/bash

# Docker Build and Push Script for Document Intelligence App
# Usage: ./build-docker.sh [dockerhub-username] [tag]

set -e

DOCKERHUB_USER="${1:-your-username}"
TAG="${2:-latest}"
IMAGE_NAME="doc-intel"
FULL_IMAGE_NAME="${DOCKERHUB_USER}/${IMAGE_NAME}:${TAG}"

echo "🐳 Building Docker image: ${FULL_IMAGE_NAME}"
echo ""

# Build the image
docker build -t "${FULL_IMAGE_NAME}" .

# Check image size
echo ""
echo "📊 Image size:"
docker images "${FULL_IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

IMAGE_SIZE=$(docker images "${FULL_IMAGE_NAME}" --format "{{.Size}}" | sed 's/[^0-9.]//g' | head -1)
echo ""
echo "✅ Build complete!"
echo ""
echo "To push to Docker Hub:"
echo "  docker login"
echo "  docker push ${FULL_IMAGE_NAME}"
echo ""
echo "To run locally:"
echo "  docker run -d -p 8000:8000 -v \$(pwd)/data:/app/data ${FULL_IMAGE_NAME}"

