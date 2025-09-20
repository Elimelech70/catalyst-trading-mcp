################################################################################
# scripts/production-manager.sh
# Save this to docker/scripts/manage.sh and chmod +x
################################################################################
# scripts/production-manager.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"
LOG_DIR="./logs"

# Create necessary directories
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗ $1${NC}"
}

# Check if market is open
is_market_open() {
    local current_time=$(date +%H%M)
    local current_day=$(date +%u)  # 1=Monday, 7=Sunday

    # Monday-Friday, 9:30 AM - 4:00 PM EST
    if [[ $current_day -ge 1 && $current_day -le 5 ]]; then
        if [[ $current_time -ge 0930 && $current_time -le 1600 ]]; then
            return 0  # Market is open
        fi
    fi
    return 1  # Market is closed
}

# Market hours aware startup
start_system() {
    print_status "Starting Catalyst Trading System..."

    # Load environment
    if [[ -f .env ]]; then
        source .env
    else
        print_error ".env file not found!"
        exit 1
    fi

    # Check if already running
    if docker-compose -f $COMPOSE_FILE ps | grep -q "Up"; then
        print_warning "System appears to be already running"
        return 1
    fi

    # Start infrastructure first
    print_status "Starting infrastructure services..."
    docker-compose -f $COMPOSE_FILE up -d postgres redis

    # Wait for infrastructure to be healthy
    print_status "Waiting for infrastructure to be ready..."
    local retries=0
    while [[ $retries -lt 30 ]]; do
        if docker-compose -f $COMPOSE_FILE ps postgres | grep -q "healthy" && \
           docker-compose -f $COMPOSE_FILE ps redis | grep -q "healthy"; then
            break
        fi
        sleep 2
        ((retries++))
    done

    if [[ $retries -eq 30 ]]; then
        print_error "Infrastructure failed to start properly"
        return 1
    fi

    # Start core services in order
    print_status "Starting core services..."
    docker-compose -f $COMPOSE_FILE up -d orchestration news
    sleep 10

    docker-compose -f $COMPOSE_FILE up -d scanner pattern technical
    sleep 10

    docker-compose -f $COMPOSE_FILE up -d trading reporting
    sleep 10

    # Start monitoring
    docker-compose -f $COMPOSE_FILE up -d system-monitor

    print_success "All services started successfully"

    # Market hours message
    if is_market_open; then
        print_status "🟢 Market is OPEN - System ready for trading"
    else
        print_status "🔴 Market is CLOSED - System in monitoring mode"
    fi

    # Show status
    sleep 5
    status_check
}

# Graceful shutdown
stop_system() {
    print_status "Stopping Catalyst Trading System..."

    # Stop in reverse order
    docker-compose -f $COMPOSE_FILE stop system-monitor
    docker-compose -f $COMPOSE_FILE stop reporting trading
    docker-compose -f $COMPOSE_FILE stop technical pattern scanner
    docker-compose -f $COMPOSE_FILE stop news orchestration
    docker-compose -f $COMPOSE_FILE stop redis postgres

    print_success "System stopped gracefully"
}

# Health check
status_check() {
    print_status "System Health Check"
    echo "=================================================="

    # Check each service
    services=("postgres" "redis" "orchestration" "news" "scanner" "pattern" "technical" "trading" "reporting")

    for service in "${services[@]}"; do
        status=$(docker-compose -f $COMPOSE_FILE ps $service 2>/dev/null | tail -n +3 | awk '{print $4}')
        if [[ "$status" == *"Up"* ]]; then
            if [[ "$status" == *"healthy"* ]]; then
                echo -e "$service: ${GREEN}Healthy${NC}"
            else
                echo -e "$service: ${YELLOW}Running (health check pending)${NC}"
            fi
        else
            echo -e "$service: ${RED}Down${NC}"
        fi
    done

    echo "=================================================="

    # Test orchestration service if running
    if curl -s http://localhost:5000/health >/dev/null 2>&1; then
        print_success "MCP orchestration service responding"
    else
        print_error "MCP orchestration service not responding"
    fi

    # Database connectivity
    if docker-compose -f $COMPOSE_FILE exec -T postgres pg_isready -U catalyst_user -d catalyst_trading >/dev/null 2>&1; then
        print_success "Database connectivity verified"
    else
        print_error "Database connectivity failed"
    fi
}

# Backup database
backup_database() {
    print_status "Creating database backup..."

    local backup_file="$BACKUP_DIR/catalyst_backup_$(date +%Y%m%d_%H%M%S).sql"

    docker-compose -f $COMPOSE_FILE exec -T postgres pg_dump \
        -U catalyst_user \
        -d catalyst_trading \
        --clean \
        --if-exists \
        > "$backup_file"

    if [[ $? -eq 0 ]]; then
        print_success "Database backup created: $backup_file"

        # Compress backup
        gzip "$backup_file"
        print_success "Backup compressed: ${backup_file}.gz"

        # Clean old backups (keep last 7 days)
        find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
    else
        print_error "Database backup failed"
        return 1
    fi
}

# Market hours automation
schedule_market_operations() {
    print_status "Setting up market hours automation..."

    # Create cron jobs for market operations
    cat > /tmp/catalyst_cron << EOF
# Catalyst Trading System Market Hours Automation

# Pre-market startup (4:00 AM EST)
0 4 * * 1-5 /path/to/catalyst/scripts/production-manager.sh start

# Market open notification (9:30 AM EST)
30 9 * * 1-5 /path/to/catalyst/scripts/production-manager.sh notify_market_open

# Market close operations (4:00 PM EST)
0 16 * * 1-5 /path/to/catalyst/scripts/production-manager.sh market_close

# After-hours shutdown (8:00 PM EST)
0 20 * * 1-5 /path/to/catalyst/scripts/production-manager.sh stop

# Weekend maintenance (Sunday 2:00 AM)
0 2 * * 0 /path/to/catalyst/scripts/production-manager.sh weekly_maintenance

# Daily backup (11:00 PM)
0 23 * * * /path/to/catalyst/scripts/production-manager.sh backup_database

# Health check every 15 minutes during market hours
*/15 9-16 * * 1-5 /path/to/catalyst/scripts/production-manager.sh quick_health_check
EOF

    # Install cron jobs
    crontab /tmp/catalyst_cron
    rm /tmp/catalyst_cron

    print_success "Market hours automation configured"
}

# Quick health check for cron
quick_health_check() {
    if ! curl -s http://localhost:5000/health >/dev/null 2>&1; then
        print_error "Health check failed - attempting restart"
        docker-compose -f $COMPOSE_FILE restart orchestration

        # Send alert
        if [[ -n "$ALERT_EMAIL" ]]; then
            echo "Catalyst Trading System health check failed at $(date)" | \
                mail -s "ALERT: Trading System Issue" "$ALERT_EMAIL"
        fi
    fi
}

# Market notifications
notify_market_open() {
    print_success "🟢 MARKET OPEN - Trading system active"
    # Send notification to Claude Desktop or other monitoring
}

market_close() {
    print_status "🔴 MARKET CLOSED - Generating end-of-day reports"
    # Trigger end-of-day reporting via orchestration service
    curl -s -X POST http://localhost:5000/generate_daily_report || true
}

# Weekly maintenance
weekly_maintenance() {
    print_status "Running weekly maintenance..."

    # Backup database
    backup_database

    # Clean logs older than 30 days
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete

    # Docker system cleanup
    docker system prune -f

    # Restart system for fresh start
    stop_system
    sleep 30
    start_system

    print_success "Weekly maintenance completed"
}

# Main command handler
case "$1" in
    start)
        start_system
        ;;
    stop)
        stop_system
        ;;
    restart)
        stop_system
        sleep 10
        start_system
        ;;
    status)
        status_check
        ;;
    backup)
        backup_database
        ;;
    schedule)
        schedule_market_operations
        ;;
    quick_health_check)
        quick_health_check
        ;;
    notify_market_open)
        notify_market_open
        ;;
    market_close)
        market_close
        ;;
    weekly_maintenance)
        weekly_maintenance
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|backup|schedule}"
        echo ""
        echo "Commands:"
        echo "  start              - Start all services with market hours awareness"
        echo "  stop               - Gracefully stop all services"
        echo "  restart            - Stop and start all services"
        echo "  status             - Check health of all services"
        echo "  backup             - Create database backup"
        echo "  schedule           - Set up automated market hours operations"
        echo "  quick_health_check - Quick health check for cron"
        echo "  notify_market_open - Market open notification"
        echo "  market_close       - Market close operations"
        echo "  weekly_maintenance - Run weekly maintenance tasks"
        exit 1
        ;;
esac