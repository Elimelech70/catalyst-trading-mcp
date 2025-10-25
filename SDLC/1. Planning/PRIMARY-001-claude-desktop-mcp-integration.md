# PRIMARY-001: Claude Desktop MCP Integration

**Name of Application**: Catalyst Trading System  
**Name of file**: PRIMARY-001-claude-desktop-mcp-integration.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-25  
**Purpose**: Complete Claude Desktop MCP integration for Production system  
**Timeline**: Days 1-3 of Week 8  
**Priority**: CRITICAL (blocks full system validation)

---

## REVISION HISTORY

**v1.0.0 (2025-10-25)** - Initial Implementation Document
- Define problem: MCP expects local server, system is remote
- Design solution: Python proxy bridge
- Implementation steps with code
- Testing procedures
- Acceptance criteria

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current Status](#2-current-status)
3. [Solution Architecture](#3-solution-architecture)
4. [Implementation Tasks](#4-implementation-tasks)
5. [Testing & Validation](#5-testing--validation)
6. [Acceptance Criteria](#6-acceptance-criteria)

---

## 1. Problem Statement

### 1.1 The Challenge

```yaml
Current Architecture:
  - Production system: DigitalOcean droplet (remote)
  - Orchestration Service: Port 5000 (FastMCP HTTP)
  - Development laptop: Windows 11 (local)
  - Claude Desktop: Expects local MCP server
  
Problem:
  - MCP protocol designed for local communication
  - Claude Desktop config points to localhost
  - Our system is REMOTE (DigitalOcean)
  - Cannot directly connect local Claude to remote MCP
```

### 1.2 Why This Matters

**Business Impact**:
- Claude Desktop provides intelligent monitoring
- Manual oversight capabilities
- ML training data analysis
- System debugging assistance

**Technical Impact**:
- Without MCP: System works (cron handles trading)
- With MCP: Enhanced observability and control
- MCP is SECONDARY (nice-to-have) not PRIMARY (required)

**Decision**: Worth solving, but not blocking live trading

---

## 2. Current Status

### 2.1 What's Working ✅

```yaml
Production System:
  ✅ All 9 services deployed on DigitalOcean
  ✅ Orchestration Service running (port 5000)
  ✅ FastMCP HTTP implementation complete
  ✅ Health endpoints responding
  ✅ Service-to-service communication working
  ✅ Cron automation functional
  ✅ Database operations normal
```

### 2.2 What's NOT Working ❌

```yaml
Claude Desktop Integration:
  ❌ Cannot connect to remote MCP server
  ❌ Config expects localhost:5000
  ❌ No proxy bridge implemented yet
  ❌ SSL/TLS handling undefined
  ❌ Authentication mechanism unclear
```

### 2.3 Blockers Identified

**Blocker #1**: MCP protocol limitation
- FastMCP designed for local communication
- No built-in remote server support
- Claude Desktop expects local process

**Blocker #2**: Network architecture
- DigitalOcean droplet not directly accessible
- Firewall rules limit exposed ports
- SSL termination required for security

**Blocker #3**: Authentication
- MCP doesn't have built-in auth
- Need API key or token mechanism
- Must secure remote communication

---

## 3. Solution Architecture

### 3.1 Three-Component Design

```yaml
Component 1: NGINX Reverse Proxy (DigitalOcean)
  Location: catalyst-droplet (production)
  Purpose: SSL termination, request routing
  Listens: 443 (HTTPS)
  Forwards to: Orchestration Service (port 5000)
  
Component 2: Python Proxy Bridge (Windows 11 Laptop)
  Location: Local development machine
  Purpose: Local MCP server that forwards to remote
  Listens: localhost:5000 (MCP protocol)
  Connects to: NGINX (https://catalyst-domain.com/mcp)
  
Component 3: Orchestration Service (Existing)
  Location: Docker container (catalyst-droplet)
  Purpose: MCP server implementation
  Listens: 5000 (HTTP, Docker network)
  No changes needed: Already implements FastMCP
```

### 3.2 Request Flow

```
┌─────────────────┐
│ Claude Desktop  │ (Windows 11 laptop)
└────────┬────────┘
         │ MCP protocol
         │ (localhost:5000)
         ▼
┌─────────────────┐
│  Python Proxy   │ (local-mcp-proxy.py)
│     Bridge      │
└────────┬────────┘
         │ HTTPS
         │ (https://catalyst.yourdomain.com/mcp)
         ▼
┌─────────────────┐
│ NGINX Proxy     │ (DigitalOcean droplet)
│  (Port 443)     │
└────────┬────────┘
         │ HTTP
         │ (http://orchestration:5000)
         ▼
┌─────────────────┐
│ Orchestration   │ (Docker container)
│    Service      │
└─────────────────┘
```

### 3.3 Why This Works

**Advantages**:
1. ✅ Claude Desktop thinks it's talking to local server
2. ✅ Proxy handles remote communication transparently
3. ✅ NGINX provides SSL/TLS security
4. ✅ No changes needed to Orchestration Service
5. ✅ Can add authentication at NGINX or proxy level
6. ✅ Works across firewall/NAT boundaries

**Disadvantages**:
1. ⚠️ Extra component to maintain (proxy bridge)
2. ⚠️ Slight latency increase (local → remote)
3. ⚠️ Requires domain + SSL certificate

---

## 4. Implementation Tasks

### 4.1 Task 1: Configure NGINX on DigitalOcean

**Duration**: 2-3 hours

**Step 1: Install NGINX** (if not already present)
```bash
# SSH into droplet
ssh root@catalyst-droplet

# Install NGINX
apt update
apt install nginx -y

# Verify installation
nginx -v
```

**Step 2: Obtain SSL Certificate**
```bash
# Install certbot
apt install certbot python3-certbot-nginx -y

# Get certificate (replace with your domain)
certbot --nginx -d catalyst.yourdomain.com

# Verify auto-renewal
certbot renew --dry-run
```

**Step 3: Configure NGINX for MCP**
```nginx
# /etc/nginx/sites-available/catalyst-mcp

upstream orchestration {
    server localhost:5000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name catalyst.yourdomain.com;

    # SSL configuration (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/catalyst.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/catalyst.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # MCP endpoint
    location /mcp {
        # Remove /mcp prefix before forwarding
        rewrite ^/mcp(.*)$ $1 break;
        
        # Proxy to Orchestration Service
        proxy_pass http://orchestration;
        proxy_http_version 1.1;
        
        # WebSocket support (if MCP needs it)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Optional: API key authentication
        # if ($http_x_api_key != "your-secret-api-key") {
        #     return 401;
        # }
    }
    
    # Health check endpoint (public)
    location /health {
        proxy_pass http://orchestration/health;
        access_log off;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name catalyst.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

**Step 4: Enable and Test**
```bash
# Enable site
ln -s /etc/nginx/sites-available/catalyst-mcp /etc/nginx/sites-enabled/

# Test configuration
nginx -t

# Reload NGINX
systemctl reload nginx

# Test health endpoint
curl https://catalyst.yourdomain.com/health

# Test MCP endpoint (should return orchestration service response)
curl https://catalyst.yourdomain.com/mcp/system/health
```

---

### 4.2 Task 2: Build Python Proxy Bridge

**Duration**: 4-6 hours

**File**: `local-mcp-proxy.py`

```python
#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: local-mcp-proxy.py
Version: 1.0.0
Last Updated: 2025-10-25
Purpose: Local MCP proxy that forwards to remote Orchestration Service

REVISION HISTORY:
v1.0.0 (2025-10-25) - Initial implementation
- HTTP server on localhost:5000
- Forwards MCP requests to remote NGINX
- Handles authentication
- Transparent proxy for Claude Desktop

Description:
This proxy presents as a local MCP server to Claude Desktop,
but forwards all requests to the remote Production system.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
REMOTE_MCP_URL = "https://catalyst.yourdomain.com/mcp"
API_KEY = "your-secret-api-key"  # Optional: for authentication
LOCAL_PORT = 5000


class MCPProxy:
    """Local MCP proxy that forwards to remote server"""
    
    def __init__(self, remote_url: str, api_key: str = None):
        self.remote_url = remote_url
        self.api_key = api_key
        self.session = None
        
    async def start(self):
        """Initialize HTTP session"""
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=60)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        logger.info(f"Proxy session initialized (target: {self.remote_url})")
        
    async def stop(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            logger.info("Proxy session closed")
    
    async def forward_request(
        self,
        method: str,
        path: str,
        headers: Dict,
        body: bytes = None
    ) -> tuple:
        """
        Forward request to remote MCP server
        
        Returns:
            (status_code, headers, body)
        """
        # Build remote URL
        url = f"{self.remote_url}{path}"
        
        # Prepare headers
        forward_headers = {
            'Content-Type': headers.get('Content-Type', 'application/json'),
            'Accept': headers.get('Accept', 'application/json'),
        }
        
        # Add API key if configured
        if self.api_key:
            forward_headers['X-API-Key'] = self.api_key
        
        try:
            logger.info(f"Forwarding {method} {path} to {url}")
            
            # Make request
            async with self.session.request(
                method=method,
                url=url,
                headers=forward_headers,
                data=body
            ) as response:
                status = response.status
                resp_headers = dict(response.headers)
                resp_body = await response.read()
                
                logger.info(f"Remote response: {status}")
                return status, resp_headers, resp_body
                
        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            return 502, {}, json.dumps({
                "error": "Bad Gateway",
                "message": str(e)
            }).encode()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return 500, {}, json.dumps({
                "error": "Internal Server Error",
                "message": str(e)
            }).encode()


async def handle_request(request: web.Request, proxy: MCPProxy) -> web.Response:
    """Handle incoming request from Claude Desktop"""
    
    # Extract request details
    method = request.method
    path = request.path
    headers = request.headers
    body = await request.read() if request.can_read_body else None
    
    # Forward to remote server
    status, resp_headers, resp_body = await proxy.forward_request(
        method=method,
        path=path,
        headers=headers,
        body=body
    )
    
    # Return response
    return web.Response(
        status=status,
        headers=resp_headers,
        body=resp_body
    )


async def create_app() -> web.Application:
    """Create aiohttp application"""
    
    # Initialize proxy
    proxy = MCPProxy(
        remote_url=REMOTE_MCP_URL,
        api_key=API_KEY
    )
    await proxy.start()
    
    # Create app
    app = web.Application()
    
    # Add routes (catch all)
    app.router.add_route('*', '/{path:.*}', lambda req: handle_request(req, proxy))
    
    # Cleanup on shutdown
    async def cleanup(app):
        await proxy.stop()
    app.on_cleanup.append(cleanup)
    
    return app


def main():
    """Run proxy server"""
    logger.info("="*60)
    logger.info("Catalyst Trading System - MCP Proxy Bridge")
    logger.info("="*60)
    logger.info(f"Local server: http://localhost:{LOCAL_PORT}")
    logger.info(f"Remote target: {REMOTE_MCP_URL}")
    logger.info(f"API Key: {'Configured' if API_KEY else 'Not configured'}")
    logger.info("="*60)
    
    # Run server
    web.run_app(
        create_app(),
        host='127.0.0.1',
        port=LOCAL_PORT
    )


if __name__ == '__main__':
    main()
```

**Installation**:
```bash
# On Windows 11 laptop

# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install aiohttp

# 3. Configure proxy
# Edit local-mcp-proxy.py:
# - Set REMOTE_MCP_URL to your domain
# - Set API_KEY if using authentication

# 4. Test proxy
python local-mcp-proxy.py

# Expected output:
# ============================================================
# Catalyst Trading System - MCP Proxy Bridge
# ============================================================
# Local server: http://localhost:5000
# Remote target: https://catalyst.yourdomain.com/mcp
# API Key: Configured
# ============================================================
```

---

### 4.3 Task 3: Update Claude Desktop Configuration

**Duration**: 30 minutes

**File**: `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["C:\\path\\to\\local-mcp-proxy.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Alternative** (if proxy runs as separate service):
```json
{
  "mcpServers": {
    "catalyst-trading": {
      "url": "http://localhost:5000",
      "transport": "http"
    }
  }
}
```

**Steps**:
1. Open Claude Desktop settings
2. Navigate to MCP configuration
3. Add catalyst-trading server
4. Restart Claude Desktop
5. Verify connection in Claude Desktop UI

---

### 4.4 Task 4: End-to-End Testing

**Duration**: 2-3 hours

**Test Scenario 1: Health Check**
```
1. Start local-mcp-proxy.py
2. Open Claude Desktop
3. In chat: "Check the Catalyst Trading System health"
4. Expected: Claude queries catalyst://system/health resource
5. Verify: Health data returned from remote system
```

**Test Scenario 2: Resource Access**
```
1. In Claude: "Show me current trading positions"
2. Expected: Claude queries catalyst://positions/active
3. Verify: Position data from Production database
4. Check: Data is current (not cached)
```

**Test Scenario 3: Tool Execution**
```
1. In Claude: "Start a trading cycle in conservative mode"
2. Expected: Claude calls start_trading_cycle tool
3. Verify: Workflow Service receives request
4. Check: Trading cycle initiated in Production
5. Validate: No errors in any service logs
```

**Test Scenario 4: Error Handling**
```
1. Stop Orchestration Service
2. In Claude: "Check system health"
3. Expected: Proxy returns 502 Bad Gateway
4. Claude: Should explain service is unavailable
5. Restart Orchestration Service
6. Retry: Should work again
```

---

## 5. Testing & Validation

### 5.1 Unit Tests

**Test 1: NGINX Configuration**
```bash
# Test SSL
curl -I https://catalyst.yourdomain.com/health

# Expected: HTTP/2 200

# Test MCP endpoint
curl https://catalyst.yourdomain.com/mcp/system/health

# Expected: JSON health data
```

**Test 2: Proxy Bridge**
```bash
# Start proxy
python local-mcp-proxy.py

# In another terminal, test forwarding
curl http://localhost:5000/system/health

# Expected: Same response as NGINX test
```

**Test 3: Claude Desktop Connection**
```
1. Open Claude Desktop
2. Check MCP server status
3. Look for "catalyst-trading" in Connected Servers
4. Status should be "Connected" (green)
```

### 5.2 Integration Tests

**Test Flow**:
```yaml
Step 1: Claude Desktop Startup
  - Reads config file
  - Launches local-mcp-proxy.py
  - Connects to localhost:5000
  - Proxy: Connects to remote NGINX
  - NGINX: Routes to Orchestration Service
  - Result: "Connected" status

Step 2: Resource Query
  - Claude: Requests catalyst://positions/active
  - Proxy: Forwards to NGINX
  - Orchestration: Queries Workflow Service
  - Workflow: Queries database
  - Response: Flows back through chain
  - Result: Claude displays position data

Step 3: Tool Execution
  - Claude: Calls start_trading_cycle
  - Proxy: Forwards to NGINX
  - Orchestration: Calls Workflow Service
  - Workflow: Initiates trading cycle
  - Response: Cycle ID returned
  - Result: Claude confirms cycle started
```

### 5.3 Performance Tests

**Latency Measurement**:
```yaml
Baseline (Local MCP):
  - Resource query: ~50ms
  - Tool execution: ~100ms

With Proxy (Remote MCP):
  - Resource query: ~150-200ms (acceptable)
  - Tool execution: ~200-300ms (acceptable)
  
Acceptable Threshold:
  - Resource queries: <500ms
  - Tool executions: <1000ms
```

---

## 6. Acceptance Criteria

### 6.1 Technical Success

```yaml
✅ NGINX configured with SSL certificate
✅ NGINX successfully proxies to Orchestration Service
✅ Python proxy bridge runs without errors
✅ Proxy forwards requests to NGINX correctly
✅ Claude Desktop connects to local proxy
✅ Claude Desktop shows "Connected" status
✅ All MCP resources accessible
✅ All MCP tools executable
✅ Response times <500ms for resources
✅ Response times <1000ms for tools
✅ Error handling works (502 when service down)
✅ Logs show successful request flow
```

### 6.2 Functional Success

```yaml
✅ Claude can query system health
✅ Claude can view trading positions
✅ Claude can check scan results
✅ Claude can read news sentiment
✅ Claude can access performance metrics
✅ Claude can start trading cycles (manual)
✅ Claude can stop trading (emergency)
✅ Claude receives real-time data (not cached)
✅ Multiple queries work in same session
✅ Reconnection works after service restart
```

### 6.3 Business Success

```yaml
✅ System operates WITHOUT Claude Desktop (cron still works)
✅ Claude provides intelligent monitoring
✅ Manual oversight possible via Claude
✅ Debugging assistance available
✅ ML analysis capabilities enabled
✅ User satisfaction with integration
```

---

## 7. Troubleshooting Guide

### 7.1 Common Issues

**Issue 1: NGINX 502 Bad Gateway**
```yaml
Symptoms: curl returns 502 error
Cause: Orchestration Service not running
Fix:
  docker-compose ps orchestration
  docker-compose logs orchestration
  docker-compose restart orchestration
```

**Issue 2: SSL Certificate Error**
```yaml
Symptoms: "SSL certificate problem: unable to get local issuer certificate"
Cause: Self-signed cert or expired cert
Fix:
  certbot renew
  systemctl reload nginx
```

**Issue 3: Proxy Connection Refused**
```yaml
Symptoms: Proxy cannot connect to NGINX
Cause: Firewall blocking port 443
Fix:
  ufw allow 443/tcp
  ufw reload
```

**Issue 4: Claude Desktop Not Connecting**
```yaml
Symptoms: "Disconnected" status in Claude Desktop
Cause: Proxy not running or config wrong
Fix:
  # Check proxy running
  netstat -an | findstr 5000
  
  # Restart proxy
  python local-mcp-proxy.py
  
  # Verify config
  type %APPDATA%\Claude\claude_desktop_config.json
```

### 7.2 Debug Checklist

```bash
# 1. Test each layer independently

# Layer 1: Orchestration Service
curl http://localhost:5000/health

# Layer 2: NGINX
curl https://catalyst.yourdomain.com/mcp/system/health

# Layer 3: Proxy Bridge
curl http://localhost:5000/system/health

# Layer 4: Claude Desktop
# Check MCP server status in UI

# 2. Check logs

# NGINX
tail -f /var/log/nginx/error.log

# Proxy
# Shows in terminal where proxy is running

# Orchestration Service
docker-compose logs orchestration -f

# Claude Desktop
# Check Help > Show Logs
```

---

## 8. Next Steps After Completion

**Immediate**:
1. Document final configuration in GitHub
2. Add monitoring for proxy bridge
3. Set up alerts for MCP disconnections

**Future Enhancements**:
1. Consider running proxy as Windows service
2. Add caching layer for frequent queries
3. Implement connection pooling
4. Add metrics collection (Prometheus)

---

## 9. Risk Mitigation

**Risk**: Proxy bridge crashes
```yaml
Impact: Claude Desktop loses connection (LOW - cron still works)
Mitigation:
  - Proxy is stateless (easy restart)
  - Document restart procedure
  - Consider Windows service wrapper
```

**Risk**: NGINX certificate expires
```yaml
Impact: SSL errors (MEDIUM - breaks MCP connection)
Mitigation:
  - Certbot auto-renewal configured
  - Monitor certificate expiry
  - Alert 30 days before expiration
```

**Risk**: Network latency too high
```yaml
Impact: Slow Claude Desktop responses (LOW - still usable)
Mitigation:
  - Monitor response times
  - Optimize NGINX configuration
  - Consider CloudFlare CDN if needed
```

---

**END OF PRIMARY-001 IMPLEMENTATION DOCUMENT**

**Status**: Ready for implementation  
**Estimated Effort**: 2-3 days  
**Dependencies**: None (can start immediately)  
**Blocking**: Paper trading validation (PRIMARY-003)

🎯 **Next Document**: PRIMARY-002-system-integration-testing.md
