// Catalyst Trading System - MCP Client Module
// Name of Application: Catalyst Trading System
// Name of file: mcp-client.js
// Version: 4.1.0
// Last Updated: 2025-09-27
// Purpose: WebSocket MCP client for orchestration service communication

// REVISION HISTORY:
// v4.1.0 (2025-09-27) - Initial implementation
// - WebSocket connection management
// - Resource retrieval with hierarchical URIs
// - Tool execution with validation
// - Automatic reconnection
// - Event subscription system

class MCPClient {
    constructor(endpoint = 'ws://localhost:5000/mcp') {
        this.endpoint = endpoint;
        this.ws = null;
        this.connected = false;
        this.requestQueue = new Map();
        this.eventHandlers = new Map();
        this.reconnectTimer = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        
        // Available resources and tools (from functional-spec-v41)
        this.resources = {
            // System Resources
            'system/health': 'Get overall system health status',
            'system/config': 'Get current system configuration',
            
            // Trading Cycle Resources
            'trading-cycle/current': 'Get current trading cycle status',
            'trading-cycle/status': 'Get detailed cycle status',
            'trading-cycle/history': 'Get recent cycle history',
            
            // Market Scan Resources
            'market-scan/status': 'Get market scan status',
            'market-scan/candidates/active': 'Get active trading candidates',
            'market-scan/candidates/scored': 'Get scored candidates list',
            'market-scan/universe': 'Get current scanning universe',
            
            // Portfolio Resources
            'portfolio/positions/open': 'Get open positions',
            'portfolio/positions/closed': 'Get closed positions today',
            'portfolio/account/status': 'Get account status',
            'portfolio/risk/metrics': 'Get risk metrics',
            
            // Analytics Resources
            'analytics/daily-summary': 'Get daily performance summary',
            'analytics/performance': 'Get performance metrics',
            'analytics/patterns/success-rate': 'Get pattern success rates'
        };
        
        this.tools = {
            // Trading Control Tools
            'start_trading_cycle': {
                description: 'Start a new trading cycle',
                params: ['mode', 'max_positions', 'risk_level']
            },
            'stop_trading': {
                description: 'Stop all trading activities',
                params: ['reason', 'close_positions']
            },
            'pause_trading': {
                description: 'Pause trading temporarily',
                params: ['duration_minutes']
            },
            
            // Risk Management Tools
            'update_risk_parameters': {
                description: 'Update risk management parameters',
                params: ['max_position_size', 'stop_loss_pct', 'daily_loss_limit']
            },
            'close_all_positions': {
                description: 'Emergency close all positions',
                params: ['reason', 'force']
            },
            
            // Manual Trading Tools
            'execute_trade': {
                description: 'Manually execute a trade',
                params: ['symbol', 'side', 'quantity', 'order_type']
            },
            'close_position': {
                description: 'Close a specific position',
                params: ['symbol', 'reason']
            }
        };
    }
    
    // Connection Management
    async connect() {
        return new Promise((resolve, reject) => {
            try {
                console.log(`[MCP] Connecting to ${this.endpoint}`);
                this.ws = new WebSocket(this.endpoint);
                
                // Connection opened
                this.ws.onopen = () => {
                    console.log('[MCP] Connection established');
                    this.connected = true;
                    this.reconnectDelay = 1000; // Reset delay on successful connection
                    this.sendHandshake();
                    resolve(true);
                };
                
                // Message received
                this.ws.onmessage = (event) => {
                    this.handleMessage(event.data);
                };
                
                // Error occurred
                this.ws.onerror = (error) => {
                    console.error('[MCP] WebSocket error:', error);
                    this.connected = false;
                };
                
                // Connection closed
                this.ws.onclose = (event) => {
                    console.log('[MCP] Connection closed:', event.code, event.reason);
                    this.connected = false;
                    this.handleDisconnect();
                };
                
                // Timeout if connection takes too long
                setTimeout(() => {
                    if (!this.connected) {
                        reject(new Error('Connection timeout'));
                    }
                }, 10000);
                
            } catch (error) {
                console.error('[MCP] Failed to connect:', error);
                reject(error);
            }
        });
    }
    
    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        
        this.connected = false;
        this.requestQueue.clear();
    }
    
    handleDisconnect() {
        // Clear pending requests
        this.requestQueue.forEach((handler, id) => {
            handler.reject(new Error('Connection lost'));
        });
        this.requestQueue.clear();
        
        // Attempt reconnection
        this.scheduleReconnect();
    }
    
    scheduleReconnect() {
        if (this.reconnectTimer) return;
        
        console.log(`[MCP] Reconnecting in ${this.reconnectDelay}ms...`);
        
        this.reconnectTimer = setTimeout(async () => {
            this.reconnectTimer = null;
            
            try {
                await this.connect();
                console.log('[MCP] Reconnection successful');
            } catch (error) {
                console.error('[MCP] Reconnection failed:', error);
                // Exponential backoff
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
                this.scheduleReconnect();
            }
        }, this.reconnectDelay);
    }
    
    // Protocol Implementation
    sendHandshake() {
        this.send({
            type: 'handshake',
            version: '1.0',
            client: 'catalyst-dashboard',
            capabilities: ['resources', 'tools', 'events']
        });
    }
    
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            
            switch (message.type) {
                case 'response':
                    this.handleResponse(message);
                    break;
                    
                case 'event':
                    this.handleEvent(message);
                    break;
                    
                case 'error':
                    this.handleError(message);
                    break;
                    
                case 'handshake_ack':
                    console.log('[MCP] Handshake acknowledged');
                    break;
                    
                default:
                    console.warn('[MCP] Unknown message type:', message.type);
            }
        } catch (error) {
            console.error('[MCP] Failed to parse message:', error);
        }
    }
    
    handleResponse(message) {
        const handler = this.requestQueue.get(message.id);
        if (handler) {
            this.requestQueue.delete(message.id);
            
            if (message.error) {
                handler.reject(new Error(message.error.message || 'Request failed'));
            } else {
                handler.resolve(message.result);
            }
        }
    }
    
    handleEvent(message) {
        const handlers = this.eventHandlers.get(message.event) || [];
        handlers.forEach(handler => {
            try {
                handler(message.data);
            } catch (error) {
                console.error('[MCP] Event handler error:', error);
            }
        });
    }
    
    handleError(message) {
        console.error('[MCP] Server error:', message.error);
        
        if (message.id) {
            const handler = this.requestQueue.get(message.id);
            if (handler) {
                this.requestQueue.delete(message.id);
                handler.reject(new Error(message.error.message || 'Server error'));
            }
        }
    }
    
    send(data) {
        if (!this.connected || !this.ws) {
            throw new Error('Not connected to MCP server');
        }
        
        this.ws.send(JSON.stringify(data));
    }
    
    // Resource Operations
    async getResource(uri) {
        if (!this.connected) {
            throw new Error('MCP client not connected');
        }
        
        // Validate URI
        if (!this.resources[uri]) {
            console.warn(`[MCP] Unknown resource: ${uri}`);
        }
        
        return this.sendRequest('resource', {
            method: 'GET',
            uri: uri
        });
    }
    
    async listResources() {
        return this.sendRequest('list_resources');
    }
    
    // Tool Operations
    async callTool(name, params = {}) {
        if (!this.connected) {
            throw new Error('MCP client not connected');
        }
        
        // Validate tool
        const toolDef = this.tools[name];
        if (!toolDef) {
            throw new Error(`Unknown tool: ${name}`);
        }
        
        // Validate parameters
        const missingParams = toolDef.params.filter(p => 
            params[p] === undefined && !p.endsWith('?')
        );
        
        if (missingParams.length > 0) {
            throw new Error(`Missing required parameters: ${missingParams.join(', ')}`);
        }
        
        return this.sendRequest('tool', {
            name: name,
            params: params
        });
    }
    
    async listTools() {
        return this.sendRequest('list_tools');
    }
    
    // Request Management
    async sendRequest(type, data = {}) {
        return new Promise((resolve, reject) => {
            const id = this.generateRequestId();
            
            const request = {
                id: id,
                type: type,
                ...data
            };
            
            // Set up response handler
            this.requestQueue.set(id, { resolve, reject });
            
            // Send request
            try {
                this.send(request);
            } catch (error) {
                this.requestQueue.delete(id);
                reject(error);
            }
            
            // Timeout after 30 seconds
            setTimeout(() => {
                if (this.requestQueue.has(id)) {
                    this.requestQueue.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 30000);
        });
    }
    
    generateRequestId() {
        return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    
    // Event Subscription
    subscribe(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        
        this.eventHandlers.get(event).push(handler);
        
        // Send subscription request
        if (this.connected) {
            this.send({
                type: 'subscribe',
                event: event
            });
        }
    }
    
    unsubscribe(event, handler) {
        const handlers = this.eventHandlers.get(event);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
            
            if (handlers.length === 0) {
                this.eventHandlers.delete(event);
                
                // Send unsubscribe request
                if (this.connected) {
                    this.send({
                        type: 'unsubscribe',
                        event: event
                    });
                }
            }
        }
    }
    
    // Utility Methods
    isConnected() {
        return this.connected;
    }
    
    async waitForConnection(timeout = 10000) {
        const start = Date.now();
        
        while (!this.connected) {
            if (Date.now() - start > timeout) {
                throw new Error('Connection timeout');
            }
            
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        return true;
    }
    
    // Testing Methods
    async test() {
        console.log('[MCP] Running connection test...');
        
        try {
            // Test connection
            if (!this.connected) {
                await this.connect();
            }
            
            // Test resource retrieval
            console.log('[MCP] Testing resource: system/health');
            const health = await this.getResource('system/health');
            console.log('[MCP] Health check result:', health);
            
            // Test tool listing
            console.log('[MCP] Listing available tools...');
            const tools = await this.listTools();
            console.log('[MCP] Available tools:', tools);
            
            console.log('[MCP] Connection test successful');
            return true;
            
        } catch (error) {
            console.error('[MCP] Connection test failed:', error);
            return false;
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MCPClient;
}