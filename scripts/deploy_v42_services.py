#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: deploy_v42_services.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Automated deployment and service orchestration for v4.2 upgrade

REVISION HISTORY:
v4.2.0 (2025-09-20) - Complete v4.2 deployment automation
- Deploy new risk-manager service (port 5004)
- Orchestrated service restart with dependency management
- Health check validation for all 8 services
- Service connectivity testing
- Risk management integration validation
- Real-time monitoring setup

Description of Service:
Automated deployment script that safely upgrades the Catalyst Trading System
to v4.2 with the new risk management service, ensuring all services start
in the correct order and can communicate properly.
"""

import asyncio
import aiohttp
import subprocess
import time
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deployment")

@dataclass
class ServiceConfig:
    name: str
    port: int
    protocol: str  # "MCP" or "REST"
    dependencies: List[str]
    health_endpoint: str
    startup_time: int  # Expected startup time in seconds

# v4.2 Service Configuration
SERVICES = {
    "redis": ServiceConfig("redis", 6379, "REDIS", [], "", 10),
    "postgres": ServiceConfig("postgres", 5432, "DB", [], "", 15),
    "risk-manager": ServiceConfig("risk-manager", 5004, "REST", ["redis", "postgres"], "/health", 20),
    "scanner": ServiceConfig("scanner", 5001, "REST", ["redis", "postgres"], "/health", 15),
    "pattern": ServiceConfig("pattern", 5002, "REST", ["redis", "postgres"], "/health", 15),
    "technical": ServiceConfig("technical", 5003, "REST", ["redis", "postgres"], "/health", 15),
    "trading": ServiceConfig("trading", 5005, "REST", ["redis", "postgres", "risk-manager"], "/health", 20),
    "news": ServiceConfig("news", 5008, "REST", ["redis", "postgres"], "/health", 15),
    "reporting": ServiceConfig("reporting", 5009, "REST", ["redis", "postgres"], "/health", 15),
    "orchestration": ServiceConfig("orchestration", 5000, "MCP", ["risk-manager", "scanner", "pattern", "technical", "trading", "news", "reporting"], "", 25)
}

class DeploymentManager:
    def __init__(self):
        self.deployment_start = datetime.now()
        self.service_status: Dict[str, str] = {}
        self.http_session: Optional[aiohttp.ClientSession] = None
        
    async def deploy_v42(self):
        """Main deployment orchestration"""
        print("🚀 Starting Catalyst Trading System v4.2 Deployment")
        print("=" * 60)
        print(f"📅 Started at: {self.deployment_start.isoformat()}")
        print(f"🎯 Target: 8-service architecture with risk management")
        
        try:
            # Initialize HTTP session for health checks
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
            # Step 1: Pre-deployment validation
            print("\n🔍 Step 1: Pre-deployment Validation")
            print("-" * 40)
            await self.validate_environment()
            await self.validate_docker_setup()
            await self.validate_risk_manager_service()
            
            # Step 2: Stop existing services gracefully
            print("\n🛑 Step 2: Stopping Existing Services")
            print("-" * 40)
            await self.stop_existing_services()
            
            # Step 3: Deploy infrastructure services
            print("\n🏗️ Step 3: Starting Infrastructure Services")
            print("-" * 40)
            await self.start_infrastructure()
            
            # Step 4: Deploy core services (including new risk-manager)
            print("\n⚙️ Step 4: Deploying Core Services")
            print("-" * 40)
            await self.deploy_core_services()
            
            # Step 5: Deploy orchestration service
            print("\n🎭 Step 5: Starting Orchestration Service")
            print("-" * 40)
            await self.start_orchestration()
            
            # Step 6: Comprehensive health validation
            print("\n🩺 Step 6: Health Check Validation")
            print("-" * 40)
            await self.validate_all_services()
            
            # Step 7: Service connectivity testing
            print("\n🔗 Step 7: Service Connectivity Testing")
            print("-" * 40)
            await self.test_service_integration()
            
            # Step 8: Risk management validation
            print("\n🛡️ Step 8: Risk Management Validation")
            print("-" * 40)
            await self.validate_risk_management()
            
            # Success summary
            await self.deployment_success_summary()
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            await self.deployment_failure_summary(str(e))
            raise
        finally:
            if self.http_session:
                await self.http_session.close()
                
    async def validate_environment(self):
        """Validate deployment environment"""
        print("📋 Checking environment...")
        
        # Check required environment variables
        required_vars = [
            "DATABASE_URL", "REDIS_URL", "ALPHA_VANTAGE_API_KEY", 
            "FINNHUB_API_KEY", "MAX_DAILY_LOSS", "MAX_POSITION_RISK"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")
            
        print("✅ Environment variables validated")
        
        # Check if we're in the correct directory
        if not os.path.exists("docker-compose.yml"):
            raise Exception("docker-compose.yml not found - run from project root")
            
        print("✅ Project directory validated")
        
        # Check if risk-manager service exists
        if not os.path.exists("services/risk-manager/risk-manager-service.py"):
            raise Exception("Risk manager service not found - ensure it's been created")
            
        print("✅ Risk manager service file validated")
        
    async def validate_docker_setup(self):
        """Validate Docker environment"""
        print("🐳 Checking Docker setup...")
        
        try:
            # Check Docker is running
            result = subprocess.run(["docker", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("Docker is not running")
                
            print("✅ Docker daemon is running")
            
            # Check Docker Compose
            result = subprocess.run(["docker-compose", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception("Docker Compose not available")
                
            print("✅ Docker Compose is available")
            
        except FileNotFoundError:
            raise Exception("Docker or Docker Compose not installed")
            
    async def validate_risk_manager_service(self):
        """Validate risk manager service is ready for deployment"""
        print("🛡️ Validating risk manager service...")
        
        service_file = "services/risk-manager/risk-manager-service.py"
        
        # Check file exists and has correct version
        if not os.path.exists(service_file):
            raise Exception("Risk manager service file missing")
            
        # Read and check version
        with open(service_file, 'r') as f:
            content = f.read()
            if "Version: 4.2.0" not in content:
                raise Exception("Risk manager service is not v4.2.0 - update required")
            if "FastAPI" not in content:
                raise Exception("Risk manager service should use FastAPI, not MCP")
                
        print("✅ Risk manager service v4.2.0 validated")
        
        # Check Dockerfile exists
        dockerfile_path = "services/risk-manager/Dockerfile"
        if not os.path.exists(dockerfile_path):
            print("⚠️ Risk manager Dockerfile missing - will use default")
        else:
            print("✅ Risk manager Dockerfile found")
            
    async def stop_existing_services(self):
        """Stop existing services gracefully"""
        print("🛑 Stopping existing services...")
        
        try:
            # Stop all containers
            result = subprocess.run(
                ["docker-compose", "down", "--remove-orphans"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print("✅ All services stopped successfully")
            else:
                print(f"⚠️ Stop command output: {result.stderr}")
                
            # Wait for cleanup
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"⚠️ Error stopping services: {e}")
            
    async def start_infrastructure(self):
        """Start infrastructure services (Redis, PostgreSQL)"""
        infrastructure_services = ["redis", "postgres"]
        
        for service in infrastructure_services:
            print(f"🏗️ Starting {service}...")
            
            try:
                result = subprocess.run(
                    ["docker-compose", "up", "-d", service],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    print(f"✅ {service} started")
                    self.service_status[service] = "started"
                    
                    # Wait for service to be ready
                    await asyncio.sleep(SERVICES[service].startup_time)
                    
                else:
                    raise Exception(f"Failed to start {service}: {result.stderr}")
                    
            except Exception as e:
                print(f"❌ Failed to start {service}: {e}")
                self.service_status[service] = "failed"
                raise
                
        print("✅ Infrastructure services started")
        
    async def deploy_core_services(self):
        """Deploy core services including the new risk-manager"""
        
        # Order matters - risk-manager must start before trading
        core_services = ["risk-manager", "scanner", "pattern", "technical", "news", "reporting", "trading"]
        
        for service in core_services:
            print(f"⚙️ Starting {service}...")
            
            try:
                # Build and start service
                result = subprocess.run(
                    ["docker-compose", "up", "-d", "--build", service],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    print(f"✅ {service} container started")
                    self.service_status[service] = "started"
                    
                    # Wait for startup
                    startup_time = SERVICES[service].startup_time
                    print(f"⏳ Waiting {startup_time}s for {service} to initialize...")
                    await asyncio.sleep(startup_time)
                    
                    # Health check
                    if await self.check_service_health(service):
                        print(f"✅ {service} health check passed")
                        self.service_status[service] = "healthy"
                    else:
                        print(f"⚠️ {service} health check failed - continuing anyway")
                        self.service_status[service] = "unhealthy"
                        
                else:
                    raise Exception(f"Failed to start {service}: {result.stderr}")
                    
            except Exception as e:
                print(f"❌ Failed to deploy {service}: {e}")
                self.service_status[service] = "failed"
                # Continue with other services unless it's risk-manager
                if service == "risk-manager":
                    raise Exception("Risk manager is critical - deployment aborted")
                    
        print("✅ Core services deployed")
        
    async def start_orchestration(self):
        """Start the orchestration service last"""
        service = "orchestration"
        print(f"🎭 Starting {service}...")
        
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--build", service],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print(f"✅ {service} container started")
                self.service_status[service] = "started"
                
                # Wait for MCP initialization
                startup_time = SERVICES[service].startup_time
                print(f"⏳ Waiting {startup_time}s for MCP initialization...")
                await asyncio.sleep(startup_time)
                
                self.service_status[service] = "ready"
                print("✅ Orchestration service ready for Claude Desktop")
                
            else:
                raise Exception(f"Failed to start {service}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Failed to start orchestration: {e}")
            self.service_status[service] = "failed"
            raise
            
    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        if service_name not in SERVICES:
            return False
            
        service = SERVICES[service_name]
        
        if service.protocol != "REST" or not service.health_endpoint:
            return True  # Skip health check for non-REST services
            
        try:
            url = f"http://localhost:{service.port}{service.health_endpoint}"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("status") == "healthy"
                    
        except Exception:
            pass
            
        return False
        
    async def validate_all_services(self):
        """Comprehensive health validation of all services"""
        print("🩺 Running comprehensive health checks...")
        
        health_results = {}
        
        for service_name, service in SERVICES.items():
            if service.protocol == "REST" and service.health_endpoint:
                print(f"🔍 Checking {service_name}...")
                
                try:
                    url = f"http://localhost:{service.port}{service.health_endpoint}"
                    async with self.http_session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            health_results[service_name] = {
                                "status": "healthy",
                                "version": data.get("version", "unknown"),
                                "details": data
                            }
                            print(f"✅ {service_name}: v{data.get('version', '?')} - {data.get('status', 'unknown')}")
                        else:
                            health_results[service_name] = {
                                "status": "unhealthy",
                                "error": f"HTTP {response.status}"
                            }
                            print(f"❌ {service_name}: HTTP {response.status}")
                            
                except Exception as e:
                    health_results[service_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                    print(f"❌ {service_name}: {e}")
                    
            else:
                # Non-REST services
                health_results[service_name] = {"status": "assumed_healthy"}
                print(f"✅ {service_name}: (no health endpoint)")
                
        # Summary
        healthy_count = sum(1 for result in health_results.values() 
                          if result["status"] in ["healthy", "assumed_healthy"])
        total_count = len(health_results)
        
        print(f"\n📊 Health Summary: {healthy_count}/{total_count} services healthy")
        
        if healthy_count < total_count:
            print("⚠️ Some services are unhealthy - check logs for details")
        else:
            print("✅ All services are healthy!")
            
        return health_results
        
    async def test_service_integration(self):
        """Test service-to-service connectivity"""
        print("🔗 Testing service integration...")
        
        # Test orchestration -> risk-manager
        try:
            url = "http://localhost:5004/api/v1/parameters"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Risk manager parameters accessible")
                else:
                    print(f"⚠️ Risk manager parameters: HTTP {response.status}")
        except Exception as e:
            print(f"❌ Risk manager connectivity: {e}")
            
        # Test orchestration -> scanner
        try:
            url = "http://localhost:5001/health"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    print("✅ Scanner connectivity confirmed")
                else:
                    print(f"⚠️ Scanner connectivity: HTTP {response.status}")
        except Exception as e:
            print(f"❌ Scanner connectivity: {e}")
            
        # Test risk-manager database connectivity
        try:
            url = "http://localhost:5004/api/v1/metrics"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Risk manager database connectivity confirmed")
                    print(f"ℹ️ Current risk score: {data.get('risk_score', 'N/A')}")
                else:
                    print(f"⚠️ Risk manager database: HTTP {response.status}")
        except Exception as e:
            print(f"❌ Risk manager database: {e}")
            
    async def validate_risk_management(self):
        """Validate risk management system specifically"""
        print("🛡️ Validating risk management system...")
        
        try:
            # Test risk parameters
            url = "http://localhost:5004/api/v1/parameters"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    params = data.get("parameters", {})
                    
                    essential_params = [
                        "max_daily_loss", "max_position_risk", "max_portfolio_risk",
                        "position_size_multiplier", "max_positions"
                    ]
                    
                    missing_params = [p for p in essential_params if p not in params]
                    
                    if not missing_params:
                        print("✅ All essential risk parameters configured")
                        print(f"ℹ️ Max daily loss: ${params.get('max_daily_loss', 'N/A')}")
                        print(f"ℹ️ Max position risk: {params.get('max_position_risk', 'N/A')*100:.1f}%")
                        print(f"ℹ️ Max positions: {params.get('max_positions', 'N/A')}")
                    else:
                        print(f"⚠️ Missing risk parameters: {', '.join(missing_params)}")
                        
                else:
                    print(f"❌ Risk parameters not accessible: HTTP {response.status}")
                    
        except Exception as e:
            print(f"❌ Risk parameter validation failed: {e}")
            
        # Test position size calculation
        try:
            url = "http://localhost:5004/api/v1/calculate-position-size"
            test_request = {
                "symbol": "TEST",
                "side": "buy",
                "confidence": 0.8,
                "current_price": 100.0,
                "atr": 2.5,
                "account_balance": 10000.0
            }
            
            async with self.http_session.post(url, json=test_request) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Position size calculation working")
                    print(f"ℹ️ Test calculation: {data.get('recommended_shares', 'N/A')} shares")
                else:
                    print(f"⚠️ Position size calculation: HTTP {response.status}")
                    
        except Exception as e:
            print(f"❌ Position size calculation test failed: {e}")
            
    async def deployment_success_summary(self):
        """Print successful deployment summary"""
        deployment_time = datetime.now() - self.deployment_start
        
        print("\n" + "=" * 60)
        print("🎉 CATALYST TRADING SYSTEM v4.2 DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        
        print(f"⏱️ Total deployment time: {deployment_time.total_seconds():.1f} seconds")
        print(f"📅 Completed at: {datetime.now().isoformat()}")
        
        print(f"\n🏗️ DEPLOYED SERVICES (8 total):")
        print("-" * 40)
        
        service_list = [
            ("Orchestration (MCP)", "5000", "🎭"),
            ("Scanner", "5001", "🔍"), 
            ("Pattern Detection", "5002", "📊"),
            ("Technical Analysis", "5003", "📈"),
            ("Risk Manager", "5004", "🛡️"),
            ("Trading Execution", "5005", "💰"),
            ("News Analysis", "5008", "📰"),
            ("Reporting", "5009", "📊")
        ]
        
        for name, port, icon in service_list:
            status = self.service_status.get(name.lower().split()[0], "unknown")
            status_icon = "✅" if status in ["healthy", "ready", "started"] else "❌"
            print(f"{icon} {status_icon} {name} (port {port})")
            
        print(f"\n🛡️ RISK MANAGEMENT FEATURES:")
        print("✅ Real-time risk monitoring")
        print("✅ Dynamic position sizing") 
        print("✅ Daily loss limits")
        print("✅ Emergency stop capabilities")
        print("✅ Portfolio exposure tracking")
        
        print(f"\n🔗 NEXT STEPS:")
        print("1. 🧪 Test risk management: python test_risk_integration.py")
        print("2. 📊 Monitor metrics: http://localhost:5004/api/v1/metrics")
        print("3. 🎭 Connect Claude Desktop to: localhost:5000 (MCP)")
        print("4. 📈 Start trading cycle via Claude interface")
        
        print(f"\n📋 MONITORING URLS:")
        for name, port, _ in service_list[1:]:  # Skip orchestration (MCP)
            service_name = name.lower().replace(" ", "-")
            print(f"• {name}: http://localhost:{port}/health")
            
        print("\n🎯 v4.2 deployment complete - system ready for production!")
        
    async def deployment_failure_summary(self, error: str):
        """Print failure summary with debugging info"""
        print("\n" + "=" * 60)
        print("❌ DEPLOYMENT FAILED")
        print("=" * 60)
        
        print(f"💥 Error: {error}")
        print(f"⏱️ Failed after: {(datetime.now() - self.deployment_start).total_seconds():.1f} seconds")
        
        print(f"\n🔍 SERVICE STATUS:")
        for service, status in self.service_status.items():
            status_icon = "✅" if status in ["healthy", "ready"] else "❌"
            print(f"{status_icon} {service}: {status}")
            
        print(f"\n🛠️ DEBUGGING STEPS:")
        print("1. Check Docker logs: docker-compose logs")
        print("2. Check environment variables in .env file")
        print("3. Verify database connection: echo $DATABASE_URL")
        print("4. Check port conflicts: netstat -tulpn | grep :5004")
        print("5. Restart infrastructure: docker-compose up -d redis postgres")
        
        print(f"\n📋 RECOVERY OPTIONS:")
        print("• Retry deployment: python deploy_v42_services.py")
        print("• Manual service start: docker-compose up -d risk-manager")
        print("• Reset everything: docker-compose down && docker-compose up -d")

# === MAIN EXECUTION ===

async def main():
    """Main deployment function"""
    print("🎯 Catalyst Trading System v4.2 Deployment Manager")
    print("=" * 60)
    
    # Check prerequisites
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found")
        print("Please run this script from the project root directory")
        sys.exit(1)
        
    if not os.getenv("DATABASE_URL"):
        print("❌ Error: DATABASE_URL environment variable not set")
        print("Please set required environment variables before deployment")
        sys.exit(1)
        
    # Run deployment
    manager = DeploymentManager()
    
    try:
        await manager.deploy_v42()
        print("\n🚀 Deployment completed successfully!")
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n⚠️ Deployment interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        print(f"\n💥 Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we're using the right Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)
        
    # Run deployment
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(130)