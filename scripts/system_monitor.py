"""
Name of Application: Catalyst Trading System
Name of file: system_monitor.py
Version: 5.1.0
Last Updated: 2025-09-20
Purpose: System health monitoring and alerting
"""

import asyncio
import aiohttp
import logging
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText 
from typing import Dict, List
import os
import psutil
import docker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("system_monitor")

class SystemMonitor:
    def __init__(self):
        self.services = {
            "orchestration": "http://localhost:5000/health",
            "scanner": "http://localhost:5001/health",
            "pattern": "http://localhost:5002/health",
            "technical": "http://localhost:5003/health",
            "trading": "http://localhost:5005/health",
            "news": "http://localhost:5008/health",
            "reporting": "http://localhost:5009/health"
        }

        self.alert_cooldown = {}  # Prevent spam alerts
        self.docker_client = docker.from_env()

    async def check_service_health(self, service: str, url: str) -> Dict:
        """Check individual service health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "service": service,
                            "status": "healthy",
                            "response_time": response.headers.get("X-Response-Time", "unknown"),
                            "details": data
                        }
                    else:
                        return {
                            "service": service,
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}"
                        }
        except Exception as e:
            return {
                "service": service,
                "status": "failed",
                "error": str(e)
            }

    async def check_system_resources(self) -> Dict:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2)
            }
        except Exception as e:
            logger.error(f"Failed to get system resources: {e}")
            return {}

    async def check_docker_containers(self) -> Dict:
        """Check Docker container status"""
        try:
            containers = {}
            for container in self.docker_client.containers.list(all=True):
                name = container.name
                if 'catalyst' in name.lower():
                    containers[name] = {
                        "status": container.status,
                        "health": getattr(container.attrs.get('State', {}), 'Health', {}).get('Status', 'unknown'),
                        "restart_count": container.attrs.get('RestartCount', 0)
                    }
            return containers
        except Exception as e:
            logger.error(f"Failed to check Docker containers: {e}")
            return {}

    async def send_alert(self, subject: str, message: str):
        """Send alert via email"""
        alert_email = os.getenv('ALERT_EMAIL')
        if not alert_email:
            logger.warning("No alert email configured")
            return

        # Check cooldown
        now = datetime.now()
        if subject in self.alert_cooldown:
            if now - self.alert_cooldown[subject] < timedelta(minutes=15):
                logger.info(f"Alert cooldown active for: {subject}")
                return

        try:
            msg = MIMEText (message)
            msg['Subject'] = f"[CATALYST ALERT] {subject}"
            msg['From'] = os.getenv('SMTP_FROM', 'catalyst@localhost')
            msg['To'] = alert_email

            # Send email (configure SMTP settings in environment)
            smtp_server = os.getenv('SMTP_SERVER', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if os.getenv('SMTP_USERNAME'):
                    server.starttls()
                    server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
                server.send_message(msg)

            self.alert_cooldown[subject] = now
            logger.info(f"Alert sent: {subject}")

        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def auto_restart_service(self, service: str):
        """Attempt to restart a failed service"""
        try:
            container_name = f"catalyst-{service}"
            container = self.docker_client.containers.get(container_name)

            logger.warning(f"Restarting service: {service}")
            container.restart()

            # Wait a bit and check if it's healthy
            await asyncio.sleep(30)
            health_check = await self.check_service_health(
                service, 
                self.services[service]
            )

            if health_check['status'] == 'healthy':
                await self.send_alert(
                    f"Service Recovered: {service}",
                    f"Service {service} was automatically restarted and is now healthy."
                )
                return True
            else:
                await self.send_alert(
                    f"Service Restart Failed: {service}",
                    f"Attempted to restart {service} but it's still unhealthy: {health_check.get('error', 'Unknown error')}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to restart service {service}: {e}")
            await self.send_alert(
                f"Auto-Restart Failed: {service}",
                f"Failed to restart service {service}: {str(e)}"
            )
            return False

    async def run_health_check(self):
        """Run complete health check"""
        logger.info("Running system health check...")

        # Check all services
        service_results = []
        for service, url in self.services.items():
            result = await self.check_service_health(service, url)
            service_results.append(result)

            # Auto-restart failed services (except during market hours for trading service)
            if result['status'] in ['failed', 'unhealthy']:
                if service == 'trading':
                    # Only auto-restart trading service outside market hours
                    current_hour = datetime.now().hour
                    if current_hour < 9 or current_hour >= 16:  # Before 9 AM or after 4 PM
                        await self.auto_restart_service(service)
                    else:
                        await self.send_alert(
                            f"Trading Service Issue",
                            f"Trading service is {result['status']} during market hours. Manual intervention required."
                        )
                else:
                    await self.auto_restart_service(service)

        # Check system resources
        system_resources = await self.check_system_resources()

        # Alert on high resource usage
        if system_resources:
            if system_resources.get('cpu_percent', 0) > 80:
                await self.send_alert(
                    "High CPU Usage",
                    f"CPU usage is {system_resources['cpu_percent']}%"
                )

            if system_resources.get('memory_percent', 0) > 85:
                await self.send_alert(
                    "High Memory Usage", 
                    f"Memory usage is {system_resources['memory_percent']}%"
                )

            if system_resources.get('disk_percent', 0) > 90:
                await self.send_alert(
                    "Low Disk Space",
                    f"Disk usage is {system_resources['disk_percent']}%"
                )

        # Check Docker containers
        containers = await self.check_docker_containers()

        # Create health report
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "services": service_results,
            "system_resources": system_resources,
            "containers": containers
        }

        # Log summary
        healthy_services = [s for s in service_results if s['status'] == 'healthy']
        logger.info(f"Health check complete: {len(healthy_services)}/{len(service_results)} services healthy")

        return health_report

    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting system monitor...")

        while True:
            try:
                await self.run_health_check()

                # Check every 2 minutes during market hours, every 5 minutes otherwise
                current_hour = datetime.now().hour
                current_day = datetime.now().weekday()  # 0=Monday, 6=Sunday

                if current_day < 5 and 9 <= current_hour < 16:  # Market hours
                    sleep_time = 120  # 2 minutes
                else:
                    sleep_time = 300  # 5 minutes

                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

if __name__ == "__main__":
    monitor = SystemMonitor()
    asyncio.run(monitor.monitor_loop())