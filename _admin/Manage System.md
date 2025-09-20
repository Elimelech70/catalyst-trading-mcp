#-------------------------------------------------------------------
# Monitoring System

# Watch for new scans every 5 minutes
tail -f scheduler.log

# Monitor scanner activity
  docker-compose logs -f scanner | grep "Scan completed"





#-------------------------------------------------------------------
# scheduler - Starts the System
# And the code to show it is running - 73162
#-------------------------------------------------------------------

# check scheduler is running

root@catalyst-trading-prod-01:~/catalyst-trading-mcp# ps aux | grep scheduler.py
root       73162  1.0  0.8  59944 32172 pts/0    S    06:09   0:00 python3 scheduler.py
root       73360  0.0  0.0   7016  2272 pts/0    S+   06:10   0:00 grep --color=auto scheduler.py

#----------------------------------------------
# Script to get all logs
# get-logs.sh
#----------------------------------------------
Puts logs in combined.log


# ----------------------------------------------
# starting service after py file updates

# Command		            Purpose 			                  When to Use
docker-compose up     	Creates + Starts containers	    First time or after changes
docker-compose start	  Only Starts existing containers	Resume stopped containers

# After changes to Py or Docker or Reqirements.txt
docker-compose up -d --build scanner

# If you change docker-compose.yml
docker-compose up -d --build --force-recreate

# Check if service is running
docker-compose ps scanner

# View logs to confirm successful restart
docker-compose logs -f scanner



#----------------------------------------------------------
# build
When You MUST Build:
✅ Required when:

First time setup
Code changes in scanner-service.py
Dockerfile changes
requirements.txt changes
New dependencies added

❌ NOT needed when:

Just changing environment variables
Restarting existing containers
Only config/docker-compose.yml changes