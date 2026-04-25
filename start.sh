#!/bin/bash
set -e

# Create MongoDB data directory if missing
mkdir -p /home/runner/workspace/.mongodb/data

# Start MongoDB in background (skip if already running)
echo "Starting MongoDB..."
mongod --dbpath /home/runner/workspace/.mongodb/data \
  --bind_ip 127.0.0.1 \
  --port 27017 \
  --logpath /home/runner/workspace/.mongodb/mongod.log \
  --fork \
  --quiet 2>/dev/null || echo "MongoDB may already be running"

# Wait for MongoDB to be ready
echo "Waiting for MongoDB..."
for i in $(seq 1 20); do
  if mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
    echo "MongoDB ready"
    break
  fi
  sleep 1
done

# Start backend in background
echo "Starting backend on port 8001..."
cd /home/runner/workspace/backend
uvicorn server:app --host 127.0.0.1 --port 8001 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Start frontend using root node_modules (clean installation)
echo "Starting frontend on port 5000..."
cd /home/runner/workspace/frontend
BROWSER=none \
  PORT=5000 \
  HOST=0.0.0.0 \
  REACT_APP_BACKEND_URL="$REACT_APP_BACKEND_URL" \
  node /home/runner/workspace/node_modules/@craco/craco/dist/scripts/start.js
