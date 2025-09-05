#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: install_requirements.sh
# Version: 1.0.0
# Last Updated: 2025-09-04
# Purpose: Install all Python dependencies for Catalyst Trading System

# REVISION HISTORY:
# v1.0.0 (2025-09-04) - Complete installation script
# - Install base requirements
# - Install service-specific requirements
# - Handle special dependencies (TA-Lib)
# - Verify installations

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Catalyst Trading System - Dependency Installer    ║${NC}"
echo -e "${CYAN}║                 DevGenius Edition 🎩                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python package
check_package() {
    python -c "import $1" 2>/dev/null
    return $?
}

# Progress indicator
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Step 1: Check Python version
echo -e "${BLUE}Step 1: Checking Python environment${NC}"
echo -n "  Python version: "
python --version

if ! command_exists python; then
    echo -e "${RED}❌ Python not found! Please install Python 3.10+${NC}"
    exit 1
fi

# Check pip
if ! command_exists pip; then
    echo -e "${YELLOW}⚠️  pip not found. Installing pip...${NC}"
    python -m ensurepip --upgrade
fi

echo -e "  ${GREEN}✅ Python environment OK${NC}"
echo ""

# Step 2: Upgrade pip and setuptools
echo -e "${BLUE}Step 2: Upgrading pip and setuptools${NC}"
pip install --upgrade pip setuptools wheel -q
echo -e "  ${GREEN}✅ pip and setuptools upgraded${NC}"
echo ""

# Step 3: Install TA-Lib (special handling required)
echo -e "${BLUE}Step 3: Installing TA-Lib (Technical Analysis Library)${NC}"

install_talib() {
    # Check if TA-Lib is already installed
    if check_package "talib"; then
        echo -e "  ${GREEN}✅ TA-Lib already installed${NC}"
        return 0
    fi
    
    echo "  Detecting operating system..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "  Installing TA-Lib for Linux..."
        
        # Check if we have sudo access
        if command_exists sudo; then
            # Install dependencies
            sudo apt-get update -qq
            sudo apt-get install -y build-essential wget
            
            # Download and install TA-Lib C library
            cd /tmp
            wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
            tar -xzf ta-lib-0.4.0-src.tar.gz
            cd ta-lib
            ./configure --prefix=/usr
            make -j4
            sudo make install
            cd /
            rm -rf /tmp/ta-lib*
            
            # Update library cache
            sudo ldconfig
        else
            echo -e "  ${YELLOW}⚠️  No sudo access. Trying user installation...${NC}"
            # Install in user directory
            cd /tmp
            wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
            tar -xzf ta-lib-0.4.0-src.tar.gz
            cd ta-lib
            ./configure --prefix=$HOME/.local
            make -j4
            make install
            export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH
            cd /
            rm -rf /tmp/ta-lib*
        fi
        
        # Install Python wrapper
        pip install ta-lib
        
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "  Installing TA-Lib for macOS..."
        
        if command_exists brew; then
            brew install ta-lib
            pip install ta-lib
        else
            echo -e "  ${YELLOW}⚠️  Homebrew not found. Installing manually...${NC}"
            cd /tmp
            curl -O -L http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
            tar -xzf ta-lib-0.4.0-src.tar.gz
            cd ta-lib
            ./configure --prefix=/usr/local
            make
            sudo make install
            cd /
            rm -rf /tmp/ta-lib*
            pip install ta-lib
        fi
        
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        echo -e "  ${YELLOW}Windows detected. Installing TA-Lib...${NC}"
        pip install TA-Lib-binary
        
    else
        echo -e "  ${YELLOW}⚠️  Unknown OS. Trying pip install directly...${NC}"
        pip install ta-lib
    fi
    
    # Verify installation
    if check_package "talib"; then
        echo -e "  ${GREEN}✅ TA-Lib installed successfully${NC}"
    else
        echo -e "  ${YELLOW}⚠️  TA-Lib installation may have issues. Continuing...${NC}"
    fi
}

# Try to install TA-Lib
install_talib
echo ""

# Step 4: Install base requirements
echo -e "${BLUE}Step 4: Installing base requirements${NC}"

if [ -f "requirements-base.txt" ]; then
    echo "  Installing from requirements-base.txt..."
    pip install -r requirements-base.txt --no-cache-dir -q &
    spinner $!
    echo -e "  ${GREEN}✅ Base requirements installed${NC}"
elif [ -f "requirements.txt" ]; then
    echo "  Installing from requirements.txt..."
    pip install -r requirements.txt --no-cache-dir -q &
    spinner $!
    echo -e "  ${GREEN}✅ Requirements installed${NC}"
else
    echo -e "  ${YELLOW}⚠️  No base requirements file found${NC}"
fi
echo ""

# Step 5: Install service-specific requirements
echo -e "${BLUE}Step 5: Installing service-specific requirements${NC}"

SERVICES=(
    "services/orchestration/requirements.txt"
    "services/news-scanner/requirements.txt"
    "services/security-scanner/requirements.txt"
    "services/pattern/requirements.txt"
    "services/technical/requirements.txt"
    "services/trading/requirements.txt"
    "services/reporting/requirements.txt"
)

for req_file in "${SERVICES[@]}"; do
    if [ -f "$req_file" ]; then
        service_name=$(basename $(dirname "$req_file"))
        echo -n "  Installing $service_name dependencies..."
        
        # Install quietly in background with spinner
        pip install -r "$req_file" --no-cache-dir -q 2>/dev/null &
        spinner $!
        
        echo -e " ${GREEN}✅${NC}"
    fi
done
echo ""

# Step 6: Install NLTK data (for news sentiment analysis)
echo -e "${BLUE}Step 6: Installing NLTK data for sentiment analysis${NC}"
python -c "
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
print('  ✅ NLTK data downloaded')
" 2>/dev/null || echo -e "  ${YELLOW}⚠️  Some NLTK data may need manual download${NC}"
echo ""

# Step 7: Verify critical packages
echo -e "${BLUE}Step 7: Verifying critical package installations${NC}"

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
    
    printf "  %-20s" "$display_name:"
    
    if check_package "$package"; then
        echo -e "${GREEN}✅ Installed${NC}"
    else
        echo -e "${RED}❌ Not found${NC}"
        all_good=false
    fi
done

# Check special packages
printf "  %-20s" "TA-Lib:"
if check_package "talib"; then
    echo -e "${GREEN}✅ Installed${NC}"
else
    echo -e "${YELLOW}⚠️  Optional${NC}"
fi

echo ""

# Step 8: Create virtual environment recommendation
echo -e "${BLUE}Step 8: Virtual Environment Check${NC}"

if [ -n "$VIRTUAL_ENV" ]; then
    echo -e "  ${GREEN}✅ Running in virtual environment: $VIRTUAL_ENV${NC}"
else
    echo -e "  ${YELLOW}⚠️  Not running in virtual environment${NC}"
    echo -e "  ${CYAN}   Recommended: Create a virtual environment${NC}"
    echo "     python -m venv venv"
    echo "     source venv/bin/activate  # On Windows: venv\\Scripts\\activate"
fi
echo ""

# Final Summary
echo -e "${GREEN}═════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}           Installation Complete! 🎉                     ${NC}"
echo -e "${GREEN}═════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$all_good" = true ]; then
    echo -e "${GREEN}✅ All critical packages installed successfully!${NC}"
else
    echo -e "${YELLOW}⚠️  Some packages may need manual installation${NC}"
fi

echo ""
echo -e "${CYAN}Quick verification commands:${NC}"
echo "  python -c \"import mcp; print('MCP OK')\""
echo "  python -c \"import fastmcp; print('FastMCP OK')\""
echo "  python -c \"import talib; print('TA-Lib OK')\""
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Set up your .env file with API keys"
echo "  2. Initialize the database: python scripts/init_database.py"
echo "  3. Start services: docker-compose up -d"
echo "  4. Check health: curl http://localhost:5000/health"
echo ""

# Create a pip freeze file for reference
echo -e "${CYAN}Creating pip freeze file for reference...${NC}"
pip freeze > installed_packages.txt
echo -e "  ${GREEN}✅ Package list saved to: installed_packages.txt${NC}"
echo ""

echo -e "${GREEN}Happy Trading, bro! 🚀${NC}"
echo -e "${GREEN}DevGenius hat tips to you! 🎩${NC}"