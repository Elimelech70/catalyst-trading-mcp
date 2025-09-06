#!/bin/bash
# Name of Application: Catalyst Trading System
# Name of file: fix_venv.sh
# Version: 1.0.0
# Last Updated: 2025-09-05
# Purpose: Diagnose and fix virtual environment issues

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Virtual Environment Diagnostic & Fix Tool       ║${NC}"
echo -e "${CYAN}║                DevGenius Edition 🎩                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Diagnose Python installation
echo -e "${BLUE}Step 1: Checking Python installation${NC}"

PYTHON_CMD=""
PYTHON_FOUND=false

# Check for python3
if command_exists python3; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} Found python3: $PYTHON_VERSION"
    PYTHON_FOUND=true
fi

# Check for python
if command_exists python; then
    PYTHON_VERSION=$(python --version 2>&1)
    if [[ $PYTHON_VERSION == *"Python 3"* ]]; then
        if [ -z "$PYTHON_CMD" ]; then
            PYTHON_CMD="python"
        fi
        echo -e "  ${GREEN}✓${NC} Found python: $PYTHON_VERSION"
        PYTHON_FOUND=true
    else
        echo -e "  ${YELLOW}⚠${NC}  python is version 2.x (not suitable)"
    fi
fi

if [ "$PYTHON_FOUND" = false ]; then
    echo -e "  ${RED}✗${NC} Python 3 not found!"
    echo -e "  ${YELLOW}Install with:${NC}"
    echo "    Ubuntu/Debian: sudo apt-get install python3 python3-venv python3-pip"
    echo "    RHEL/CentOS: sudo yum install python3"
    echo "    macOS: brew install python3"
    exit 1
fi

echo ""

# Step 2: Check for venv module
echo -e "${BLUE}Step 2: Checking venv module${NC}"

$PYTHON_CMD -c "import venv" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} venv module is installed"
else
    echo -e "  ${RED}✗${NC} venv module not found!"
    echo -e "  ${YELLOW}Installing venv module...${NC}"
    
    # Try to install python3-venv
    if command_exists apt-get; then
        echo "  Running: sudo apt-get install python3-venv"
        sudo apt-get update && sudo apt-get install -y python3-venv
    elif command_exists yum; then
        echo "  Running: sudo yum install python3-venv"
        sudo yum install -y python3-venv
    elif command_exists dnf; then
        echo "  Running: sudo dnf install python3-venv"
        sudo dnf install -y python3-venv
    elif command_exists brew; then
        echo "  venv should be included with Python on macOS"
    else
        echo -e "  ${RED}Please install python3-venv manually${NC}"
        exit 1
    fi
    
    # Check again
    $PYTHON_CMD -c "import venv" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo -e "  ${RED}Failed to install venv module${NC}"
        echo "  Try: pip3 install virtualenv"
        exit 1
    fi
fi

echo ""

# Step 3: Check for existing virtual environments
echo -e "${BLUE}Step 3: Checking for existing virtual environments${NC}"

VENV_DIRS=("catalyst_venv" "venv" ".venv" "env" ".env")
EXISTING_VENVS=()

for venv_dir in "${VENV_DIRS[@]}"; do
    if [ -d "$venv_dir" ]; then
        echo -e "  ${YELLOW}Found:${NC} $venv_dir/"
        EXISTING_VENVS+=("$venv_dir")
        
        # Check if it's valid
        if [ -f "$venv_dir/bin/activate" ] || [ -f "$venv_dir/Scripts/activate" ]; then
            echo -e "    ${GREEN}✓${NC} Contains activation script"
        else
            echo -e "    ${RED}✗${NC} Missing activation script (corrupted?)"
        fi
    fi
done

if [ ${#EXISTING_VENVS[@]} -eq 0 ]; then
    echo -e "  ${YELLOW}No existing virtual environments found${NC}"
fi

echo ""

# Step 4: Create or fix virtual environment
echo -e "${BLUE}Step 4: Virtual Environment Setup${NC}"

VENV_NAME="catalyst_venv"

if [ -d "$VENV_NAME" ]; then
    echo -e "${YELLOW}Virtual environment '$VENV_NAME' exists${NC}"
    echo -n "Do you want to (r)emove and recreate, (f)ix, or (k)eep it? (r/f/k): "
    read -r choice
    
    case $choice in
        r|R)
            echo "Removing old virtual environment..."
            rm -rf "$VENV_NAME"
            echo "Creating fresh virtual environment..."
            $PYTHON_CMD -m venv "$VENV_NAME"
            ;;
        f|F)
            echo "Attempting to fix virtual environment..."
            # Try to repair it
            $PYTHON_CMD -m venv --clear "$VENV_NAME"
            ;;
        k|K)
            echo "Keeping existing virtual environment"
            ;;
        *)
            echo "Keeping existing virtual environment"
            ;;
    esac
else
    echo "Creating new virtual environment: $VENV_NAME"
    $PYTHON_CMD -m venv "$VENV_NAME"
fi

# Verify creation
if [ ! -d "$VENV_NAME" ]; then
    echo -e "${RED}Failed to create virtual environment${NC}"
    echo "Trying alternative method with virtualenv..."
    
    # Try virtualenv as fallback
    if command_exists virtualenv; then
        virtualenv "$VENV_NAME"
    else
        pip3 install virtualenv
        virtualenv "$VENV_NAME"
    fi
fi

echo ""

# Step 5: Test activation
echo -e "${BLUE}Step 5: Testing activation${NC}"

# Detect the shell
SHELL_TYPE=$(basename "$SHELL")
echo -e "  Detected shell: ${CYAN}$SHELL_TYPE${NC}"

# Find activation script
ACTIVATE_SCRIPT=""
if [ -f "$VENV_NAME/bin/activate" ]; then
    ACTIVATE_SCRIPT="$VENV_NAME/bin/activate"
elif [ -f "$VENV_NAME/Scripts/activate" ]; then
    # Windows
    ACTIVATE_SCRIPT="$VENV_NAME/Scripts/activate"
else
    echo -e "  ${RED}✗${NC} Activation script not found!"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Found activation script: $ACTIVATE_SCRIPT"
echo ""

# Step 6: Create helper scripts
echo -e "${BLUE}Step 6: Creating helper scripts${NC}"

# Create activation helper
cat > activate_catalyst.sh << EOF
#!/bin/bash
# Catalyst Trading System - Virtual Environment Activation

if [ -f "$ACTIVATE_SCRIPT" ]; then
    source "$ACTIVATE_SCRIPT"
    echo -e "${GREEN}✅ Catalyst virtual environment activated${NC}"
    echo "Python: \$(which python)"
    echo "Pip: \$(which pip)"
    echo ""
    echo "To deactivate, type: deactivate"
else
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Run: ./fix_venv.sh"
fi
EOF

chmod +x activate_catalyst.sh
echo -e "  ${GREEN}✓${NC} Created: activate_catalyst.sh"

# Create requirements installer for venv
cat > install_in_venv.sh << EOF
#!/bin/bash
# Install requirements in virtual environment

# Activate virtual environment
if [ -f "$ACTIVATE_SCRIPT" ]; then
    source "$ACTIVATE_SCRIPT"
    echo "✅ Virtual environment activated"
    
    # Upgrade pip first
    pip install --upgrade pip setuptools wheel
    
    # Install requirements
    if [ -f "requirements-base.txt" ]; then
        echo "Installing base requirements..."
        pip install -r requirements-base.txt
    fi
    
    # Install service requirements
    for req in services/*/requirements.txt; do
        if [ -f "\$req" ]; then
            echo "Installing \$(dirname \$req) requirements..."
            pip install -r "\$req" --no-cache-dir || echo "⚠️  Some packages failed"
        fi
    done
    
    echo "✅ Installation complete"
    pip freeze > installed_packages.txt
else
    echo "❌ Virtual environment not found"
fi
EOF

chmod +x install_in_venv.sh
echo -e "  ${GREEN}✓${NC} Created: install_in_venv.sh"

echo ""

# Step 7: Show instructions
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}           Virtual Environment Ready! 🎉              ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${CYAN}Method 1 - Direct activation:${NC}"
echo -e "${YELLOW}  source $ACTIVATE_SCRIPT${NC}"
echo ""

echo -e "${CYAN}Method 2 - Use helper script:${NC}"
echo -e "${YELLOW}  ./activate_catalyst.sh${NC}"
echo ""

echo -e "${CYAN}Method 3 - One-line activation and install:${NC}"
echo -e "${YELLOW}  source $ACTIVATE_SCRIPT && pip install -r requirements-base.txt${NC}"
echo ""

echo -e "${CYAN}Method 4 - Use automated installer:${NC}"
echo -e "${YELLOW}  ./install_in_venv.sh${NC}"
echo ""

# Test if we can activate it
echo -e "${BLUE}Testing activation...${NC}"
(
    source "$ACTIVATE_SCRIPT" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✅ Activation successful!${NC}"
        echo -e "  Python in venv: $(which python)"
    else
        echo -e "  ${RED}✗ Activation failed${NC}"
        echo -e "  ${YELLOW}Try manually: source $ACTIVATE_SCRIPT${NC}"
    fi
)

echo ""
echo -e "${CYAN}Common Issues & Solutions:${NC}"
echo "1. 'source: not found' → Use: . $ACTIVATE_SCRIPT"
echo "2. Permission denied → Run: chmod +x $ACTIVATE_SCRIPT"
echo "3. On Windows → Use: $VENV_NAME\\Scripts\\activate.bat"
echo "4. In fish shell → Use: source $VENV_NAME/bin/activate.fish"
echo ""

echo -e "${GREEN}DevGenius hat tip: Virtual environment is the way! 🎩${NC}"