#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: setup_python.sh
# Version: 1.0.0
# Last Updated: 2025-09-04
# Purpose: Setup Python environment for Catalyst Trading System

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}   Python Environment Setup Helper      ${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    # Detect distribution
    if [ -f /etc/debian_version ]; then
        DISTRO="debian"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="redhat"
    elif [ -f /etc/arch-release ]; then
        DISTRO="arch"
    else
        DISTRO="unknown"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="windows"
fi

echo -e "${BLUE}Detected OS: $OS${NC}"

# Check for Python installations
echo -e "\n${BLUE}Checking for Python installations...${NC}"

PYTHON_FOUND=false
PYTHON_CMD=""

# Check python3
if command -v python3 >/dev/null 2>&1; then
    PYTHON3_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} python3 found: $PYTHON3_VERSION"
    PYTHON_FOUND=true
    PYTHON_CMD="python3"
else
    echo -e "  ${RED}✗${NC} python3 not found"
fi

# Check python
if command -v python >/dev/null 2>&1; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo -e "  ${GREEN}✓${NC} python found: $PYTHON_VERSION"
    
    # Check if it's Python 3
    if [[ $PYTHON_VERSION == *"Python 3"* ]]; then
        PYTHON_FOUND=true
        if [ -z "$PYTHON_CMD" ]; then
            PYTHON_CMD="python"
        fi
    else
        echo -e "  ${YELLOW}⚠${NC}  python is version 2.x (not suitable)"
    fi
else
    echo -e "  ${RED}✗${NC} python not found"
fi

# Check pip
echo -e "\n${BLUE}Checking for pip installations...${NC}"

if command -v pip3 >/dev/null 2>&1; then
    PIP3_VERSION=$(pip3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} pip3 found: $PIP3_VERSION"
else
    echo -e "  ${RED}✗${NC} pip3 not found"
fi

if command -v pip >/dev/null 2>&1; then
    PIP_VERSION=$(pip --version 2>&1)
    echo -e "  ${GREEN}✓${NC} pip found: $PIP_VERSION"
else
    echo -e "  ${RED}✗${NC} pip not found"
fi

# If Python not found, provide installation instructions
if [ "$PYTHON_FOUND" = false ]; then
    echo -e "\n${RED}Python 3 is not installed!${NC}"
    echo -e "\n${CYAN}Installation instructions for your OS:${NC}\n"
    
    case "$OS" in
        "linux")
            case "$DISTRO" in
                "debian")
                    echo "  ${YELLOW}Ubuntu/Debian:${NC}"
                    echo "    sudo apt update"
                    echo "    sudo apt install python3 python3-pip python3-venv"
                    ;;
                "redhat")
                    echo "  ${YELLOW}RedHat/CentOS/Fedora:${NC}"
                    echo "    sudo yum install python3 python3-pip"
                    # or for newer versions
                    echo "    # or"
                    echo "    sudo dnf install python3 python3-pip"
                    ;;
                "arch")
                    echo "  ${YELLOW}Arch Linux:${NC}"
                    echo "    sudo pacman -S python python-pip"
                    ;;
                *)
                    echo "  ${YELLOW}Generic Linux:${NC}"
                    echo "    # Use your package manager to install:"
                    echo "    python3 python3-pip python3-venv"
                    ;;
            esac
            ;;
        "macos")
            echo "  ${YELLOW}macOS:${NC}"
            echo ""
            echo "  Option 1 - Using Homebrew (recommended):"
            echo "    # Install Homebrew if not installed:"
            echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            echo ""
            echo "    # Then install Python:"
            echo "    brew install python@3.11"
            echo ""
            echo "  Option 2 - Download from python.org:"
            echo "    Visit https://www.python.org/downloads/"
            ;;
        "windows")
            echo "  ${YELLOW}Windows:${NC}"
            echo ""
            echo "  Option 1 - Microsoft Store (easiest):"
            echo "    Open Microsoft Store and search for Python 3.11"
            echo ""
            echo "  Option 2 - Download installer:"
            echo "    Visit https://www.python.org/downloads/windows/"
            echo "    Download and run the installer"
            echo "    ⚠️  IMPORTANT: Check 'Add Python to PATH' during installation!"
            echo ""
            echo "  Option 3 - Using winget:"
            echo "    winget install Python.Python.3.11"
            ;;
        *)
            echo "  Visit https://www.python.org/downloads/"
            ;;
    esac
    
    echo -e "\n${CYAN}After installation, run this script again.${NC}"
    exit 1
fi

# Python found, create alias if needed
echo -e "\n${GREEN}Python 3 is installed!${NC}"
echo -e "Using command: ${CYAN}$PYTHON_CMD${NC}"

# Check if we need to create an alias
if [ "$PYTHON_CMD" = "python3" ] && ! command -v python >/dev/null 2>&1; then
    echo -e "\n${YELLOW}Creating 'python' alias for convenience...${NC}"
    
    # Detect shell
    SHELL_RC=""
    if [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    else
        SHELL_RC="$HOME/.profile"
    fi
    
    echo ""
    echo "Add this line to your $SHELL_RC file:"
    echo -e "${CYAN}alias python='python3'${NC}"
    echo -e "${CYAN}alias pip='pip3'${NC}"
    echo ""
    echo "Or run these commands:"
    echo -e "${YELLOW}echo \"alias python='python3'\" >> $SHELL_RC${NC}"
    echo -e "${YELLOW}echo \"alias pip='pip3'\" >> $SHELL_RC${NC}"
    echo -e "${YELLOW}source $SHELL_RC${NC}"
fi

# Create virtual environment
echo -e "\n${BLUE}Setting up virtual environment...${NC}"

VENV_DIR="catalyst_venv"

if [ -d "$VENV_DIR" ]; then
    echo -e "  ${YELLOW}Virtual environment already exists at $VENV_DIR${NC}"
    echo "  To use it: source $VENV_DIR/bin/activate"
else
    echo "  Creating virtual environment..."
    $PYTHON_CMD -m venv $VENV_DIR
    
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ Virtual environment created: $VENV_DIR${NC}"
        echo ""
        echo -e "${CYAN}To activate the virtual environment:${NC}"
        
        if [[ "$OS" == "windows" ]]; then
            echo "  $VENV_DIR\\Scripts\\activate"
        else
            echo "  source $VENV_DIR/bin/activate"
        fi
        
        echo ""
        echo -e "${CYAN}Then run the installation script:${NC}"
        echo "  ./install_requirements.sh"
    else
        echo -e "  ${RED}Failed to create virtual environment${NC}"
        echo "  Try installing venv package:"
        if [[ "$OS" == "linux" ]]; then
            echo "    sudo apt install python3-venv  # Debian/Ubuntu"
            echo "    sudo yum install python3-venv  # RedHat/CentOS"
        fi
    fi
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}         Setup Complete!                ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo "  1. Activate virtual environment:"
if [[ "$OS" == "windows" ]]; then
    echo "     $VENV_DIR\\Scripts\\activate"
else
    echo "     source $VENV_DIR/bin/activate"
fi
echo ""
echo "  2. Run the requirements installer:"
echo "     ./install_requirements.sh"
echo ""
echo "  3. If you get 'permission denied':"
echo "     chmod +x install_requirements.sh"
echo "     chmod +x setup_python.sh"
echo ""
echo -e "${GREEN}Happy coding, bro! 🚀${NC}"