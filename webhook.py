import os
import logging
import asyncio
import ssl
from aiohttp import web
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from config import (
    API_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_PORT,  # Changed from PORT to be more specific
    HEALTH_CHECK_PORT,  # New configuration for health check port
    SSL_CERT,
    SSL_PRIV,
    DEBUG_MODE
)

# Setup logging with more detail
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = AsyncTeleBot(API_TOKEN, parse_mode="HTML")

# Initialize aiohttp web apps - separate apps for webhook and health check
webhook_app = web.Application()
health_app = web.Application()
routes = web.RouteTableDef()
health_routes = web.RouteTableDef()

# Flag to track server health
is_server_healthy = True
last_error = None

@routes.post(f'/{API_TOKEN}')
async def handle_webhook(request):
    """Handles incoming Telegram updates."""
    global is_server_healthy, last_error
    try:
        if request.content_type != 'application/json':
            return web.Response(status=403, text="Invalid content type")
        
        data = await request.json()
        if not data:
            return web.Response(status=400, text="Empty request")

        update = types.Update.de_json(data)
        if not update:
            return web.Response(status=400, text="Invalid update format")

        await bot.process_new_updates([update])
        is_server_healthy = True
        last_error = None
        return web.Response(status=200, text="OK")

    except Exception as e:
        is_server_healthy = False
        last_error = str(e)
        logger.error(f"Error processing update: {e}", exc_info=True)
        return web.Response(status=500, text=f"Internal server error: {str(e)}")

@health_routes.get('/health')
async def health_check(request):
    """Health check endpoint"""
    try:
        # Comprehensive health check
        health_status = {
            "status": "healthy" if is_server_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "ports": {
                "webhook": WEBHOOK_PORT,
                "health": HEALTH_CHECK_PORT
            },
            "services": {
                "webhook_server": "running",
                "health_check": "running"
            }
        }

        # Check if bot can communicate with Telegram
        try:
            me = await bot.get_me()
            health_status["bot_info"] = {
                "id": me.id,
                "username": me.username,
                "webhook_url": WEBHOOK_URL
            }
        except Exception as bot_error:
            health_status["status"] = "unhealthy"
            health_status["bot_info"] = {"error": str(bot_error)}

        # Check webhook info
        try:
            webhook_info = await bot.get_webhook_info()
            health_status["webhook_info"] = {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count
            }
        except Exception as webhook_error:
            health_status["status"] = "unhealthy"
            health_status["webhook_info"] = {"error": str(webhook_error)}

        # Add error information if exists
        if last_error:
            health_status["last_error"] = last_error

        status_code = 200 if health_status["status"] == "healthy" else 503
        return web.json_response(health_status, status=status_code)

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return web.json_response({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, status=503)

async def start_servers():
    """Starts both webhook and health check servers."""
    try:
        # Setup webhook
        if not await setup_webhook():
            logger.error("Failed to setup webhook, exiting...")
            return

        # Add routes to apps
        webhook_app.add_routes(routes)
        health_app.add_routes(health_routes)

        # Setup SSL context if certificates are provided
        ssl_context = None
        if SSL_CERT and SSL_PRIV and os.path.exists(SSL_CERT) and os.path.exists(SSL_PRIV):
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(SSL_CERT, SSL_PRIV)

        # Start webhook server
        webhook_runner = web.AppRunner(webhook_app)
        await webhook_runner.setup()
        webhook_site = web.TCPSite(
            webhook_runner,
            '0.0.0.0',
            WEBHOOK_PORT,
            ssl_context=ssl_context
        )
        
        # Start health check server (no SSL needed for internal health checks)
        health_runner = web.AppRunner(health_app)
        await health_runner.setup()
        health_site = web.TCPSite(
            health_runner,
            '0.0.0.0',
            HEALTH_CHECK_PORT
        )
        
        # Start both servers
        await webhook_site.start()
        await health_site.start()
        
        logger.info(f"Webhook server started on port {WEBHOOK_PORT}")
        logger.info(f"Health check server started on port {HEALTH_CHECK_PORT}")

        # Keep the servers running
        while True:
            await asyncio.sleep(60)  # Check every minute
            if not is_server_healthy:
                logger.warning("Server health check failed, attempting recovery...")
                await recovery_procedure()

    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
    finally:
        await cleanup()

async def recovery_procedure():
    """Attempts to recover from unhealthy state."""
    try:
        # Reset webhook
        await bot.delete_webhook()
        await setup_webhook()
        
        # Reset health status
        global is_server_healthy
        is_server_healthy = True
        
        logger.info("Recovery procedure completed successfully")
    except Exception as e:
        logger.error(f"Recovery failed: {e}", exc_info=True)

def main():
    """Main function to start the servers."""
    try:
        if os.name == 'nt':  # Windows
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()