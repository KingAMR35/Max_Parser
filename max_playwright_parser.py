from playwright.sync_api import sync_playwright
import re
import time
import requests
import os
from typing import List, Dict
from config import MAX_GROUP_URL, MAX_PHONE
from datetime import datetime

# 🔥 СЕССИЯ сохраняется в папке
SESSION_DIR = "max_session"
os.makedirs(SESSION_DIR, exist_ok=True)

def download_file(url: str, filename: str = None) -> str:
    """Скачивает медиафайлы"""
    os.makedirs("downloads", exist_ok=True)
    if not filename:
        filename = f"max_{int(time.time())}"
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    filepath = f"downloads/{filename}"
    
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return filepath
    except:
        pass
    return None

def is_human_message(text: str) -> bool:
    """🚫 Боты → ✅ Только люди"""
    text = text.strip().lower()
    
    # 🚫 Системные сообщения ботов
    bot_phrases = [
        'теперь в max', 'напишите что-нибудь', 'сферум',
        'удалил', 'удалила', 'изменил', 'изменила', 'обновил', 'обновила',
        'вошел', 'вошла', 'покинул', 'покинула', 'пригласил', 'исключил'
    ]
    
    if any(phrase in text for phrase in bot_phrases):
        print(f"🤖 Бот: '{text[:40]}...'")
        return False
    
    # ✅ Реальные сообщения
    return (15 < len(text) < 600 and 
            text[0].isalpha() and 
            not re.match(r'^\d+$', text))

def parse_max_group_media() -> List[Dict]:
    """🔥 5 САМЫХ НОВЫХ сообщений ЛЮДЕЙ с автологином"""
    human_posts = []
    
    with sync_playwright() as p:
        # 🔥 ВОССТАНАВЛИВАЕМ СЕССИЮ браузера
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  # Видим браузер
            viewport={'width': 1920, 'height': 1080},
            slow_mo=300  # Медленно — для отладки
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("🔍 MAX автологин...")
        
        # 1. Проверяем авторизацию
        current_url = page.url
        if "web.max.ru" not in current_url or "login" in current_url:
            print("📱 Нужна авторизация...")
            page.goto("https://web.max.ru")
            page.wait_for_timeout(5000)
            
            try:
                phone_input = page.query_selector("input[type='tel'], input[placeholder*='телефон']")
                if phone_input:
                    phone_input.fill(MAX_PHONE)
                    page.click("button, input[type='submit']")
                    print("❗ ПЕРВЫЙ РАЗ: Введите SMS код в браузере (2 минуты)...")
                    page.wait_for_timeout(120000)  # Ждём SMS
                else:
                    print("✅ Уже авторизованы")
            except Exception as e:
                print(f"⚠️ Авторизация: {e}")
        
        # 2. Открываем группу
        print(f"📱 Переходим: {MAX_GROUP_URL}")
        page.goto(MAX_GROUP_URL)
        page.wait_for_timeout(10000)  # Ждём загрузки группы
        
        # 3. СКРОЛЛ К САМЫМ НОВЫМ СООБЩЕНИЯМ
        print("⬆️ Скроллим к новым сообщениям...")
        page.keyboard.press("Home")
        page.wait_for_timeout(2000)
        page.keyboard.press("Home")
        page.wait_for_timeout(2000)
        page.keyboard.press("Control+Home")  # Максимум вверх
        page.wait_for_timeout(4000)
        
        # 4. Ищем сообщения (ТОЛЬКО ПЕРВЫЕ = НОВЫЕ)
        message_selectors = [
            "div[class*='message']",
            "div[class*='chat-message']", 
            "div[class*='post']",
            ".bubble",
            "[data-testid*='message']"
        ]
        
        all_candidates = []
        for selector in message_selectors:
            try:
                elements = page.query_selector_all(selector)[:20]  # ТОЛЬКО ПЕРВЫЕ 20!
                print(f"   {selector}: {len(elements)}")
                all_candidates.extend(elements)
            except Exception as e:
                print(f"   {selector}: ошибка")
        
        print(f"📦 Кандидатов найдено: {len(all_candidates)}")
        
        # 5. ФИЛЬТРУЕМ только ЛЮДЕЙ (ТОЛЬКО ПЕРВЫЕ 5)
        human_count = 0
        for i, elem in enumerate(set(all_candidates[:25])):  # Убираем дубли
            try:
                full_text = elem.text_content().strip()
                
                # Проверяем — человек ли?
                if not is_human_message(full_text):
                    continue
                
                # Ищем ИМЯ пользователя
                name = "Пользователь"
                name_selectors = [
                    "[class*='name']", "[class*='author']", 
                    "[class*='username']", ".user-name", "span"
                ]
                for name_sel in name_selectors:
                    name_elem = elem.query_selector(name_sel)
                    if name_elem:
                        name_text = name_elem.text_content().strip()
                        if 2 < len(name_text) < 50 and name_text != full_text[:len(name_text)]:
                            name = name_text[:30]
                            break
                
                # 🔥 МЕДИА (картинки, НЕ аватарки)
                media_files = []
                imgs = elem.query_selector_all("img")
                for img in imgs[:2]:
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if (src and len(src) > 30 and 
                        all(x not in src.lower() for x in ['avatar', 'icon', 'logo'])):
                        local_path = download_file(src)
                        if local_path:
                            media_files.append({
                                'url': src,
                                'local_path': local_path,
                                'type': 'image'
                            })
                
                # ✅ РЕАЛЬНОЕ сообщение человека!
                post_data = {
                    'id': f'human_{human_count}_{int(time.time())}',
                    'name': name,
                    'text': full_text[:450],
                    'media_files': media_files,
                    'time': datetime.now().strftime("%H:%M")
                }
                
                human_posts.append(post_data)
                human_count += 1
                print(f"✅ #{human_count} 👤{name}: '{full_text[:60]}...' | 📁{len(media_files)}")
                
                if human_count >= 5:  # ДОВОЛЬНО!
                    break
                    
            except Exception as e:
                print(f"❌ Элемент {i}: {e}")
                continue
        
        browser.close()
    
    print(f"🎉 НАЙДЕНО {len(human_posts)} человеческих сообщений")
    return human_posts

if __name__ == "__main__":
    print("🧪 ТЕСТ парсера...")
    posts = parse_max_group_media()
    print("\n📋 РЕЗУЛЬТАТ:")
    for i, post in enumerate(posts, 1):
        print(f"{i}. 👤 {post['name']}")
        print(f"   {post['text'][:100]}...")
        if post['media_files']:
            print(f"   📁 {len(post['media_files'])} файлов")
    print(f"\n✅ Готово! {len(posts)} сообщений")
