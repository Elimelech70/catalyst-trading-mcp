#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: safe_install.sh
# Version: 2.0.0
# Last Updated: 2025-09-05
# Purpose: Safe installation with virtual environment and root protection

# REVISION HISTORY:
# v2.0.0 (2025-09-05) - Added root user protection and automatic venv setup
# v1.2.0 (2025-09-05) - Added comprehensive logging
# v1.1.0 (2025-09-05) - Fixed for python3/pip3 detection

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Catalyst Trading System - Safe Installer          ║${NC}"
echo -e "${CYAN}║                 DevGenius Edition 🎩                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect Python command
PYTHON_CMD=""
if command_exists python3; then
    PYTHON_CMD="python3"
elif command_exists python; then
    PYTHON_VERSION=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null)
    if [ "$PYTHON_VERSION" = "3" ]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    log_error "${RED}❌ Python 3 not found! Please install Python 3.10+${NC}"
    exit 1
fi

# CHECK FOR ROOT USER
if [ "$EUID" -eq 0 ]; then
    log_message "${RED}⚠️  WARNING: Running as root user detected!${NC}"
    log_message "${YELLOW}This can break your system Python installation.${NC}"
    log_message ""
    log_message "${CYAN}Options:${NC}"
    log_message "  1) ${GREEN}[Recommended]${NC} Let this script create a virtual environment"
    log_message "  2) Continue as root with --root-user-action=ignore ${RED}(risky)${NC}"
    log_message "  3) Exit and run as normal user"
    log_message ""
    
    echo -n "Choose option (1/2/3): "
    read -r choice
    
    case $choice in
        1)
            log_message "${GREEN}Creating virtual environment...${NC}"
            USE_VENV=true
            ;;
        2)
            log_message "${YELLOW}⚠️  Continuing as root (not recommended)${NC}"
            PIP_EXTRA_ARGS="--root-user-action=ignore"
            USE_VENV=false
            ;;
        3|*)
            log_message "${CYAN}Exiting. Please run as normal user:${NC}"
            log_message "  ${YELLOW}sudo -u youruser $0${NC}"
            log_message "  ${YELLOW}or just: ./$0 (without sudo)${NC}"
            exit 0
            ;;
    esac
else
    # Not root, check for virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        log_message "${YELLOW}📦 Not in a virtual environment${NC}"
        log_message "${CYAN}Would you like to create one? (recommended)${NC}"
        echo -n "Create virtual environment? (y/n): "
        read -r create_venv
        
        if [[ "$create_venv" =~ ^[Yy]$ ]]; then
            USE_VENV=true
        else
            USE_VENV=false
            log_message "${YELLOW}⚠️  Proceeding without virtual environment${NC}"
        fi
    else
        log_message "${GREEN}✅ Already in virtual environment: $VIRTUAL_ENV${NC}"
        USE_VENV=false
    fi
fi

# VIRTUAL ENVIRONMENT SETUP
VENV_DIR="catalyst_venv"

if [ "$USE_VENV" = true ]; then
    log_message ""
    log_message "${BLUE}Setting up virtual environment...${NC}"
    
    # Create venv if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        log_message "Creating new virtual environment: $VENV_DIR"
        $PYTHON_CMD -m venv "$VENV_DIR"
        
        if [ $? -ne 0 ]; then
            log_error "${RED}Failed to create virtual environment${NC}"
            log_message "Try installing venv: sudo apt-get install python3-venv"
            exit 1
        fi
    else
        log_message "Using existing virtual environment: $VENV_DIR"
    fi
    
    # Activate virtual environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        log_message "Activating virtual environment..."
        source "$VENV_DIR/bin/activate"
        log_message "${GREEN}✅ Virtual environment activated${NC}"
        
        # Update Python and pip commands to use venv
        PYTHON_CMD="python"
        PIP_CMD="pip"
    else
        log_error "${RED}Failed to activate virtual environment${NC}"
        exit 1
    fi
else
    # Determine pip command
    if command_exists pip3; then
        PIP_CMD="pip3"
    elif command_exists pip; then
        PIP_CMD="pip"
    else
        PIP_CMD="$PYTHON_CMD -m pip"
    fi
fi

# Add safety flags for pip
if [ -n "$PIP_EXTRA_ARGS" ]; then
    PIP_CMD="$PIP_CMD $PIP_EXTRA_ARGS"
fi

log_message ""
log_message "${CYAN}Installation Configuration:${NC}"
log_message "  Python: $PYTHON_CMD ($(which $PYTHON_CMD))"
log_message "  Pip: $PIP_CMD"
log_message "  User: $(whoami)"
log_message "  Virtual Env: ${VIRTUAL_ENV:-None}"
log_message "  Log File: $LOG_FILE"
log_message ""

# Function to install with timeout and logging
install_with_timeout() {
    local requirements_file=$1
    local service_name=$2
    local timeout_seconds=300  # 5 minutes timeout
    
    log_message "  Installing $service_name from $requirements_file"
    
    # Use timeout and add root user action if needed
    local pip_command="$PIP_CMD install -r $requirements_file --no-cache-dir"
    
    log_message "  Command: $pip_command"
    
    timeout $timeout_seconds bash -c "$pip_command" >> "$LOG_FILE" 2>&1
    
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

# Step 1: Upgrade pip and setuptools
log_message "${BLUE}Step 1: Upgrading pip and setuptools${NC}"
$PIP_CMD install --upgrade pip setuptools wheel >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log_message "  ${GREEN}✅ pip and setuptools upgraded${NC}"
else
    log_error "  ${YELLOW}⚠️  Failed to upgrade pip/setuptools${NC}"
fi
log_message ""

# Step 2: Install base requirements
log_message "${BLUE}Step 2: Installing base requirements${NC}"

# Create a minimal base requirements if it doesn't exist
if [ ! -f "requirements-base.txt" ]; then
    log_message "  Creating minimal base requirements..."
    cat > requirements-base.txt << 'EOF'
# Minimal base requirements
mcp>=1.7.0
fastmcp==0.1.2
fastapi==0.109.0
uvicorn[standard]==0.25.0
pandas==2.1.4
numpy==1.26.2
aiohttp==3.9.1
asyncpg==0.29.0
redis==5.0.1
structlog==24.1.0
python-dotenv==1.0.0
EOF
fi

install_with_timeout "requirements-base.txt" "base requirements"
log_message ""

# Step 3: Install service requirements (with option to skip problematic ones)
log_message "${BLUE}Step 3: Installing service-specific requirements${NC}"

SERVICES=(
    "services/orchestration/requirements.txt:orchestration"
    "services/security-scanner/requirements.txt:security-scanner"
    "services/pattern/requirements.txt:pattern"
    "services/technical/requirements.txt:technical"
    "services/trading/requirements.txt:trading"
    "services/reporting/requirements.txt:reporting"
    "services/news-scanner/requirements.txt:news-scanner"  # Put heavy one last
)

log_message "${YELLOW}Note: news-scanner has heavy dependencies (ML models)${NC}"
log_message "${YELLOW}It may take longer or you can skip it if needed.${NC}"
echo -n "Install news-scanner dependencies? (y/n): "
read -r install_news

SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_SERVICES=()

for service_spec in "${SERVICES[@]}"; do
    IFS=':' read -r req_file service_name <<< "$service_spec"
    
    # Skip news-scanner if user chose not to install
    if [[ "$service_name" == "news-scanner" ]] && [[ ! "$install_news" =~ ^[Yy]$ ]]; then
        log_message "${YELLOW}Skipping news-scanner${NC}"
        continue
    fi
    
    if [ -f "$req_file" ]; then
        log_message "${CYAN}Installing $service_name...${NC}"
        
        if install_with_timeout "$req_file" "$service_name"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAIL_COUNT=$((FAIL_COUNT + 1))
            FAILED_SERVICES+=("$service_name")
        fi
    else
        log_message "  ${YELLOW}⚠️  $req_file not found${NC}"
    fi
    
    log_message ""
done

# Step 4: Verify installation
log_message "${BLUE}Step 4: Verifying critical packages${NC}"

CRITICAL_PACKAGES=(
    "fastapi:FastAPI"
    "mcp:MCP Protocol"
    "fastmcp:FastMCP"
    "pandas:Pandas"
    "numpy:NumPy"
)

for package_info in "${CRITICAL_PACKAGES[@]}"; do
    IFS=':' read -r package display_name <<< "$package_info"
    
    if $PYTHON_CMD -c "import $package" 2>/dev/null; then
        log_message "  $display_name: ${GREEN}✅ Installed${NC}"
    else
        log_message "  $display_name: ${RED}❌ Not found${NC}"
    fi
done

# Create package list
$PIP_CMD freeze > installed_packages.txt 2>&1

# Final Summary
log_message ""
log_message "${GREEN}═════════════════════════════════════════════════════════${NC}"
log_message "${GREEN}           Installation Complete! 🎉                     ${NC}"
log_message "${GREEN}═════════════════════════════════════════════════════════${NC}"
log_message ""

if [ "$USE_VENV" = true ]; then
    log_message "${GREEN}✅ Virtual environment created and activated${NC}"
    log_message ""
    log_message "${CYAN}IMPORTANT: To use the installation:${NC}"
    log_message "${YELLOW}  source $VENV_DIR/bin/activate${NC}"
    log_message ""
    log_message "${CYAN}To deactivate later:${NC}"
    log_message "${YELLOW}  deactivate${NC}"
    log_message ""
fi

log_message "Installation summary:"
log_message "  Services installed: $SUCCESS_COUNT"
log_message "  Services failed: $FAIL_COUNT"
if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    log_message "  Failed: ${FAILED_SERVICES[*]}"
fi

log_message ""
log_message "Log files:"
log_message "  Full log: $LOG_FILE"
log_message "  Errors: $ERROR_LOG"
log_message "  Packages: installed_packages.txt"
log_message ""

# Create activation script for convenience
if [ "$USE_VENV" = true ]; then
    cat > activate_catalyst.sh << 'EOF'
#!/bin/bash
# Quick activation script for Catalyst Trading System
source catalyst_venv/bin/activate
echo "✅ Catalyst virtual environment activated"
echo "To deactivate: type 'deactivate'"
EOF
    chmod +x activate_catalyst.sh
    log_message "${GREEN}Created quick activation script: ./activate_catalyst.sh${NC}"
fi

log_message "${GREEN}Happy Trading, bro! 🚀${NC}"
log_message "${GREEN}DevGenius hat tips to you! 🎩${NC}"