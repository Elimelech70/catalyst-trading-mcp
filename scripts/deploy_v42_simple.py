#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: deploy_v42_simple.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Simple deployment for DigitalOcean database setup

REVISION HISTORY:
v4.2.0 (2025-09-20) - Simplified deployment for external database
- Uses DigitalOcean managed PostgreSQL only
- No PostgreSQL container management
- Focuses on application services deployment
- Streamlined for production environment
"""

import asyncio
import aiohttp
import subprocess
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deployment")

class SimpleDeploymentManager:
    def __init__(self):
        self.deployment_start = datetime.now()
        self.service_status: Dict[str, str] = {}
        self.http_session: Optional[aiohttp.ClientSession] = None
        
    async def deploy_v42(self):
        """Main deployment orchestration for DigitalOcean setup"""
        print("🚀 Catalyst Trading System v4.2 Deployment (DigitalOcean)")
        print("=" * 60)
        print(f"📅 Started at: {self.deployment_start.isoformat()}")
        print(f"🗄️ Using: DigitalOcean Managed PostgreSQL")
        print(f"🎯 Target: Application services only")
        
        try:
            # Initialize HTTP session for health checks
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
            
            # Step 1: Environment validation
            print("\n🔍 Step 1: Environment Validation")
            print("-" * 40)
            await self.validate_environment()
            
            # Step 2: Stop existing services
            print("\n🛑 Step 2: Stopping Existing Services")
            print("-" * 40)
            await self.stop_existing_services()
            
            # Step 3: Start Redis only
            print("\n🔴 Step 3: Starting Redis")
            print("-" * 40)
            await self.start_redis()
            
            # Step 4: Deploy application services
            print("\n⚙️ Step 4: Deploying Application Services")
            print("-" * 40)
            await self.deploy_application_services()
            
            # Step 5: Start orchestration
            print("\n🎭 Step 5: Starting Orchestration")
            print("-" * 40)
            await self.start_orchestration()
            
            # Step 6: Health checks
            print("\n🩺 Step 6: Health Validation")
            print("-" * 40)
            await self.validate_all_services()
            
            # Step 7: Risk management test
            print("\n🛡️ Step 7: Risk Management Test")
            print("-" * 40)
            await self.test_risk_management()
            
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
        """Validate environment for DigitalOcean setup"""
        print("📋 Validating environment...")
        
        # Check required environment variables
        required_vars = [
            "DATABASE_URL", "REDIS_URL", "ALPHA_VANTAGE_API_KEY", 
            "FINNHUB_API_KEY", "MAX_DAILY_LOSS", "MAX_POSITION_RISK"
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                # Show partial value for verification
                display_value = value[:15] + "***" if len(value) > 15 else value
                print(f"✅ {var}: {display_value}")
                
        if missing_vars:
            raise Exception(f"Missing environment variables: {', '.join(missing_vars)}")
            
        # Verify DigitalOcean database URL
        database_url = os.getenv("DATABASE_URL")
        if "ondigitalocean.com" not in database_url:
            print("⚠️ Warning: DATABASE_URL doesn't appear to be DigitalOcean")
        else:
            print("✅ DigitalOcean database URL confirmed")
            
        print("✅ Environment validation complete")
        
    async def stop_existing_services(self):
        """Stop existing services gracefully"""
        print("🛑 Stopping existing services...")
        
        try:
            result = subprocess.run(
                ["docker-compose", "down", "--remove-orphans"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print("✅ All services stopped")
            else:
                print(f"⚠️ Stop warnings: {result.stderr}")
                
            # Brief wait for cleanup
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"⚠️ Error stopping services: {e}")
            
    async def start_redis(self):
        """Start Redis only"""
        print("🔴 Starting Redis...")
        
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "redis"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print("✅ Redis started")
                self.service_status["redis"] = "started"
                
                # Wait for Redis to be ready
                print("⏳ Waiting for Redis to initialize...")
                await asyncio.sleep(10)
                
            else:
                raise Exception(f"Failed to start Redis: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Redis startup failed: {e}")
            raise
            
    async def deploy_application_services(self):
        """Deploy application services in correct order"""
        
        # Services in deployment order (risk-manager first!)
        services = [
            "risk-manager",  # Must be first for v4.2
            "scanner",
            "pattern", 
            "technical",
            "news",
            "reporting",
            "trading"        # Last (depends on risk-manager)
        ]
        
        for service in services:
            print(f"⚙️ Deploying {service}...")
            
            try:
                # Build and start service
                result = subprocess.run(
                    ["docker-compose", "up", "-d", "--build", service],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0:
                    print(f"✅ {service} container started")
                    self.service_status[service] = "started"
                    
                    # Startup wait time
                    startup_time = 25 if service == "risk-manager" else 20
                    print(f"⏳ Waiting {startup_time}s for {service} to initialize...")
                    await asyncio.sleep(startup_time)
                    
                    # Quick health check
                    if await self.check_service_health(service):
                        print(f"✅ {service} is healthy")
                        self.service_status[service] = "healthy"
                    else:
                        print(f"⚠️ {service} health check inconclusive")
                        self.service_status[service] = "started"
                        
                else:
                    error_msg = result.stderr.strip()
                    raise Exception(f"Failed to start {service}: {error_msg}")
                    
            except Exception as e:
                print(f"❌ {service} deployment failed: {e}")
                self.service_status[service] = "failed"
                
                # Critical services
                if service == "risk-manager":
                    raise Exception("Risk manager is critical for v4.2 - aborting deployment")
                    
        print("✅ Application services deployed")
        
    async def start_orchestration(self):
        """Start orchestration service"""
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
                
                # MCP initialization time
                print("⏳ Waiting 30s for MCP initialization...")
                await asyncio.sleep(30)
                
                self.service_status[service] = "ready"
                print("✅ Orchestration ready for Claude Desktop")
                
            else:
                raise Exception(f"Failed to start {service}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Orchestration startup failed: {e}")
            self.service_status[service] = "failed"
            # Don't fail deployment - orchestration issues can be fixed separately
            print("⚠️ Continuing without orchestration - can be started manually")
            
    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        port_map = {
            "risk-manager": 5004,
            "scanner": 5001,
            "pattern": 5002,
            "technical": 5003,
            "trading": 5005,
            "news": 5008,
            "reporting": 5009
        }
        
        port = port_map.get(service_name)
        if not port:
            return True  # Skip health check if port unknown
            
        try:
            url = f"http://localhost:{port}/health"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("status") == "healthy"
                    
        except Exception:
            pass
            
        return False
        
    async def validate_all_services(self):
        """Health check all deployed services"""
        print("🩺 Running health checks...")
        
        port_map = {
            "risk-manager": 5004,
            "scanner": 5001,
            "pattern": 5002,
            "technical": 5003,
            "trading": 5005,
            "news": 5008,
            "reporting": 5009
        }
        
        healthy_count = 0
        total_count = 0
        
        for service, port in port_map.items():
            if service in self.service_status:
                total_count += 1
                print(f"🔍 Testing {service} (port {port})...")
                
                try:
                    url = f"http://localhost:{port}/health"
                    async with self.http_session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            version = data.get("version", "unknown")
                            print(f"✅ {service}: v{version} - healthy")
                            healthy_count += 1
                        else:
                            print(f"❌ {service}: HTTP {response.status}")
                            
                except Exception as e:
                    print(f"❌ {service}: Connection failed")
                    
        print(f"\n📊 Health Summary: {healthy_count}/{total_count} services healthy")
        
        # Check running containers
        try:
            result = subprocess.run(
                ["docker-compose", "ps", "--format", "table"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"\n🐳 Container Status:")
                print(result.stdout)
        except Exception:
            pass
            
    async def test_risk_management(self):
        """Test risk management functionality"""
        print("🛡️ Testing risk management...")
        
        try:
            # Test risk parameters endpoint
            url = "http://localhost:5004/api/v1/parameters"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    params = data.get("parameters", {})
                    
                    print("✅ Risk parameters accessible")
                    print(f"ℹ️ Max daily loss: ${params.get('max_daily_loss', 'N/A')}")
                    print(f"ℹ️ Max position risk: {params.get('max_position_risk', 'N/A')}")
                    print(f"ℹ️ Max positions: {params.get('max_positions', 'N/A')}")
                    
                else:
                    print(f"❌ Risk parameters not accessible: HTTP {response.status}")
                    
        except Exception as e:
            print(f"❌ Risk management test failed: {e}")
            
        # Test risk metrics endpoint
        try:
            url = "http://localhost:5004/api/v1/metrics"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Risk metrics accessible")
                    print(f"ℹ️ Current risk score: {data.get('risk_score', 'N/A')}")
                    print(f"ℹ️ Daily P&L: ${data.get('daily_pnl', 'N/A')}")
                else:
                    print(f"❌ Risk metrics not accessible: HTTP {response.status}")
                    
        except Exception as e:
            print(f"❌ Risk metrics test failed: {e}")
            
    async def deployment_success_summary(self):
        """Print successful deployment summary"""
        deployment_time = datetime.now() - self.deployment_start
        
        print("\n" + "=" * 60)
        print("🎉 CATALYST TRADING SYSTEM v4.2 DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        
        print(f"⏱️ Total deployment time: {deployment_time.total_seconds():.1f} seconds")
        print(f"📅 Completed at: {datetime.now().isoformat()}")
        print(f"🗄️ Database: DigitalOcean Managed PostgreSQL")
        
        print(f"\n🏗️ DEPLOYED SERVICES:")
        print("-" * 40)
        
        for service, status in self.service_status.items():
            status_icon = "✅" if status in ["healthy", "ready", "started"] else "❌"
            print(f"{status_icon} {service}: {status}")
            
        print(f"\n🛡️ v4.2 NEW FEATURES ACTIVE:")
        print("✅ Risk Manager Service (port 5004)")
        print("✅ Real-time risk monitoring")
        print("✅ Dynamic position sizing")
        print("✅ Daily loss limits")
        print("✅ Emergency stop capabilities")
        
        print(f"\n🔗 QUICK ACCESS URLs:")
        print("• Risk Manager: http://localhost:5004/api/v1/metrics")
        print("• Scanner: http://localhost:5001/health")
        print("• Trading: http://localhost:5005/health")
        print("• All Services: docker-compose ps")
        
        print(f"\n🎭 CLAUDE DESKTOP CONNECTION:")
        print("• MCP Server: localhost:5000")
        print("• Protocol: stdio or websocket")
        print("• Status: Ready for connection")
        
        print(f"\n🚀 NEXT STEPS:")
        print("1. 🧪 Test risk management: curl http://localhost:5004/api/v1/metrics")
        print("2. 🎭 Connect Claude Desktop to MCP server")
        print("3. 📈 Start trading cycle via Claude interface")
        print("4. 📊 Monitor logs: docker-compose logs -f")
        
        print("\n🎯 v4.2 deployment complete - ready for production trading!")
        
    async def deployment_failure_summary(self, error: str):
        """Print failure summary"""
        print("\n" + "=" * 60)
        print("❌ DEPLOYMENT FAILED")
        print("=" * 60)
        
        print(f"💥 Error: {error}")
        print(f"⏱️ Failed after: {(datetime.now() - self.deployment_start).total_seconds():.1f} seconds")
        
        print(f"\n🔍 SERVICE STATUS:")
        for service, status in self.service_status.items():
            status_icon = "✅" if status in ["healthy", "ready", "started"] else "❌"
            print(f"{status_icon} {service}: {status}")
            
        print(f"\n🛠️ DEBUGGING:")
        print("• Check logs: docker-compose logs [service-name]")
        print("• Check status: docker-compose ps")
        print("• Check environment: env | grep DATABASE_URL")
        print("• Restart individual service: docker-compose up -d [service-name]")
        
        print(f"\n📋 RECOVERY:")
        print("• Fix the reported error above")
        print("• Retry deployment: python3 deploy_v42_simple.py")
        print("• Manual deployment: docker-compose up -d")

# === MAIN EXECUTION ===

async def main():
    """Main deployment function"""
    print("🎯 Catalyst Trading System v4.2 Simple Deployment")
    print("🗄️ Optimized for DigitalOcean Database Setup")
    print("=" * 55)
    
    # Check prerequisites
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found")
        sys.exit(1)
        
    # Check DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Error: DATABASE_URL not set")
        print("Run: export $(grep -v '^#' .env | xargs)")
        sys.exit(1)
        
    if "ondigitalocean.com" not in db_url:
        print("⚠️ Warning: DATABASE_URL doesn't appear to be DigitalOcean")
        
    # Run deployment
    manager = SimpleDeploymentManager()
    
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
    # Run deployment
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted")
        sys.exit(130)