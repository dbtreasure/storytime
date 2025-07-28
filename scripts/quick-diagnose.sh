#!/bin/bash

echo "=== Quick Worker Diagnostics ==="
echo "Date: $(date)"
echo ""

# Find worker container
WORKER=$(docker ps --format "{{.Names}}" | grep -i worker | head -1)
echo "Worker container: $WORKER"
echo ""

# Check if worker was OOM killed
echo "=== Checking for OOM Kill ==="
docker inspect $WORKER | grep -A5 -B5 "OOMKilled"
echo ""

# Check memory usage
echo "=== Memory Stats ==="
docker stats --no-stream $WORKER
echo ""

# Check last 50 lines of logs
echo "=== Last 50 log lines ==="
docker logs --tail 50 $WORKER 2>&1
echo ""

# Check dmesg for OOM
echo "=== System OOM Messages ==="
sudo dmesg | grep -i "killed process" | tail -5
echo ""

# Quick memory check
echo "=== System Memory ==="
free -h