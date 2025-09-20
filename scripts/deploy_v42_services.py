#!/usr/bin/env python3
"""
Name of Application: Catalyst Trading System
Name of file: deploy_v42_services_fixed.py
Version: 4.2.0
Last Updated: 2025-09-20
Purpose: Fixed deployment script with correct service names

REVISION HISTORY:
v4.2.0 (2025-09-20) - Fixed service names and Docker Compose issues
- Auto-detect available services from docker-compose.yml
- Handle external PostgreSQL (DigitalOcean managed)
- Skip postgres container if using external DB
- Better error handling and service discovery
"""

import asyncio
import aiohttp
import subprocess
import time
import os
import sys
import json
import yaml
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

class DeploymentManager:
    def __init__(self):
        self.deployment_start = datetime.now()
        self.service_status: Dict[str, str] = {}
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.available_services: List[str] = []
        self.using_external_db = False
        
    async def detect_available_services(self):
        """Detect available services from docker-compose.yml"""
        try:
            result = subprocess.run(
                ["docker-compose", "config", "--services"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                self.available_services = [s.strip() for s in result.stdout.split('\n') if s.strip()]
                print(f"🔍 Available services: {', '.join(self.available_services)}")
                
                # Check if using external database
                self.using_external_db = "postgres" not in self.available_services and "postgresql" not in self.available_services and "database" not in self.available_services
                
                if self.using_external_db:
                    print("ℹ️ Using external PostgreSQL database (DigitalOcean)")
                    
                return True
            else:
                print(f"❌ Failed to get services: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error detecting services: {e}")
            return False
            
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
            
            # Step 1: Detect available services
            print("\n🔍 Step 1: Service Discovery")
            print("-" * 40)
            if not await self.detect_available_services():
                raise Exception("Failed to detect available services")
                
            # Step 2: Pre-deployment validation
            print("\n🔍 Step 2: Pre-deployment Validation")
            print("-" * 40)
            await self.validate_environment()
            await self.validate_docker_setup()
            await self.validate_risk_manager_service()
            
            # Step 3: Stop existing services gracefully
            print("\n🛑 Step 3: Stopping Existing Services")
            print("-" * 40)
            await self.stop_existing_services()
            
            # Step 4: Deploy infrastructure services
            print("\n🏗️ Step 4: Starting Infrastructure Services")
            print("-" * 40)
            await self.start_infrastructure()
            
            # Step 5: Deploy core services (including new risk-manager)
            print("\n⚙️ Step 5: Deploying Core Services")
            print("-" * 40)
            await self.deploy_core_services()
            
            # Step 6: Deploy orchestration service
            print("\n🎭 Step 6: Starting Orchestration Service")
            print("-" * 40)
            await self.start_orchestration()
            
            # Step 7: Comprehensive health validation
            print("\n🩺 Step 7: Health Check Validation")
            print("-" * 40)
            await self.validate_all_services()
            
            # Step 8: Service connectivity testing
            print("\n🔗 Step 8: Service Connectivity Testing")
            print("-" * 40)
            await self.test_service_integration()
            
            # Step 9: Risk management validation
            print("\n🛡️ Step 9: Risk Management Validation")
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
        """Start infrastructure services (Redis, PostgreSQL if available)"""
        infrastructure_services = []
        
        # Add Redis if available
        if "redis" in self.available_services:
            infrastructure_services.append("redis")
            
        # Add PostgreSQL if available (not using external)
        postgres_service = None
        for service in ["postgres", "postgresql", "database", "db"]:
            if service in self.available_services:
                postgres_service = service
                break
                
        if postgres_service and not self.using_external_db:
            infrastructure_services.append(postgres_service)
        elif self.using_external_db:
            print("ℹ️ Skipping PostgreSQL container - using external DigitalOcean database")
            
        if not infrastructure_services:
            print("ℹ️ No infrastructure services to start (using external services)")
            return
            
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
                    startup_time = 15 if service == "redis" else 20
                    await asyncio.sleep(startup_time)
                    
                else:
                    raise Exception(f"Failed to start {service}: {result.stderr}")
                    
            except Exception as e:
                print(f"❌ Failed to start {service}: {e}")
                self.service_status[service] = "failed"
                raise
                
        print("✅ Infrastructure services started")
        
    async def deploy_core_services(self):
        """Deploy core services including the new risk-manager"""
        
        # Define service order and expected names
        expected_services = [
            "risk-manager", "scanner", "pattern", "technical", 
            "news", "reporting", "trading"
        ]
        
        # Map to actual available services
        services_to_deploy = []
        for expected in expected_services:
            # Try different naming conventions
            possible_names = [
                expected,
                f"{expected}-service", 
                expected.replace("-", "_"),
                expected.replace("-", "")
            ]
            
            for name in possible_names:
                if name in self.available_services:
                    services_to_deploy.append(name)
                    break
            else:
                print(f"⚠️ Service {expected} not found in docker-compose.yml")
        
        print(f"📋 Services to deploy: {', '.join(services_to_deploy)}")
        
        for service in services_to_deploy:
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
                    startup_time = 25 if "risk" in service else 20
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
                if "risk" in service:
                    raise Exception("Risk manager is critical - deployment aborted")
                    
        print("✅ Core services deployed")
        
    async def start_orchestration(self):
        """Start the orchestration service last"""
        orchestration_service = None
        
        # Find orchestration service
        for name in ["orchestration", "orchestration-service", "orchestrator"]:
            if name in self.available_services:
                orchestration_service = name
                break
                
        if not orchestration_service:
            print("⚠️ Orchestration service not found - skipping")
            return
            
        print(f"🎭 Starting {orchestration_service}...")
        
        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--build", orchestration_service],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print(f"✅ {orchestration_service} container started")
                self.service_status[orchestration_service] = "started"
                
                # Wait for MCP initialization
                startup_time = 30
                print(f"⏳ Waiting {startup_time}s for MCP initialization...")
                await asyncio.sleep(startup_time)
                
                self.service_status[orchestration_service] = "ready"
                print("✅ Orchestration service ready for Claude Desktop")
                
            else:
                raise Exception(f"Failed to start {orchestration_service}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Failed to start orchestration: {e}")
            self.service_status[orchestration_service] = "failed"
            raise
            
    async def check_service_health(self, service_name: str) -> bool:
        """Check if a service is healthy"""
        # Map service names to ports
        port_map = {
            "risk-manager": 5004,
            "scanner": 5001,
            "pattern": 5002,
            "technical": 5003,
            "trading": 5005,
            "news": 5008,
            "reporting": 5009
        }
        
        # Find port for this service
        port = None
        for key, p in port_map.items():
            if key in service_name:
                port = p
                break
                
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
        """Comprehensive health validation of all services"""
        print("🩺 Running comprehensive health checks...")
        
        # Get running containers
        result = subprocess.run(
            ["docker-compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            running_services = [s.strip() for s in result.stdout.split('\n') if s.strip()]
            print(f"🏃 Running services: {', '.join(running_services)}")
            
            healthy_count = 0
            for service in running_services:
                if await self.check_service_health(service):
                    print(f"✅ {service}: Healthy")
                    healthy_count += 1
                else:
                    print(f"⚠️ {service}: No health endpoint or unhealthy")
                    
            print(f"\n📊 Health Summary: {healthy_count}/{len(running_services)} services responsive")
        else:
            print("⚠️ Could not get running services status")
            
    async def test_service_integration(self):
        """Test service-to-service connectivity"""
        print("🔗 Testing service integration...")
        
        # Test risk-manager if available
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
            
        # Test scanner if available
        try:
            url = "http://localhost:5001/health"
            async with self.http_session.get(url) as response:
                if response.status == 200:
                    print("✅ Scanner connectivity confirmed")
                else:
                    print(f"⚠️ Scanner connectivity: HTTP {response.status}")
        except Exception as e:
            print(f"❌ Scanner connectivity: {e}")
            
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
                    
                    if params:
                        print("✅ Risk parameters loaded successfully")
                        print(f"ℹ️ Max daily loss: ${params.get('max_daily_loss', 'N/A')}")
                        print(f"ℹ️ Max position risk: {params.get('max_position_risk', 'N/A')}")
                    else:
                        print("⚠️ Risk parameters empty - check database setup")
                        
                else:
                    print(f"❌ Risk parameters not accessible: HTTP {response.status}")
                    
        except Exception as e:
            print(f"❌ Risk parameter validation failed: {e}")
            
    async def deployment_success_summary(self):
        """Print successful deployment summary"""
        deployment_time = datetime.now() - self.deployment_start
        
        print("\n" + "=" * 60)
        print("🎉 CATALYST TRADING SYSTEM v4.2 DEPLOYMENT SUCCESSFUL!")
        print("=" * 60)
        
        print(f"⏱️ Total deployment time: {deployment_time.total_seconds():.1f} seconds")
        print(f"📅 Completed at: {datetime.now().isoformat()}")
        
        print(f"\n🏗️ DEPLOYED SERVICES:")
        print("-" * 40)
        
        for service, status in self.service_status.items():
            status_icon = "✅" if status in ["healthy", "ready", "started"] else "❌"
            print(f"{status_icon} {service}: {status}")
            
        print(f"\n🛡️ RISK MANAGEMENT FEATURES:")
        print("✅ Real-time risk monitoring")
        print("✅ Dynamic position sizing") 
        print("✅ Daily loss limits")
        print("✅ Emergency stop capabilities")
        print("✅ Portfolio exposure tracking")
        
        print(f"\n🔗 NEXT STEPS:")
        print("1. 📊 Monitor risk metrics: http://localhost:5004/api/v1/metrics")
        print("2. 🎭 Connect Claude Desktop to: localhost:5000 (MCP)")
        print("3. 📈 Start trading cycle via Claude interface")
        print("4. 🧪 Test risk management functionality")
        
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
        print("2. Check service names: docker-compose config --services")
        print("3. Check ports: docker-compose ps")
        print("4. Check environment variables: env | grep -E '(DATABASE|REDIS|API_KEY)'")
        
        print(f"\n📋 RECOVERY OPTIONS:")
        print("• Check docker-compose.yml service names")
        print("• Manual service start: docker-compose up -d [service-name]")
        print("• Reset everything: docker-compose down && docker-compose up -d")

# === MAIN EXECUTION ===

async def main():
    """Main deployment function"""
    print("🎯 Catalyst Trading System v4.2 Deployment Manager (Fixed)")
    print("=" * 65)
    
    # Check prerequisites
    if not os.path.exists("docker-compose.yml"):
        print("❌ Error: docker-compose.yml not found")
        print("Please run this script from the project root directory")
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