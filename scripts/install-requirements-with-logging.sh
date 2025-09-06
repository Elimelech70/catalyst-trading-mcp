#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: install_requirements_logged.sh
# Version: 1.2.0
# Last Updated: 2025-09-05
# Purpose: Install all Python dependencies with comprehensive logging

# REVISION HISTORY:
# v1.2.0 (2025-09-05) - Added comprehensive logging and timeout handling
# v1.1.0 (2025-09-05) - Fixed for python3/pip3 detection
# v1.0.0 (2025-09-04) - Complete installation script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Create logs directory
mkdir -p logs/install

# Create log file with timestamp
LOG_FILE="logs/install/install_$(date +%Y%m%d_%H%M%S).log"
ERROR_LOG="logs/install/install_errors_$(date +%Y%m%d_%H%M%S).log"

# Function to log messages
log_message() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "$1" | tee -a "$ERROR_LOG"
}

# Start logging
{
echo "=========================================="
echo "Catalyst Trading System - Installation Log"
echo "Started: $(date)"
echo "=========================================="
echo ""
} | tee "$LOG_FILE"

log_message "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
log_message "${CYAN}║   Catalyst Trading System - Dependency Installer    ║${NC}"
log_message "${CYAN}║                 DevGenius Edition 🎩                 ║${NC}"
log_message "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
log_message ""
log_message "${MAGENTA}📝 Full log: $LOG_FILE${NC}"
log_message "${MAGENTA}📝 Error log: $ERROR_LOG${NC}"
log_message ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Determine Python command (python vs python3)
log_message "${BLUE}Detecting Python installation...${NC}"
PYTHON_CMD=""
PIP_CMD=""

if command_exists python3; then
    PYTHON_CMD="python3"
    log_message "  ${GREEN}✓${NC} Found python3"
    log_message "  Path: $(which python3)"
elif command_exists python; then
    # Check if it's Python 3
    PYTHON_VERSION=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null)
    if [ "$PYTHON_VERSION" = "3" ]; then
        PYTHON_CMD="python"
        log_message "  ${GREEN}✓${NC} Found python (version 3)"
        log_message "  Path: $(which python)"
    else
        log_error "${RED}❌ Python 2 detected, Python 3 required${NC}"
        exit 1
    fi
else
    log_error "${RED}❌ Python not found! Please install Python 3.10+${NC}"
    log_message "${YELLOW}  Try: sudo apt-get install python3 python3-pip${NC}"
    log_message "${YELLOW}  Or:  brew install python3${NC}"
    exit 1
fi

# Determine pip command (pip vs pip3)
if command_exists pip3; then
    PIP_CMD="pip3"
    log_message "  ${GREEN}✓${NC} Found pip3"
    log_message "  Path: $(which pip3)"
elif command_exists pip; then
    PIP_CMD="pip"
    log_message "  ${GREEN}✓${NC} Found pip"
    log_message "  Path: $(which pip)"
else
    log_message "${YELLOW}⚠️  pip not found. Trying python -m pip...${NC}"
    PIP_CMD="$PYTHON_CMD -m pip"
fi

log_message "  ${CYAN}Using: $PYTHON_CMD and $PIP_CMD${NC}"
log_message ""

# Function to check Python package
check_package() {
    $PYTHON_CMD -c "import $1" 2>/dev/null
    return $?
}

# Function to install with timeout and logging
install_with_timeout() {
    local requirements_file=$1
    local service_name=$2
    local timeout_seconds=300  # 5 minutes timeout
    
    log_message "  Installing $service_name from $requirements_file"
    log_message "  Command: $PIP_CMD install -r $requirements_file --no-cache-dir"
    
    # Run pip install with timeout and capture output
    timeout $timeout_seconds $PIP_CMD install -r "$requirements_file" --no-cache-dir -v \
        >> "$LOG_FILE" 2>&1
    
    local exit_code=$?
    
    if [ $exit_code -eq 124 ]; then
        log_error "  ${RED}❌ Timeout after ${timeout_seconds} seconds${NC}"
        return 1
    elif [ $exit_code -eq 0 ]; then
        log_message "  ${GREEN}✅ $service_name installed successfully${NC}"
        return 0
    else
        log_error "  ${RED}❌ Failed to install $service_name (exit code: $exit_code)${NC}"
        return 1
    fi
}

# Step 1: Check Python version
log_message "${BLUE}Step 1: Checking Python environment${NC}"
PYTHON_FULL_VERSION=$($PYTHON_CMD --version 2>&1)
log_message "  Python version: $PYTHON_FULL_VERSION"

# Get detailed version info
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null)
log_message "  Python detailed version: $PYTHON_VERSION"

# Check pip version
PIP_VERSION=$($PIP_CMD --version 2>&1)
log_message "  Pip version: $PIP_VERSION"

log_message "  ${GREEN}✅ Python environment OK${NC}"
log_message ""

# Step 2: Upgrade pip and setuptools
log_message "${BLUE}Step 2: Upgrading pip and setuptools${NC}"
log_message "  Running: $PIP_CMD install --upgrade pip setuptools wheel"

$PIP_CMD install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    log_message "  ${GREEN}✅ pip and setuptools upgraded${NC}"
else
    log_error "  ${YELLOW}⚠️  Failed to upgrade pip/setuptools${NC}"
fi
log_message ""

# Step 3: Install TA-Lib (optional, with timeout)
log_message "${BLUE}Step 3: Checking TA-Lib (Technical Analysis Library)${NC}"

if check_package "talib"; then
    log_message "  ${GREEN}✅ TA-Lib already installed${NC}"
else
    log_message "  ${YELLOW}⚠️  TA-Lib not installed (optional)${NC}"
    log_message "  To install: See https://github.com/mrjbq7/ta-lib#installation"
fi
log_message ""

# Step 4: Install base requirements
log_message "${BLUE}Step 4: Installing base requirements${NC}"

if [ -f "requirements-base.txt" ]; then
    install_with_timeout "requirements-base.txt" "base requirements"
elif [ -f "requirements.txt" ]; then
    install_with_timeout "requirements.txt" "requirements"
else
    log_message "  ${YELLOW}⚠️  No base requirements file found${NC}"
fi
log_message ""

# Step 5: Install service-specific requirements
log_message "${BLUE}Step 5: Installing service-specific requirements${NC}"
log_message "  This may take several minutes per service..."
log_message ""

SERVICES=(
    "services/orchestration/requirements.txt:orchestration"
    "services/news-scanner/requirements.txt:news-scanner"
    "services/security-scanner/requirements.txt:security-scanner"
    "services/pattern/requirements.txt:pattern"
    "services/technical/requirements.txt:technical"
    "services/trading/requirements.txt:trading"
    "services/reporting/requirements.txt:reporting"
)

FAILED_SERVICES=()
SUCCESS_COUNT=0
FAIL_COUNT=0

for service_spec in "${SERVICES[@]}"; do
    IFS=':' read -r req_file service_name <<< "$service_spec"
    
    if [ -f "$req_file" ]; then
        log_message "${CYAN}Installing $service_name...${NC}"
        
        # Show the file size for debugging
        file_size=$(wc -l < "$req_file")
        log_message "  Requirements file has $file_size lines"
        
        # Try to install
        if install_with_timeout "$req_file" "$service_name"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAIL_COUNT=$((FAIL_COUNT + 1))
            FAILED_SERVICES+=("$service_name")
            log_error "  ${RED}Failed to install $service_name - continuing...${NC}"
        fi
    else
        log_message "  ${YELLOW}⚠️  $req_file not found${NC}"
    fi
    
    log_message ""
done

log_message "Service installation summary:"
log_message "  ${GREEN}✅ Successful: $SUCCESS_COUNT${NC}"
log_message "  ${RED}❌ Failed: $FAIL_COUNT${NC}"

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    log_message "  Failed services: ${FAILED_SERVICES[*]}"
fi
log_message ""

# Step 6: Install NLTK data (with timeout)
log_message "${BLUE}Step 6: Installing NLTK data for sentiment analysis${NC}"

timeout 60 $PYTHON_CMD -c "
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

print('Downloading NLTK data...')
nltk.download('vader_lexicon', quiet=False)
nltk.download('punkt', quiet=False)
nltk.download('stopwords', quiet=False)
print('NLTK data downloaded')
" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log_message "  ${GREEN}✅ NLTK data downloaded${NC}"
else
    log_message "  ${YELLOW}⚠️  Some NLTK data may need manual download${NC}"
fi
log_message ""

# Step 7: Verify critical packages
log_message "${BLUE}Step 7: Verifying critical package installations${NC}"

CRITICAL_PACKAGES=(
    "fastapi:FastAPI"
    "mcp:MCP Protocol"
    "fastmcp:FastMCP"
    "pandas:Pandas"
    "numpy:NumPy"
    "aiohttp:AioHTTP"
    "asyncpg:AsyncPG"
    "redis:Redis"
    "structlog:Structlog"
)

all_good=true
for package_info in "${CRITICAL_PACKAGES[@]}"; do
    IFS=':' read -r package display_name <<< "$package_info"
    
    if check_package "$package"; then
        log_message "  ${display_name}: ${GREEN}✅ Installed${NC}"
    else
        log_message "  ${display_name}: ${RED}❌ Not found${NC}"
        all_good=false
    fi
done

# Check special packages
if check_package "talib"; then
    log_message "  TA-Lib: ${GREEN}✅ Installed${NC}"
else
    log_message "  TA-Lib: ${YELLOW}⚠️  Optional${NC}"
fi

log_message ""

# Step 8: Create pip freeze file
log_message "${BLUE}Step 8: Creating package list${NC}"
$PIP_CMD freeze > installed_packages.txt 2>&1
log_message "  ${GREEN}✅ Package list saved to: installed_packages.txt${NC}"
log_message ""

# Final Summary
log_message "${GREEN}═════════════════════════════════════════════════════════${NC}"
log_message "${GREEN}           Installation Complete! 🎉                     ${NC}"
log_message "${GREEN}═════════════════════════════════════════════════════════${NC}"
log_message ""

if [ "$all_good" = true ] && [ $FAIL_COUNT -eq 0 ]; then
    log_message "${GREEN}✅ All packages installed successfully!${NC}"
else
    log_message "${YELLOW}⚠️  Some packages may need manual installation${NC}"
    log_message "Check the error log: $ERROR_LOG"
fi

log_message ""
log_message "${CYAN}Environment Info:${NC}"
log_message "  Python: $(which $PYTHON_CMD)"
log_message "  Pip: $(which $PIP_CMD 2>/dev/null || echo '$PYTHON_CMD -m pip')"
log_message "  Python Version: $PYTHON_VERSION"
log_message "  Virtual Env: ${VIRTUAL_ENV:-Not activated}"
log_message ""

log_message "${CYAN}Log files:${NC}"
log_message "  Full log: $LOG_FILE"
log_message "  Error log: $ERROR_LOG"
log_message "  Package list: installed_packages.txt"
log_message ""

# Show tail of log for immediate issues
if [ -s "$ERROR_LOG" ]; then
    log_message "${YELLOW}Recent errors:${NC}"
    tail -n 10 "$ERROR_LOG" | while IFS= read -r line; do
        log_message "  $line"
    done
fi

log_message ""
log_message "Installation finished at: $(date)"
log_message ""
log_message "${GREEN}Happy Trading, bro! 🚀${NC}"
log_message "${GREEN}DevGenius hat tips to you! 🎩${NC}"

# Final message outside of logging
echo ""
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo -e "${CYAN}  To view the full installation log:${NC}"
echo -e "${CYAN}  cat $LOG_FILE${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"