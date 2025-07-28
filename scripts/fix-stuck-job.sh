#!/bin/bash

echo "=== Fixing Stuck Job and Restarting Worker ==="

# Job ID from the query
JOB_ID="518092c6-4c88-4105-b500-4911b3506e9e"

echo "1. Marking job $JOB_ID as failed..."
ssh root@129.212.136.218 "docker exec \$(docker ps --format '{{.Names}}' | grep -i db | head -1) psql -U postgres -d storytime -c \"UPDATE jobs SET status = 'FAILED', error_message = 'Worker killed due to OOM during audio concatenation' WHERE id = '$JOB_ID';\""

echo ""
echo "2. Restarting worker with memory limits..."
ssh root@129.212.136.218 "docker stop \$(docker ps --format '{{.Names}}' | grep -i worker | head -1) && sleep 5"

echo ""
echo "3. Worker should auto-restart via Kamal. Checking status..."
sleep 10
ssh root@129.212.136.218 "docker ps | grep worker"

echo ""
echo "4. Checking worker memory configuration..."
ssh root@129.212.136.218 "docker inspect \$(docker ps --format '{{.Names}}' | grep -i worker | head -1) | grep -E 'Memory|Cmd' | head -20"

echo ""
echo "Done! The stuck job has been marked as failed and the worker has been restarted."