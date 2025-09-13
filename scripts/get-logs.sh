# Save each service log to its own file
for service in orchestration risk-manager scanner pattern trading news reporting; do \
  docker-compose logs $service --tail=50 > logs/$service.log 2>&1; \
done

# Concatenate all logs into one file with headers
echo "=== CATALYST TRADING SYSTEM LOGS ===" > logs/combined.log
echo "Generated: $(date)" >> logs/combined.log
echo "" >> logs/combined.log

for service in orchestration risk-manager scanner pattern trading news reporting; do \
  echo "=== $service ===" >> logs/combined.log; \
  cat logs/$service.log >> logs/combined.log; \
  echo "" >> logs/combined.log; \
done

# View the combined file
cat logs/combined.log