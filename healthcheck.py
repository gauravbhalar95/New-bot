#!/usr/bin/env python3

import os
import sys
import json
import logging
import requests
import subprocess
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/healthcheck.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotHealthCheck:
    def __init__(self):
        self.config_dir = Path('/app/config')
        self.downloads_dir = Path('/app/downloads')
        self.log_dir = Path('/var/log/supervisor')
        self.status = {
            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            "status": "unknown",
            "checks": {},
            "errors": []
        }

    def check_directories(self):
        """Check if required directories exist and are accessible"""
        try:
            directories = {
                "config": self.config_dir,
                "logs": self.log_dir,
                "downloads": self.downloads_dir
            }
            
            for name, path in directories.items():
                if not path.exists():
                    raise Exception(f"{name} directory not found: {path}")
                if not os.access(path, os.R_OK | os.W_OK):
                    raise Exception(f"Insufficient permissions for {name} directory: {path}")
                
            self.status["checks"]["directories"] = "healthy"
            return True
        except Exception as e:
            self.status["checks"]["directories"] = "unhealthy"
            self.status["errors"].append(f"Directory check failed: {str(e)}")
            return False

    def check_telegram_token(self):
        """Verify Telegram bot token is valid"""
        try:
            token = os.getenv('BOT_TOKEN')
            if not token:
                raise Exception("BOT_TOKEN environment variable not set")

            response = requests.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=10
            )
            
            if not response.ok:
                raise Exception(f"Telegram API check failed: {response.text}")

            self.status["checks"]["telegram_api"] = "healthy"
            return True
        except Exception as e:
            self.status["checks"]["telegram_api"] = "unhealthy"
            self.status["errors"].append(f"Telegram API check failed: {str(e)}")
            return False

    def check_mega_config(self):
        """Verify MEGA.nz configuration and connectivity"""
        try:
            # Check environment variables
            required_vars = ['MEGA_EMAIL', 'MEGA_PASSWORD']
            missing = [var for var in required_vars if not os.getenv(var)]
            if missing:
                raise Exception(f"Missing MEGA environment variables: {', '.join(missing)}")

            # Check MEGA session
            result = subprocess.run(
                ['mega-whoami'],
                capture_output=True,
                text=True
            )

            if "Not logged in" in result.stdout:
                # Try to login
                login_result = subprocess.run(
                    ['mega-login', os.getenv('MEGA_EMAIL'), os.getenv('MEGA_PASSWORD')],
                    capture_output=True,
                    text=True
                )
                if login_result.returncode != 0:
                    raise Exception(f"MEGA login failed: {login_result.stderr}")

            # Verify storage space
            space_result = subprocess.run(
                ['mega-df'],
                capture_output=True,
                text=True
            )
            if space_result.returncode != 0:
                raise Exception("Failed to check MEGA storage space")

            self.status["checks"]["mega_config"] = "healthy"
            return True
        except Exception as e:
            self.status["checks"]["mega_config"] = "unhealthy"
            self.status["errors"].append(f"MEGA configuration check failed: {str(e)}")
            return False

    def check_process_status(self):
        """Check if bot process is running via supervisord"""
        try:
            result = subprocess.run(
                ['supervisorctl', 'status', 'telegram_bot'],
                capture_output=True,
                text=True
            )
            
            if "RUNNING" not in result.stdout:
                raise Exception("Bot process is not running")

            # Check log file for recent activity
            log_file = self.log_dir / 'telegram_bot.stdout.log'
            if not log_file.exists():
                raise Exception("Bot log file not found")

            # Check if log was modified in last 5 minutes
            if (datetime.now().timestamp() - log_file.stat().st_mtime) > 300:
                raise Exception("No recent bot activity detected")

            self.status["checks"]["process"] = "healthy"
            return True
        except Exception as e:
            self.status["checks"]["process"] = "unhealthy"
            self.status["errors"].append(f"Process check failed: {str(e)}")
            return False

    def check_system_resources(self):
        """Check system resources (CPU, memory, disk)"""
        try:
            # Check disk space
            df = subprocess.run(['df', '-h', '/app'], capture_output=True, text=True)
            usage = int(df.stdout.split('\n')[1].split()[4].rstrip('%'))
            if usage > 90:
                raise Exception(f"Disk usage critical: {usage}%")

            # Check memory
            with open('/proc/meminfo', 'r') as f:
                mem_info = f.read()
            
            total = int([l for l in mem_info.split('\n') if 'MemTotal' in l][0].split()[1])
            available = int([l for l in mem_info.split('\n') if 'MemAvailable' in l][0].split()[1])
            mem_usage = (total - available) / total * 100
            
            if mem_usage > 90:
                raise Exception(f"Memory usage critical: {mem_usage:.1f}%")

            # Check CPU load
            with open('/proc/loadavg', 'r') as f:
                load = float(f.read().split()[0])
                if load > os.cpu_count() * 2:
                    raise Exception(f"CPU load critical: {load}")

            self.status["checks"]["resources"] = "healthy"
            return True
        except Exception as e:
            self.status["checks"]["resources"] = "unhealthy"
            self.status["errors"].append(f"Resource check failed: {str(e)}")
            return False

    def run_checks(self):
        """Run all health checks"""
        try:
            checks = [
                self.check_directories(),
                self.check_telegram_token(),
                self.check_mega_config(),
                self.check_process_status(),
                self.check_system_resources()
            ]
            
            # Overall status is healthy only if all checks pass
            self.status["status"] = "healthy" if all(checks) else "unhealthy"
            
            # Save status to file
            status_file = self.config_dir / 'healthcheck_status.json'
            with open(status_file, 'w') as f:
                json.dump(self.status, f, indent=2)

            # Log status
            logger.info(f"Health check completed. Status: {self.status['status']}")
            if self.status["errors"]:
                logger.error("Errors found:\n" + "\n".join(self.status["errors"]))

            # Exit with appropriate code
            sys.exit(0 if self.status["status"] == "healthy" else 1)

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    try:
        logger.info("Starting health check...")
        logger.info(f"Check initiated by: {os.getenv('USER', 'unknown')}")
        logger.info(f"Current UTC time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        
        health_check = BotHealthCheck()
        health_check.run_checks()
    except KeyboardInterrupt:
        logger.info("Health check interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()