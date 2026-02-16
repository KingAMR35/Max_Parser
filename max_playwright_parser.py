from playwright.sync_api import sync_playwright
import re
import time
import requests
import os
import json
from typing import List, Dict
from configuration import MAX_GROUP_URL, MAX_PHONE
from datetime import datetime, timedelta
import hashlib
import shutil


SESSION_DIR = "chrome_max_session_permanent"
SEEN_MESSAGES_FILE = "seen_messages.json"
PHOTO_CACHE_FILE = "seen_images.json"
os.makedirs(SESSION_DIR, exist_ok=True)

message_cache = set()
photo_cache = set()


def load_message_cache():
    """Загружает хэши сообщений из seen_messages.json"""
    global message_cache
    if os.path.exists(SEEN_MESSAGES_FILE):
        try:
            with open(SEEN_MESSAGES_FILE, "r", encoding="utf-8") as f:
                message_cache = set(json.load(f).get('message_hashes', []))
            print(f"✅ seen_messages.json: {len(message_cache)} сообщений")
        except:
            message_cache = set()
    else:
        message_cache = set()


def save_message_cache():
    """Сохраняет хэши сообщений в seen_messages.json"""
    try:
        with open(SEEN_MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump({'message_hashes': list(message_cache)}, f)
        print(f"💾 seen_messages.json: {len(message_cache)} сообщений")
    except:
        pass


def load_photo_cache():
    """Загружает хэши фото из cache_file.json"""
    global photo_cache
    if os.path.exists(PHOTO_CACHE_FILE):
        try:
            with open(PHOTO_CACHE_FILE, "r", encoding="utf-8") as f:
                photo_cache = set(json.load(f).get('photo_hashes', []))
            print(f"✅ cache_file.json: {len(photo_cache)} фото")
        except:
            photo_cache = set()
    else:
        photo_cache = set()


def save_photo_cache():
    """Сохраняет хэши фото в cache_file.json"""
    try:
        with open(PHOTO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({'photo_hashes': list(photo_cache)}, f)
        print(f"💾 cache_file.json: {len(photo_cache)} фото")
    except:
        pass


def get_message_hash(post: dict) -> str:
    content = f"{post['name']}{post['text']}"
    return hashlib.md5(content.encode()).hexdigest()


def get_photo_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def is_new_message(post: dict) -> bool:
    """Проверяет новое сообщение (seen_messages.json)"""
    msg_hash = get_message_hash(post)
    if msg_hash in message_cache:
        return False
    message_cache.add(msg_hash)
    save_message_cache() 
    return True


def is_new_photo(url: str) -> bool:
    """Проверяет новое фото (cache_file.json)"""
    photo_hash = get_photo_hash(url)
    if photo_hash in photo_cache:
        print(f"🚫 ДУБЛЬ ФОТО: {url[:60]}")
        return False
    photo_cache.add(photo_hash)
    save_photo_cache()
    return True


def clear_all_caches():
    """Очищает ВСЕ кэши"""
    global message_cache, photo_cache
    message_cache.clear()
    photo_cache.clear()
    
    for file in [SEEN_MESSAGES_FILE, PHOTO_CACHE_FILE, "max_cookies.json"]:
        if os.path.exists(file):
            os.remove(file)
    
    for folder in ["chrome_max_session_permanent", "downloads"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    print("✅ ВСЕ КЭШИ ОЧИЩЕНЫ!")


def is_photo_not_avatar(url: str, element) -> bool:
    """СУПЕРСТРОГИЙ ФИЛЬТР АВАТАРОК"""
    url_lower = url.lower()
    
    banlist = [
        'avatar', 'profile', 'userpic', 'user-', 'icon', 'logo', 'emoji', 
        'sticker', 'thumb', 'thumbnail', 'preview', 'small', 'circle', 
        'round', 'mini', 'tiny', 'badge', 'status', 'placeholder'
    ]
    if any(ban in url_lower for ban in banlist):
        print(f"🚫 БАН ПО СЛОВУ: {url[:50]}")
        return False
    
    try:
        width = element.get_attribute("width")
        height = element.get_attribute("height")
        if width and int(width) < 300:
            print(f"🚫 width < 300px: {width}")
            return False
        if height and int(height) < 300:
            print(f"🚫 height < 300px: {height}")
            return False
        
        box = element.bounding_box()
        if box and (box['width'] < 250 or box['height'] < 250):
            print(f"🚫 box < 250px: {box['width']}x{box['height']}")
            return False
    except:
        pass
    
    if len(url) < 70:
        print(f"🚫 URL слишком короткий: {len(url)} символов")
        return False
    
    print(f"✅ ✅ РЕАЛЬНОЕ ФОТО: {url[:60]}")
    return True


def download_file(url: str) -> str:
    if not is_new_photo(url):
        return None
    
    os.makedirs("downloads", exist_ok=True)
    filename = f"photo_{int(time.time())}_{get_photo_hash(url)[:12]}.jpg"
    filepath = f"downloads/{filename}"
    
    try:
        print(f"📥 НОВОЕ ФОТО: {url[:80]}...")
        response = requests.get(url, timeout=30, stream=True)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return filepath
    except:
        pass
    return None


def is_human_message(text: str) -> bool:
    text = text.strip().lower()
    bot_phrases = ['теперь в max', 'напишите что-нибудь', 'сферум', 'удалил', 'удалила', 'изменил', 'изменила', 'вошел', 'вошла', 'покинул', 'покинула']
    if any(phrase in text for phrase in bot_phrases):
        return False
    return (15 < len(text) < 900 and text[0].isalpha())


def chronological_scroll(page, target_url: str):
    """ХРОНОЛОГИЧЕСКИЙ СКРОЛЛ: СТАРЫЕ → НОВЫЕ"""
    print("📜 ХРОНОЛОГИЯ: СТАРЫЕ → НОВЫЕ")
    
    if target_url not in page.url:
        page.goto(target_url)
        page.wait_for_timeout(5000)
    
    print("📜 1. К САМЫМ СТАРЫМ...")
    for i in range(20):
        page.keyboard.press("Home")
        page.wait_for_timeout(300)
    
    page.wait_for_timeout(4000)
    
    print("📜 2. МЕДЛЕННЫЙ скролл ВНИЗ...")
    scroll_count = 0
    previous_height = 0
    
    while scroll_count < 25:
        current_height = page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            print("📜 ✅ ВСЯ ИСТОРИЯ!")
            break
        
        print(f"📜 Раунд {scroll_count+1}/25...")
        for i in range(15):
            page.keyboard.press("PageDown")
            page.wait_for_timeout(400)
        
        previous_height = current_height
        scroll_count += 1
        page.wait_for_timeout(1500)
    
    print("📜 3. К НОВЫМ...")
    for i in range(30):
        page.keyboard.press("End")
        page.wait_for_timeout(200)
    
    page.wait_for_timeout(5000)


def extract_timestamp(text: str, element) -> tuple:
    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    if time_match:
        try:
            dt = datetime.strptime(time_match.group(1), '%H:%M')
            dt = dt + timedelta(hours=4)
            return dt.timestamp(), 0
        except:
            pass
    return time.time(), 3


def session_is_valid(page) -> bool:
    try:
        page.goto("https://web.max.ru", timeout=15000)
        page.wait_for_timeout(4000)
        return bool(page.query_selector("div[class*='chat'], div[class*='group']"))
    except:
        return False


def parse_max_group_media() -> List[Dict]:
    print("🔥 ПАРСИНГ: seen_messages.json + СТАРЫЕ→НОВЫЕ")
    load_message_cache()
    load_photo_cache()
    
    human_posts = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={'width': 1920, 'height': 1080},
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            slow_mo=50
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        
        try:
            if not session_is_valid(page):
                print("📱 Логиньтесь вручную...")
                page.goto("https://web.max.ru")
                page.wait_for_timeout(5000)
                phone_input = page.query_selector("input[type='tel']")
                if phone_input:
                    phone_input.fill(MAX_PHONE)
                    page.click("button")
                    page.wait_for_timeout(120000)
            
            page.goto(MAX_GROUP_URL, timeout=60000)
            page.wait_for_timeout(10000)
            chronological_scroll(page, MAX_GROUP_URL)
            
            selectors = [
                "div[class*='message']", "div[class*='chat-message']", 
                "div[class*='post']", ".bubble", "[data-testid*='message']",
                "div[role='listitem']", ".message-content"
            ]
            
            all_candidates = []
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    print(f"🔍 {selector}: {len(elements)}")
                    all_candidates.extend(elements)
                except:
                    pass
            
            post_candidates = []
            seen_timestamps = set()
            
            for elem in all_candidates:
                try:
                    text = elem.text_content().strip()
                    if len(text) < 15 or not is_human_message(text):
                        continue
                    
                    timestamp, _ = extract_timestamp(text, elem)
                    timestamp_key = f"{int(timestamp)}_{hash(text[:50])}"
                    
                    if timestamp_key in seen_timestamps:
                        continue
                    
                    seen_timestamps.add(timestamp_key)
                    post_candidates.append({
                        'element': elem, 'text': text, 'timestamp': timestamp
                    })
                except:
                    continue
            
            post_candidates.sort(key=lambda x: x['timestamp'])  # СТАРЫЕ ПЕРВЫМИ
            print(f"📊 Постов (СТАРЫЕ→НОВЫЕ): {len(post_candidates)}")
            
            photo_posts = 0
            text_posts = 0
            
            for i, candidate in enumerate(post_candidates[:100]):
                try:
                    elem = candidate['element']
                    text = candidate['text']
                    
                    post = {'name': '👤', 'text': text}
                    if not is_new_message(post):  # seen_messages.json
                        continue
                    
                    name = "👤"
                    name_elem = elem.query_selector("[class*='name'], [class*='author'], [class*='user']")
                    if name_elem:
                        name = name_elem.text_content().strip()[:30]
                    
                    media_files = []
                    imgs = elem.query_selector_all("img")
                    for img in imgs:
                        src = (img.get_attribute("src") or img.get_attribute("data-src"))
                        if not src or len(src) < 60:
                            continue
                        
                        if not is_photo_not_avatar(src, img):
                            continue
                        
                        local_path = download_file(src)  # cache_file.json
                        if local_path:
                            media_files.append({
                                'url': src, 'local_path': local_path, 'type': 'image'
                            })
                    
                    post_data = {
                        'id': f'post_{i}_{int(time.time())}',
                        'name': name,
                        'text': text[:500],
                        'media_files': media_files,
                        'timestamp': candidate['timestamp']
                    }
                    
                    human_posts.append(post_data)
                    
                    if media_files:
                        photo_posts += 1
                        display_time = time.strftime('%H:%M', time.localtime(candidate['timestamp']))
                        print(f"✅ 📸 #{photo_posts} [{display_time}] {name}")
                    else:
                        text_posts += 1
                        print(f"✅ 💬 #{text_posts} {name}")
                    
                except:
                    continue
            
        finally:
            browser.close()
    
    print(f"🎉 {photo_posts} ФОТО + {text_posts} ТЕКСТ = {len(human_posts)} ПОСТОВ!")
    return human_posts


def is_new_post(post: dict) -> bool:
    return is_new_message(post)
