import os
import httpx # Використовуємо httpx замість requests
import asyncio

# --- Конфігурація ---
GPT_MODEL = "gpt-4.1"
MAX_TOKENS = 4000
TEMPERATURE = 0.7
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунди

# --- Функція побудови промпту (з невеликими покращеннями) ---
def build_social_prompt(form_data: dict) -> tuple:
    """Формує текстовий запит (промпт) для мовної моделі."""
    
    # ... (ця функція залишається майже без змін, копіюю її для повноти) ...
    social_network = form_data.get('platform', 'Instagram')
    post_type = form_data.get('goal', 'Продемонструвати якість та деталі')
    variations = form_data.get('variations', '1')

    topic_parts = [f"Допис про {form_data.get('propertyType', 'нерухомість')}"]
    rooms = form_data.get('rooms')
    if rooms and rooms != '_пропущено_': topic_parts.append(f"({rooms})" if rooms in ['Студія', '4+'] else f"({rooms} кімнат)")
    area = form_data.get('area')
    if area and area != '_пропущено_': topic_parts.append(f"площею {area} м²")
    district = form_data.get('district')
    if district and district != '_пропущено_': topic_parts.append(f"в районі {district}")
    topic = " ".join(topic_parts) + "."

    features = form_data.get('features')
    street = form_data.get('street')
    complex_name = form_data.get('complexName')
    object_status = form_data.get('objectStatus')

    details = []
    if features and features != '_пропущено_':
        details.append(f"Ключові особливості: {features}.")
    if object_status and object_status != '_пропущено_':
        details.append(f"Статус об'єкта: {object_status}.")
    if complex_name and complex_name != '_пропущено_':
        details.append(f"ЖК: {complex_name}.")
    if street and street != '_пропущено_':
        details.append(f"Вулиця: {street}.")

    details_text = " ".join(details) if details else ""
    
    # ... (решта логіки побудови промпту без змін) ...
    system_prompt = 'Ти — SMM-стратег...' # (для скорочення, тут ваш повний системний промпт)
    
    user_prompt_parts = [
        f"Згенеруй текст для допису в {social_network} на тему: {topic}",
        f"Мета: {post_type}",
        f"Кількість варіантів: {variations}",
        "Мова: українська",
    ]
    if details_text:
        user_prompt_parts.append(details_text)
    user_prompt = "\n".join(user_prompt_parts)

    return (system_prompt, user_prompt)

# --- АСИНХРОННА функція виклику LLM ---
async def call_llm(system_prompt: str, user_prompt: str) -> str:
    """АСИНХРОННО викликає мовну модель OpenAI з логікою повторних спроб."""
    
    api_key = os.getenv("OPENAI_API_KEY") 
    api_url = "https://api.openai.com/v1/chat/completions"

    if not api_key:
        raise ValueError("OPENAI_API_KEY не знайдено!")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": GPT_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    }

    last_error = None
    async with httpx.AsyncClient(timeout=90.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(api_url, headers=headers, json=payload)
                response.raise_for_status() # Генерує помилку для кодів 4xx/5xx

                json_response = response.json()
                if json_response.get("choices"):
                    return json_response["choices"][0]["message"]["content"].strip()
                else:
                    raise Exception(f"Відповідь від API не містить 'choices'.")
            
            except httpx.HTTPStatusError as e:
                # Обробка помилок сервера
                print(f"Помилка API (статус {e.response.status_code}). Спроба {attempt + 1}/{MAX_RETRIES}")
                last_error = e.response.text
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"Не вдалося отримати відповідь після {MAX_RETRIES} спроб. Остання помилка: {last_error}")
            except httpx.RequestError as e:
                # Обробка помилок з'єднання/таймаутів
                print(f"Помилка з'єднання: {e}. Спроба {attempt + 1}/{MAX_RETRIES}")
                last_error = str(e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
    
    raise Exception(f"Не вдалося отримати відповідь після {MAX_RETRIES} спроб. Остання помилка: {last_error}")