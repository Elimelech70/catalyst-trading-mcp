# Catalyst Trading System - Claude Desktop Secure Access Guide v4.2

**Name of Application**: Catalyst Trading System  
**Name of file**: claude-desktop-secure-access-v42.md  
**Version**: 4.2.0  
**Last Updated**: 2025-09-14  
**Purpose**: Staged secure access implementation for Claude Desktop to existing Catalyst Trading MCP system

**REVISION HISTORY**:
- v4.2.0 (2025-09-14) - Focused on secure access to existing system
  - Phase 1: Basic secure connection setup
  - Phase 2: Enhanced authentication and encryption
  - Phase 3: Enterprise-grade access security
  - DigitalOcean security configuration
  - Certificate management for existing system
  - Progressive security hardening approach

**Description of Service**:
This guide provides a staged approach to securely connect Claude Desktop on Windows 11 to your existing Catalyst Trading MCP system. Focuses purely on access security, authentication, and encrypted communications.

---

## Implementation Stages Overview

```
Phase 1 (Week 1): Basic Secure Connection
├── HTTPS/SSL setup on existing system
├── Basic authentication tokens
├── Simple Windows MCP client
└── Connection validation

Phase 2 (Week 2-3): Enhanced Security
├── Advanced authentication
├── Windows security integration
├── Connection monitoring
└── Backup access methods

Phase 3 (Month 2+): Enterprise Access Security
├── Advanced threat detection
├── Audit logging
├── Multi-factor authentication
└── Zero-trust architecture
```

---

## Phase 1: Basic Secure Connection (Priority)

### 1.1 Secure Your Existing DigitalOcean Infrastructure

#### 1.1.1 SSL Certificate Setup for Existing System

**Option A: Let's Encrypt (Free, Recommended)**

```bash
# SSH into your DigitalOcean droplet where Catalyst is running
ssh root@your-droplet-ip

# Install Certbot and Nginx (if not already installed)
apt update
apt install certbot python3-certbot-nginx nginx -y

# Create Nginx configuration for your existing MCP service
cat > /etc/nginx/sites-available/catalyst-mcp << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;  # Replace with your domain
    
    # SSL Configuration will be added by Certbot
    
    # Proxy to your existing MCP service (usually port 5000)
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
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
EOF

# Enable the site
ln -s /etc/nginx/sites-available/catalyst-mcp /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site

# Test Nginx configuration
nginx -t

# Start Nginx
systemctl enable nginx
systemctl start nginx

# Get SSL certificate (replace your-domain.com)
certbot --nginx -d your-domain.com --non-interactive --agree-tos --email your-email@example.com

# Setup auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer
```

**Option B: Use IP Address with Self-Signed Certificate (Testing Only)**

```bash
# Generate self-signed certificate for testing
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/catalyst-selfsigned.key \
    -out /etc/ssl/certs/catalyst-selfsigned.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=your-droplet-ip"

# Update Nginx config to use self-signed cert
# (Modify the server block above to include SSL certificate paths)
```

#### 1.1.2 Firewall Configuration

```bash
# Configure UFW for secure access
ufw --force enable
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (change port if you use custom SSH port)
ufw allow ssh

# Allow HTTPS only (remove direct access to MCP port)
ufw allow 443/tcp

# Remove any existing rules for port 5000 or other MCP ports
ufw delete allow 5000/tcp

# Reload firewall
ufw reload
ufw status
```

#### 1.1.3 Basic Authentication for MCP Service

**Add simple API key authentication to your existing MCP service:**

```javascript
// Add this to your existing orchestration service
class SimpleAPIAuth {
    constructor() {
        // Generate a secure API key for Claude Desktop
        this.claudeDesktopKey = process.env.CLAUDE_DESKTOP_API_KEY || this.generateSecureKey();
        console.log('Claude Desktop API Key:', this.claudeDesktopKey);
        console.log('Add this key to your Windows client configuration');
    }
    
    generateSecureKey() {
        const crypto = require('crypto');
        return 'catalyst_' + crypto.randomBytes(32).toString('hex');
    }
    
    validateRequest(req, res, next) {
        const authHeader = req.headers.authorization;
        
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Missing or invalid authorization header' });
        }
        
        const token = authHeader.substring(7);
        
        if (token !== this.claudeDesktopKey) {
            return res.status(401).json({ error: 'Invalid API key' });
        }
        
        // Add client info to request
        req.client = { name: 'claude-desktop', authenticated: true };
        next();
    }
}

// Use in your existing Express/FastAPI routes
const auth = new SimpleAPIAuth();

// Apply to all MCP routes
app.use('/api/*', auth.validateRequest.bind(auth));
```

**Add to your existing .env file:**
```bash
# Generate a secure key and add to your .env
CLAUDE_DESKTOP_API_KEY=catalyst_your_generated_secure_key_here
```

### 1.2 Windows 11 Client Setup (Minimal Security)

#### 1.2.1 System Preparation

```yaml
Required:
  - Windows 11 (any edition)
  - Claude Desktop (latest version)
  - Node.js LTS installed
  - Internet connection

Recommended:
  - Windows Defender enabled (default)
  - Automatic updates enabled
  - Standard user account (not administrator)

Optional for Phase 3:
  - TPM 2.0 for credential storage
  - BitLocker for disk encryption
  - Enterprise security features
```

#### 1.2.2 Secure MCP Client Implementation

**Create folder:** `C:\CatalystTrading\`

**Create:** `C:\CatalystTrading\secure-client.js`

```javascript
const https = require('https');
const fs = require('fs');
const path = require('path');

class SecureCatalystClient {
    constructor() {
        this.baseUrl = process.env.CATALYST_ENDPOINT;
        this.apiKey = process.env.CATALYST_API_KEY;
        this.logFile = path.join(__dirname, 'client.log');
        
        if (!this.baseUrl || !this.apiKey) {
            throw new Error('Missing required environment variables: CATALYST_ENDPOINT, CATALYST_API_KEY');
        }
        
        this.setupMCPServer();
        this.log('Client initialized', { endpoint: this.baseUrl });
    }
    
    log(message, data = {}) {
        const timestamp = new Date().toISOString();
        const logEntry = `${timestamp}: ${message} ${JSON.stringify(data)}\n`;
        
        console.log(logEntry.trim());
        
        // Simple file logging
        try {
            fs.appendFileSync(this.logFile, logEntry);
        } catch (error) {
            console.error('Failed to write to log file:', error);
        }
    }
    
    setupMCPServer() {
        const { MCPServer } = require('@anthropic-ai/mcp-server');
        this.server = new MCPServer();
        
        // Register trading tools
        this.server.tool('get_trading_status', 'Get current trading status', {}, 
            async () => this.secureRequest('GET', '/api/status'));
            
        this.server.tool('start_trading_cycle', 'Start daily trading cycle', {}, 
            async () => this.secureRequest('POST', '/api/trading/start'));
            
        this.server.tool('get_positions', 'Get current positions', {}, 
            async () => this.secureRequest('GET', '/api/positions'));
            
        this.server.tool('get_market_scan', 'Get current market scan results', {}, 
            async () => this.secureRequest('GET', '/api/scan/current'));
            
        this.server.tool('emergency_stop', 'Emergency stop all trading', {}, 
            async () => this.secureRequest('POST', '/api/trading/emergency-stop'));
        
        // Register resources
        this.server.resource('trading-dashboard', 'Trading dashboard data',
            async () => this.secureRequest('GET', '/api/dashboard'));
            
        this.server.resource('performance-metrics', 'Performance metrics',
            async () => this.secureRequest('GET', '/api/metrics/performance'));
    }
    
    async secureRequest(method, path, body = null) {
        return new Promise((resolve, reject) => {
            const url = new URL(this.baseUrl + path);
            
            const options = {
                hostname: url.hostname,
                port: url.port || 443,
                path: url.pathname + url.search,
                method: method,
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json',
                    'User-Agent': 'CatalystMCP-SecureClient/1.0'
                },
                // SSL options
                rejectUnauthorized: true, // Verify SSL certificates
                timeout: 30000
            };
            
            if (body) {
                const bodyString = JSON.stringify(body);
                options.headers['Content-Length'] = Buffer.byteLength(bodyString);
            }
            
            this.log('Making request', { method, path, headers: this.sanitizeHeaders(options.headers) });
            
            const req = https.request(options, (res) => {
                let data = '';
                
                res.on('data', (chunk) => {
                    data += chunk;
                });
                
                res.on('end', () => {
                    this.log('Request completed', { 
                        statusCode: res.statusCode, 
                        path,
                        responseSize: data.length 
                    });
                    
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        try {
                            const jsonData = JSON.parse(data);
                            resolve(jsonData);
                        } catch (error) {
                            resolve({ success: true, raw: data });
                        }
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${data}`));
                    }
                });
            });
            
            req.on('error', (error) => {
                this.log('Request error', { error: error.message, path });
                reject(error);
            });
            
            req.on('timeout', () => {
                this.log('Request timeout', { path });
                req.destroy();
                reject(new Error('Request timeout'));
            });
            
            if (body) {
                req.write(JSON.stringify(body));
            }
            
            req.end();
        });
    }
    
    sanitizeHeaders(headers) {
        // Remove sensitive data from logs
        const sanitized = { ...headers };
        if (sanitized.Authorization) {
            sanitized.Authorization = 'Bearer [REDACTED]';
        }
        return sanitized;
    }
    
    start() {
        this.log('Starting MCP server');
        this.server.run();
    }
}

// Handle process termination gracefully
process.on('SIGINT', () => {
    console.log('\nReceived SIGINT. Graceful shutdown...');
    process.exit(0);
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

// Start the client
try {
    const client = new SecureCatalystClient();
    client.start();
} catch (error) {
    console.error('Failed to start client:', error.message);
    process.exit(1);
}
```

#### 1.2.3 Claude Desktop Configuration

**Create/Update:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node",
      "args": [
        "C:\\CatalystTrading\\secure-client.js"
      ],
      "env": {
        "CATALYST_ENDPOINT": "https://your-domain.com",
        "CATALYST_API_KEY": "catalyst_your_generated_secure_key_here"
      }
    }
  }
}
```

#### 1.2.4 Test Basic Secure Connection

**Create test script:** `C:\CatalystTrading\test-connection.js`

```javascript
const https = require('https');

const endpoint = 'https://your-domain.com/api/status';  // Replace with your domain
const apiKey = 'catalyst_your_generated_secure_key_here';  // Replace with your API key

const options = {
    headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    }
};

console.log('Testing connection to:', endpoint);

https.get(endpoint, options, (res) => {
    let data = '';
    
    res.on('data', (chunk) => {
        data += chunk;
    });
    
    res.on('end', () => {
        console.log('Status Code:', res.statusCode);
        console.log('Response:', data);
        
        if (res.statusCode === 200) {
            console.log('✅ Connection successful!');
        } else {
            console.log('❌ Connection failed!');
        }
    });
}).on('error', (error) => {
    console.error('❌ Connection error:', error.message);
});
```

**Run test:**
```cmd
cd C:\CatalystTrading\
node test-connection.js
```

### 1.3 Validation Phase 1

```cmd
# Test from Windows Command Prompt
cd C:\CatalystTrading\
node test-connection.js

# Should see:
# ✅ Connection successful!
# Status Code: 200
# Response: {"status":"healthy","timestamp":"..."}
```

**Test Claude Desktop Integration:**
1. Restart Claude Desktop completely
2. Look for hammer icon (🔨) in bottom right
3. Ask Claude: "What's the current trading status?"
4. Try: "Show me the trading dashboard"
5. Try: "Get current positions"

---

## Phase 2: Enhanced Security (Week 2-3)

### 2.1 Advanced Authentication

#### 2.1.1 Token Rotation System

**Add to your existing MCP service:**

```javascript
class TokenRotationAuth {
    constructor() {
        this.tokens = new Map();
        this.refreshTokens = new Map();
        this.tokenLifetime = 3600000; // 1 hour
        this.refreshLifetime = 86400000; // 24 hours
    }
    
    generateTokenPair(clientId) {
        const crypto = require('crypto');
        
        const accessToken = crypto.randomBytes(32).toString('hex');
        const refreshToken = crypto.randomBytes(32).toString('hex');
        
        const now = Date.now();
        
        this.tokens.set(accessToken, {
            clientId,
            created: now,
            expires: now + this.tokenLifetime
        });
        
        this.refreshTokens.set(refreshToken, {
            clientId,
            accessToken,
            created: now,
            expires: now + this.refreshLifetime
        });
        
        return { accessToken, refreshToken, expiresIn: this.tokenLifetime };
    }
    
    validateToken(token) {
        const tokenData = this.tokens.get(token);
        
        if (!tokenData) {
            return { valid: false, reason: 'Token not found' };
        }
        
        if (Date.now() > tokenData.expires) {
            this.tokens.delete(token);
            return { valid: false, reason: 'Token expired' };
        }
        
        return { valid: true, clientId: tokenData.clientId };
    }
    
    refreshAccessToken(refreshToken) {
        const refreshData = this.refreshTokens.get(refreshToken);
        
        if (!refreshData || Date.now() > refreshData.expires) {
            return null;
        }
        
        // Invalidate old access token
        this.tokens.delete(refreshData.accessToken);
        
        // Generate new token pair
        return this.generateTokenPair(refreshData.clientId);
    }
}

// Add refresh endpoint to your existing API
app.post('/api/auth/refresh', (req, res) => {
    const { refreshToken } = req.body;
    const newTokens = tokenAuth.refreshAccessToken(refreshToken);
    
    if (newTokens) {
        res.json(newTokens);
    } else {
        res.status(401).json({ error: 'Invalid refresh token' });
    }
});
```

#### 2.1.2 Windows Credential Storage

**Enhanced Windows client with credential management:**

```javascript
// Add to secure-client.js
const os = require('os');
const { spawn } = require('child_process');

class WindowsCredentialManager {
    constructor() {
        this.credentialTarget = 'CatalystTrading:APIAccess';
    }
    
    async storeCredentials(accessToken, refreshToken) {
        if (os.platform() !== 'win32') {
            // Fallback to environment variables on non-Windows
            return this.storeInEnv(accessToken, refreshToken);
        }
        
        try {
            // Store access token
            await this.runCmdKey('add', `${this.credentialTarget}:AccessToken`, 'catalyst-user', accessToken);
            
            // Store refresh token  
            await this.runCmdKey('add', `${this.credentialTarget}:RefreshToken`, 'catalyst-user', refreshToken);
            
            return true;
        } catch (error) {
            console.error('Failed to store credentials:', error);
            return false;
        }
    }
    
    async retrieveCredentials() {
        if (os.platform() !== 'win32') {
            return this.retrieveFromEnv();
        }
        
        try {
            const accessToken = await this.runCmdKey('list', `${this.credentialTarget}:AccessToken`);
            const refreshToken = await this.runCmdKey('list', `${this.credentialTarget}:RefreshToken`);
            
            return { accessToken, refreshToken };
        } catch (error) {
            console.error('Failed to retrieve credentials:', error);
            return null;
        }
    }
    
    runCmdKey(action, target, user = null, password = null) {
        return new Promise((resolve, reject) => {
            let args;
            
            if (action === 'add') {
                args = ['/add:' + target, '/user:' + user, '/pass:' + password];
            } else if (action === 'list') {
                args = ['/list:' + target];
            }
            
            const process = spawn('cmdkey', args, { windowsHide: true });
            let output = '';
            
            process.stdout.on('data', (data) => {
                output += data.toString();
            });
            
            process.on('close', (code) => {
                if (code === 0) {
                    resolve(output);
                } else {
                    reject(new Error(`cmdkey failed with code ${code}`));
                }
            });
        });
    }
}
```

### 2.2 Connection Monitoring

#### 2.2.1 Simple Connection Health Monitoring

**Add to secure-client.js:**

```javascript
class ConnectionMonitor {
    constructor(client) {
        this.client = client;
        this.healthCheckInterval = 60000; // 1 minute
        this.failedChecks = 0;
        this.maxFailures = 3;
        this.isMonitoring = false;
    }
    
    startMonitoring() {
        if (this.isMonitoring) return;
        
        this.isMonitoring = true;
        this.client.log('Started connection monitoring');
        
        this.monitorInterval = setInterval(() => {
            this.performHealthCheck();
        }, this.healthCheckInterval);
    }
    
    async performHealthCheck() {
        try {
            await this.client.secureRequest('GET', '/api/health');
            
            if (this.failedChecks > 0) {
                this.client.log('Connection restored', { previousFailures: this.failedChecks });
            }
            
            this.failedChecks = 0;
        } catch (error) {
            this.failedChecks++;
            this.client.log('Health check failed', { 
                failures: this.failedChecks, 
                maxFailures: this.maxFailures,
                error: error.message 
            });
            
            if (this.failedChecks >= this.maxFailures) {
                this.handleConnectionFailure();
            }
        }
    }
    
    handleConnectionFailure() {
        this.client.log('Connection failure threshold reached - attempting recovery');
        
        // Attempt token refresh if we have refresh capabilities
        if (this.client.credentialManager) {
            this.attemptTokenRefresh();
        }
        
        // Reset failure count to avoid spam
        this.failedChecks = 0;
    }
    
    async attemptTokenRefresh() {
        try {
            const credentials = await this.client.credentialManager.retrieveCredentials();
            if (credentials && credentials.refreshToken) {
                const response = await this.client.secureRequest('POST', '/api/auth/refresh', {
                    refreshToken: credentials.refreshToken
                });
                
                if (response.accessToken) {
                    this.client.apiKey = response.accessToken;
                    await this.client.credentialManager.storeCredentials(
                        response.accessToken, 
                        response.refreshToken
                    );
                    
                    this.client.log('Successfully refreshed access token');
                }
            }
        } catch (error) {
            this.client.log('Token refresh failed', { error: error.message });
        }
    }
    
    stopMonitoring() {
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
            this.isMonitoring = false;
            this.client.log('Stopped connection monitoring');
        }
    }
}

// Add to SecureCatalystClient constructor
this.monitor = new ConnectionMonitor(this);
this.monitor.startMonitoring();
```

### 2.3 Enhanced Logging and Audit Trail

**Create:** `C:\CatalystTrading\audit-logger.js`

```javascript
const fs = require('fs');
const path = require('path');

class AuditLogger {
    constructor() {
        this.logDir = path.join(__dirname, 'logs');
        this.ensureLogDirectory();
    }
    
    ensureLogDirectory() {
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }
    }
    
    log(category, event, details = {}) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            category,
            event,
            details,
            sessionId: this.getSessionId()
        };
        
        // Write to category-specific log file
        const filename = `${category}-${this.getDateString()}.log`;
        const filepath = path.join(this.logDir, filename);
        
        try {
            fs.appendFileSync(filepath, JSON.stringify(logEntry) + '\n');
        } catch (error) {
            console.error('Failed to write audit log:', error);
        }
        
        // Also write to console in development
        if (process.env.NODE_ENV !== 'production') {
            console.log(`[${category}] ${event}:`, details);
        }
    }
    
    getSessionId() {
        if (!this.sessionId) {
            const crypto = require('crypto');
            this.sessionId = crypto.randomBytes(8).toString('hex');
        }
        return this.sessionId;
    }
    
    getDateString() {
        return new Date().toISOString().split('T')[0];
    }
}

module.exports = AuditLogger;
```

---

## Phase 3: Enterprise Access Security (Month 2+)

### 3.1 Advanced Features (Future Implementation)

```yaml
Advanced Security Features (Implement Later):
  
  Multi-Factor Authentication:
    - Hardware security keys (YubiKey)
    - Time-based OTP (TOTP)
    - SMS/Email verification codes
    
  Zero-Trust Network Access:
    - VPN with certificate authentication
    - Network micro-segmentation
    - Device compliance verification
    
  Advanced Threat Detection:
    - Behavioral analysis
    - Anomaly detection
    - Machine learning threat models
    
  Enterprise Compliance:
    - SOC 2 compliance logging
    - GDPR data protection
    - Financial services regulations
    
  High Availability:
    - Multi-region deployment
    - Automated failover
    - Load balancing
```

---

## Quick Implementation Checklist

### Phase 1 - Basic Secure Connection ✅

**Server-Side (DigitalOcean):**
- [ ] Install Nginx and configure SSL proxy
- [ ] Get SSL certificate (Let's Encrypt or custom)
- [ ] Configure firewall (only HTTPS/443 allowed)
- [ ] Add API key authentication to existing MCP service
- [ ] Test HTTPS endpoint with curl

**Client-Side (Windows 11):**
- [ ] Install Node.js if not present
- [ ] Create secure MCP client script
- [ ] Configure Claude Desktop with HTTPS endpoint
- [ ] Test connection with test script
- [ ] Verify Claude Desktop shows hammer icon

**Validation:**
- [ ] HTTPS connection works without certificate warnings
- [ ] API authentication prevents unauthorized access
- [ ] Claude can successfully query trading status
- [ ] All MCP tools and resources accessible

### Phase 2 - Enhanced Security (Later)
- [ ] Implement token rotation system
- [ ] Add Windows Credential Manager integration
- [ ] Setup connection monitoring
- [ ] Enable audit logging
- [ ] Test failover scenarios

---

## Configuration Templates

### Environment Variables Template
```bash
# Add to your existing .env file on DigitalOcean
CLAUDE_DESKTOP_API_KEY=catalyst_your_generated_secure_key_here
ENABLE_TOKEN_ROTATION=false  # Enable in Phase 2
MAX_FAILED_CONNECTIONS=3
CONNECTION_TIMEOUT=30000
```

### Windows Client Environment Template
```json
{
  "mcpServers": {
    "catalyst-trading": {
      "command": "node",
      "args": ["C:\\CatalystTrading\\secure-client.js"],
      "env": {
        "CATALYST_ENDPOINT": "https://your-domain.com",
        "CATALYST_API_KEY": "catalyst_your_generated_secure_key_here",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## Testing Your Secure Setup

### Connection Tests
```bash
# Test 1: Basic HTTPS connectivity
curl -H "Authorization: Bearer your_api_key" https://your-domain.com/api/health

# Test 2: MCP endpoint accessibility  
curl -H "Authorization: Bearer your_api_key" https://your-domain.com/api/status

# Test 3: Invalid key rejection
curl -H "Authorization: Bearer invalid_key" https://your-domain.com/api/status
# Should return 401 Unauthorized
```

### Claude Desktop Tests
1. **Connection Test**: "What's the trading system status?"
2. **Authentication Test**: Restart Claude Desktop, verify auto-reconnection
3. **Error Handling**: Temporarily block connection, verify graceful failure

---

## Support & Troubleshooting

### Common Issues

**Issue: Certificate errors**
```bash
# Check certificate status
curl -I https://your-domain.com
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

**Issue: Authentication failures**
```bash
# Verify API key in server logs
docker-compose logs orchestration | grep -i auth

# Test API key directly
curl -v -H "Authorization: Bearer your_key" https://your-domain.com/api/health
```

**Issue: Claude Desktop not connecting**
1. Check `%APPDATA%\Claude\claude_desktop_config.json` syntax
2. Verify secure-client.js runs independently: `node C:\CatalystTrading\secure-client.js`
3. Check Windows Event Viewer for application errors

---

*Now focused purely on securing your access to the existing Catalyst Trading system! 🔐*