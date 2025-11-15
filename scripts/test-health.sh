#!/bin/bash
echo "Testing service health..."

services=(
    "orchestration:5000"
    "workflow:5006"
    "scanner:5001"
    "pattern:5002"
    "technical:5003"
    "risk-manager:5004"
    "trading:5005"
    "news:5008"
    "reporting:5009"
)

failed=0
for service in "${services[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"
    
    if curl -sf "http://localhost:$port/health" >/dev/null 2>&1; then
        echo "[OK] $name"
    else
        echo "[ERROR] $name FAILED"
        failed=$((failed + 1))
    fi
done

if [ $failed -eq 0 ]; then
    echo "[OK] All services healthy"
    exit 0
else
    echo "[ERROR] $failed services failed"
    exit 1
fi
