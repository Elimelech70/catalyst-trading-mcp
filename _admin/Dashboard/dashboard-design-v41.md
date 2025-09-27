# Catalyst Trading Dashboard Design v4.1

**Name of Application**: Catalyst Trading System  
**Name of file**: dashboard-design-v41.md  
**Version**: 4.1.0  
**Last Updated**: 2025-09-27  
**Purpose**: Complete dashboard design specification aligned with MCP architecture v4.1

**REVISION HISTORY**:
- v4.1.0 (2025-09-27) - Complete redesign for v4.1 compliance
  - MCP WebSocket integration for orchestration
  - REST API clients for internal services
  - Removed non-existent Database MCP Service
  - Enhanced monitoring and control features
  - Added MCP Console for direct interaction

**Description**:
Comprehensive dashboard design for the Catalyst Trading System, providing real-time monitoring, control, and analytics through a modular web interface with MCP and REST integration.

---

## 1. Architecture Overview

### 1.1 Service Integration Model

```yaml
Dashboard Client Architecture:
  ├── MCP WebSocket Client
  │   └── Orchestration Service (Port 5000)
  │       ├── Resources (GET operations)
  │       └── Tools (Control operations)
  │
  └── REST API Clients
      ├── Scanner Service (Port 5001)
      ├── Pattern Service (Port 5002)
      ├── Technical Service (Port 5003)
      ├── Trading Service (Port 5005)
      ├── News Service (Port 5008)
      └── Reporting Service (Port 5009)
```

### 1.2 Key Design Principles

- **Dual Protocol Support**: MCP for orchestration, REST for services
- **Real-Time Updates**: WebSocket for live data, polling for service status
- **Modular Architecture**: Independent modules for maintainability
- **Responsive Design**: Mobile-first, adaptive layouts
- **Error Resilience**: Graceful degradation with fallbacks

---

## 2. File Structure

```
/var/www/catalyst-dashboard/
│
├── index.html                 # Main application shell
├── css/
│   ├── main.css              # Global styles
│   └── themes/               # Theme variations
│       ├── dark.css
│       └── light.css
│
├── js/
│   ├── app.js                # Core application logic
│   ├── mcp-client.js         # MCP WebSocket client
│   ├── rest-client.js        # REST API wrapper
│   └── utils.js              # Utility functions
│
├── modules/                  # Dynamic module templates
│   ├── home/
│   ├── dashboard/
│   ├── mcp-console/
│   ├── workflow/
│   ├── positions/
│   ├── signals/
│   ├── risk/
│   └── performance/
│
├── components/               # Reusable UI components
│   ├── service-card.js
│   ├── position-table.js
│   ├── workflow-stage.js
│   └── metric-display.js
│
└── config/
    ├── endpoints.json        # Service endpoint configuration
    └── settings.json         # User preferences
```

---

## 3. Navigation Structure

### 3.1 Primary Navigation

```javascript
const navigationStructure = {
    main: [
        {
            path: 'home',
            title: 'Home',
            icon: '🏠',
            description: 'System overview and quick actions'
        },
        {
            path: 'dashboard',
            title: 'Dashboard',
            icon: '📊',
            description: 'Real-time monitoring grid'
        },
        {
            path: 'mcp-console',
            title: 'MCP Console',
            icon: '🤖',
            description: 'Direct MCP interaction interface'
        },
        {
            path: 'workflow',
            title: 'Workflow',
            icon: '🔄',
            description: 'Trading pipeline visualization'
        }
    ],
    
    trading: [
        {
            path: 'positions',
            title: 'Positions',
            icon: '💰',
            description: 'Active and closed positions'
        },
        {
            path: 'signals',
            title: 'Trading Signals',
            icon: '📡',
            description: 'Generated trading signals'
        },
        {
            path: 'risk',
            title: 'Risk Management',
            icon: '⚠️',
            description: 'Risk metrics and controls'
        },
        {
            path: 'performance',
            title: 'Performance',
            icon: '📈',
            description: 'Analytics and reporting'
        }
    ],
    
    services: [
        {
            path: 'services/orchestration',
            title: 'Orchestration (MCP)',
            icon: '🎯',
            port: 5000,
            protocol: 'MCP'
        },
        {
            path: 'services/scanner',
            title: 'Scanner',
            icon: '🔍',
            port: 5001,
            protocol: 'REST'
        },
        {
            path: 'services/news',
            title: 'News',
            icon: '📰',
            port: 5008,
            protocol: 'REST'
        },
        {
            path: 'services/pattern',
            title: 'Pattern',
            icon: '📊',
            port: 5002,
            protocol: 'REST'
        },
        {
            path: 'services/technical',
            title: 'Technical',
            icon: '📉',
            port: 5003,
            protocol: 'REST'
        },
        {
            path: 'services/trading',
            title: 'Trading',
            icon: '💹',
            port: 5005,
            protocol: 'REST'
        },
        {
            path: 'services/reporting',
            title: 'Reporting',
            icon: '📋',
            port: 5009,
            protocol: 'REST'
        }
    ],
    
    troubleshooting: [
        {
            path: 'troubleshoot/system',
            title: 'System Health'
        },
        {
            path: 'troubleshoot/services',
            title: 'Service Issues'
        },
        {
            path: 'troubleshoot/workflow',
            title: 'Workflow Problems'
        },
        {
            path: 'troubleshoot/logs',
            title: 'Log Viewer'
        }
    ]
};
```

---

## 4. Core Modules

### 4.1 Home Module

**Purpose**: Landing page with system overview and quick actions

**Features**:
- System health summary with MCP connection status
- Quick action buttons (Start/Stop cycle)
- Active positions summary
- Recent signals feed
- Performance metrics

**Data Sources**:
- MCP: `system/health`, `trading-cycle/current`
- REST: Trading service positions endpoint

### 4.2 Dashboard Module

**Purpose**: Real-time monitoring grid

**Layout**:
```
┌─────────────────────────────────────────┐
│         Services Health Grid            │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐   │
│  │MCP │ │Scan│ │News│ │Pat │ │Tech│   │
│  └────┘ └────┘ └────┘ └────┘ └────┘   │
├─────────────────────────────────────────┤
│  Trading Metrics  │   Market Scan       │
│  ┌─────┬─────┐   │  Universe: 100      │
│  │Pos: │P&L: │   │  Catalysts: 15      │
│  │  5  │+2.3%│   │  Top 5: Selected    │
│  └─────┴─────┘   │  Next: 2:30 PM      │
├─────────────────────────────────────────┤
│         Active Positions Table          │
│  Symbol │ Qty │ Entry │ Current │ P&L  │
│  AAPL   │ 100 │ 150.0 │ 152.5  │ +250 │
└─────────────────────────────────────────┘
```

**Update Frequency**:
- Services: 30 seconds
- Positions: 10 seconds
- Metrics: 5 seconds

### 4.3 MCP Console Module

**Purpose**: Direct interaction with MCP orchestration service

**Features**:
- Connection status indicator
- Resource browser with clickable URIs
- Tool executor with parameter forms
- Real-time response display
- Event subscription manager

**Interface**:
```javascript
// Resource Testing
Resources:
├── system/health          [Test]
├── trading-cycle/current  [Test]
├── market-scan/candidates [Test]
└── portfolio/positions    [Test]

// Tool Execution
Tools:
├── start_trading_cycle    [Execute]
│   ├── mode: [dropdown]
│   ├── max_positions: [number]
│   └── risk_level: [select]
├── stop_trading          [Execute]
└── update_risk_params    [Execute]

// Console Output
> GET system/health
< {
    "status": "healthy",
    "services": {...},
    "timestamp": "2025-09-27T10:30:00Z"
  }
```

### 4.4 Workflow Module

**Purpose**: Visualize the 100→5 securities trading pipeline

**Pipeline Stages**:
1. **Market Universe** (100 securities scanned)
2. **Catalyst Detection** (News filtering applied)
3. **Top 5 Selection** (Scoring and ranking)
4. **Pattern Analysis** (Technical patterns on top 5)
5. **Signal Generation** (Entry/exit points)
6. **Trade Execution** (Max 5 positions)

**Visual Design**:
- Interactive flow diagram
- Active stage highlighting
- Real-time status updates
- Click for stage details
- Pipeline statistics

---

## 5. API Integration

### 5.1 MCP Client Configuration

```javascript
class MCPClient {
    constructor() {
        this.endpoint = 'ws://localhost:5000/mcp';
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
    }
    
    // Hierarchical URI Resources
    resources = {
        'system/health': 'System health status',
        'system/config': 'System configuration',
        'trading-cycle/current': 'Current cycle status',
        'trading-cycle/history': 'Recent cycles',
        'market-scan/status': 'Scan status',
        'market-scan/candidates/active': 'Active candidates',
        'portfolio/positions/open': 'Open positions',
        'portfolio/risk/metrics': 'Risk metrics',
        'analytics/daily-summary': 'Daily summary',
        'analytics/performance': 'Performance metrics'
    };
    
    // Available Tools
    tools = {
        'start_trading_cycle': {
            params: ['mode', 'max_positions', 'risk_level']
        },
        'stop_trading': {
            params: ['reason', 'close_positions']
        },
        'update_risk_parameters': {
            params: ['max_position_size', 'stop_loss_pct']
        },
        'close_all_positions': {
            params: ['reason', 'force']
        }
    };
}
```

### 5.2 REST Client Configuration

```javascript
const restEndpoints = {
    scanner: {
        base: 'http://localhost:5001/api/v1',
        endpoints: {
            health: '/health',
            scan: '/scan',
            candidates: '/candidates',
            universe: '/universe'
        }
    },
    pattern: {
        base: 'http://localhost:5002/api/v1',
        endpoints: {
            health: '/health',
            detect: '/detect',
            patterns: '/patterns/{symbol}'
        }
    },
    technical: {
        base: 'http://localhost:5003/api/v1',
        endpoints: {
            health: '/health',
            indicators: '/indicators/{symbol}',
            signals: '/signals'
        }
    },
    trading: {
        base: 'http://localhost:5005/api/v1',
        endpoints: {
            health: '/health',
            positions: '/positions',
            orders: '/orders',
            execute: '/execute'
        }
    },
    news: {
        base: 'http://localhost:5008/api/v1',
        endpoints: {
            health: '/health',
            latest: '/news/latest',
            sentiment: '/sentiment/{symbol}'
        }
    },
    reporting: {
        base: 'http://localhost:5009/api/v1',
        endpoints: {
            health: '/health',
            daily: '/reports/daily',
            performance: '/reports/performance'
        }
    }
};
```

---

## 6. Real-Time Updates

### 6.1 WebSocket Events

```javascript
// MCP WebSocket Events
const mcpEvents = {
    'trading_cycle_started': (data) => {
        updateWorkflowStatus(data);
        showNotification('Trading cycle started');
    },
    
    'position_opened': (data) => {
        addPosition(data);
        updateMetrics();
    },
    
    'signal_generated': (data) => {
        addSignal(data);
        highlightCandidate(data.symbol);
    },
    
    'cycle_completed': (data) => {
        updatePerformance(data.summary);
        resetWorkflow();
    }
};
```

### 6.2 Polling Strategy

```javascript
const pollingIntervals = {
    // Critical updates
    positions: 5000,      // 5 seconds
    signals: 5000,        // 5 seconds
    
    // Standard updates
    services: 30000,      // 30 seconds
    metrics: 10000,       // 10 seconds
    
    // Low priority
    performance: 60000,   // 1 minute
    reports: 300000      // 5 minutes
};
```

---

## 7. UI Components

### 7.1 Service Health Card

```javascript
class ServiceHealthCard {
    render(service) {
        return `
            <div class="service-card ${service.status}">
                <div class="service-header">
                    <span class="service-name">${service.name}</span>
                    <span class="service-protocol">${service.protocol}</span>
                </div>
                <div class="service-status">
                    <span class="status-icon">${this.getStatusIcon(service.status)}</span>
                    <span class="status-text">${service.status}</span>
                </div>
                <div class="service-metrics">
                    <div>Port: ${service.port}</div>
                    <div>Uptime: ${service.uptime}</div>
                    <div>Last Check: ${service.lastCheck}</div>
                </div>
            </div>
        `;
    }
}
```

### 7.2 Position Table

```javascript
class PositionTable {
    columns = [
        { key: 'symbol', label: 'Symbol', width: '15%' },
        { key: 'quantity', label: 'Qty', width: '10%' },
        { key: 'entry_price', label: 'Entry', width: '15%', format: 'currency' },
        { key: 'current_price', label: 'Current', width: '15%', format: 'currency' },
        { key: 'pnl', label: 'P&L', width: '15%', format: 'pnl' },
        { key: 'stop_loss', label: 'Stop', width: '15%', format: 'currency' },
        { key: 'actions', label: 'Actions', width: '15%' }
    ];
    
    renderRow(position) {
        const pnl = (position.current_price - position.entry_price) * position.quantity;
        const pnlClass = pnl >= 0 ? 'profit' : 'loss';
        
        return `
            <tr>
                <td>${position.symbol}</td>
                <td>${position.quantity}</td>
                <td>$${position.entry_price.toFixed(2)}</td>
                <td>$${position.current_price.toFixed(2)}</td>
                <td class="${pnlClass}">$${pnl.toFixed(2)}</td>
                <td>$${position.stop_loss?.toFixed(2) || '-'}</td>
                <td>
                    <button onclick="closePosition('${position.symbol}')">Close</button>
                </td>
            </tr>
        `;
    }
}
```

---

## 8. Error Handling

### 8.1 Connection Recovery

```javascript
class ConnectionManager {
    handleMCPDisconnect() {
        // Show connection lost indicator
        this.showConnectionStatus('disconnected');
        
        // Fall back to REST endpoints
        this.enableFallbackMode();
        
        // Attempt reconnection with exponential backoff
        this.scheduleReconnect();
    }
    
    handleServiceError(service, error) {
        // Log error
        console.error(`Service ${service} error:`, error);
        
        // Update UI
        this.markServiceUnhealthy(service);
        
        // Show user notification
        this.showNotification({
            type: 'warning',
            message: `${service} service is experiencing issues`,
            duration: 5000
        });
    }
}
```

### 8.2 Fallback Strategies

```javascript
const fallbackStrategies = {
    // If MCP unavailable, use REST aggregation
    systemHealth: async () => {
        const services = await Promise.allSettled([
            fetch('http://localhost:5001/api/v1/health'),
            fetch('http://localhost:5002/api/v1/health'),
            // ... other services
        ]);
        return aggregateHealth(services);
    },
    
    // If real-time updates fail, increase polling
    positions: () => {
        clearInterval(wsSubscription);
        setInterval(() => fetchPositions(), 3000);
    }
};
```

---

## 9. Performance Optimization

### 9.1 Caching Strategy

```javascript
class DataCache {
    constructor() {
        this.cache = new Map();
        this.ttl = {
            positions: 5000,      // 5 seconds
            candidates: 30000,    // 30 seconds
            performance: 60000,   // 1 minute
            config: 300000       // 5 minutes
        };
    }
    
    get(key) {
        const entry = this.cache.get(key);
        if (!entry) return null;
        
        if (Date.now() - entry.timestamp > this.ttl[key]) {
            this.cache.delete(key);
            return null;
        }
        
        return entry.data;
    }
}
```

### 9.2 Lazy Loading

```javascript
const lazyLoadModules = {
    'mcp-console': () => import('./modules/mcp-console.js'),
    'performance': () => import('./modules/performance.js'),
    'risk': () => import('./modules/risk.js')
};

async function loadModule(name) {
    if (lazyLoadModules[name]) {
        const module = await lazyLoadModules[name]();
        return module.default;
    }
}
```

---

## 10. Security Considerations

### 10.1 Authentication

```javascript
const authConfig = {
    // API key management
    apiKeys: {
        storage: 'sessionStorage', // Never localStorage
        encryption: true,
        rotation: 86400000 // 24 hours
    },
    
    // Session management
    session: {
        timeout: 1800000, // 30 minutes
        refresh: true,
        secure: true
    }
};
```

### 10.2 Data Sanitization

```javascript
function sanitizeInput(input) {
    // Prevent XSS
    const div = document.createElement('div');
    div.textContent = input;
    return div.innerHTML;
}

function validateTradeParams(params) {
    const schema = {
        symbol: /^[A-Z]{1,5}$/,
        quantity: (v) => v > 0 && v <= 10000,
        price: (v) => v > 0 && v < 100000
    };
    
    return Object.entries(schema).every(([key, validator]) => {
        if (typeof validator === 'function') {
            return validator(params[key]);
        }
        return validator.test(params[key]);
    });
}
```

---

## 11. Mobile Responsiveness

### 11.1 Breakpoints

```css
/* Mobile First Design */
@media (min-width: 640px) {  /* Tablet */
    .sidebar { width: 280px; }
    .grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) { /* Desktop */
    .grid { grid-template-columns: repeat(3, 1fr); }
}

@media (min-width: 1440px) { /* Wide */
    .grid { grid-template-columns: repeat(4, 1fr); }
}
```

### 11.2 Touch Optimization

```javascript
const touchConfig = {
    swipeThreshold: 50,
    tapDelay: 300,
    doubleTapZoom: false
};

// Swipe navigation
let touchStart = null;
element.addEventListener('touchstart', (e) => {
    touchStart = e.changedTouches[0].clientX;
});

element.addEventListener('touchend', (e) => {
    if (!touchStart) return;
    
    const touchEnd = e.changedTouches[0].clientX;
    const diff = touchStart - touchEnd;
    
    if (Math.abs(diff) > touchConfig.swipeThreshold) {
        if (diff > 0) navigateNext();
        else navigatePrev();
    }
});
```

---

## 12. Deployment Configuration

### 12.1 Environment Variables

```javascript
// config/environment.js
const config = {
    development: {
        mcpEndpoint: 'ws://localhost:5000/mcp',
        apiBaseUrl: 'http://localhost',
        debug: true
    },
    
    production: {
        mcpEndpoint: 'wss://trading.example.com/mcp',
        apiBaseUrl: 'https://api.trading.example.com',
        debug: false
    }
};

export default config[process.env.NODE_ENV || 'development'];
```

### 12.2 Nginx Configuration

```nginx
server {
    listen 80;
    server_name dashboard.catalyst-trading.com;
    
    root /var/www/catalyst-dashboard;
    index index.html;
    
    # WebSocket proxy for MCP
    location /mcp {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
    
    # REST API proxies
    location /api/scanner {
        proxy_pass http://localhost:5001/api/v1;
    }
    
    location /api/pattern {
        proxy_pass http://localhost:5002/api/v1;
    }
    
    # ... other services
}
```

---

## 13. Testing Strategy

### 13.1 Unit Tests

```javascript
describe('MCPClient', () => {
    it('should connect to WebSocket', async () => {
        const client = new MCPClient('ws://localhost:5000/mcp');
        await client.connect();
        expect(client.isConnected()).toBe(true);
    });
    
    it('should retrieve resources', async () => {
        const health = await client.getResource('system/health');
        expect(health).toHaveProperty('status');
    });
    
    it('should execute tools', async () => {
        const result = await client.callTool('start_trading_cycle', {
            mode: 'test',
            max_positions: 1
        });
        expect(result).toHaveProperty('cycle_id');
    });
});
```

### 13.2 Integration Tests

```javascript
describe('Dashboard Integration', () => {
    it('should display service health', async () => {
        await page.goto('http://localhost/dashboard');
        await page.waitForSelector('.services-grid');
        
        const services = await page.$$('.service-item');
        expect(services.length).toBeGreaterThan(0);
    });
    
    it('should update positions in real-time', async () => {
        await page.goto('http://localhost/positions');
        
        // Trigger position update
        await mockPositionUpdate();
        
        // Wait for update
        await page.waitForSelector('.position-row');
        const positions = await page.$$('.position-row');
        expect(positions.length).toBeGreaterThan(0);
    });
});
```

---

## 14. Future Enhancements

### Phase 2 Features (Q4 2025)
- [ ] Advanced charting with TradingView integration
- [ ] Multi-account support
- [ ] Backtesting interface
- [ ] Custom alert configuration
- [ ] Strategy builder UI

### Phase 3 Features (Q1 2026)
- [ ] AI-powered trade recommendations
- [ ] Social trading features
- [ ] Mobile native apps
- [ ] Voice command interface
- [ ] Advanced risk analytics

---

## 15. Conclusion

This dashboard design provides a comprehensive, production-ready interface for the Catalyst Trading System v4.1. Key features include:

✅ **Full v4.1 Compliance** - Correctly implements MCP and REST protocols  
✅ **Modular Architecture** - Maintainable and extensible design  
✅ **Real-Time Updates** - WebSocket and polling for live data  
✅ **Error Resilience** - Graceful degradation and recovery  
✅ **Mobile Ready** - Responsive design for all devices  
✅ **Performance Optimized** - Caching and lazy loading  
✅ **Security Focused** - Proper authentication and sanitization  

The dashboard serves as the primary control interface for traders, providing complete visibility and control over the automated trading system while maintaining the architectural integrity of the v4.1 specifications.

---

*DevGenius Hat Status: Dashboard design documented* 🎩