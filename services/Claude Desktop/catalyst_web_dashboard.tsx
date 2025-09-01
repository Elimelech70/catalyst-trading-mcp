import React, { useState, useEffect } from 'react';
import { 
  Activity, TrendingUp, AlertTriangle, BarChart3, Settings, Play, Square, 
  Monitor, Zap, Clock, DollarSign, Target, Shield, Wifi, WifiOff,
  RefreshCw, Bell, Users, Database, TrendingDown
} from 'lucide-react';

const CatalystDashboard = () => {
  const [systemStatus, setSystemStatus] = useState('active');
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Sample data - in real implementation, this would come from your REST APIs
  const [currentCycle, setCurrentCycle] = useState({
    id: '20250831-001',
    mode: 'normal',
    status: 'scanning',
    progress: 67,
    runtime: '2h 34m',
    positions: 3,
    maxPositions: 5
  });

  const [positions, setPositions] = useState([
    { symbol: 'AAPL', side: 'LONG', shares: 100, entry: '$175.20', current: '$179.54', pnl: '+2.47%', pnlDollar: '+$434' },
    { symbol: 'TSLA', side: 'LONG', shares: 50, entry: '$248.90', current: '$246.91', pnl: '-0.80%', pnlDollar: '-$99' },
    { symbol: 'NVDA', side: 'SHORT', shares: 25, entry: '$445.30', current: '$439.85', pnl: '+1.22%', pnlDollar: '+$136' }
  ]);

  const [candidates, setCandidates] = useState([
    { symbol: 'META', catalyst: 'Q3 Earnings Beat Expected', confidence: 92, signal: 'BUY', score: 8.4 },
    { symbol: 'GOOGL', catalyst: 'AI Partnership News', confidence: 87, signal: 'BUY', score: 7.8 },
    { symbol: 'AMZN', catalyst: 'Cloud Growth Acceleration', confidence: 84, signal: 'BUY', score: 7.2 },
    { symbol: 'MSFT', catalyst: 'Office 365 Expansion', confidence: 79, signal: 'WATCH', score: 6.9 },
    { symbol: 'CRM', catalyst: 'Sales Automation News', confidence: 76, signal: 'WATCH', score: 6.5 }
  ]);

  const [services, setServices] = useState({
    orchestration: { status: 'healthy', uptime: '99.8%', responseTime: '12ms' },
    scanner: { status: 'healthy', uptime: '99.2%', responseTime: '45ms' },
    news: { status: 'healthy', uptime: '98.9%', responseTime: '23ms' },
    pattern: { status: 'warning', uptime: '97.1%', responseTime: '89ms' },
    technical: { status: 'healthy', uptime: '99.5%', responseTime: '34ms' },
    trading: { status: 'healthy', uptime: '99.9%', responseTime: '8ms' },
    reporting: { status: 'healthy', uptime: '99.0%', responseTime: '56ms' }
  });

  const [marketMetrics, setMarketMetrics] = useState({
    totalScanned: 100,
    candidates: 20,
    finalPicks: 5,
    winRate: '68.3%',
    avgReturn: '+2.1%',
    totalPnL: '+$1,247'
  });

  // Status badge component
  const StatusBadge = ({ status, size = 'sm' }) => {
    const colors = {
      healthy: 'bg-green-100 text-green-800 border-green-200',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      error: 'bg-red-100 text-red-800 border-red-200',
      active: 'bg-blue-100 text-blue-800 border-blue-200',
      inactive: 'bg-gray-100 text-gray-800 border-gray-200'
    };
    
    const sizes = {
      sm: 'px-2 py-1 text-xs',
      md: 'px-3 py-1 text-sm',
      lg: 'px-4 py-2 text-base'
    };
    
    return (
      <span className={`${colors[status]} ${sizes[size]} rounded-full font-medium border`}>
        {status.toUpperCase()}
      </span>
    );
  };

  // Auto-refresh simulation
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        setLastUpdate(new Date());
        // In real implementation, fetch fresh data here
      }, 30000); // 30 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-3 rounded-lg">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900 mb-1">
                  Catalyst Trading System
                </h1>
                <p className="text-gray-600 flex items-center gap-2">
                  AI-Native News-Driven Trading Platform
                  <span className="text-sm text-gray-500">
                    • Last Update: {formatTime(lastUpdate)}
                  </span>
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button 
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 border ${
                  autoRefresh 
                    ? 'bg-green-50 border-green-200 text-green-700' 
                    : 'bg-gray-50 border-gray-200 text-gray-700'
                }`}
              >
                {autoRefresh ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                {autoRefresh ? 'Live' : 'Manual'}
              </button>
              <button className="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 transition-colors">
                <Play className="w-4 h-4" />
                Start New Cycle
              </button>
              <button className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg flex items-center gap-2 transition-colors">
                <Square className="w-4 h-4" />
                Emergency Stop
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <Target className="w-8 h-8 text-blue-600" />
            <div>
              <div className="text-2xl font-bold text-blue-600">{marketMetrics.totalScanned}</div>
              <div className="text-sm text-gray-600">Scanned</div>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-green-600" />
            <div>
              <div className="text-2xl font-bold text-green-600">{marketMetrics.candidates}</div>
              <div className="text-sm text-gray-600">Candidates</div>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-purple-600" />
            <div>
              <div className="text-2xl font-bold text-purple-600">{marketMetrics.finalPicks}</div>
              <div className="text-sm text-gray-600">Final Picks</div>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-indigo-600" />
            <div>
              <div className="text-2xl font-bold text-indigo-600">{marketMetrics.winRate}</div>
              <div className="text-sm text-gray-600">Win Rate</div>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-orange-600" />
            <div>
              <div className="text-2xl font-bold text-orange-600">{marketMetrics.avgReturn}</div>
              <div className="text-sm text-gray-600">Avg Return</div>
            </div>
          </div>
        </div>

        <div className="bg-white p-4 rounded-lg shadow-sm border">
          <div className="flex items-center gap-3">
            <DollarSign className="w-8 h-8 text-green-600" />
            <div>
              <div className="text-2xl font-bold text-green-600">{marketMetrics.totalPnL}</div>
              <div className="text-sm text-gray-600">Total P&L</div>
            </div>
          </div>
        </div>
      </div>

      {/* Current Trading Cycle Status */}
      <div className="mb-8">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-600" />
              Current Trading Cycle: {currentCycle.id}
            </h2>
            <div className="flex items-center gap-4">
              <StatusBadge status={currentCycle.status} size="md" />
              <div className="text-sm text-gray-600">Mode: {currentCycle.mode.toUpperCase()}</div>
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600 mb-1">{currentCycle.progress}%</div>
              <div className="text-sm text-gray-600">Scan Progress</div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${currentCycle.progress}%` }}
                ></div>
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600 mb-1">{currentCycle.positions}</div>
              <div className="text-sm text-gray-600">Active Positions</div>
              <div className="text-xs text-gray-500 mt-1">Max: {currentCycle.maxPositions}</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600 mb-1">{currentCycle.runtime}</div>
              <div className="text-sm text-gray-600">Runtime</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-orange-600 mb-1">Pattern Analysis</div>
              <div className="text-sm text-gray-600">Current Stage</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-indigo-600 mb-1">5 min</div>
              <div className="text-sm text-gray-600">Next Scan</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Trading Candidates */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-600" />
            Top Trading Candidates
          </h2>
          
          <div className="space-y-3">
            {candidates.map((candidate, idx) => (
              <div key={idx} className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-50 to-white rounded-lg border hover:shadow-sm transition-shadow">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="font-bold text-blue-600 text-lg">{candidate.symbol}</div>
                    <div className={`px-2 py-1 rounded text-xs font-medium ${
                      candidate.signal === 'BUY' 
                        ? 'bg-green-100 text-green-800' 
                        : candidate.signal === 'SELL'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {candidate.signal}
                    </div>
                  </div>
                  <div className="text-sm text-gray-600 mb-1">{candidate.catalyst}</div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>Confidence: {candidate.confidence}%</span>
                    <span>Score: {candidate.score}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="w-12 h-12 rounded-full border-4 border-green-200 flex items-center justify-center">
                    <span className="text-sm font-bold text-green-600">{candidate.confidence}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Active Positions */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-purple-600" />
            Active Positions
          </h2>
          
          <div className="space-y-3">
            {positions.map((position, idx) => (
              <div key={idx} className="p-4 bg-gradient-to-r from-gray-50 to-white rounded-lg border">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="font-bold text-blue-600 text-lg">{position.symbol}</div>
                    <div className={`px-2 py-1 rounded text-xs font-medium ${
                      position.side === 'LONG' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {position.side}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-bold ${
                      position.pnl.startsWith('+') ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {position.pnl}
                    </div>
                    <div className={`text-sm ${
                      position.pnlDollar.startsWith('+') ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {position.pnlDollar}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                  <div>Shares: {position.shares}</div>
                  <div>Entry: {position.entry}</div>
                  <div>Current: {position.current}</div>
                </div>
              </div>
            ))}
            
            {positions.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                No active positions
              </div>
            )}
          </div>
        </div>

        {/* System Health & Services */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Monitor className="w-5 h-5 text-blue-600" />
            System Health & Services
          </h2>
          
          <div className="space-y-3">
            {Object.entries(services).map(([service, data]) => (
              <div key={service} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    data.status === 'healthy' 
                      ? 'bg-green-400' 
                      : data.status === 'warning'
                      ? 'bg-yellow-400'
                      : 'bg-red-400'
                  }`}></div>
                  <div>
                    <div className="font-medium capitalize">{service}</div>
                    <div className="text-xs text-gray-500">
                      {data.uptime} uptime • {data.responseTime} avg
                    </div>
                  </div>
                </div>
                <StatusBadge status={data.status} />
              </div>
            ))}
          </div>
          
          {/* Quick Actions */}
          <div className="mt-6 pt-6 border-t">
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <button className="p-3 text-left border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                <div className="font-medium">Health Check</div>
                <div className="text-xs text-gray-600">Verify all services</div>
              </button>
              
              <button className="p-3 text-left border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                <div className="font-medium">View Logs</div>
                <div className="text-xs text-gray-600">System diagnostics</div>
              </button>
              
              <button className="p-3 text-left border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                <div className="font-medium">Export Data</div>
                <div className="text-xs text-gray-600">Download reports</div>
              </button>
              
              <button className="p-3 text-left border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                <div className="font-medium">Settings</div>
                <div className="text-xs text-gray-600">Configure system</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CatalystDashboard;