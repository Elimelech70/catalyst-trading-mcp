# Claude Desktop to DigitalOcean Droplet Configuration Guide

**Name of Application**: Catalyst Trading System  
**Name of file**: claude-desktop-droplet-setup.md  
**Version**: 1.0.0  
**Last Updated**: 2025-09-20  
**Purpose**: Complete guide for connecting Claude Desktop to DigitalOcean Catalyst Trading System

---

## Overview

This guide provides step-by-step instructions for establishing secure communication between Claude Desktop running on Windows and the Catalyst Trading System deployed on DigitalOcean using Docker containers.

**Architecture:**
```
Windows Claude Desktop → SSH Tunnel → DigitalOcean Droplet → Docker Container (Orchestration Service Port 5000)
```

---

## Method 1: SSH Tunnel Connection (Recommended)

### Step 1: Generate SSH Keys on DigitalOcean

**In VSCode Terminal (connected to DigitalOcean):**

```bash
# Navigate to SSH directory
cd ~/.ssh

# Generate SSH key pair specifically for Claude Desktop access
ssh-keygen -t rsa -b 4096 -f ~/.ssh/claude_desktop_key -C "claude-desktop-access"

# Add public key to authorized_keys on the same DigitalOcean machine
cat ~/.ssh/claude_desktop_key.pub >> ~/.ssh/authorized_keys

# Set proper permissions
chmod 600 ~/.ssh/claude_desktop_key
chmod 644 ~/.ssh/claude_desktop_key.pub  
chmod 600 ~/.ssh/authorized_keys

# Display private key for copying to Windows
echo "=== COPY THIS PRIVATE KEY TO WINDOWS ==="
cat ~/.ssh/claude_desktop_key
echo "=== END PRIVATE KEY ==="
```

### Step 2: Copy Private Key to Windows

**Option A: Copy/Paste Method (Simplest)**
1. Copy the entire private key output (including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----`)
2. On Windows, create directory: `mkdir C:\Users\%USERNAME%\.ssh`
3. Open Notepad and paste the key content
4. Save as: `C:\Users\%USERNAME%\.ssh\claude_desktop_key` (ensure no .txt extension)

**Option B: SCP Method**
```powershell
# From Windows PowerShell/Command Prompt
mkdir C:\Users\%USERNAME%\.ssh

# Copy the file using scp (replace YOUR_DROPLET_IP)
scp root@YOUR_DROPLET_IP:~/.ssh/claude_desktop_key C:\Users\%USERNAME%\.ssh\claude_desktop_key
```

### Step 3: Create SSH Tunnel from Windows

**From Windows PowerShell or Command Prompt:**

```powershell
# Test SSH connection first
ssh -i C:\Users\%USERNAME%\.ssh\claude_desktop_key root@YOUR_DROPLET_IP

# If successful, exit and create the tunnel
# Create SSH tunnel (replace YOUR_DROPLET_IP with actual IP)
ssh -i C:\Users\%USERNAME%\.ssh\claude_desktop_key -L 5000:localhost:5000 root@YOUR_DROPLET_IP -N

# Leave this terminal window open while using Claude Desktop
```

**What this does:**
- Creates secure tunnel: Windows `localhost:5000` → DigitalOcean `localhost:5000`
- `-N` means "don't run commands, just tunnel"
- `-L 5000:localhost:5000` forwards local port 5000 to remote port 5000

### Step 4: Test Tunnel Connection

**In a new Windows terminal:**
```powershell
# Test connection through tunnel
curl http://localhost:5000/health

# Should return orchestration service health status
# Example: {"status":"healthy","service":"orchestration","version":"4.1.0"}
```

### Step 5: Configure Claude Desktop

**Create/Update:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node",
      "args": [
        "-e",
        "const http = require('http'); const server = http.createServer((req, res) => { const options = { hostname: 'localhost', port: 5000, path: req.url, method: req.method, headers: req.headers }; const proxyReq = http.request(options, (proxyRes) => { res.writeHead(proxyRes.statusCode, proxyRes.headers); proxyRes.pipe(res); }); req.pipe(proxyReq); }); server.listen(0, () => { console.log('MCP proxy ready'); });"
      ]
    }
  }
}
```

### Step 6: Test Claude Desktop Connection

1. Ensure SSH tunnel is running (from Step 3)
2. Restart Claude Desktop completely
3. Look for hammer icon (🔨) in bottom right
4. Test with Claude: "What's the current trading system status?"
5. Try: "Show me the trading dashboard"
6. Try: "Get current positions"

---

## Method 2: Direct Port Access (Less Secure, Faster Setup)

### Step 1: Open Firewall Port on DigitalOcean

**In VSCode Terminal (DigitalOcean):**

```bash
# Find your Windows machine's IP address
# Visit https://whatismyipaddress.com/ to get your public IP

# Allow access from your IP only (replace YOUR_WINDOWS_IP)
ufw allow from YOUR_WINDOWS_IP to any port 5000

# Check firewall status
ufw status
```

### Step 2: Configure Claude Desktop for Direct Connection

**Create/Update:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node",
      "args": [
        "-e",
        "const http = require('http'); const server = http.createServer((req, res) => { const options = { hostname: 'YOUR_DROPLET_IP', port: 5000, path: req.url, method: req.method, headers: req.headers }; const proxyReq = http.request(options, (proxyRes) => { res.writeHead(proxyRes.statusCode, proxyRes.headers); proxyRes.pipe(res); }); req.pipe(proxyReq); }); server.listen(0, () => { console.log('MCP proxy ready'); });"
      ]
    }
  }
}
```

### Step 3: Test Direct Connection

```powershell
# From Windows, test direct connection
curl http://YOUR_DROPLET_IP:5000/health
```

---

## Method 3: Nginx Proxy with HTTP (Good Balance)

### Step 1: Install and Configure Nginx on DigitalOcean

**In VSCode Terminal (DigitalOcean):**

```bash
# Install Nginx
apt update
apt install nginx -y

# Create Nginx configuration for Catalyst MCP
cat > /etc/nginx/sites-available/catalyst << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
    
    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
}
EOF

# Enable the site
ln -s /etc/nginx/sites-available/catalyst /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Start Nginx
systemctl enable nginx
systemctl restart nginx

# Open HTTP port
ufw allow 80/tcp
```

### Step 2: Configure Claude Desktop for HTTP Connection

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node", 
      "args": [
        "-e",
        "const http = require('http'); const server = http.createServer((req, res) => { const options = { hostname: 'YOUR_DROPLET_IP', port: 80, path: req.url, method: req.method, headers: req.headers }; const proxyReq = http.request(options, (proxyRes) => { res.writeHead(proxyRes.statusCode, proxyRes.headers); proxyRes.pipe(res); }); req.pipe(proxyReq); }); server.listen(0, () => { console.log('MCP proxy ready'); });"
      ]
    }
  }
}
```

---

## Troubleshooting Guide

### Common Connection Issues

**Issue: SSH key permission errors**
```bash
# Fix key permissions on Windows (in PowerShell as Administrator)
icacls C:\Users\%USERNAME%\.ssh\claude_desktop_key /inheritance:r
icacls C:\Users\%USERNAME%\.ssh\claude_desktop_key /grant:r %USERNAME%:R
```

**Issue: SSH tunnel connection refused**
```bash
# Check if orchestration service is running on DigitalOcean
docker-compose ps orchestration

# Check service logs
docker-compose logs orchestration --tail=20

# Restart orchestration service if needed
docker-compose restart orchestration
```

**Issue: Claude Desktop not showing hammer icon**

1. Verify `claude_desktop_config.json` file location: `%APPDATA%\Claude\`
2. Check JSON syntax with online validator
3. Restart Claude Desktop completely
4. Check Windows Event Viewer for Claude Desktop errors

**Issue: Tunnel works but Claude can't connect**

```powershell
# Test tunnel functionality
curl http://localhost:5000/health

# If tunnel works but Claude doesn't, try simpler config:
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "python",
      "args": ["-c", "import http.server; import socketserver; import urllib.request; class ProxyHandler(http.server.BaseHTTPRequestHandler): def do_GET(self): self.proxy_request(); def do_POST(self): self.proxy_request(); def proxy_request(self): try: url = 'http://localhost:5000' + self.path; req = urllib.request.Request(url); with urllib.request.urlopen(req) as response: self.send_response(200); self.end_headers(); self.wfile.write(response.read()); except: self.send_response(500); self.end_headers(); with socketserver.TCPServer(('', 0), ProxyHandler) as httpd: httpd.serve_forever()"]
    }
  }
}
```

### Testing Commands

**Test SSH Connection:**
```powershell
# Basic SSH test
ssh -i C:\Users\%USERNAME%\.ssh\claude_desktop_key root@YOUR_DROPLET_IP "echo 'SSH connection successful'"

# Test port forwarding
ssh -i C:\Users\%USERNAME%\.ssh\claude_desktop_key -L 5000:localhost:5000 root@YOUR_DROPLET_IP -N &
curl http://localhost:5000/health
```

**Test Docker Services:**
```bash
# Check all services status
docker-compose ps

# Check orchestration service specifically
docker-compose logs orchestration --tail=10

# Test orchestration service directly
curl http://localhost:5000/health
```

**Test Claude Desktop Configuration:**
```powershell
# Validate JSON syntax
powershell -c "Get-Content '%APPDATA%\Claude\claude_desktop_config.json' | ConvertFrom-Json"

# Check Claude Desktop logs (if available)
# Look in Windows Event Viewer under Applications
```

---

## Security Considerations

### SSH Tunnel Security (Recommended)
- Uses encrypted SSH connection
- No exposed ports on DigitalOcean
- Key-based authentication
- Limited to specific key access

### Direct Port Access Security
- Exposes trading system port to internet
- Should limit to specific IP addresses only  
- Consider for development/testing only
- Not recommended for production trading

### Nginx Proxy Security
- Standard HTTP proxy setup
- Can add authentication if needed
- Good balance of security and simplicity
- Consider SSL certificate for production

---

## Configuration File Templates

### Complete Claude Desktop Config (SSH Tunnel)
```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node",
      "args": [
        "-e",
        "const http = require('http'); const server = http.createServer((req, res) => { console.log(`${req.method} ${req.url}`); const options = { hostname: 'localhost', port: 5000, path: req.url, method: req.method, headers: req.headers }; const proxyReq = http.request(options, (proxyRes) => { res.writeHead(proxyRes.statusCode, proxyRes.headers); proxyRes.pipe(res); }).on('error', (err) => { console.error('Proxy error:', err); res.writeHead(500); res.end('Proxy error'); }); if (req.method === 'POST' || req.method === 'PUT') { req.pipe(proxyReq); } else { proxyReq.end(); } }); server.listen(0, () => { console.log('MCP proxy server started'); });"
      ]
    }
  }
}
```

### Windows SSH Connection Script
```batch
@echo off
echo Starting SSH tunnel for Claude Desktop...
echo Press Ctrl+C to stop the tunnel

ssh -i C:\Users\%USERNAME%\.ssh\claude_desktop_key -L 5000:localhost:5000 root@YOUR_DROPLET_IP -N

echo SSH tunnel stopped
pause
```

Save as `start-claude-tunnel.bat` for easy tunnel startup.

---

## Validation Steps

### Step-by-Step Validation Process

1. **SSH Key Generation Complete**
   - [ ] Keys generated on DigitalOcean
   - [ ] Public key added to authorized_keys
   - [ ] Private key copied to Windows
   - [ ] Key permissions set correctly

2. **SSH Connection Working**
   - [ ] Basic SSH connection successful
   - [ ] SSH tunnel creates without errors
   - [ ] Local port 5000 accessible

3. **Docker Services Operational**
   - [ ] Orchestration service running
   - [ ] Health endpoint responding
   - [ ] All required services healthy

4. **Claude Desktop Integration**
   - [ ] Config file created correctly
   - [ ] Claude Desktop shows hammer icon
   - [ ] Basic trading queries work
   - [ ] MCP tools and resources accessible

### Success Indicators

**SSH Tunnel Success:**
```powershell
curl http://localhost:5000/health
# Returns: {"status":"healthy","service":"orchestration",...}
```

**Claude Desktop Success:**
- Hammer icon appears in Claude Desktop
- Claude responds to: "What's the current trading system status?"
- Claude can access: trading cycle data, risk metrics, position information

**Full Integration Success:**
- Claude can start/stop trading cycles
- Claude can review market scan results  
- Claude can validate trades through risk manager
- Claude can monitor portfolio performance

---

## Next Steps After Connection

Once Claude Desktop is connected to your DigitalOcean Catalyst Trading System:

1. **Test Basic Functionality**
   - Query system status
   - Review trading cycle capabilities
   - Test risk management integration

2. **Implement Phase 2 Security**
   - Add SSL certificates for HTTPS
   - Implement API key authentication
   - Set up audit logging

3. **Enable Advanced Features**
   - Live market data integration testing
   - Paper trading execution through Claude
   - Performance monitoring and reporting

4. **Prepare for Phase 3**
   - Plan ML model integration
   - Design enhanced data processing
   - Develop Claude-assisted trading strategies

The connection established here provides the foundation for transforming your operational trading system into an AI-assisted trading platform with Claude as your strategic partner.

---

*Once connection is established, Claude Desktop becomes your interface to the complete Catalyst Trading System, enabling sophisticated trading analysis and decision-making capabilities.*