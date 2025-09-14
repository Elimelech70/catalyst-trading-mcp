**Name of Application**: Catalyst Trading System  
**Name of file**: claude-desktop-setup-mcp-v41.md  
**Version**: 4.1.0  
**Last Updated**: 2025-08-31  
**Purpose**: Claude Desktop configuration guide for MCP integration

**REVISION HISTORY**:
- v4.1.0 (2025-08-31) - Production-ready Claude Desktop setup
  - Updated MCP configuration for latest architecture
  - Added troubleshooting section
  - WebSocket and stdio transport options
  - Environment variable management

**Description of Service**:
This guide configures Claude Desktop to connect with the Catalyst Trading System via MCP protocol, enabling Claude to:
1. Monitor trading cycles and system status
2. Execute trading commands and workflows  
3. Access real-time market data and analysis
4. Generate performance reports and insights
5. Manage system configurations dynamically

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Claude Desktop Installation](#2-claude-desktop-installation)
3. [MCP Configuration](#3-mcp-configuration)
4. [Environment Setup](#4-environment-setup)
5. [Connection Testing](#5-connection-testing)
6. [Troubleshooting](#6-troubleshooting)
7. [Usage Examples](#7-usage-examples)
8. [Advanced Configuration](#8-advanced-configuration)

---

## 1. Prerequisites

### 1.1 Required Software
- **Claude Desktop**: Latest version installed
- **Python**: 3.10+ installed and accessible in PATH
- **Catalyst Trading System**: Services running (see implementation guide)
- **Operating System**: Windows, macOS, or Linux

### 1.2 Required Services Running
Before configuring Claude Desktop, ensure these services are operational:

```bash
# Check service status
curl -f http://localhost:5000/health  # Orchestration service
curl -f http://localhost:5001/health  # Scanner service  
curl -f http://localhost:5008/health  # News service
```

### 1.3 Environment Variables
Verify these environment variables are set:

```bash
echo $DATABASE_URL
echo $REDIS_URL  
echo $ALPACA_API_KEY
echo $ALPACA_SECRET_KEY
echo $NEWS_API_KEY
```

---

## 2. Claude Desktop Installation

### 2.1 Download Claude Desktop
Visit [claude.ai](https://claude.ai) and download the desktop application for your operating system.

### 2.2 Create Configuration Directory

**Windows:**
```powershell
mkdir "~\.claude"
```

**macOS/Linux:**
```bash
mkdir -p ~/.claude
```

---

## 3. MCP Configuration

### 3.1 Primary Configuration (stdio transport)

Create the main MCP configuration file:

**File**: `~/.claude/mcp_settings.json`

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": [
        "/absolute/path/to/catalyst/services/orchestration/orchestration-service.py"
      ],
      "env": {
        "DATABASE_URL": "postgresql://catalyst_user:password@localhost:25060/catalyst_trading",
        "REDIS_URL": "redis://localhost:6379/0",
        "ALPACA_API_KEY": "your_alpaca_api_key",
        "ALPACA_SECRET_KEY": "your_alpaca_secret_key", 
        "NEWS_API_KEY": "your_news_api_key",
        "ENVIRONMENT": "production",
        "LOG_LEVEL": "INFO"
      },
      "transport": "stdio"
    }
  }
}
```

### 3.2 Alternative WebSocket Configuration

For remote or containerized deployments:

**File**: `~/.claude/mcp_settings.json`

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "url": "ws://localhost:5000/mcp",
      "transport": "websocket",
      "reconnect": true,
      "reconnect_delay": 5000,
      "timeout": 30000,
      "heartbeat_interval": 10000
    }
  }
}
```

### 3.3 Development Configuration

For development with verbose logging:

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": [
        "/path/to/catalyst/services/orchestration/orchestration-service.py",
        "--verbose"
      ],
      "env": {
        "DATABASE_URL": "postgresql://catalyst_user:password@localhost:5432/catalyst_trading",
        "REDIS_URL": "redis://localhost:6379/0",
        "LOG_LEVEL": "DEBUG",
        "ENVIRONMENT": "development"
      },
      "transport": "stdio"
    }
  }
}
```

---

## 4. Environment Setup

### 4.1 Create Environment File

**File**: `~/.catalyst/.env`

```env
# Database Configuration
DATABASE_URL=postgresql://catalyst_user:secure_password@localhost:25060/catalyst_trading

# Redis Configuration  
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=RedisCatalyst2025!SecureCache

# Trading API Keys
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# News API
NEWS_API_KEY=your_newsapi_key

# System Configuration
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_POSITIONS=5
SCAN_FREQUENCY=300
```

### 4.2 Secure Permissions

**macOS/Linux:**
```bash
chmod 600 ~/.claude/mcp_settings.json
chmod 600 ~/.catalyst/.env
```

**Windows:**
```powershell
icacls "$env:USERPROFILE\.claude\mcp_settings.json" /inheritance:r /grant:r "$env:USERNAME:R"
```

---

## 5. Connection Testing

### 5.1 Basic Connection Test

Open Claude Desktop and try these commands:

```
Hi Claude! Can you check if the Catalyst Trading System is running?
```

Expected response should include system status and available services.

### 5.2 Service Health Check

```
Claude, what's the current health status of all trading services?
```

Expected response should show status of all 7 services (orchestration, news, scanner, pattern, technical, trading, reporting).

### 5.3 Trading Cycle Test

```
Can you start a new conservative trading cycle for me?
```

Expected response should create a new trading cycle and return the cycle ID.

---

## 6. Troubleshooting

### 6.1 Common Connection Issues

**Problem**: Claude Desktop can't connect to MCP server  
**Solution**: 
```bash
# Check if orchestration service is running
curl -f http://localhost:5000/health

# Check Python path in configuration
which python  # Use this full path in mcp_settings.json

# Test MCP server directly
python /path/to/orchestration-service.py --test
```

**Problem**: Environment variables not loading  
**Solution**: 
```bash
# Test environment loading
python -c "import os; print(os.getenv('DATABASE_URL'))"

# Check file permissions
ls -la ~/.claude/mcp_settings.json
```

### 6.2 Service Startup Issues

**Problem**: Services not starting properly  
**Solution**:
```bash
# Check Docker status
docker-compose ps

# Restart specific service
docker-compose restart orchestration

# View service logs
docker-compose logs orchestration
```

### 6.3 Database Connection Issues

**Problem**: Database connection failures  
**Solution**:
```bash
# Test database connectivity
psql "postgresql://catalyst_user:password@localhost:25060/catalyst_trading" -c "SELECT 1;"

# Check connection pool status
psql -c "SELECT * FROM pg_stat_activity WHERE application_name LIKE '%catalyst%';"
```

---

## 7. Usage Examples

### 7.1 Basic Commands

```
# System status
"What's the current status of the trading system?"

# Start trading
"Start a new trading cycle in normal mode"

# View positions  
"Show me all open trading positions"

# Market scan
"Run a market scan and show me the top candidates"
```

### 7.2 Advanced Operations

```
# Custom configuration
"Start an aggressive trading cycle with 8 max positions and 5-minute scan frequency"

# Performance analysis
"Generate a performance report for the last trading cycle"

# Risk management
"What's our current risk exposure and position sizes?"
```

### 7.3 Debugging Commands

```
# Service diagnostics
"Check the health of all services and show any errors"

# Data pipeline status
"Show me the current data flow through the scanning pipeline"

# Trading cycle details
"Give me complete details on trading cycle 20250831-001"
```

---

## 8. Advanced Configuration

### 8.1 Multiple Environment Support

```json
{
  "mcpServers": {
    "catalyst-trading-dev": {
      "command": "python",
      "args": ["/path/to/orchestration-service.py"],
      "env": {
        "DATABASE_URL": "postgresql://localhost:5432/catalyst_dev",
        "ENVIRONMENT": "development"
      }
    },
    "catalyst-trading-prod": {
      "url": "wss://catalyst.yourdomain.com/mcp",
      "transport": "websocket"
    }
  }
}
```

### 8.2 Custom Logging Configuration

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["/path/to/orchestration-service.py"],
      "env": {
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "json",
        "LOG_FILE": "/var/log/catalyst/mcp.log"
      },
      "logLevel": "debug"
    }
  }
}
```

### 8.3 Performance Tuning

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["/path/to/orchestration-service.py"],
      "env": {
        "MCP_TIMEOUT": "60000",
        "WORKER_THREADS": "4",
        "CONNECTION_POOL_SIZE": "20"
      },
      "timeout": 60000,
      "max_restart_attempts": 3
    }
  }
}
```

---

## 9. Security Considerations

### 9.1 Secure Environment Variables

Use a secure secrets management approach:

```bash
# Install age for encryption
brew install age  # macOS
apt install age   # Linux

# Encrypt environment file
age --encrypt --recipient $(age-keygen -y ~/.catalyst/keys/key.txt) ~/.catalyst/.env > ~/.catalyst/.env.age

# Decrypt in configuration
"command": "bash",
"args": ["-c", "age --decrypt ~/.catalyst/.env.age | source && python orchestration-service.py"]
```

### 9.2 Network Security

For production deployments:

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "url": "wss://catalyst-mcp.yourcompany.com/mcp",
      "transport": "websocket",
      "auth": {
        "type": "bearer",
        "token": "${MCP_AUTH_TOKEN}"
      },
      "tls": {
        "verify": true,
        "cert_path": "/path/to/client.crt",
        "key_path": "/path/to/client.key"
      }
    }
  }
}
```

---

## 10. Monitoring and Maintenance

### 10.1 Health Monitoring

Claude can monitor system health:

```
"Set up automated health monitoring for the next hour and alert me if any service goes down"
```

### 10.2 Log Analysis

```
"Analyze the last 100 log entries for any errors or performance issues"
```

### 10.3 Performance Metrics

```
"Show me system performance metrics for the last 24 hours including response times and error rates"
```

---

## 11. Next Steps

After successful configuration:

1. **Test all major workflows** with Claude
2. **Set up monitoring alerts** through Claude
3. **Configure automated reporting** schedules
4. **Integrate with paper trading** account
5. **Begin live trading** (with proper risk management)

---

## 12. Support

For issues with Claude Desktop MCP integration:

- **Catalyst Trading System**: Check project documentation
- **MCP Protocol**: [Anthropic MCP Documentation](https://docs.anthropic.com)
- **Claude Desktop**: [Claude Support](https://support.anthropic.com)

---

*DevGenius Hat Status: Claude Desktop Ready* 🎩

**The honourable Claude approves this configuration** ✨