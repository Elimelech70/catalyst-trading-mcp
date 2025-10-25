# Catalyst Trading System - Claude Desktop Deployment Guide

**Name of Application**: Catalyst Trading System  
**Name of file**: claude-desktop-deployment.md  
**Version**: 1.0.0  
**Last Updated**: 2025-10-18  
**Purpose**: Simple step-by-step deployment for Claude Desktop integration

---

## Architecture Overview

```
┌──────────────────────────┐
│ Claude Desktop           │
│ (Your Computer)          │
└────────────┬─────────────┘
             │
             │ HTTPS + API Key
             │ (Internet)
             ↓
┌──────────────────────────┐
│ DigitalOcean Droplet     │
│                          │
│  ┌────────────────────┐ │
│  │ Nginx (Port 443)   │ │
│  │ - SSL/TLS          │ │
│  │ - API Key Auth     │ │
│  └─────────┬──────────┘ │
│            │ HTTP        │
│            ↓             │
│  ┌────────────────────┐ │
│  │ Orchestration      │ │
│  │ (Port 5000)        │ │
│  │ - MCP Server       │ │
│  └─────────┬──────────┘ │
│            │             │
│            │ REST APIs   │
│            ↓             │
│  ┌────────────────────┐ │
│  │ Trading Services   │ │
│  │ - Scanner (5001)   │ │
│  │ - Pattern (5002)   │ │
│  │ - Technical (5003) │ │
│  │ - Risk (5004)      │ │
│  │ - Trading (5005)   │ │
│  │ - News (5008)      │ │
│  │ - Reporting (5009) │ │
│  └────────────────────┘ │
└──────────────────────────┘
```

---

## Prerequisites

### On DigitalOcean:
- ✅ Catalyst Trading System already deployed
- ✅ All services running (scanner, pattern, etc.)
- ✅ Port 5000 available internally

### On Your Computer:
- [ ] Claude Desktop installed (Windows, macOS, or Linux)
- [ ] Internet connection

### Domain/DNS:
- [ ] Domain name pointing to DigitalOcean IP (e.g., catalyst.yourdomain.com)
- OR use DigitalOcean IP directly with self-signed cert (testing only)

---

## Step 1: Deploy New Orchestration Service

### 1.1 Update Orchestration Service

Replace your current `orchestration-service.py` with the new v6.0 version.

**File Location:**
```
services/orchestration/orchestration-service.py
```

**The new file:**
- ✅ Uses HTTP transport (not WebSocket)
- ✅ Pure FastMCP (no FastAPI mixing)
- ✅ All MCP resources and tools included
- ✅ Ready for Nginx reverse proxy

### 1.2 Update Dockerfile (if needed)

```dockerfile
# services/orchestration/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service
COPY orchestration-service.py .

# Expose port
EXPOSE 5000

# Run service
CMD ["python", "orchestration-service.py"]
```

### 1.3 Update requirements.txt

```txt
# services/orchestration/requirements.txt
fastmcp>=2.0.0
aiohttp>=3.9.0
```

### 1.4 Restart Orchestration Service

```bash
# SSH into DigitalOcean
ssh root@your-droplet-ip

# Navigate to project
cd /path/to/catalyst-trading

# Rebuild and restart orchestration
docker-compose up -d --build orchestration

# Verify it's running
docker-compose logs orchestration

# Should see:
# "Catalyst Trading MCP Orchestration Service"
# "Version: 6.0.0"
# "Running on http://0.0.0.0:5000"
```

---

## Step 2: Set Up Nginx Reverse Proxy

### 2.1 Install Nginx and Certbot

```bash
# On DigitalOcean droplet
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2.2 Configure Nginx

**Create configuration file:**

```bash
sudo nano /etc/nginx/sites-available/catalyst-mcp
```

**Add this configuration:**

```nginx
# Catalyst MCP Server Configuration

# Generate a secure API key first:
# python3 -c "import secrets; print('catalyst_' + secrets.token_urlsafe(32))"

server {
    listen 80;
    server_name your-domain.com;  # CHANGE THIS
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # CHANGE THIS
    
    # SSL certificates (will be added by certbot)
    # ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # API Key authentication
    set $api_key "YOUR_API_KEY_HERE";  # CHANGE THIS
    
    # MCP endpoint
    location /mcp {
        # Validate API key
        if ($http_authorization != "Bearer $api_key") {
            return 401 '{"error": "Unauthorized"}';
        }
        
        # Proxy to orchestration service
        proxy_pass http://localhost:5000/mcp;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for HTTP SSE)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_read_timeout 86400;
        proxy_connect_timeout 60;
        proxy_send_timeout 60;
    }
    
    # Health check endpoint (no auth required)
    location /health {
        proxy_pass http://localhost:5000/health;
        proxy_http_version 1.1;
        access_log off;
    }
}
```

**Generate secure API key:**

```bash
python3 -c "import secrets; print('catalyst_' + secrets.token_urlsafe(32))"
```

**Save this key!** You'll need it for Claude Desktop configuration.

### 2.3 Enable Nginx Configuration

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/catalyst-mcp /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Should show: "test is successful"
```

### 2.4 Get SSL Certificate

**Option A: With Domain Name (Recommended)**

```bash
# Get Let's Encrypt certificate
sudo certbot --nginx -d your-domain.com --non-interactive --agree-tos --email your-email@example.com

# Enable auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

**Option B: Self-Signed Certificate (Testing Only)**

```bash
# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/catalyst-selfsigned.key \
    -out /etc/ssl/certs/catalyst-selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=Catalyst/CN=your-droplet-ip"

# Update nginx config to use these certificates
sudo nano /etc/nginx/sites-available/catalyst-mcp

# Add these lines in the ssl server block:
ssl_certificate /etc/ssl/certs/catalyst-selfsigned.crt;
ssl_certificate_key /etc/ssl/private/catalyst-selfsigned.key;
```

### 2.5 Start Nginx

```bash
# Start nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

---

## Step 3: Configure Firewall

```bash
# Enable firewall
sudo ufw --force enable

# Allow SSH (IMPORTANT!)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Allow HTTPS only
sudo ufw allow 443/tcp

# Block direct access to orchestration port
sudo ufw deny 5000/tcp

# Reload firewall
sudo ufw reload

# Check status
sudo ufw status

# Should show:
# 22/tcp     ALLOW       Anywhere
# 443/tcp    ALLOW       Anywhere
# 5000/tcp   DENY        Anywhere
```

---

## Step 4: Test the Setup

### 4.1 Test Health Endpoint

```bash
# From your local computer
curl https://your-domain.com/health

# Should return:
# OK - Orchestration v6.0.0
```

### 4.2 Test with API Key

```bash
# Test with correct API key
curl -H "Authorization: Bearer your_api_key_here" \
     https://your-domain.com/mcp

# Should return MCP protocol response

# Test with wrong API key
curl -H "Authorization: Bearer wrong_key" \
     https://your-domain.com/mcp

# Should return: 401 Unauthorized
```

---

## Step 5: Configure Claude Desktop

### 5.1 Find Configuration File Location

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### 5.2 Create/Edit Configuration

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "transport": "http",
      "url": "https://your-domain.com/mcp",
      "headers": {
        "Authorization": "Bearer your_api_key_here"
      }
    }
  }
}
```

**Replace:**
- `your-domain.com` with your actual domain or IP
- `your_api_key_here` with the API key you generated

### 5.3 Restart Claude Desktop

1. **Completely quit** Claude Desktop
2. **Restart** Claude Desktop
3. **Look for hammer icon** (🔨) in bottom right corner
4. If you see the hammer, MCP is connected! ✅

---

## Step 6: Verify Claude Integration

### 6.1 Basic Connection Test

In Claude Desktop, ask:

```
What's the current trading system status?
```

**Expected response:**
Claude should query the `system/health` resource and tell you about the status of all services.

### 6.2 Test Resources

```
Show me the current trading cycle information.
```

**Expected response:**
Claude should access `trading-cycle/current` resource.

### 6.3 Test Tools

```
Analyze the symbol AAPL for me.
```

**Expected response:**
Claude should use the `analyze_symbol` tool and return technical analysis.

---

## Complete Deployment Checklist

### DigitalOcean Setup:
- [ ] New orchestration-service.py v6.0 deployed
- [ ] Service running on port 5000
- [ ] Nginx installed and configured
- [ ] SSL certificate obtained
- [ ] API key generated and configured in Nginx
- [ ] Firewall configured (443 open, 5000 blocked)
- [ ] Health endpoint accessible: `https://your-domain.com/health`
- [ ] MCP endpoint requires authentication

### Claude Desktop Setup:
- [ ] Claude Desktop installed
- [ ] Configuration file created
- [ ] Correct URL configured
- [ ] API key added to config
- [ ] Claude Desktop restarted
- [ ] Hammer icon visible (🔨)

### Verification:
- [ ] Can query system health
- [ ] Can access trading cycle info
- [ ] Can use analysis tools
- [ ] Can start/stop trading cycles

---

## Troubleshooting

### No hammer icon in Claude Desktop

**Check:**
1. Configuration file location correct?
2. JSON syntax valid? (use jsonlint.com)
3. Claude Desktop fully restarted?
4. Check Claude Desktop logs

**Windows logs:**
```
%APPDATA%\Claude\logs\
```

**macOS logs:**
```
~/Library/Logs/Claude/
```

### Connection refused

**Check:**
1. Is orchestration service running?
   ```bash
   docker-compose ps orchestration
   ```

2. Is Nginx running?
   ```bash
   sudo systemctl status nginx
   ```

3. Is firewall blocking?
   ```bash
   sudo ufw status
   ```

4. Can you access health endpoint?
   ```bash
   curl https://your-domain.com/health
   ```

### 401 Unauthorized

**Check:**
1. API key matches between Nginx and Claude Desktop config
2. Authorization header format: `Bearer your_key`
3. No extra spaces in API key

### SSL Certificate errors

**Check:**
1. Certificate valid?
   ```bash
   sudo certbot certificates
   ```

2. If using self-signed, may need to accept certificate warning

---

## Quick Command Reference

```bash
# Restart orchestration service
docker-compose restart orchestration

# View orchestration logs
docker-compose logs -f orchestration

# Restart Nginx
sudo systemctl restart nginx

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Test Nginx configuration
sudo nginx -t

# Renew SSL certificate manually
sudo certbot renew

# Check firewall status
sudo ufw status verbose
```

---

## Security Notes

1. **API Key:** Keep your API key secure and never commit to version control
2. **SSL:** Always use valid SSL certificates in production
3. **Firewall:** Never expose port 5000 directly to internet
4. **Updates:** Keep Nginx and SSL certificates updated
5. **Monitoring:** Set up alerts for service health

---

## Next Steps After Deployment

Once Claude Desktop is connected:

1. **Test basic queries:**
   - "What's the system status?"
   - "Show me the latest market scan"
   - "What are the current risk metrics?"

2. **Try trading operations:**
   - "Start a conservative trading cycle"
   - "Analyze TSLA for me"
   - "Show me open positions"

3. **Explore advanced features:**
   - "What was our best trade today?"
   - "Give me a daily performance summary"
   - "What are the top 5 trading candidates?"

---

## Support

If you encounter issues:

1. Check logs: `docker-compose logs orchestration`
2. Verify Nginx: `sudo nginx -t`
3. Test connectivity: `curl https://your-domain.com/health`
4. Review Claude Desktop logs

---

**You're now ready to deploy!** 🚀

The orchestration service v6.0 is already created. Follow the steps above to get Claude Desktop connected to your Catalyst Trading System.
