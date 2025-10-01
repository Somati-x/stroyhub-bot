import os
import requests
from time import sleep

# --- Конфігурація ---
GPT_MODEL = "gpt-4o"  # Використовуємо найновішу модель
MAX_TOKENS = 4000  # Достатньо для 3 детальних постів
TEMPERATURE = 0.7
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунди

# --- Функція побудови промпту ---
def build_social_prompt(form_data: dict) -> tuple:
    """Формує текстовий запит (промпт) для мовної моделі."""
    
    # Базові параметри
    social_network = form_data.get('platform', 'Instagram')
    post_type = form_data.get('goal', 'Продемонструвати якість та деталі')
    variations = form_data.get('variations', '1')
    language_raw = form_data.get('language', 'Українська')
    
    # Конвертація мови
    language_map = {
        'Українська': 'українська',
        'Русский': 'русский'
    }
    language = language_map.get(language_raw, 'українська')
    
    # Збираємо всі дані про об'єкт
    property_type = form_data.get('propertyType', 'нерухомість')
    district = form_data.get('district', '')
    street = form_data.get('street', '')
    complex_name = form_data.get('complexName', '')
    area = form_data.get('area', '')
    rooms = form_data.get('rooms', '')
    object_status = form_data.get('objectStatus', '')
    features = form_data.get('features', '')
    
    # Формуємо детальний опис теми
    topic_parts = []
    topic_parts.append(f"Допис про {property_type}")
    
    if rooms and rooms != '_пропущено_':
        topic_parts.append(f"({rooms} кімнат)" if rooms not in ['Студія', '4+'] else f"({rooms})")
    
    if area and area != '_пропущено_':
        topic_parts.append(f"площею {area} м²")
    
    if district and district != '_пропущено_':
        topic_parts.append(f"в районі {district}")
    
    if street and street != '_пропущено_':
        topic_parts.append(f"на вулиці {street}")
    
    if complex_name and complex_name != '_пропущено_':
        topic_parts.append(f"в ЖК «{complex_name}»")
    
    topic = " ".join(topic_parts) + "."
    
    # Додаткові деталі
    additional_info = []
    if object_status and object_status != '_пропущено_':
        additional_info.append(f"Статус: {object_status}")
    
    if features and features != '_пропущено_':
        additional_info.append(f"Ключові особливості: {features}")
    
    # Системний промпт
    system_prompt_parts = [
        'Ти — SMM-стратег і копірайтер рівня senior, що спеціалізується на створенні сильних текстів для Instagram, які користувачі хочуть зберігати та перечитувати.',
        'Твоя головна мета — створити текст, який захоплює увагу з перших секунд, утримує її до кінця і спонукає читача до цільової дії (підписка, коментар, збереження, консультація).',
        '',
        '### 1. Структура Ідеального Посту',
        '',
        '**1.1. Сильний Вступ (Перші 125 символів):**',
        '- Це **головна частина тексту**, яка вирішує, чи будуть його читати далі. У стрічці видно лише перші 125 символів, тому вони мають бути максимально чіпляючими.',
        '- **Обов\'язково використовуй один із трьох прийомів для вступу:**',
        '  1. **Заголовок, що розриває шаблони:** Створи інтригуючу та нестандартну назву, яка викликає цікавість.',
        '  2. **Аргументація цінності:** У першому абзаці одразу поясни, яку користь читач отримає від поста.',
        '  3. **Мотивація дочитати:** Пообіцяй наприкінці щось корисне — кейси, деталі проєкту, експертні поради.',
        '',
        '**1.2. Основна Частина:**',
        '- **Розділяй текст на абзаци:** Ніколи не пиши суцільним полотном. Кожен абзац має містити 2-4 речення.',
        '- **Використовуй списки:** Для переліку переваг або особливостей використовуй списки, оформлені за допомогою тире, стрілок або емодзі.',
        '- **Розкривай деталі:** Детально описуй матеріали, рішення, унікальні елементи дизайну.',
        '',
        '**1.3. Заклик до Дії (CTA):**',
        '- **Завжди розміщуй CTA в кінці посту**.',
        '- Заклик має спонукати до дискусії в коментарях або запису на консультацію.',
        '- Ставай відкрите питання читачам — це позитивно впливає на охоплення.',
        '',
        '### 2. Стиль та Тон',
        '- Пиши природно, як експерт, який ділиться досвідом з колегою.',
        '- Уникай банальних фраз на кшталт "ми пишаємося", "неперевершена якість".',
        '- Використовуй конкретику: не "якісні матеріали", а "італійська плитка Marazzi".',
        '- Додавай емодзі там, де це природно, але не перестарайся.',
        '',
        '### 3. Формат Відповіді',
        '- Надай кожен варіант допису чітко відокремленим.',
        '- Почни кожен варіант із заголовка `## Варіант N`, а потім сам текст допису.',
        '- Текст має бути готовим до публікації — без додаткових пояснень чи коментарів.'
    ]
    system_prompt = "\n".join(system_prompt_parts)

    # Користувацький промпт
    user_prompt_parts = [
        'Згенеруй текст для допису в соціальних мережах за такими параметрами:',
        '',
        f"**Соціальна мережа:** {social_network}",
        f"**Тема:** {topic}",
        ''
    ]
    
    if additional_info:
        user_prompt_parts.append("**Додаткова інформація:**")
        for info in additional_info:
            user_prompt_parts.append(f"- {info}")
        user_prompt_parts.append('')
    
    user_prompt_parts.extend([
        f"**Мета допису:** {post_type}",
        f"**Кількість варіантів:** {variations}",
        f"**Мова:** {language}",
        '',
        'Кожен варіант має бути унікальним за структурою та підходом, але зберігати професійний тон.'
    ])
    
    user_prompt = "\n".join(user_prompt_parts)

    return (system_prompt, user_prompt)


# --- Функція виклику LLM з retry логікою ---
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Викликає мовну модель OpenAI з наданим промптом."""
    
    api_key = os.getenv("OPENAI_API_KEY") 
    api_url = "https://api.openai.com/v1/chat/completions"

    if not api_key:
        raise ValueError("OPENAI_API_KEY не знайдено! Додайте його в змінні середовища.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": GPT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    }

    # Retry логіка
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                json_response = response.json()
                if json_response.get("choices"):
                    return json_response["choices"][0]["message"]["content"].strip()
                else:
                    raise Exception(f"Відповідь від API не містить 'choices'. Повна відповідь: {response.text}")
            
            elif response.status_code == 429:  # Rate limit
                print(f"Rate limit досягнуто. Спроба {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    sleep(RETRY_DELAY * (attempt + 1))  # Експоненційна затримка
                    continue
                else:
                    raise Exception(f"Перевищено ліміт запитів до API: {response.text}")
            
            elif response.status_code == 503:  # Service unavailable
                print(f"Сервіс тимчасово недоступний. Спроба {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    sleep(RETRY_DELAY)
                    continue
                else:
                    raise Exception(f"Сервіс OpenAI недоступний: {response.text}")
            
            else:
                raise Exception(f"Помилка API: {response.status_code} - {response.text}")
        
        except requests.exceptions.Timeout:
            print(f"Timeout при запиті до API. Спроба {attempt + 1}/{MAX_RETRIES}")
            last_error = "Перевищено час очікування відповіді від OpenAI"
            if attempt < MAX_RETRIES - 1:
                sleep(RETRY_DELAY)
                continue
        
        except requests.exceptions.RequestException as e:
            print(f"Помилка з'єднання: {e}. Спроба {attempt + 1}/{MAX_RETRIES}")
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                sleep(RETRY_DELAY)
                continue
    
    # Якщо всі спроби вичерпані
    raise Exception(f"Не вдалося отримати відповідь після {MAX_RETRIES} спроб. Остання помилка: {last_error}")