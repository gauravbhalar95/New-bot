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
    PORT,
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

# Initialize aiohttp web app
app = web.Application()
routes = web.RouteTableDef()

@routes.post(f'/{API_TOKEN}')
async def handle_webhook(request):
    """Handles incoming Telegram updates."""
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
        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return web.Response(status=500, text=f"Internal server error: {str(e)}")

@routes.get('/')
async def home(request):
    """Root endpoint"""
    return web.Response(text="Telegram bot webhook server is running!")

@routes.get('/health')
async def health_check(request):
    """Health check endpoint"""
    try:
        # Check if bot can communicate with Telegram
        me = await bot.get_me()
        return web.json_response({
            "status": "healthy",
            "bot_info": {
                "id": me.id,
                "username": me.username,
                "webhook_url": WEBHOOK_URL
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return web.json_response({
            "status": "unhealthy",
            "error": str(e)
        }, status=500)

async def setup_webhook():
    """Sets up the webhook with proper error handling and validation."""
    try:
        # Remove any existing webhook first
        await bot.delete_webhook()
        logger.info("Existing webhook removed successfully")

        # Validate webhook URL
        if not WEBHOOK_URL or not WEBHOOK_URL.startswith(('http://', 'https://')):
            raise ValueError("Invalid WEBHOOK_URL configuration")

        webhook_url = f"{WEBHOOK_URL}/{API_TOKEN}"
        
        # Set up webhook with SSL if certificates are provided
        if SSL_CERT and SSL_PRIV and os.path.exists(SSL_CERT) and os.path.exists(SSL_PRIV):
            with open(SSL_CERT, 'rb') as cert:
                success = await bot.set_webhook(
                    url=webhook_url,
                    certificate=cert,
                    max_connections=100,
                    allowed_updates=['message', 'callback_query']
                )
        else:
            success = await bot.set_webhook(
                url=webhook_url,
                max_connections=100,
                allowed_updates=['message', 'callback_query']
            )

        if success:
            webhook_info = await bot.get_webhook_info()
            logger.info(f"Webhook set successfully. Info: {webhook_info}")
            return True
        else:
            logger.error("Failed to set webhook")
            return False

    except Exception as e:
        logger.error(f"Error setting up webhook: {e}", exc_info=True)
        return False

async def cleanup():
    """Cleanup function to remove webhook on shutdown."""
    try:
        await bot.delete_webhook()
        logger.info("Webhook removed during cleanup")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)

async def start_webhook_server():
    """Starts the webhook server with proper initialization and cleanup."""
    try:
        # Setup webhook
        if not await setup_webhook():
            logger.error("Failed to setup webhook, exiting...")
            return

        # Add routes to app
        app.add_routes(routes)

        # Setup SSL context if certificates are provided
        ssl_context = None
        if SSL_CERT and SSL_PRIV and os.path.exists(SSL_CERT) and os.path.exists(SSL_PRIV):
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(SSL_CERT, SSL_PRIV)

        # Start web server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            '0.0.0.0',
            PORT,
            ssl_context=ssl_context
        )
        
        await site.start()
        logger.info(f"Webhook server started on port {PORT}")

        # Keep the server running
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour

    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
    finally:
        await cleanup()

def main():
    """Main function to start the webhook server."""
    try:
        if os.name == 'nt':  # Windows
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(start_webhook_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()