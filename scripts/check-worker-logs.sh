#!/bin/bash

# Script to check worker logs on production server

echo "=== Celery Worker Diagnostics ==="
echo "Current time: $(date)"
echo ""

# Check running containers
echo "=== Running Containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
echo ""

# Get worker container name
WORKER_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "storytime-worker|worker" | head -1)

if [ -z "$WORKER_CONTAINER" ]; then
    echo "ERROR: No worker container found!"
    exit 1
fi

echo "Found worker container: $WORKER_CONTAINER"
echo ""

# Check container resource usage
echo "=== Container Resource Usage ==="
docker stats --no-stream $WORKER_CONTAINER
echo ""

# Check recent logs (last 100 lines)
echo "=== Recent Worker Logs (last 100 lines) ==="
docker logs --tail 100 $WORKER_CONTAINER 2>&1
echo ""

# Check for specific error patterns
echo "=== Error Summary ==="
echo "SIGKILL occurrences:"
docker logs $WORKER_CONTAINER 2>&1 | grep -c "SIGKILL"

echo "OOM (Out of Memory) indicators:"
docker logs $WORKER_CONTAINER 2>&1 | grep -i -E "memory|oom|killed" | tail -10

echo "Worker lost errors:"
docker logs $WORKER_CONTAINER 2>&1 | grep -i "WorkerLostError" | tail -10
echo ""

# Check system memory
echo "=== System Memory Info ==="
free -h
echo ""

# Check Docker daemon logs for OOM kills
echo "=== Checking for OOM kills in system logs ==="
if [ -f "/var/log/messages" ]; then
    sudo grep -i "oom-killer" /var/log/messages | tail -5
elif [ -f "/var/log/syslog" ]; then
    sudo grep -i "oom-killer" /var/log/syslog | tail -5
else
    dmesg | grep -i "oom-killer" | tail -5
fi
echo ""

# Check worker log files inside container (if they exist)
echo "=== Checking worker log files inside container ==="
docker exec $WORKER_CONTAINER sh -c "ls -la /tmp/*.log 2>/dev/null && echo '' && tail -20 /tmp/celery_*.log 2>/dev/null" || echo "No log files found in /tmp/"
echo ""

# Get container inspect info for memory limits
echo "=== Container Memory Configuration ==="
docker inspect $WORKER_CONTAINER | grep -E "Memory|CpuShares|CpuQuota" | grep -v "null"
echo ""

# Check Redis connection
echo "=== Redis Connection Test ==="
REDIS_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "redis" | head -1)
if [ ! -z "$REDIS_CONTAINER" ]; then
    docker exec $REDIS_CONTAINER redis-cli ping
    docker exec $REDIS_CONTAINER redis-cli info memory | grep -E "used_memory_human|used_memory_peak_human"
else
    echo "Redis container not found on this host"
fi
echo ""

# Suggestions
echo "=== Diagnostic Summary ==="
echo "1. If seeing SIGKILL/OOM errors, the worker is running out of memory"
echo "2. Check if specific tasks are consuming too much memory"
echo "3. Consider adding memory limits and monitoring"
echo "4. Look for stuck tasks that might be accumulating memory"
echo ""
echo "To follow logs in real-time: docker logs -f $WORKER_CONTAINER"
echo "To get into container shell: docker exec -it $WORKER_CONTAINER /bin/bash"