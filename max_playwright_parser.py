from playwright.sync_api import sync_playwright
import re
import time
import requests
import os
from typing import List, Dict
from configuration import MAX_GROUP_URL, MAX_PHONE
from datetime import datetime, timedelta

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
    
    filename = re.sub(r'[^\\w\\-\\.]', '_', filename)[:100]
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

    return (10 < len(text) < 800 and 
            text[0].isalpha() and 
            not re.match(r'^\d+$', text))

def safe_scroll(page, target_url: str):
    print("📜 Безопасный скролл...")
    
    if target_url not in page.url:
        print(f"⚠️ Возвращаемся в чат: {target_url}")
        page.goto(target_url)
        page.wait_for_timeout(5000)
    
    for i in range(3):
        page.keyboard.press("Home")
        page.wait_for_timeout(1500)
    
    for i in range(8):
        page.keyboard.press("PageDown")
        page.wait_for_timeout(1200)
        if target_url not in page.url:
            page.goto(target_url)
            page.wait_for_timeout(3000)
            break
    
    page.wait_for_timeout(3000)
    print("✅ Скролл завершен!")

def extract_timestamp(text: str, element) -> tuple:
    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    if time_match:
        try:
            dt = datetime.strptime(time_match.group(1), '%H:%M')
            dt = dt + timedelta(hours=4)
            timestamp = dt.timestamp()
            return timestamp, 0
        except:
            pass
    
    timestamp_attrs = ['data-timestamp', 'data-time', 'title', 'datetime']
    for attr in timestamp_attrs:
        ts = element.get_attribute(attr)
        if ts:
            try:
                for fmt in ['%H:%M', '%Y-%m-%d %H:%M', '%d.%m.%Y %H:%M']:
                    dt = datetime.strptime(ts, fmt)
                    dt = dt + timedelta(hours=4)  # 🔥 +4 часа
                    return dt.timestamp(), 1
            except:
                pass
    
    try:
        box = element.bounding_box()
        if box:
            return box['y'], 2
    except:
        pass
    
    return time.time(), 3

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
            print("📱 Авторизация...")
            page.goto("https://web.max.ru")
            page.wait_for_timeout(5000)
            
            try:
                phone_input = page.query_selector("input[type='tel'], input[placeholder*='телефон']")
                if phone_input:
                    phone_input.fill(MAX_PHONE)
                    page.click("button, input[type='submit']")
                    print("❗ Введите SMS код (2 минуты)...")
                    page.wait_for_timeout(120000)
            except:
                pass
        
        print(f"📱 Чат: {MAX_GROUP_URL}")
        page.goto(MAX_GROUP_URL)
        page.wait_for_timeout(10000)
        
        safe_scroll(page, MAX_GROUP_URL)
        
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
                elements = page.query_selector_all(selector)
                print(f"🔍 {selector}: {len(elements)}")
                all_candidates.extend(elements)
            except:
                pass
        
        unique_candidates = list(set(all_candidates))
        print(f"📦 Кандидатов: {len(unique_candidates)}")
        
        post_candidates = []
        for i, elem in enumerate(unique_candidates):
            try:
                full_text = elem.text_content().strip()
                if len(full_text) < 10 or not is_human_message(full_text):
                    continue
                
                timestamp, priority = extract_timestamp(full_text, elem)
                
                post_candidates.append({
                    'element': elem,
                    'text': full_text,
                    'timestamp': timestamp,
                    'priority': priority,
                    'index': i
                })
                
            except Exception as e:
                continue
        
        post_candidates.sort(key=lambda x: (x['timestamp'], x['priority'], x['index']))
        print(f"📊 Отсортировано: {len(post_candidates)} (СТАРЫЕ → НОВЫЕ +4ч)")
        
        human_count = 0
        for candidate in post_candidates:
            elem = candidate['element']
            full_text = candidate['text']
            
            try:
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
                
                # Изображения
                imgs = elem.query_selector_all("img")
                for img in imgs[:5]:
                    src = (img.get_attribute("src") or 
                           img.get_attribute("data-src") or 
                           img.get_attribute("srcset"))
                    
                    if not src or len(src) < 50:
                        continue
                    
                    src_lower = src.lower()
                    avatar_banlist = [
                        'avatar', 'profile', 'userpic', 'photo-', 'icon', 'logo', 
                        'emoji', 'sticker', 'thumb', 'preview', 'small', 'circle'
                    ]
                    
                    if any(ban in src_lower for ban in avatar_banlist):
                        continue
                    
                    width = img.get_attribute("width")
                    height = img.get_attribute("height")
                    if width and int(width) < 150:
                        continue
                    if height and int(height) < 150:
                        continue
                    
                    try:
                        box = img.bounding_box()
                        if box and (box['width'] < 120 or box['height'] < 120):
                            continue
                    except:
                        pass
                    
                    print(f"🖼️ [{human_count+1}] {src[:60]}...")
                    local_path = download_file(src)
                    if local_path:
                        media_files.append({
                            'url': src,
                            'local_path': local_path,
                            'type': 'image'
                        })
                
                video_selectors = ["video", "video source"]
                for video_sel in video_selectors:
                    video_elements = elem.query_selector_all(video_sel)
                    for video_elem in video_elements:
                        src = (video_elem.get_attribute("src") or 
                               video_elem.get_attribute("data-src"))
                        
                        if src and len(src) > 50:
                            print(f"🎥 [{human_count+1}] {src[:60]}...")
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
                    'text': full_text[:600],
                    'media_files': media_files,
                    'timestamp': candidate['timestamp']
                }
                
                human_posts.append(post_data)
                human_count += 1
                
                try:
                    display_time = time.strftime('%H:%M', time.localtime(candidate['timestamp']))
                    print(f"✅ #{human_count} [{display_time}] 👤{name}")
                except:
                    print(f"✅ #{human_count} 👤{name}")
                
            except Exception as e:
                print(f"⚠️ Пост {human_count}: {str(e)[:50]}")
                continue
        
        browser.close()
    
    print(f"🎉 НАЙДЕНО {len(human_posts)} сообщений!")
    return human_posts

if __name__ == "__main__":
    print("🚀 ТЕСТ парсера...")
    posts = parse_max_group_media()
    print("\n📋 ПЕРВЫЕ 5 В ПОРЯДКЕ (+4ч):")
    for i, post in enumerate(posts[:5], 1):
        try:
            display_time = time.strftime('%H:%M', time.localtime(post['timestamp']))
            print(f"{i}. 👤 {post['name']} | [{display_time}]")
        except:
            print(f"{i}. 👤 {post['name']}")
        print(f"   {post['text'][:100]}...")
    print(f"\n✅ Всего: {len(posts)} сообщений")
