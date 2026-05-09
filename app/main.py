import asyncio
import logging
from app.bot.config import dp, bot
from app.bot.handlers import router
from app.db.database import init_db

logging.basicConfig(level=logging.INFO)

async def main():
    # Initialize Database
    await init_db()

    # Include routers
    dp.include_router(router)

    # Start Trading Engine in background
    from app.core.engine import engine
    asyncio.create_task(engine.start())

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
