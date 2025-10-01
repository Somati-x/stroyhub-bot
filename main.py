# --- Розділ 1: Імпорти ---
import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
# ↓↓↓ ОНОВЛЕНІ ІМПОРТИ для клавіатур ↓↓↓
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties

# Імпортуємо наші функції для AI
from prompt_logic import build_social_prompt, call_llm

# --- Розділ 2: Конфігурація та ініціалізація ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_WEBHOOK_URL = "https://stroyhub-bot.onrender.com"
WEBHOOK_PATH = "/webhook"

app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# --- Розділ 3: Налаштування візарда та станів (FSM) ---
WIZARD_STEPS = [
  { 'key': 'features',     'type': 'text',   'label': 'Ключові особливості', 'question': "Крок 1/13: Введіть ключові особливості та 'фішки' проєкту." },
  { 'key': 'platform',     'type': 'choice', 'label': 'Платформа',          'question': "Крок 2/13: Оберіть платформу.", 'options': ['Instagram', 'Facebook'] },
  { 'key': 'objectStatus', 'type': 'choice', 'label': 'Статус об\'єкта',     'question': "Крок 3/13: Оберіть статус об'єкта.", 'options': ['Об\'єкт зданий', 'Робота в процесі'] },
  { 'key': 'street',       'type': 'text',   'label': 'Вулиця',             'question': "Крок 4/13: Вкажіть вулицю (можна пропустити)." },
  { 'key': 'district',     'type': 'text',   'label': 'Район',              'question': "Крок 5/13: Вкажіть район (напр: Аркадія)." },
  { 'key': 'style',        'type': 'text',   'label': 'Стиль ремонту',      'question': "Крок 6/13: Опишіть стиль ремонту." },
  { 'key': 'propertyType', 'type': 'choice', 'label': 'Тип нерухомості',    'question': "Крок 7/13: Оберіть тип нерухомості.", 'options': ['Квартира', 'Апартаменти', 'Будинок', 'Комерційне приміщення'] },
  { 'key': 'complexName',  'type': 'text',   'label': 'Назва ЖК',           'question': "Крок 8/13: Вкажіть назву ЖК (можна пропустити)." },
  { 'key': 'area',         'type': 'text',   'label': 'Площа, м²',          'question': "Крок 9/13: Яка площа об'єкта в м²?" },
  { 'key': 'rooms',        'type': 'choice', 'label': 'К-ть кімнат',        'question': "Крок 10/13: Оберіть кількість кімнат.", 'options': ['1', '2', '3', '4+', 'Студія'] },
  { 'key': 'goal',         'type': 'choice', 'label': 'Мета тексту',        'question': "Крок 11/13: Оберіть головну мету тексту.", 'options': ['Продемонструвати якість та деталі', 'Показати експертність', 'Створити емоційний зв\'язок', 'Залучити на консультацію', 'Розповісти історію "до/після"'] },
  { 'key': 'variations',   'type': 'choice', 'label': 'Кількість варіантів', 'question': "Крок 12/13: Скільки варіантів допису згенерувати?", 'options': ['1', '2', '3'] },
  { 'key': 'language',     'type': 'choice', 'label': 'Мова',               'question': "Крок 13/13: Оберіть мову.", 'options': ['Українська', 'Русский'] }
]

# Створюємо назву для нашої постійної кнопки
MAIN_BUTTON_TEXT = "📝 Написати новий допис"

class Form(StatesGroup):
    in_wizard = State()

# --- Розділ 4: Допоміжні функції ---
async def ask_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_step_index = data.get("current_step_index", 0)

    if current_step_index >= len(WIZARD_STEPS):
        await finish_wizard(message, state, is_regenerate=False)
        return

    step = WIZARD_STEPS[current_step_index]
    keyboard = []
    
    if step['type'] == 'choice':
        buttons = [InlineKeyboardButton(text=option, callback_data=f"select:{step['key']}:{option}") for option in step['options']]
        keyboard.extend([buttons[i:i + 2] for i in range(0, len(buttons), 2)])
    else:
        keyboard.append([InlineKeyboardButton(text="⏩ Пропустити", callback_data="skip_step")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_wizard")])
    
    await message.answer(step['question'], reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

async def finish_wizard(message: types.Message, state: FSMContext, is_regenerate: bool = False):
    data = await state.get_data()
    if not is_regenerate:
        summary = "*Дякую! Ви заповнили всі дані:*\n\n"
        for step in WIZARD_STEPS:
            answer = data.get(step['key'], "_пропущено_")
            summary += f"*{step['label']}:* {answer}\n"
        await message.answer(summary)
    
    await message.answer("⏳ *Генерую допис...*", reply_markup=ReplyKeyboardRemove())
    try:
        system_prompt, user_prompt = build_social_prompt(data)
        result_string = call_llm(system_prompt, user_prompt)
        posts = re.split(r'## Варіант \d+', result_string)
        posts = [post.strip() for post in posts if post.strip()]

        if not posts:
            await message.answer("Не вдалося розпізнати варіанти у відповіді від AI.\n\n" + result_string)
        else:
            for i, post in enumerate(posts):
                await message.answer(f"## Варіант {i+1}\n\n{post}")
        
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Згенерувати знову", callback_data="regenerate"), InlineKeyboardButton(text="✅ Закінчити", callback_data="finish_generation")]])
        await message.answer("Що робимо далі?", reply_markup=final_keyboard)
    except Exception as e:
        await message.answer(f"❌ Під час генерації сталася помилка: {e}")
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Спробувати знову", callback_data="regenerate"), InlineKeyboardButton(text="❌ Закінчити", callback_data="finish_generation")]])
        await message.answer("Спробувати згенерувати ще раз?", reply_markup=final_keyboard)

# --- Розділ 5: Обробники команд та дій ---
# ↓↓↓ ОНОВЛЕНО: Тепер обробляємо і текст кнопки ↓↓↓
@dp.message(F.text.in_({"/start", "/newpost", MAIN_BUTTON_TEXT}))
async def command_start_handler(message: types.Message, state: FSMContext):
    """Починає діалог та запускає візард."""
    await state.clear()
    await state.set_data({"current_step_index": 0})
    await state.set_state(Form.in_wizard)
    # Прибираємо постійну клавіатуру на час візарда
    await message.answer("👋 Вітаю! Давайте створимо допис.", reply_markup=ReplyKeyboardRemove())
    await ask_question(message, state)

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    """Дозволяє користувачу скасувати дію в будь-який момент."""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Дію скасовано.")
    await send_main_menu(message) # Показуємо головне меню з кнопкою

@dp.message(Form.in_wizard, F.text)
async def process_text_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_step_index = data.get("current_step_index", 0)
    step = WIZARD_STEPS[current_step_index]
    if step['type'] == 'text':
        await state.update_data({step['key']: message.text})
        await state.update_data({"current_step_index": current_step_index + 1})
        await ask_question(message, state)
    else:
        await message.answer("Будь ласка, оберіть один з варіантів за допомогою кнопок.")

@dp.callback_query()
async def process_callback(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    current_state = await state.get_state()
    
    if current_state == Form.in_wizard:
        data = await state.get_data()
        current_step_index = data.get("current_step_index", 0)
        if call.data == "skip_step":
            await call.message.delete()
            await state.update_data({"current_step_index": current_step_index + 1})
            await ask_question(call.message, state)
        elif call.data.startswith("select:"):
            parts = call.data.split(':')
            key, value = parts[1], parts[2]
            await state.update_data({key: value})
            await state.update_data({"current_step_index": current_step_index + 1})
            await call.message.delete()
            await ask_question(call.message, state)

    if call.data == "regenerate":
        await call.message.delete()
        await finish_wizard(call.message, state, is_regenerate=True)
    elif call.data == "finish_generation":
        await state.clear()
        await call.message.edit_text("✅ Дякую за використання бота!")
        await send_main_menu(call.message)
    elif call.data == "cancel_wizard":
        await state.clear()
        await call.message.edit_text("❌ Створення допису скасовано.")
        await send_main_menu(call.message)

# --- Розділ 6: Налаштування вебхука ---
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)

@app.on_event("startup")
async def on_startup():
    webhook_url = BASE_WEBHOOK_URL + WEBHOOK_PATH
    await bot.set_webhook(url=webhook_url)

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()

# --- Розділ 7: Головне меню ---
# ↓↓↓ НОВА ФУНКЦІЯ для показу головного меню ↓↓↓
async def send_main_menu(message: types.Message):
    """Надсилає головне меню з постійною кнопкою внизу."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_BUTTON_TEXT)]],
        resize_keyboard=True
    )
    await message.answer("Щоб створити новий допис, натисніть кнопку внизу або введіть /newpost.", reply_markup=keyboard)

# Цей обробник потрібен, щоб бот не відповідав "Невідома команда" на інші повідомлення
@dp.message()
async def echo_handler(message: types.Message):
    await send_main_menu(message)