# --- Розділ 1: Імпорти ---
# Імпортуємо необхідні інструменти з бібліотек, які ми встановили.
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types

# --- Розділ 2: Конфігурація та ініціалізація ---
# Завантажуємо змінні з нашого .env файлу (щоб отримати доступ до токена)
load_dotenv()
# Зчитуємо токен і зберігаємо його у змінну
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# URL нашого майбутнього сервісу на Render. Ми вставимо сюди реальний URL пізніше.
BASE_WEBHOOK_URL = "https://stroyhub-bot.onrender.com"
# Шлях, за яким Telegram буде надсилати нам оновлення. Може бути будь-яким.
WEBHOOK_PATH = "/webhook"

# Створюємо основні об'єкти:
app = FastAPI()  # "app" - це наш веб-сервер, який приймає запити.
bot = Bot(token=TELEGRAM_TOKEN)  # "bot" - це наш бот, який надсилає повідомлення.
dp = Dispatcher()  # "dp" (Dispatcher) - це "мозок" aiogram, який вирішує, яку функцію викликати у відповідь на повідомлення.

# --- Розділ 3: Обробники повідомлень (хендлери) ---
# Цей декоратор каже диспетчеру: "Якщо отримаєш повідомлення, яке є командою /start або /newpost, виклич функцію нижче".
@dp.message(commands=["start", "newpost"])
async def send_welcome(message: types.Message):
    """Ця функція (хендлер) відповідає на команди."""
    # `await` означає, що ми чекаємо, поки повідомлення буде надіслано, перш ніж продовжити.
    # `message.answer()` - це простий спосіб відповісти на отримане повідомлення.
    await message.answer("✅ Вітаю! Я бот, що працює на Render. Готовий до роботи!")

# --- Розділ 4: Налаштування вебхука ---
# Цей декоратор FastAPI створює "вхідні двері" для Telegram.
# Усі запити від Telegram будуть надходити на URL, що закінчується на /webhook.
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    """Ця функція приймає "сирі" дані від Telegram, перетворює їх у зрозумілий для aiogram формат і передає диспетчеру."""
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)

# --- Розділ 5: Події життєвого циклу сервера ---
# Ця функція виконається ОДИН РАЗ, коли наш сервер на Render запуститься.
@app.on_event("startup")
async def on_startup():
    """Встановлює зв'язок з Telegram (вебхук) при старті додатку."""
    webhook_url = BASE_WEBHOOK_URL + WEBHOOK_PATH
    # Кажемо Telegram: "Будь ласка, всі оновлення для мого бота надсилай на цей URL".
    await bot.set_webhook(url=webhook_url)

# Ця функція виконається ОДИН РАЗ, коли сервер зупиняється.
@app.on_event("shutdown")
async def on_shutdown():
    """Коректно розриває зв'язок з Telegram при зупинці додатку."""
    # Кажемо Telegram: "Більше не надсилай мені оновлення".
    await bot.delete_webhook()