    #!/bin/bash

# Name of Application: Catalyst Trading System Dashboard
# Name of file: setup-dashboard.sh
# Version: 1.0.0
# Last Updated: 2025-09-24
# Purpose: Setup web dashboard for Catalyst Trading System

set -e  # Exit on error

echo "=========================================="
echo "🎩 CATALYST TRADING DASHBOARD SETUP"
echo "=========================================="
echo ""

# Configuration
WEB_DIR="/var/www/catalyst-dashboard"
NGINX_SITE="/etc/nginx/sites-available/catalyst-dashboard"
NGINX_ENABLED="/etc/nginx/sites-enabled/catalyst-dashboard"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Step 1: Installing Nginx (if not already installed)"
echo "----------------------------------------------------"
if ! command -v nginx &> /dev/null; then
    apt-get update
    apt-get install -y nginx
    echo -e "${GREEN}✓${NC} Nginx installed"
else
    echo -e "${GREEN}✓${NC} Nginx already installed"
fi

echo ""
echo "Step 2: Creating web directory structure"
echo "----------------------------------------"
mkdir -p $WEB_DIR
mkdir -p $WEB_DIR/logs
mkdir -p $WEB_DIR/api

echo -e "${GREEN}✓${NC} Created directory structure at $WEB_DIR"

echo ""
echo "Step 3: Installing dashboard files"
echo "----------------------------------"

# Create the main dashboard HTML file
cat > $WEB_DIR/index.html << 'EOF'
[PASTE THE FULL HTML CONTENT FROM THE PREVIOUS ARTIFACT HERE]
EOF

echo -e "${GREEN}✓${NC} Dashboard HTML created"

# Create API proxy configuration for Nginx to handle CORS
cat > $WEB_DIR/api/proxy.conf << 'EOF'
# API Proxy Configuration
location /api/ {
    proxy_pass http://localhost:5000/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
    
    # CORS headers
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range' always;
}

# Service-specific proxies
location /scanner/ {
    proxy_pass http://localhost:5001/;
    include /var/www/catalyst-dashboard/api/proxy.conf;
}

location /pattern/ {
    proxy_pass http://localhost:5002/;
    include /var/www/catalyst-dashboard/api/proxy.conf;
}

location /trading/ {
    proxy_pass http://localhost:5005/;
    include /var/www/catalyst-dashboard/api/proxy.conf;
}

location /news/ {
    proxy_pass http://localhost:5008/;
    include /var/www/catalyst-dashboard/api/proxy.conf;
}

location /reporting/ {
    proxy_pass http://localhost:5009/;
    include /var/www/catalyst-dashboard/api/proxy.conf;
}
EOF

echo -e "${GREEN}✓${NC} API proxy configuration created"

echo ""
echo "Step 4: Configuring Nginx"
echo "-------------------------"

# Create Nginx site configuration
cat > $NGINX_SITE << 'EOF'
server {
    listen 8080;
    listen [::]:8080;
    server_name _;
    
    root /var/www/catalyst-dashboard;
    index index.html;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # Main dashboard
    location / {
        try_files $uri $uri/ =404;
    }
    
    # API proxy to orchestration service
    location /api/ {
        proxy_pass http://localhost:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Content-Type' always;
        
        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
    
    # Direct service proxies (for troubleshooting)
    location /services/scanner/ {
        proxy_pass http://localhost:5001/;
        proxy_set_header Host $host;
    }
    
    location /services/pattern/ {
        proxy_pass http://localhost:5002/;
        proxy_set_header Host $host;
    }
    
    location /services/trading/ {
        proxy_pass http://localhost:5005/;
        proxy_set_header Host $host;
    }
    
    location /services/news/ {
        proxy_pass http://localhost:5008/;
        proxy_set_header Host $host;
    }
    
    location /services/reporting/ {
        proxy_pass http://localhost:5009/;
        proxy_set_header Host $host;
    }
    
    # Logs viewer (optional)
    location /logs {
        alias /root/catalyst-trading-mcp/logs/;
        autoindex on;
        autoindex_exact_size off;
        autoindex_localtime on;
    }
    
    # Error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
EOF

echo -e "${GREEN}✓${NC} Nginx site configuration created"

# Enable the site
ln -sf $NGINX_SITE $NGINX_ENABLED
echo -e "${GREEN}✓${NC} Site enabled"

# Test Nginx configuration
nginx -t
echo -e "${GREEN}✓${NC} Nginx configuration valid"

echo ""
echo "Step 5: Updating dashboard with correct API endpoint"
echo "----------------------------------------------------"

# Update the dashboard to use relative paths for API calls
sed -i "s|const API_BASE = 'http://localhost:5000';|const API_BASE = '/api';|g" $WEB_DIR/index.html
echo -e "${GREEN}✓${NC} Updated API endpoints"

echo ""
echo "Step 6: Restarting Nginx"
echo "------------------------"
systemctl restart nginx
echo -e "${GREEN}✓${NC} Nginx restarted"

echo ""
echo "Step 7: Setting up firewall rules"
echo "---------------------------------"
if command -v ufw &> /dev/null; then
    ufw allow 8080/tcp
    echo -e "${GREEN}✓${NC} Firewall rule added for port 8080"
else
    echo -e "${YELLOW}⚠${NC} UFW not found, please manually configure firewall"
fi

echo ""
echo "Step 8: Creating helper scripts"
echo "-------------------------------"

# Create update script
cat > /root/update-dashboard.sh << 'EOF'
#!/bin/bash
# Quick script to update dashboard
cd /var/www/catalyst-dashboard
echo "Updating dashboard..."
# Add any update commands here
systemctl reload nginx
echo "Dashboard updated!"
EOF
chmod +x /root/update-dashboard.sh
echo -e "${GREEN}✓${NC} Created update script"

# Create monitoring script
cat > /root/monitor-dashboard.sh << 'EOF'
#!/bin/bash
# Monitor dashboard and services
while true; do
    clear
    echo "=== CATALYST DASHBOARD MONITOR ==="
    echo "Time: $(date)"
    echo ""
    
    # Check Nginx
    if systemctl is-active --quiet nginx; then
        echo "✅ Nginx: Running"
    else
        echo "❌ Nginx: Stopped"
    fi
    
    # Check dashboard accessibility
    if curl -s http://localhost:8080 > /dev/null; then
        echo "✅ Dashboard: Accessible"
    else
        echo "❌ Dashboard: Not accessible"
    fi
    
    # Check orchestration service
    if curl -s http://localhost:5000/health > /dev/null; then
        echo "✅ Orchestration: Healthy"
    else
        echo "❌ Orchestration: Unhealthy"
    fi
    
    echo ""
    echo "Press Ctrl+C to exit"
    sleep 5
done
EOF
chmod +x /root/monitor-dashboard.sh
echo -e "${GREEN}✓${NC} Created monitoring script"

echo ""
echo "=========================================="
echo "✅ DASHBOARD SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "📊 Dashboard URL: http://$(curl -s ifconfig.me):8080"
echo ""
echo "🔧 Quick Commands:"
echo "  - View dashboard: Open http://your-server-ip:8080 in browser"
echo "  - Check status: /root/monitor-dashboard.sh"
echo "  - Update dashboard: /root/update-dashboard.sh"
echo "  - View Nginx logs: tail -f /var/log/nginx/access.log"
echo "  - Restart Nginx: systemctl restart nginx"
echo ""
echo "⚠️  Note: Make sure your Catalyst Trading services are running"
echo "    for the dashboard to display data correctly."
echo ""
echo "🔒 Security: Consider adding SSL with Let's Encrypt:"
echo "    certbot --nginx -d your-domain.com"
echo ""
echo "=========================================="
