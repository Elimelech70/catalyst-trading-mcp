// Catalyst Trading System - Modular Application Framework v4.1
// Name of Application: Catalyst Trading System
// Name of file: app.js
// Version: 4.1.0
// Last Updated: 2025-09-27
// Purpose: Main application logic with MCP and REST integration

// REVISION HISTORY:
// v4.1.0 (2025-09-27) - Complete architecture alignment
// - Added MCP client for orchestration service
// - REST clients for internal services
// - Removed Database MCP Service references
// - Corrected workflow visualization
// - Enhanced error handling

class CatalystApp {
    constructor() {
        this.config = {
            // MCP endpoint for orchestration
            mcpEndpoint: 'ws://localhost:5000/mcp',
            
            // REST endpoints for services
            restEndpoints: {
                scanner: 'http://localhost:5001/api/v1',
                pattern: 'http://localhost:5002/api/v1',
                technical: 'http://localhost:5003/api/v1',
                trading: 'http://localhost:5005/api/v1',
                news: 'http://localhost:5008/api/v1',
                reporting: 'http://localhost:5009/api/v1'
            },
            
            refreshIntervals: {
                dashboard: 5000,
                positions: 10000,
                services: 30000,
                mcpHeartbeat: 15000
            },
            
            maxRetries: 3,
            retryDelay: 1000
        };
        
        this.state = {
            currentModule: null,
            mcpConnected: false,
            services: {},
            positions: [],
            tradingCycle: null,
            signals: [],
            lastUpdate: null
        };
        
        this.moduleCache = new Map();
        this.refreshTimers = new Map();
        this.moduleInitializers = new Map();
        
        // Initialize clients
        this.mcpClient = null;
        this.restClients = {};
        
        this.init();
    }
    
    async init() {
        try {
            // Initialize MCP client for orchestration
            await this.initializeMCPClient();
            
            // Initialize REST clients for services
            this.initializeRESTClients();
            
            // Register module initializers
            this.registerModuleInitializers();
            
            // Load initial module from URL hash or default to home
            const initialModule = window.location.hash.slice(1) || 'home';
            await this.loadModule(initialModule);
            
            // Start system monitoring
            this.startSystemMonitoring();
            
            // Handle browser back/forward
            window.addEventListener('popstate', () => {
                const module = window.location.hash.slice(1) || 'home';
                this.loadModule(module);
            });
        } catch (error) {
            console.error('Failed to initialize application:', error);
            this.displayInitError(error);
        }
    }
    
    async initializeMCPClient() {
        try {
            // Initialize MCP WebSocket connection
            this.mcpClient = new WebSocket(this.config.mcpEndpoint);
            
            this.mcpClient.onopen = () => {
                console.log('MCP connection established');
                this.state.mcpConnected = true;
                this.updateMCPStatus('Connected');
            };
            
            this.mcpClient.onmessage = (event) => {
                this.handleMCPMessage(JSON.parse(event.data));
            };
            
            this.mcpClient.onerror = (error) => {
                console.error('MCP connection error:', error);
                this.state.mcpConnected = false;
                this.updateMCPStatus('Error');
            };
            
            this.mcpClient.onclose = () => {
                console.log('MCP connection closed');
                this.state.mcpConnected = false;
                this.updateMCPStatus('Disconnected');
                // Attempt reconnection
                setTimeout(() => this.initializeMCPClient(), 5000);
            };
            
            // Wait for connection
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('MCP connection timeout'));
                }, 5000);
                
                this.mcpClient.addEventListener('open', () => {
                    clearTimeout(timeout);
                    resolve();
                }, { once: true });
            });
        } catch (error) {
            console.error('Failed to initialize MCP client:', error);
            // Continue without MCP - fallback to REST only
            this.state.mcpConnected = false;
            this.updateMCPStatus('Unavailable');
        }
    }
    
    initializeRESTClients() {
        // Create REST clients for each service
        Object.entries(this.config.restEndpoints).forEach(([service, endpoint]) => {
            this.restClients[service] = {
                endpoint,
                get: async (path) => this.restCall('GET', endpoint + path),
                post: async (path, data) => this.restCall('POST', endpoint + path, data),
                put: async (path, data) => this.restCall('PUT', endpoint + path, data),
                delete: async (path) => this.restCall('DELETE', endpoint + path)
            };
        });
    }
    
    // MCP Communication Methods
    async mcpGetResource(uri) {
        if (!this.state.mcpConnected) {
            throw new Error('MCP not connected');
        }
        
        return new Promise((resolve, reject) => {
            const requestId = Date.now().toString();
            
            const request = {
                type: 'resource',
                method: 'GET',
                uri: uri,
                id: requestId
            };
            
            // Set up response handler
            const handler = (event) => {
                const data = JSON.parse(event.data);
                if (data.id === requestId) {
                    this.mcpClient.removeEventListener('message', handler);
                    if (data.error) {
                        reject(new Error(data.error.message));
                    } else {
                        resolve(data.result);
                    }
                }
            };
            
            this.mcpClient.addEventListener('message', handler);
            this.mcpClient.send(JSON.stringify(request));
            
            // Timeout after 10 seconds
            setTimeout(() => {
                this.mcpClient.removeEventListener('message', handler);
                reject(new Error('MCP request timeout'));
            }, 10000);
        });
    }
    
    async mcpCallTool(name, params = {}) {
        if (!this.state.mcpConnected) {
            throw new Error('MCP not connected');
        }
        
        return new Promise((resolve, reject) => {
            const requestId = Date.now().toString();
            
            const request = {
                type: 'tool',
                name: name,
                params: params,
                id: requestId
            };
            
            const handler = (event) => {
                const data = JSON.parse(event.data);
                if (data.id === requestId) {
                    this.mcpClient.removeEventListener('message', handler);
                    if (data.error) {
                        reject(new Error(data.error.message));
                    } else {
                        resolve(data.result);
                    }
                }
            };
            
            this.mcpClient.addEventListener('message', handler);
            this.mcpClient.send(JSON.stringify(request));
            
            setTimeout(() => {
                this.mcpClient.removeEventListener('message', handler);
                reject(new Error('MCP tool call timeout'));
            }, 10000);
        });
    }
    
    handleMCPMessage(data) {
        // Handle MCP events/notifications
        switch (data.type) {
            case 'event':
                this.handleMCPEvent(data.event);
                break;
            case 'notification':
                this.handleMCPNotification(data.notification);
                break;
        }
    }
    
    handleMCPEvent(event) {
        switch (event.name) {
            case 'trading_cycle_started':
                this.state.tradingCycle = event.data;
                this.updateWorkflowDisplay();
                break;
            case 'position_opened':
                this.state.positions.push(event.data);
                this.updatePositionsDisplay();
                break;
            case 'signal_generated':
                this.state.signals.unshift(event.data);
                this.updateSignalsDisplay();
                break;
        }
    }
    
    handleMCPNotification(notification) {
        console.log('MCP Notification:', notification);
    }
    
    // REST Communication Methods
    async restCall(method, url, data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        for (let i = 0; i < this.config.maxRetries; i++) {
            try {
                const response = await fetch(url, options);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return await response.json();
            } catch (error) {
                if (i === this.config.maxRetries - 1) {
                    throw error;
                }
                await this.delay(this.config.retryDelay * Math.pow(2, i));
            }
        }
    }
    
    // Module Management
    registerModuleInitializers() {
        this.moduleInitializers.set('home', () => this.initHomeModule());
        this.moduleInitializers.set('dashboard', () => this.initDashboardModule());
        this.moduleInitializers.set('mcp-console', () => this.initMCPConsoleModule());
        this.moduleInitializers.set('workflow', () => this.initWorkflowModule());
        this.moduleInitializers.set('positions', () => this.initPositionsModule());
        this.moduleInitializers.set('signals', () => this.initSignalsModule());
        this.moduleInitializers.set('risk', () => this.initRiskModule());
        this.moduleInitializers.set('performance', () => this.initPerformanceModule());
        this.moduleInitializers.set('services/scanner', () => this.initScannerModule());
        this.moduleInitializers.set('services/news', () => this.initNewsModule());
        this.moduleInitializers.set('services/trading', () => this.initTradingModule());
        this.moduleInitializers.set('troubleshoot/system', () => this.initTroubleshootModule());
    }
    
    async loadModule(modulePath) {
        // Update state
        this.state.currentModule = modulePath;
        window.location.hash = modulePath;
        
        // Clear existing refresh timers
        this.stopAllRefreshTimers();
        
        // Update UI
        this.updateNavigation(modulePath);
        this.updatePageTitle(modulePath);
        
        // Show loading state
        this.showLoading();
        
        try {
            // Get module content
            const content = await this.getModuleContent(modulePath);
            
            // Display module
            this.displayModule(content);
            
            // Initialize module
            const initializer = this.moduleInitializers.get(modulePath);
            if (initializer) {
                await initializer.call(this);
            }
            
        } catch (error) {
            console.error(`Failed to load module ${modulePath}:`, error);
            this.displayError(modulePath, error);
        }
    }
    
    async getModuleContent(modulePath) {
        // Check cache first
        if (this.moduleCache.has(modulePath)) {
            return this.moduleCache.get(modulePath);
        }
        
        // Generate module content
        const content = this.generateModuleContent(modulePath);
        this.moduleCache.set(modulePath, content);
        return content;
    }
    
    generateModuleContent(modulePath) {
        const generators = {
            'home': () => this.getHomeTemplate(),
            'dashboard': () => this.getDashboardTemplate(),
            'mcp-console': () => this.getMCPConsoleTemplate(),
            'workflow': () => this.getWorkflowTemplate(),
            'positions': () => this.getPositionsTemplate(),
            'signals': () => this.getSignalsTemplate(),
            'risk': () => this.getRiskTemplate(),
            'performance': () => this.getPerformanceTemplate()
        };
        
        const generator = generators[modulePath];
        if (generator) {
            return generator();
        }
        
        return this.getDefaultTemplate(modulePath);
    }
    
    // Module Templates
    getHomeTemplate() {
        return `
            <div class="module-home">
                <div class="welcome-banner">
                    <h1>Welcome to Catalyst Trading System v4.1</h1>
                    <p>AI-driven trading powered by MCP architecture</p>
                </div>
                
                <div class="grid-container">
                    <div class="card">
                        <h2>System Status</h2>
                        <div id="system-overview">
                            <div class="loading-small">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Quick Actions</h2>
                        <div class="button-group">
                            <button onclick="app.startTradingCycle()" class="btn-primary">Start Trading Cycle</button>
                            <button onclick="app.stopTradingCycle()" class="btn-secondary">Stop Trading Cycle</button>
                            <button onclick="app.loadModule('dashboard')" class="btn-info">View Dashboard</button>
                            <button onclick="app.loadModule('mcp-console')" class="btn-info">MCP Console</button>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Active Positions</h2>
                        <div id="home-positions">
                            <div class="loading-small">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Market Activity</h2>
                        <div id="market-activity">
                            <div class="loading-small">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Recent Signals</h2>
                        <div id="recent-signals">
                            <div class="loading-small">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Performance Summary</h2>
                        <div id="performance-summary">
                            <div class="loading-small">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                .module-home { padding: 20px; }
                .welcome-banner {
                    background: linear-gradient(135deg, rgba(79, 195, 247, 0.1), rgba(41, 182, 246, 0.05));
                    border: 1px solid rgba(79, 195, 247, 0.3);
                    padding: 30px;
                    border-radius: 12px;
                    margin-bottom: 30px;
                    text-align: center;
                }
                .welcome-banner h1 { color: var(--primary-color); margin-bottom: 10px; }
                .welcome-banner p { color: var(--text-secondary); }
                .grid-container {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                }
                .card {
                    background: var(--card-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 12px;
                    padding: 20px;
                }
                .card h2 {
                    color: var(--primary-color);
                    margin-bottom: 15px;
                    font-size: 18px;
                }
                .button-group {
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                }
                .btn-primary, .btn-secondary, .btn-info {
                    padding: 10px 20px;
                    border: none;
                    border-radius: 6px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s;
                }
                .btn-primary {
                    background: linear-gradient(135deg, var(--primary-color), #29b6f6);
                    color: white;
                }
                .btn-secondary {
                    background: linear-gradient(135deg, #f44336, #d32f2f);
                    color: white;
                }
                .btn-info {
                    background: var(--card-bg);
                    color: var(--primary-color);
                    border: 1px solid var(--primary-color);
                }
                .loading-small {
                    text-align: center;
                    color: var(--text-secondary);
                    padding: 20px;
                }
            </style>
        `;
    }
    
    getDashboardTemplate() {
        return `
            <div class="module-dashboard">
                <div class="dashboard-grid">
                    <!-- Services Health Grid -->
                    <div class="card services-card">
                        <h2>Services Health</h2>
                        <div id="services-grid" class="services-grid">
                            <div class="loading-small">Loading services...</div>
                        </div>
                    </div>
                    
                    <!-- Trading Metrics -->
                    <div class="card metrics-card">
                        <h2>Trading Metrics</h2>
                        <div id="trading-metrics" class="metrics-grid">
                            <div class="metric">
                                <div class="metric-value" id="positions-count">-</div>
                                <div class="metric-label">Positions</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value" id="daily-pnl">-</div>
                                <div class="metric-label">Daily P&L</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value" id="win-rate">-</div>
                                <div class="metric-label">Win Rate</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value" id="cycle-status">-</div>
                                <div class="metric-label">Cycle</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Live Positions -->
                    <div class="card positions-card">
                        <h2>Active Positions</h2>
                        <div id="positions-table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Qty</th>
                                        <th>Entry</th>
                                        <th>Current</th>
                                        <th>P&L</th>
                                        <th>Stop</th>
                                    </tr>
                                </thead>
                                <tbody id="positions-body">
                                    <tr><td colspan="6" style="text-align: center;">No active positions</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <!-- Market Scan Status -->
                    <div class="card scan-card">
                        <h2>Market Scan Status</h2>
                        <div id="scan-status">
                            <div class="scan-metric">
                                <span class="label">Universe:</span>
                                <span class="value" id="universe-count">100</span>
                            </div>
                            <div class="scan-metric">
                                <span class="label">Catalysts Found:</span>
                                <span class="value" id="catalyst-count">-</span>
                            </div>
                            <div class="scan-metric">
                                <span class="label">Top Candidates:</span>
                                <span class="value" id="candidate-count">-</span>
                            </div>
                            <div class="scan-metric">
                                <span class="label">Next Scan:</span>
                                <span class="value" id="next-scan">-</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Recent Signals -->
                    <div class="card signals-card">
                        <h2>Recent Trading Signals</h2>
                        <div id="recent-signals-dash">
                            <div class="loading-small">Loading signals...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                .module-dashboard { padding: 20px; }
                .dashboard-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                }
                .services-card, .positions-card { grid-column: span 2; }
                .services-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                    gap: 10px;
                    margin-top: 15px;
                }
                .service-item {
                    background: rgba(20, 20, 35, 0.5);
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                    border: 1px solid transparent;
                    transition: all 0.3s;
                }
                .service-item:hover {
                    border-color: var(--primary-color);
                }
                .service-item.healthy { border-color: var(--success-color); }
                .service-item.unhealthy { border-color: var(--danger-color); }
                .service-item.mcp {
                    background: linear-gradient(135deg, rgba(79, 195, 247, 0.1), rgba(41, 182, 246, 0.05));
                    border-color: var(--primary-color);
                }
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                }
                .metric {
                    text-align: center;
                    padding: 15px;
                    background: rgba(20, 20, 35, 0.5);
                    border-radius: 8px;
                }
                .metric-value {
                    font-size: 24px;
                    font-weight: bold;
                    color: var(--primary-color);
                }
                .metric-label {
                    font-size: 12px;
                    color: var(--text-secondary);
                    text-transform: uppercase;
                    margin-top: 5px;
                }
                .scan-metric {
                    display: flex;
                    justify-content: space-between;
                    padding: 10px;
                    border-bottom: 1px solid var(--border-color);
                }
                .scan-metric .label {
                    color: var(--text-secondary);
                }
                .scan-metric .value {
                    color: var(--primary-color);
                    font-weight: bold;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th {
                    text-align: left;
                    padding: 10px;
                    border-bottom: 1px solid var(--border-color);
                    color: var(--primary-color);
                }
                td {
                    padding: 10px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }
                .profit { color: var(--success-color); }
                .loss { color: var(--danger-color); }
            </style>
        `;
    }
    
    getMCPConsoleTemplate() {
        return `
            <div class="module-mcp-console">
                <h1>MCP Console - Orchestration Service Interface</h1>
                
                <div class="console-grid">
                    <div class="card">
                        <h2>Connection Status</h2>
                        <div class="connection-info">
                            <div class="status-row">
                                <span>MCP WebSocket:</span>
                                <span class="${this.state.mcpConnected ? 'connected' : 'disconnected'}">
                                    ${this.state.mcpConnected ? '✓ Connected' : '✗ Disconnected'}
                                </span>
                            </div>
                            <div class="status-row">
                                <span>Endpoint:</span>
                                <span>${this.config.mcpEndpoint}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Available Resources</h2>
                        <div class="resource-list">
                            <div class="resource-item" onclick="app.testMCPResource('system/health')">
                                <code>system/health</code> - System health status
                            </div>
                            <div class="resource-item" onclick="app.testMCPResource('trading-cycle/current')">
                                <code>trading-cycle/current</code> - Current trading cycle
                            </div>
                            <div class="resource-item" onclick="app.testMCPResource('market-scan/candidates/active')">
                                <code>market-scan/candidates/active</code> - Active candidates
                            </div>
                            <div class="resource-item" onclick="app.testMCPResource('portfolio/positions/open')">
                                <code>portfolio/positions/open</code> - Open positions
                            </div>
                            <div class="resource-item" onclick="app.testMCPResource('analytics/daily-summary')">
                                <code>analytics/daily-summary</code> - Daily summary
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h2>Available Tools</h2>
                        <div class="tool-list">
                            <div class="tool-item" onclick="app.showToolDialog('start_trading_cycle')">
                                <code>start_trading_cycle</code> - Start new trading cycle
                            </div>
                            <div class="tool-item" onclick="app.showToolDialog('stop_trading')">
                                <code>stop_trading</code> - Stop all trading
                            </div>
                            <div class="tool-item" onclick="app.showToolDialog('update_risk_parameters')">
                                <code>update_risk_parameters</code> - Update risk settings
                            </div>
                            <div class="tool-item" onclick="app.showToolDialog('close_all_positions')">
                                <code>close_all_positions</code> - Emergency close
                            </div>
                        </div>
                    </div>
                    
                    <div class="card console-output">
                        <h2>Console Output</h2>
                        <div id="mcp-console-output">
                            <div class="console-entry">Ready for MCP commands...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                .module-mcp-console { padding: 20px; }
                .console-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                }
                .console-output { grid-column: span 2; }
                .connection-info {
                    padding: 10px;
                }
                .status-row {
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid var(--border-color);
                }
                .connected { color: var(--success-color); }
                .disconnected { color: var(--danger-color); }
                .resource-item, .tool-item {
                    padding: 10px;
                    margin: 5px 0;
                    background: rgba(20, 20, 35, 0.5);
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.3s;
                }
                .resource-item:hover, .tool-item:hover {
                    background: rgba(79, 195, 247, 0.1);
                    border: 1px solid var(--primary-color);
                }
                #mcp-console-output {
                    background: #000;
                    color: #0f0;
                    font-family: monospace;
                    padding: 15px;
                    border-radius: 6px;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .console-entry {
                    margin: 5px 0;
                    font-size: 14px;
                }
            </style>
        `;
    }
    
    getWorkflowTemplate() {
        return `
            <div class="module-workflow">
                <h1>Trading Workflow - 100 → 5 Securities Pipeline</h1>
                
                <div class="workflow-diagram">
                    <!-- Stage 1: Market Universe -->
                    <div class="workflow-stage" id="stage-universe" data-service="scanner">
                        <div class="stage-icon">🌍</div>
                        <div class="stage-title">Market Universe</div>
                        <div class="stage-detail">Scan 100 securities</div>
                        <div class="stage-status" id="universe-status">Idle</div>
                    </div>
                    
                    <div class="workflow-arrow">→</div>
                    
                    <!-- Stage 2: News Catalyst -->
                    <div class="workflow-stage" id="stage-news" data-service="news">
                        <div class="stage-icon">📰</div>
                        <div class="stage-title">Catalyst Detection</div>
                        <div class="stage-detail">Filter by news</div>
                        <div class="stage-status" id="news-status">Idle</div>
                    </div>
                    
                    <div class="workflow-arrow">→</div>
                    
                    <!-- Stage 3: Top Candidates -->
                    <div class="workflow-stage" id="stage-candidates" data-service="scanner">
                        <div class="stage-icon">🎯</div>
                        <div class="stage-title">Select Top 5</div>
                        <div class="stage-detail">Score & rank</div>
                        <div class="stage-status" id="candidates-status">Idle</div>
                    </div>
                    
                    <div class="workflow-arrow">→</div>
                    
                    <!-- Stage 4: Pattern Analysis -->
                    <div class="workflow-stage" id="stage-pattern" data-service="pattern">
                        <div class="stage-icon">📊</div>
                        <div class="stage-title">Pattern Detection</div>
                        <div class="stage-detail">Technical patterns</div>
                        <div class="stage-status" id="pattern-status">Idle</div>
                    </div>
                    
                    <div class="workflow-arrow">→</div>
                    
                    <!-- Stage 5: Technical Signals -->
                    <div class="workflow-stage" id="stage-technical" data-service="technical">
                        <div class="stage-icon">📈</div>
                        <div class="stage-title">Generate Signals</div>
                        <div class="stage-detail">Entry/exit points</div>
                        <div class="stage-status" id="technical-status">Idle</div>
                    </div>
                    
                    <div class="workflow-arrow">→</div>
                    
                    <!-- Stage 6: Trade Execution -->
                    <div class="workflow-stage" id="stage-trade" data-service="trading">
                        <div class="stage-icon">💰</div>
                        <div class="stage-title">Execute Trades</div>
                        <div class="stage-detail">Max 5 positions</div>
                        <div class="stage-status" id="trade-status">Idle</div>
                    </div>
                </div>
                
                <div class="workflow-details card">
                    <h2>Current Cycle Details</h2>
                    <div id="cycle-details">
                        <p>No active trading cycle</p>
                    </div>
                </div>
                
                <div class="workflow-stats card">
                    <h2>Pipeline Statistics</h2>
                    <div class="stats-grid">
                        <div class="stat">
                            <div class="stat-value" id="scanned-count">0</div>
                            <div class="stat-label">Securities Scanned</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" id="catalyst-count">0</div>
                            <div class="stat-label">With Catalysts</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" id="selected-count">0</div>
                            <div class="stat-label">Top Candidates</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" id="signals-count">0</div>
                            <div class="stat-label">Signals Generated</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                .module-workflow { padding: 20px; }
                .workflow-diagram {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                    background: var(--card-bg);
                    border-radius: 12px;
                    margin-bottom: 30px;
                    overflow-x: auto;
                }
                .workflow-stage {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 20px;
                    background: rgba(79, 195, 247, 0.1);
                    border: 2px solid var(--border-color);
                    border-radius: 12px;
                    min-width: 120px;
                    transition: all 0.3s;
                }
                .workflow-stage.active {
                    border-color: var(--primary-color);
                    background: rgba(79, 195, 247, 0.2);
                    box-shadow: 0 0 20px rgba(79, 195, 247, 0.4);
                }
                .stage-icon {
                    font-size: 32px;
                    margin-bottom: 10px;
                }
                .stage-title {
                    font-weight: 600;
                    margin-bottom: 5px;
                    text-align: center;
                }
                .stage-detail {
                    font-size: 11px;
                    color: var(--text-secondary);
                    text-align: center;
                }
                .stage-status {
                    font-size: 12px;
                    color: var(--primary-color);
                    margin-top: 8px;
                }
                .workflow-arrow {
                    font-size: 24px;
                    margin: 0 15px;
                    color: var(--primary-color);
                }
                .workflow-details, .workflow-stats {
                    margin-top: 30px;
                }
                .stats-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                .stat {
                    text-align: center;
                    padding: 15px;
                    background: rgba(20, 20, 35, 0.5);
                    border-radius: 8px;
                }
                .stat-value {
                    font-size: 28px;
                    font-weight: bold;
                    color: var(--primary-color);
                }
                .stat-label {
                    font-size: 12px;
                    color: var(--text-secondary);
                    text-transform: uppercase;
                    margin-top: 8px;
                }
            </style>
        `;
    }
    
    getDefaultTemplate(modulePath) {
        const info = this.getModuleInfo(modulePath);
        return `
            <div class="module-default">
                <div class="card">
                    <h1>${info.title}</h1>
                    <p>Module: ${modulePath}</p>
                    <p>This module is under development.</p>
                    <button class="btn" onclick="app.loadModule('home')">← Back to Home</button>
                </div>
            </div>
        `;
    }
    
    // Module Initializers
    async initHomeModule() {
        await this.loadSystemOverview();
        await this.loadHomePositions();
        await this.loadMarketActivity();
        await this.loadRecentSignals();
        await this.loadPerformanceSummary();
    }
    
    async initDashboardModule() {
        await this.loadServicesGrid();
        await this.loadTradingMetrics();
        await this.loadPositions();
        await this.loadScanStatus();
        
        // Start auto-refresh
        this.startRefreshTimer('dashboard', () => {
            this.loadServicesGrid();
            this.loadTradingMetrics();
            this.loadPositions();
            this.loadScanStatus();
        }, this.config.refreshIntervals.dashboard);
    }
    
    async initMCPConsoleModule() {
        // Console is interactive, no auto-refresh needed
        this.addConsoleEntry('MCP Console initialized');
        this.addConsoleEntry(`Connection status: ${this.state.mcpConnected ? 'Connected' : 'Disconnected'}`);
    }
    
    async initWorkflowModule() {
        await this.loadWorkflowStatus();
        this.startRefreshTimer('workflow', () => {
            this.loadWorkflowStatus();
        }, 5000);
    }
    
    // Data Loading Functions
    async loadSystemOverview() {
        try {
            let status;
            if (this.state.mcpConnected) {
                status = await this.mcpGetResource('system/health');
            } else {
                // Fallback to REST endpoints
                status = await this.aggregateServiceHealth();
            }
            
            const container = document.getElementById('system-overview');
            if (!container) return;
            
            const services = status.services || {};
            const healthyCount = Object.values(services).filter(s => s.status === 'healthy').length;
            const totalCount = Object.keys(services).length;
            
            container.innerHTML = `
                <div class="status-summary">
                    <div class="status-metric">
                        <span class="big-number">${healthyCount}/${totalCount}</span>
                        <span class="label">Services Healthy</span>
                    </div>
                    <div class="status-indicator ${healthyCount === totalCount ? 'all-healthy' : 'some-unhealthy'}">
                        ${healthyCount === totalCount ? '✔ All Systems Operational' : '⚠ Some Services Down'}
                    </div>
                    <div class="mcp-indicator">
                        MCP: ${this.state.mcpConnected ? '✔ Connected' : '✗ Disconnected'}
                    </div>
                </div>
            `;
        } catch (error) {
            console.error('Failed to load system overview:', error);
        }
    }
    
    async loadServicesGrid() {
        try {
            const container = document.getElementById('services-grid');
            if (!container) return;
            
            // Build services list with MCP and REST services
            const services = [
                { 
                    name: 'Orchestration (MCP)', 
                    healthy: this.state.mcpConnected,
                    type: 'mcp'
                }
            ];
            
            // Check REST services
            for (const [name, client] of Object.entries(this.restClients)) {
                try {
                    await client.get('/health');
                    services.push({ name, healthy: true, type: 'rest' });
                } catch {
                    services.push({ name, healthy: false, type: 'rest' });
                }
            }
            
            container.innerHTML = services.map(service => `
                <div class="service-item ${service.healthy ? 'healthy' : 'unhealthy'} ${service.type}">
                    <div class="service-name">${service.name}</div>
                    <div class="service-status">${service.healthy ? '✔' : '✗'}</div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to load services:', error);
        }
    }
    
    async loadTradingMetrics() {
        try {
            if (this.state.mcpConnected) {
                const cycle = await this.mcpGetResource('trading-cycle/current');
                this.updateElement('cycle-status', cycle?.status || 'IDLE');
            }
            
            // Get positions from trading service
            try {
                const positions = await this.restClients.trading.get('/positions');
                this.updateElement('positions-count', positions?.length || '0');
                
                // Calculate daily P&L
                const dailyPnL = positions?.reduce((sum, pos) => {
                    return sum + ((pos.current_price - pos.entry_price) * pos.quantity);
                }, 0) || 0;
                
                this.updateElement('daily-pnl', `$${dailyPnL.toFixed(2)}`);
            } catch {
                this.updateElement('positions-count', '0');
                this.updateElement('daily-pnl', '$0.00');
            }
            
        } catch (error) {
            console.error('Failed to load metrics:', error);
        }
    }
    
    async loadPositions() {
        try {
            const positions = await this.restClients.trading.get('/positions');
            const tbody = document.getElementById('positions-body');
            if (!tbody) return;
            
            if (!positions || positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No active positions</td></tr>';
                return;
            }
            
            tbody.innerHTML = positions.map(pos => {
                const pnl = (pos.current_price - pos.entry_price) * pos.quantity;
                return `
                    <tr>
                        <td>${pos.symbol}</td>
                        <td>${pos.quantity}</td>
                        <td>$${pos.entry_price?.toFixed(2)}</td>
                        <td>$${pos.current_price?.toFixed(2)}</td>
                        <td class="${pnl >= 0 ? 'profit' : 'loss'}">$${pnl.toFixed(2)}</td>
                        <td>$${pos.stop_loss?.toFixed(2) || '-'}</td>
                    </tr>
                `;
            }).join('');
            
        } catch (error) {
            console.error('Failed to load positions:', error);
        }
    }
    
    async loadScanStatus() {
        try {
            if (this.state.mcpConnected) {
                const scan = await this.mcpGetResource('market-scan/status');
                this.updateElement('universe-count', scan?.universe_size || '100');
                this.updateElement('catalyst-count', scan?.catalysts_found || '-');
                this.updateElement('candidate-count', scan?.top_candidates || '-');
                this.updateElement('next-scan', scan?.next_scan || '-');
            }
        } catch (error) {
            console.error('Failed to load scan status:', error);
        }
    }
    
    async loadWorkflowStatus() {
        try {
            if (this.state.mcpConnected) {
                const cycle = await this.mcpGetResource('trading-cycle/current');
                
                // Update cycle details
                const detailsContainer = document.getElementById('cycle-details');
                if (detailsContainer && cycle) {
                    detailsContainer.innerHTML = `
                        <p><strong>Cycle ID:</strong> ${cycle.cycle_id || 'N/A'}</p>
                        <p><strong>Status:</strong> ${cycle.status || 'idle'}</p>
                        <p><strong>Stage:</strong> ${cycle.current_stage || 'N/A'}</p>
                        <p><strong>Started:</strong> ${cycle.start_time || 'N/A'}</p>
                    `;
                    
                    // Highlight active stage
                    this.updateWorkflowStage(cycle.current_stage);
                }
                
                // Update statistics
                this.updateElement('scanned-count', cycle?.statistics?.scanned || '0');
                this.updateElement('catalyst-count', cycle?.statistics?.with_catalysts || '0');
                this.updateElement('selected-count', cycle?.statistics?.selected || '0');
                this.updateElement('signals-count', cycle?.statistics?.signals || '0');
            }
        } catch (error) {
            console.error('Failed to load workflow status:', error);
        }
    }
    
    updateWorkflowStage(stage) {
        // Clear all active states
        document.querySelectorAll('.workflow-stage').forEach(el => {
            el.classList.remove('active');
        });
        
        // Map stage to element
        const stageMap = {
            'scanning': 'stage-universe',
            'catalyst_detection': 'stage-news',
            'candidate_selection': 'stage-candidates',
            'pattern_analysis': 'stage-pattern',
            'signal_generation': 'stage-technical',
            'trade_execution': 'stage-trade'
        };
        
        const elementId = stageMap[stage];
        if (elementId) {
            document.getElementById(elementId)?.classList.add('active');
        }
    }
    
    // Trading Control Functions
    async startTradingCycle() {
        if (!confirm('Start a new trading cycle?')) return;
        
        try {
            let result;
            
            if (this.state.mcpConnected) {
                // Use MCP tool
                result = await this.mcpCallTool('start_trading_cycle', {
                    mode: 'normal',
                    max_positions: 5,
                    risk_level: 'conservative'
                });
            } else {
                // Fallback to REST
                result = await this.restClients.scanner.post('/start-cycle', {
                    mode: 'normal',
                    target_securities: 100
                });
            }
            
            if (result) {
                alert('Trading cycle started successfully');
                this.refreshModule();
            }
        } catch (error) {
            alert('Failed to start trading cycle: ' + error.message);
        }
    }
    
    async stopTradingCycle() {
        if (!confirm('Stop the current trading cycle?')) return;
        
        try {
            if (this.state.mcpConnected) {
                await this.mcpCallTool('stop_trading', {
                    reason: 'User requested stop',
                    close_positions: false
                });
            } else {
                // Fallback REST implementation
                await this.restClients.scanner.post('/stop-cycle');
            }
            
            alert('Trading cycle stopped');
            this.refreshModule();
        } catch (error) {
            alert('Error stopping trading cycle: ' + error.message);
        }
    }
    
    async emergencyStop() {
        if (!confirm('Execute emergency stop? This will halt ALL trading and close ALL positions.')) return;
        
        try {
            if (this.state.mcpConnected) {
                await this.mcpCallTool('close_all_positions', {
                    reason: 'Emergency stop',
                    force: true
                });
            }
            
            alert('Emergency stop executed');
            this.refreshModule();
        } catch (error) {
            alert('Failed to execute emergency stop: ' + error.message);
        }
    }
    
    // MCP Console Functions
    async testMCPResource(uri) {
        if (!this.state.mcpConnected) {
            this.addConsoleEntry('Error: MCP not connected');
            return;
        }
        
        this.addConsoleEntry(`> GET ${uri}`);
        
        try {
            const result = await this.mcpGetResource(uri);
            this.addConsoleEntry(JSON.stringify(result, null, 2));
        } catch (error) {
            this.addConsoleEntry(`Error: ${error.message}`);
        }
    }
    
    showToolDialog(toolName) {
        // Simple prompt for tool parameters
        const params = prompt(`Enter parameters for ${toolName} (JSON format):`);
        if (params) {
            try {
                const parsedParams = JSON.parse(params);
                this.executeMCPTool(toolName, parsedParams);
            } catch (error) {
                alert('Invalid JSON parameters');
            }
        }
    }
    
    async executeMCPTool(name, params) {
        if (!this.state.mcpConnected) {
            this.addConsoleEntry('Error: MCP not connected');
            return;
        }
        
        this.addConsoleEntry(`> TOOL ${name} ${JSON.stringify(params)}`);
        
        try {
            const result = await this.mcpCallTool(name, params);
            this.addConsoleEntry(JSON.stringify(result, null, 2));
        } catch (error) {
            this.addConsoleEntry(`Error: ${error.message}`);
        }
    }
    
    addConsoleEntry(text) {
        const console = document.getElementById('mcp-console-output');
        if (console) {
            const entry = document.createElement('div');
            entry.className = 'console-entry';
            entry.textContent = text;
            console.appendChild(entry);
            console.scrollTop = console.scrollHeight;
        }
    }
    
    // Utility Functions
    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }
    
    updateMCPStatus(status) {
        const statusElement = document.getElementById('mcp-status');
        const dotElement = document.getElementById('mcp-connection');
        
        if (statusElement) statusElement.textContent = status;
        if (dotElement) {
            dotElement.classList.toggle('active', status === 'Connected');
        }
    }
    
    displayModule(content) {
        const container = document.getElementById('module-container');
        if (container) container.innerHTML = content;
    }
    
    showLoading() {
        const container = document.getElementById('module-container');
        if (container) {
            container.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    <p style="margin-top: 20px;">Loading module...</p>
                </div>
            `;
        }
    }
    
    displayError(modulePath, error) {
        const container = document.getElementById('module-container');
        if (container) {
            container.innerHTML = `
                <div class="error-container">
                    <h2>Failed to Load Module</h2>
                    <p>Module: ${modulePath}</p>
                    <p>Error: ${error.message}</p>
                    <button class="btn" onclick="app.loadModule('home')">Go Home</button>
                </div>
            `;
        }
    }
    
    displayInitError(error) {
        const container = document.getElementById('module-container');
        if (container) {
            container.innerHTML = `
                <div class="error-container">
                    <h2>Initialization Error</h2>
                    <p>${error.message}</p>
                    <p>The application may not function correctly.</p>
                    <button class="btn" onclick="location.reload()">Reload</button>
                </div>
            `;
        }
    }
    
    updateNavigation(modulePath) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset?.page === modulePath) {
                item.classList.add('active');
            }
        });
    }
    
    updatePageTitle(modulePath) {
        const info = this.getModuleInfo(modulePath);
        const titleElement = document.getElementById('page-title');
        if (titleElement) titleElement.textContent = info.title;
    }
    
    getModuleInfo(modulePath) {
        const moduleMap = {
            'home': { title: 'Home' },
            'dashboard': { title: 'Dashboard' },
            'mcp-console': { title: 'MCP Console' },
            'workflow': { title: 'Trading Workflow' },
            'positions': { title: 'Positions' },
            'signals': { title: 'Trading Signals' },
            'risk': { title: 'Risk Management' },
            'performance': { title: 'Performance Analytics' },
            'services/orchestration': { title: 'Orchestration Service (MCP)' },
            'services/scanner': { title: 'Scanner Service' },
            'services/news': { title: 'News Service' },
            'services/pattern': { title: 'Pattern Recognition' },
            'services/technical': { title: 'Technical Analysis' },
            'services/trading': { title: 'Trading Execution' },
            'services/reporting': { title: 'Reporting Service' },
            'troubleshoot/system': { title: 'System Troubleshooting' }
        };
        
        return moduleMap[modulePath] || {
            title: modulePath.split('/').pop().replace(/-/g, ' ')
        };
    }
    
    async aggregateServiceHealth() {
        const services = {};
        
        // Check MCP connection
        services['orchestration'] = {
            status: this.state.mcpConnected ? 'healthy' : 'unhealthy',
            type: 'mcp'
        };
        
        // Check REST services
        for (const [name, client] of Object.entries(this.restClients)) {
            try {
                await client.get('/health');
                services[name] = { status: 'healthy', type: 'rest' };
            } catch {
                services[name] = { status: 'unhealthy', type: 'rest' };
            }
        }
        
        return { services };
    }
    
    startRefreshTimer(name, callback, interval) {
        this.stopRefreshTimer(name);
        this.refreshTimers.set(name, setInterval(callback.bind(this), interval));
    }
    
    stopRefreshTimer(name) {
        const timer = this.refreshTimers.get(name);
        if (timer) {
            clearInterval(timer);
            this.refreshTimers.delete(name);
        }
    }
    
    stopAllRefreshTimers() {
        this.refreshTimers.forEach((timer) => {
            clearInterval(timer);
        });
        this.refreshTimers.clear();
    }
    
    refreshModule() {
        if (this.state.currentModule) {
            this.loadModule(this.state.currentModule);
        }
    }
    
    async startSystemMonitoring() {
        // Check system status periodically
        setInterval(async () => {
            try {
                const status = await this.aggregateServiceHealth();
                this.state.services = status.services || {};
                this.state.lastUpdate = new Date();
                
                // Update status indicator
                const services = Object.values(this.state.services);
                const healthyCount = services.filter(s => s.status === 'healthy').length;
                const totalCount = services.length;
                
                const statusDot = document.getElementById('system-status');
                const statusText = document.getElementById('status-text');
                
                if (statusDot && statusText) {
                    if (healthyCount === totalCount) {
                        statusDot.classList.add('active');
                        statusText.textContent = 'All Systems Operational';
                    } else {
                        statusDot.classList.remove('active');
                        statusText.textContent = `${healthyCount}/${totalCount} Services Healthy`;
                    }
                }
            } catch (error) {
                console.error('System monitoring error:', error);
            }
        }, 30000);
    }
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // Additional template methods
    getPositionsTemplate() {
        return this.getDefaultTemplate('positions');
    }
    
    getSignalsTemplate() {
        return this.getDefaultTemplate('signals');
    }
    
    getRiskTemplate() {
        return this.getDefaultTemplate('risk');
    }
    
    getPerformanceTemplate() {
        return this.getDefaultTemplate('performance');
    }
    
    // Additional data loading methods
    async loadHomePositions() {
        const container = document.getElementById('home-positions');
        if (!container) return;
        
        try {
            const positions = await this.restClients.trading.get('/positions');
            if (positions && positions.length > 0) {
                container.innerHTML = `${positions.length} active position(s)`;
            } else {
                container.innerHTML = 'No active positions';
            }
        } catch {
            container.innerHTML = 'Unable to load positions';
        }
    }
    
    async loadMarketActivity() {
        const container = document.getElementById('market-activity');
        if (!container) return;
        
        container.innerHTML = 'Market scan scheduled every 30 minutes';
    }
    
    async loadRecentSignals() {
        const container = document.getElementById('recent-signals');
        if (!container) return;
        
        container.innerHTML = 'No recent signals';
    }
    
    async loadPerformanceSummary() {
        const container = document.getElementById('performance-summary');
        if (!container) return;
        
        container.innerHTML = `
            <div style="text-align: center;">
                <div style="font-size: 24px; color: var(--success-color);">+0.00%</div>
                <div style="color: var(--text-secondary);">Today's Performance</div>
            </div>
        `;
    }
}

// Initialize app when DOM is ready
let app;
window.addEventListener('DOMContentLoaded', () => {
    app = new CatalystApp();
    window.app = app; // Make available globally for onclick handlers
});