#!/bin/bash

# Name of Application: Catalyst Trading System
# Name of file: catalyst-mcp.sh
# Version: 3.0.1
# Last Updated: 2025-01-31
# Purpose: Management script for Catalyst Trading System MCP Docker deployment

# REVISION HISTORY:
# v3.0.1 (2025-01-31) - Fixed service names to match docker-compose.yml
# v3.0.0 (2025-08-16) - Complete management script for MCP architecture
# - Docker Compose orchestration
# - Health monitoring for all services
# - Database connectivity testing
# - Log management
# - Backup and restore capabilities
# - Service debugging tools

# Description of Service:
# Comprehensive management script for the Catalyst Trading System running
# in Docker containers with DigitalOcean managed PostgreSQL database.
# Provides easy commands for deployment, monitoring, and maintenance.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
ENV_FILE="${PROJECT_ROOT}/config/.env"  # Changed to config/.env
LOG_DIR="${PROJECT_ROOT}/logs"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Service names (FIXED to match docker-compose.yml)
SERVICES=(
    "orchestration-service"
    "news-service"
    "scanner-service"
    "pattern-service"
    "technical-service"
    "trading-service"
    "reporting-service"
    "redis"
)

# Create directories if they don't exist
mkdir -p "${LOG_DIR}" "${BACKUP_DIR}"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check environment file
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file not found at $ENV_FILE"
        log_info "Please create the environment file with your configuration."
        exit 1
    fi
    
    # Check docker-compose.yml
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose file not found at $COMPOSE_FILE"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Test database connection
test_database() {
    log_info "Testing database connection..."
    
    # Load database URL from env file
    if [[ -f "$ENV_FILE" ]]; then
        export $(grep -E '^DATABASE_URL=' "$ENV_FILE" | xargs)
    fi
    
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not found in environment file"
        return 1
    fi
    
    # Test connection using psql
    if command -v psql &> /dev/null; then
        if psql "$DATABASE_URL" -c "SELECT current_database(), version();" &> /dev/null; then
            log_success "Database connection successful"
            return 0
        else
            log_error "Failed to connect to database"
            log_info "Please check your DATABASE_URL in $ENV_FILE"
            return 1
        fi
    else
        log_warning "psql not installed, skipping database test"
        log_info "Install postgresql-client to enable database testing"
        return 0
    fi
}

# Start all services
start_services() {
    log_info "Starting Catalyst Trading System services..."
    
    check_prerequisites
    
    cd "$PROJECT_ROOT"
    docker-compose up -d
    
    log_success "Services started. Waiting for health checks..."
    sleep 10
    
    check_health
}

# Stop all services
stop_services() {
    log_info "Stopping Catalyst Trading System services..."
    
    cd "$PROJECT_ROOT"
    docker-compose down
    
    log_success "All services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting Catalyst Trading System services..."
    
    stop_services
    sleep 5
    start_services
}

# Fresh start (clean volumes and restart)
fresh_start() {
    log_warning "This will remove all Docker volumes and start fresh!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cancelled"
        return
    fi
    
    log_info "Performing fresh start..."
    
    cd "$PROJECT_ROOT"
    
    # Stop and remove containers, volumes
    docker-compose down -v
    
    # Remove any dangling volumes
    docker volume prune -f
    
    # Clear logs
    rm -rf "${LOG_DIR:?}"/*
    
    log_success "Cleaned up old data"
    
    # Start fresh
    start_services
}

# Check health of all services
check_health() {
    log_info "Checking health of all services..."
    
    local all_healthy=true
    
    for service in "${SERVICES[@]}"; do
        if [[ "$service" == "redis" ]]; then
            # Special health check for Redis
            if docker-compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" ping &> /dev/null; then
                echo -e "${GREEN}✓${NC} $service: HEALTHY"
            else
                echo -e "${RED}✗${NC} $service: UNHEALTHY"
                all_healthy=false
            fi
        else
            # HTTP health check for other services
            local container_name="catalyst-${service%-service}"  # Remove -service suffix for container name
            local container_id=$(docker ps -q -f name="$container_name")
            
            if [[ -n "$container_id" ]]; then
                local running=$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null)
                
                if [[ "$running" == "true" ]]; then
                    # Get port from service name (FIXED PORT MAPPING)
                    local port
                    case "$service" in
                        "orchestration-service") port=5000 ;;
                        "news-service") port=5008 ;;
                        "scanner-service") port=5001 ;;
                        "pattern-service") port=5002 ;;
                        "technical-service") port=5003 ;;
                        "trading-service") port=5005 ;;
                        "reporting-service") port=5009 ;;
                        *) port=5000 ;;
                    esac
                    
                    # Try health endpoint
                    if curl -sf "http://localhost:$port/health" &> /dev/null; then
                        echo -e "${GREEN}✓${NC} $service: HEALTHY"
                    else
                        echo -e "${YELLOW}⚠${NC} $service: RUNNING (no health endpoint)"
                    fi
                else
                    echo -e "${RED}✗${NC} $service: NOT RUNNING"
                    all_healthy=false
                fi
            else
                echo -e "${RED}✗${NC} $service: NOT FOUND"
                all_healthy=false
            fi
        fi
    done
    
    if $all_healthy; then
        log_success "All services are healthy"
    else
        log_warning "Some services are not healthy"
    fi
}

# View logs
view_logs() {
    local service="${1:-}"
    
    if [[ -z "$service" ]]; then
        log_info "Following logs for all services..."
        cd "$PROJECT_ROOT"
        docker-compose logs -f --tail=100
    else
        log_info "Following logs for $service..."
        cd "$PROJECT_ROOT"
        docker-compose logs -f --tail=100 "$service"
    fi
}

# Show service status
show_status() {
    log_info "Catalyst Trading System Status"
    echo "================================"
    
    cd "$PROJECT_ROOT"
    docker-compose ps
    
    echo
    echo "Container Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | grep catalyst || true
}

# Backup data
backup_data() {
    log_info "Creating backup..."
    
    local backup_name="catalyst_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    mkdir -p "$backup_path"
    
    # Backup Redis data
    log_info "Backing up Redis data..."
    docker-compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}" BGSAVE
    sleep 5
    docker cp "$(docker-compose ps -q redis):/data/dump.rdb" "${backup_path}/redis_dump.rdb"
    
    # Backup logs
    log_info "Backing up logs..."
    if [ -d "${LOG_DIR}" ]; then
        cp -r "${LOG_DIR}" "${backup_path}/logs"
    fi
    
    # Backup environment (without sensitive data)
    log_info "Backing up configuration..."
    grep -v "PASSWORD\|KEY\|SECRET" "$ENV_FILE" > "${backup_path}/env_sanitized"
    
    # Create tarball
    cd "$BACKUP_DIR"
    tar -czf "${backup_name}.tar.gz" "$backup_name"
    rm -rf "$backup_name"
    
    log_success "Backup created: ${BACKUP_DIR}/${backup_name}.tar.gz"
}

# Execute command in service
exec_service() {
    local service="$1"
    shift
    local cmd="$@"
    
    log_info "Executing in $service: $cmd"
    cd "$PROJECT_ROOT"
    docker-compose exec "$service" $cmd
}

# Database console
db_console() {
    log_info "Opening database console..."
    
    # Load database URL
    if [[ -f "$ENV_FILE" ]]; then
        export $(grep -E '^DATABASE_URL=' "$ENV_FILE" | xargs)
    fi
    
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not found in environment file"
        return 1
    fi
    
    psql "$DATABASE_URL"
}

# Redis console
redis_console() {
    log_info "Opening Redis console..."
    cd "$PROJECT_ROOT"
    # Include password in Redis CLI connection
    docker-compose exec redis redis-cli -a "${REDIS_PASSWORD:-RedisCatalyst2025!SecureCache}"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    cd "$PROJECT_ROOT"
    docker-compose build --no-cache
    log_success "Docker images built successfully"
}

# Show info
show_info() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Catalyst Trading System MCP Information      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${YELLOW}Service Ports:${NC}"
    echo "  Orchestration: 5000"
    echo "  News Service:  5008"
    echo "  Scanner:       5001"
    echo "  Pattern:       5002"
    echo "  Technical:     5003"
    echo "  Trading:       5005"
    echo "  Reporting:     5009"
    echo "  Redis:         6379"
    echo
    echo -e "${YELLOW}Claude Desktop MCP:${NC}"
    echo "  Connect to: ws://localhost:5000/mcp"
    echo
    echo -e "${YELLOW}Configuration:${NC}"
    echo "  Environment: $ENV_FILE"
    echo "  Logs:        $LOG_DIR"
    echo "  Backups:     $BACKUP_DIR"
}

# Show help
show_help() {
    echo "Catalyst Trading System Management Script"
    echo "========================================="
    echo
    echo "Usage: $0 [command] [options]"
    echo
    echo "Commands:"
    echo "  start             Start all services"
    echo "  stop              Stop all services"
    echo "  restart           Restart all services"
    echo "  fresh-start       Clean start (removes all data)"
    echo "  build             Build Docker images"
    echo "  status            Show service status"
    echo "  health            Check health of all services"
    echo "  info              Show system information"
    echo "  logs [service]    View logs (all services or specific)"
    echo "  test-db           Test database connection"
    echo "  backup            Create backup of data"
    echo "  exec <service> <cmd>  Execute command in service"
    echo "  db-console        Open PostgreSQL console"
    echo "  redis-console     Open Redis console"
    echo "  help              Show this help message"
    echo
    echo "Examples:"
    echo "  $0 start                    # Start all services"
    echo "  $0 logs trading-service     # View trading service logs"
    echo "  $0 exec redis redis-cli     # Open Redis CLI"
    echo "  $0 health                   # Check all services"
}

# Main command handling
main() {
    case "${1:-help}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        fresh-start)
            fresh_start
            ;;
        build)
            build_images
            ;;
        status)
            show_status
            ;;
        health)
            check_health
            ;;
        info)
            show_info
            ;;
        logs)
            view_logs "${2:-}"
            ;;
        test-db)
            test_database
            ;;
        backup)
            backup_data
            ;;
        exec)
            shift
            exec_service "$@"
            ;;
        db-console)
            db_console
            ;;
        redis-console)
            redis_console
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"