#!/bin/bash
echo "Testing complete workflow execution..."

# Start workflow in test mode
response=$(curl -sf -X POST http://localhost:5006/api/v1/workflow/start \
    -H "Content-Type: application/json" \
    -d '{"mode": "test", "max_positions": 1, "risk_per_trade": 0.001}')

if [ $? -eq 0 ]; then
    cycle_id=$(echo "$response" | jq -r '.cycle_id')
    echo "[OK] Workflow started: $cycle_id"
    
    # Monitor for completion (max 5 minutes)
    timeout=300
    elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        status=$(curl -sf "http://localhost:5006/api/v1/workflow/status/$cycle_id" | jq -r '.status')
        
        if [ "$status" == "completed" ]; then
            echo "[OK] Workflow completed successfully"
            exit 0
        elif [ "$status" == "error" ]; then
            echo "[ERROR] Workflow failed"
            exit 1
        fi
        
        echo "  Status: $status (elapsed: ${elapsed}s)"
        sleep 30
        elapsed=$((elapsed + 30))
    done
    
    echo "[ERROR] Workflow timeout"
    exit 1
else
    echo "[ERROR] Failed to start workflow"
    exit 1
fi
