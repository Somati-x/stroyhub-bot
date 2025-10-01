# --- Розділ 1: Імпорти ---
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
# Додаємо імпорт Command з фільтрів aiogram
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- Розділ 2: Конфігурація та ініціалізація ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_WEBHOOK_URL = "https://stroyhub-bot.onrender.com"
WEBHOOK_PATH = "/webhook"

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Розділ 3: Обробники повідомлень (хендлери) ---
# Оновлюємо синтаксис декоратора для aiogram 3.x
@dp.message(Command(commands=["start", "newpost"]))
async def send_welcome(message: types.Message):
    """Ця функція (хендлер) відповідає на команди."""
    await message.answer("✅ Вітаю! Я бот, що працює на Render. Готовий до роботи!")

# --- Розділ 4: Налаштування вебхука ---
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    """Ця функція приймає "сирі" дані від Telegram, перетворює їх у зрозумілий для aiogram формат і передає диспетчеру."""
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)

# --- Розділ 5: Події життєвого циклу сервера ---
@app.on_event("startup")
async def on_startup():
    """Встановлює зв'язок з Telegram (вебхук) при старті додатку."""
    webhook_url = BASE_WEBHOOK_URL + WEBHOOK_PATH
    await bot.set_webhook(url=webhook_url)

@app.on_event("shutdown")
async def on_shutdown():
    """Коректно розриває зв'язок з Telegram при зупинці додатку."""
    await bot.delete_webhook()