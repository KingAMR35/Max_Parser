from playwright.sync_api import sync_playwright
import re
import time
import requests
import os
from typing import List, Dict
from config import MAX_GROUP_URL, MAX_PHONE

SESSION_DIR = "max_session"
os.makedirs(SESSION_DIR, exist_ok=True)

def download_file(url: str, filename: str = None) -> str:
    os.makedirs("downloads", exist_ok=True)
    if not filename:
        filename = f"max_{int(time.time())}"
    
    url_lower = url.lower()
    if not filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.mov', '.avi')):
        if any(ext in url_lower for ext in ['.mp4', 'video', '/video/']):
            filename += '.mp4'
        elif '.webm' in url_lower:
            filename += '.webm'
        elif any(ext in url_lower for ext in ['.jpg', '.jpeg', 'image', '/img/']):
            filename += '.jpg'
        else:
            filename += '.jpg'
    
    filename = re.sub(r'[^\w\-\.]', '_', filename)[:100]
    filepath = f"downloads/{filename}"
    
    try:
        print(f"📥 Скачиваю: {url[:80]}...")
        response = requests.get(url, timeout=30, stream=True)
        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"   📊 {progress:.1f}%", end='\r')
            
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            print(f"\n✅ Сохранено: {filepath} ({size_mb:.1f} MB)")
            return filepath
    except Exception as e:
        print(f"❌ Скачивание: {e}")
    return None

def is_human_message(text: str) -> bool:
    text = text.strip().lower()
    
    bot_phrases = [
        'теперь в max', 'напишите что-нибудь', 'сферум',
        'удалил', 'удалила', 'изменил', 'изменила', 'обновил', 'обновила',
        'вошел', 'вошла', 'покинул', 'покинула', 'пригласил', 'исключил'
    ]
    
    if any(phrase in text for phrase in bot_phrases):
        print(f"🤖 Бот: '{text[:40]}...'")
        return False

    return (15 < len(text) < 600 and 
            text[0].isalpha() and 
            not re.match(r'^\d+$', text))

def parse_max_group_media() -> List[Dict]:
    human_posts = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  
            viewport={'width': 1920, 'height': 1080},
            slow_mo=300  
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        print("🔍 MAX автологин...")
        
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
                    page.wait_for_timeout(120000)  
                else:
                    print("✅ Уже авторизованы")
            except Exception as e:
                print(f"⚠️ Авторизация: {e}")
        
        print(f"📱 Переходим: {MAX_GROUP_URL}")
        page.goto(MAX_GROUP_URL)
        page.wait_for_timeout(10000)  
        
        print("⬆️ Скроллим к новым сообщениям...")
        page.keyboard.press("Home")
        page.wait_for_timeout(2000)
        page.keyboard.press("Home")
        page.wait_for_timeout(2000)
        page.keyboard.press("Control+Home")  
        page.wait_for_timeout(4000)
        
        message_selectors = [
            "div[class*='message']",
            "div[class*='chat-message']", 
            "div[class*='post']",
            ".bubble",
            "[data-testid*='message']",
            "div[role='listitem']"
        ]
        
        all_candidates = []
        for selector in message_selectors:
            try:
                elements = page.query_selector_all(selector)[:20]  
                print(f"   {selector}: {len(elements)}")
                all_candidates.extend(elements)
            except Exception as e:
                print(f"   {selector}: ошибка")
        
        print(f"📦 Кандидатов найдено: {len(all_candidates)}")
        
        human_count = 0
        for i, elem in enumerate(set(all_candidates[:25])):  
            try:
                full_text = elem.text_content().strip()
                
                if not is_human_message(full_text):
                    continue
                
                name = "Пользователь"
                name_selectors = [
                    "[class*='name']", "[class*='author']", 
                    "[class*='username']", ".user-name", 
                    "span[title]", ".author-name"
                ]
                for name_sel in name_selectors:
                    name_elem = elem.query_selector(name_sel)
                    if name_elem:
                        name_text = name_elem.text_content().strip()
                        if 2 < len(name_text) < 50 and name_text != full_text[:len(name_text)]:
                            name = name_text[:30]
                            break
                
                media_files = []
                
                imgs = elem.query_selector_all("img")
                for img in imgs[:3]:
                    src = (img.get_attribute("src") or 
                           img.get_attribute("data-src") or 
                           img.get_attribute("srcset"))
                    
                    if not src or len(src) < 50:
                        continue
                    
                    src_lower = src.lower()
                    
                    avatar_banlist = [
                        'avatar', 'profile', 'userpic', 'photo-', 'icon', 'logo', 
                        'emoji', 'sticker', 'thumb', 'preview', 'small', 'circle', 
                        'round', 'badge', 'placeholder', '/static/', '/assets/', 
                        'default', 'blank', 'user-', 'profile-'
                    ]
                    
                    if any(ban in src_lower for ban in avatar_banlist):
                        print(f"🚫 АВАТАРКА пропущена: {src[:60]}...")
                        continue
                    
                    width = img.get_attribute("width")
                    height = img.get_attribute("height")
                    if width and int(width) < 200:
                        continue
                    if height and int(height) < 200:
                        continue
                    
                    try:
                        box = img.bounding_box()
                        if box and (box['width'] < 150 or box['height'] < 150):
                            print(f"🚫 Маленькое изображение: {box['width']}x{box['height']}")
                            continue
                    except:
                        pass
                    
                    print(f"🖼️ ИЗОБРАЖЕНИЕ ОК: {src[:60]}...")
                    local_path = download_file(src)
                    if local_path:
                        media_files.append({
                            'url': src,
                            'local_path': local_path,
                            'type': 'image'
                        })
                
                video_selectors = ["video", "video source", "[data-video]"]
                for video_sel in video_selectors:
                    video_elements = elem.query_selector_all(video_sel)
                    for video_elem in video_elements[:1]:
                        src = (video_elem.get_attribute("src") or 
                               video_elem.get_attribute("data-src"))
                        
                        if src and len(src) > 50:
                            print(f"🎥 ВИДЕО ОК: {src[:60]}...")
                            local_path = download_file(src)
                            if local_path:
                                media_files.append({
                                    'url': src,
                                    'local_path': local_path,
                                    'type': 'video'
                                })
                                break
                
                post_data = {
                    'id': f'human_{human_count}_{int(time.time())}',
                    'name': name,
                    'text': full_text[:450],
                    'media_files': media_files,
                }
                
                human_posts.append(post_data)
                human_count += 1
                media_types = [m['type'] for m in media_files]
                print(f"✅ #{human_count} 👤{name}: '{full_text[:60]}...' | 📁{len(media_files)} {media_types}")
                
                if human_count >= 5:  
                    break
                    
            except Exception as e:
                print(f"❌ Элемент {i}: {e}")
                continue
        
        browser.close()
    
    print(f"🎉 НАЙДЕНО {len(human_posts)} человеческих сообщений")
    return human_posts

if __name__ == "__main__":
    print("ТЕСТ парсера...")
    posts = parse_max_group_media()
    print("\n📋 РЕЗУЛЬТАТ:")
    for i, post in enumerate(posts, 1):
        print(f"{i}. 👤 {post['name']}")
        print(f"   {post['text'][:100]}...")
        if post['media_files']:
            for media in post['media_files']:
                print(f"   📁 {media['type']}: {media['local_path']}")
    print(f"\n✅ Готово! {len(posts)} сообщений")
