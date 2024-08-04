import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

logging.basicConfig(level=logging.INFO)
TOKEN = "6713953154:AAECYRfZxOQYAbMJOsrKsApbulPDKTc3hI4"
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hello!")
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())