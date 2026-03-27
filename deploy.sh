#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.50.135:5500}"
IMAGE="${REGISTRY}/wechat-oa-reader"
TAG="${IMAGE_TAG:-latest}"
NAS_HOST="${NAS_HOST:-192.168.50.135}"
NAS_USER="${NAS_USER:-root}"
NAS_DIR="${NAS_DIR:-/opt/wechat-oa-reader}"

echo "==> Building ${IMAGE}:${TAG}"
docker build -t "${IMAGE}:${TAG}" .

echo "==> Pushing to registry"
docker push "${IMAGE}:${TAG}"

echo "==> Deploying to NAS (${NAS_HOST})"
ssh "${NAS_USER}@${NAS_HOST}" bash -s <<EOF
  cd ${NAS_DIR}
  docker pull ${IMAGE}:${TAG}
  docker compose -f docker-compose.prod.yml up -d
EOF

echo "==> Done"
