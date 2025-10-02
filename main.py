import os
import re
import asyncio
import logging
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties

# --- Завантаження конфігів ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

BASE_WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "https://stroyhub-bot.onrender.com")
WEBHOOK_PATH = "/webhook"

# Логування
logging.basicConfig(level=logging.INFO)

# --- FastAPI + Aiogram ---
app = FastAPI()
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()


def format_button_label(text: str, icon: str) -> str:
    sanitized_text = text.strip()
    if not sanitized_text:
        return icon

    chars = list(sanitized_text)
    for idx, char in enumerate(chars):
        if char.isalpha():
            chars[idx] = char.upper()
            break

    return f"{icon} {''.join(chars)}"

# --- Імпорт власної логіки ---
from prompt_logic import build_social_prompt, call_llm

# --- Константи ---
MAIN_BUTTON_TEXT = format_button_label("Написати новий допис", "📝")
CANCEL_WIZARD_BUTTON_TEXT = format_button_label("Скасувати створення допису", "❌")
SKIP_STEP_BUTTON_TEXT = format_button_label("Пропустити", "⏩")
CONFIRM_GENERATION_BUTTON_TEXT = format_button_label("Згенерувати допис", "✅")
REGENERATE_BUTTON_TEXT = format_button_label("Згенерувати знову", "🔄")
FINISH_BUTTON_TEXT = format_button_label("Закінчити", "✅")
ERROR_RETRY_BUTTON_TEXT = format_button_label("Спробувати знову", "🔄")
ERROR_FINISH_BUTTON_TEXT = format_button_label("Закінчити", "❌")
CHOICE_BUTTON_ICON = "🔹"

# --- Кроки ---
WIZARD_STEPS = [
    { 'key': 'features',     'type': 'text',   'label': 'Ключові особливості', 'question': "Опишіть про що буде допис" },
    { 'key': 'platform',     'type': 'choice', 'label': 'Платформа', 'question': "Оберіть платформу.", 'options': ['Instagram', 'Facebook', 'Tik-Tok'] },
    { 'key': 'objectStatus', 'type': 'choice', 'label': 'Статус об\'єкта', 'question': "Оберіть статус об'єкта.", 'options': ['Об\'єкт зданий', 'Робота в процесі'] },
    { 'key': 'street',       'type': 'text',   'label': 'Вулиця', 'question': "Вкажіть вулицю (можна пропустити)." },
    { 'key': 'district',     'type': 'text',   'label': 'Район', 'question': "Вкажіть район (напр: Аркадія)." },
    { 'key': 'propertyType', 'type': 'choice', 'label': 'Тип нерухомості', 'question': "Оберіть тип нерухомості.", 'options': ['Квартира', 'Апартаменти', 'Будинок', 'Комерційне приміщення'] },
    { 'key': 'complexName',  'type': 'text',   'label': 'Назва ЖК', 'question': "Вкажіть назву ЖК (можна пропустити)." },
    { 'key': 'area',         'type': 'text',   'label': 'Площа, м²', 'question': "Яка площа об'єкта в м²?" },
    { 'key': 'rooms',        'type': 'choice', 'label': 'К-ть кімнат', 'question': "Оберіть кількість кімнат.", 'options': ['1', '2', '3', '4+', 'Студія'] },
    { 'key': 'goal',         'type': 'choice', 'label': 'Мета тексту', 'question': "Оберіть головну мету тексту.", 'options': ['Продемонструвати якість та деталі', 'Показати експертність', 'Створити емоційний зв\'язок', 'Залучити на консультацію', 'Розповісти історію \"до/після\"'] },
    { 'key': 'variations',   'type': 'choice', 'label': 'Кількість варіантів допису', 'question': "Скільки варіантів допису згенерувати?", 'options': ['1', '2', '3'] },
]

# --- FSM ---
class Form(StatesGroup):
    in_wizard = State()
    confirm_generation = State()

# --- Допоміжні функції ---
async def send_main_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_BUTTON_TEXT)]],
        resize_keyboard=True
    )
    await message.answer(
        "Щоб створити новий допис, натисніть кнопку внизу",
        reply_markup=keyboard
    )


def wizard_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_WIZARD_BUTTON_TEXT)]],
        resize_keyboard=True
    )

async def ask_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_step_index = data.get("current_step_index", 0)
    if current_step_index >= len(WIZARD_STEPS):
        await state.set_state(Form.confirm_generation)
        await show_summary(message, state)
        return
    step = WIZARD_STEPS[current_step_index]
    keyboard = []
    if step['type'] == 'choice':
        buttons = [
            InlineKeyboardButton(
                text=format_button_label(option, CHOICE_BUTTON_ICON),
                callback_data=f"select:{step['key']}:{idx}"
            )
            for idx, option in enumerate(step['options'])
        ]
        keyboard.extend([buttons[i:i + 2] for i in range(0, len(buttons), 2)])
    else:
        keyboard.append([InlineKeyboardButton(text=SKIP_STEP_BUTTON_TEXT, callback_data="skip_step")])
    await message.answer(step['question'], reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

async def show_summary(message: types.Message, state: FSMContext):
    data = await state.get_data()
    summary_lines = ["Дякую! Ви заповнили всі дані:", ""]
    for step in WIZARD_STEPS:
        answer = data.get(step['key'], "пропущено")
        summary_lines.append(f"{step['label']}: {answer}")
        summary_lines.append("")
    summary_text = "\n".join(summary_lines).strip()
    await message.answer(summary_text, parse_mode=None)
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=CONFIRM_GENERATION_BUTTON_TEXT, callback_data="confirm_generation")]]
    )
    await message.answer("Перевірте введені дані", reply_markup=confirm_keyboard)


async def generate_posts(message: types.Message, state: FSMContext, is_regenerate: bool = False):
    data = await state.get_data()
    await state.set_state(Form.confirm_generation)
    await message.answer("⏳ *Генерую допис...*", reply_markup=ReplyKeyboardRemove())
    try:
        system_prompt, user_prompt = build_social_prompt(data)
        result_string = await call_llm(system_prompt, user_prompt)
        result_string = result_string.replace("—", "-")

        pattern = r'(## Варіант \d+.*?)(?=\n## Варіант \d+|\Z)'
        posts = re.findall(pattern, result_string, flags=re.S)
        posts = [post.strip() for post in posts if post.strip()]
        if not posts:
            await message.answer("Не вдалося розпізнати варіанти.\n\n" + result_string)
        else:
            for post in posts:
                await message.answer(post)
        
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=REGENERATE_BUTTON_TEXT, callback_data="regenerate"),
             InlineKeyboardButton(text=FINISH_BUTTON_TEXT, callback_data="finish_generation")]
        ])
        await message.answer("Що робимо далі?", reply_markup=final_keyboard)
    except Exception as e:
        await message.answer(f"❌ Під час генерації сталася помилка: {e}")
        final_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=ERROR_RETRY_BUTTON_TEXT, callback_data="regenerate"),
             InlineKeyboardButton(text=ERROR_FINISH_BUTTON_TEXT, callback_data="finish_generation")]
        ])
        await message.answer("Спробувати згенерувати ще раз?", reply_markup=final_keyboard)

# --- Хендлери ---
@dp.message(F.text.in_({"/start", "/newpost", MAIN_BUTTON_TEXT}))
async def command_start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_data({"current_step_index": 0})
    await state.set_state(Form.in_wizard)
    await message.answer("👋 Вітаю! Давайте створимо допис.", reply_markup=wizard_keyboard())
    await ask_question(message, state)

@dp.message(F.text.lower() == CANCEL_WIZARD_BUTTON_TEXT.lower())
async def cancel_wizard_via_button(message: types.Message, state: FSMContext):
    if await state.get_state() not in {Form.in_wizard, Form.confirm_generation}:
        return
    await state.clear()
    await message.answer("❌ Створення допису скасовано.", reply_markup=ReplyKeyboardRemove())
    await send_main_menu(message)

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Дію скасовано.")
    await send_main_menu(message)

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


@dp.message(Form.confirm_generation, F.text)
async def process_confirmation_text(message: types.Message):
    await message.answer(
        f"Натисніть кнопку \"{CONFIRM_GENERATION_BUTTON_TEXT}\" або скористайтеся кнопкою скасування нижче."
    )

@dp.callback_query()
async def process_callback(call: types.CallbackQuery, state: FSMContext):
    try:
        await call.answer()
    except Exception:
        pass
    
    if await state.get_state() == Form.in_wizard:
        data = await state.get_data()
        current_step_index = data.get("current_step_index", 0)
        try:
            if call.data == "skip_step":
                await call.message.delete()
                await state.update_data({"current_step_index": current_step_index + 1})
                await ask_question(call.message, state)
            elif call.data.startswith("select:"):
                parts = call.data.split(':')
                if len(parts) != 3:
                    return
                key, raw_idx = parts[1], parts[2]

                step_index = next(
                    (idx for idx, s in enumerate(WIZARD_STEPS) if s['key'] == key and s.get('type') == 'choice'),
                    None
                )
                if step_index is None or step_index != current_step_index:
                    return
                step = WIZARD_STEPS[step_index]

                try:
                    option_index = int(raw_idx)
                    selected_value = step['options'][option_index]
                except (ValueError, IndexError):
                    return

                updated_text = f"{step['question']}\n\n*✅ Ваш вибір: {selected_value}*"
                await call.message.edit_text(updated_text)
                await state.update_data({key: selected_value})
                await state.update_data({"current_step_index": step_index + 1})
                await asyncio.sleep(1)
                await ask_question(call.message, state)
        except Exception:
            pass

    try:
        if call.data == "confirm_generation":
            await call.message.edit_reply_markup()
            await generate_posts(call.message, state)
        elif call.data == "regenerate":
            await call.message.delete()
            await generate_posts(call.message, state, is_regenerate=True)
        elif call.data == "finish_generation":
            await state.clear()
            await call.message.edit_text("✅ Дякую за використання бота!")
            await send_main_menu(call.message)
        elif call.data == "cancel_wizard":
            await state.clear()
            await call.message.edit_text("❌ Створення допису скасовано.")
            await send_main_menu(call.message)
    except Exception:
        pass

# --- Health-check ---
@app.get("/")
async def root():
    return {"status": "ok"}

# --- Webhook ---
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    if "update_id" not in update:  # щоб health-check не заважав
        return {"status": "ignored"}
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    webhook_url = BASE_WEBHOOK_URL + WEBHOOK_PATH
    await bot.delete_webhook()
    await bot.set_webhook(url=webhook_url)
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f"✅ Бот перезапущено!\nWebhook: {webhook_url}")
        except Exception as e:
            logging.error(f"Не вдалося надіслати повідомлення адміну: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()

# --- Запуск uvicorn ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
