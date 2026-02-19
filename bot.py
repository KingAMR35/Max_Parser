import telebot
import hashlib
import json
import os
import time
import re
import threading
from datetime import datetime
from max_playwright_parser import parse_max_group_media
from configuration import BOT_TOKEN
from telebot import types

print("🚀 MAX Parser Bot запущен")
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = 5213315899
CACHE_FILE = "seen_messages.json"
CACHE_FILE2 = "seen_images.json"
seen_hashes = set()

PARSING_ACTIVE = False
PARSING_THREAD = None
CURRENT_CHAT_ID = None

def escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\\\{char}')
    return text

def load_cache():
    global seen_hashes
    all_hashes = set()
    
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_hashes.update(data.get('hashes', []))
                all_hashes.update(data.get('message_hashes', []))
            print(f"📦 Кэш загружен: {len(all_hashes)} сообщений")
        except Exception as e:
            print(f"❌ Ошибка кэша: {e}")
    
    seen_hashes = all_hashes


def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'hashes': list(seen_hashes)}, f)
    except:
        pass

def is_new_message(post: dict) -> bool:
    full_text = f"{post['name']}:{post['text']}"
    text_hash = hashlib.md5(full_text.encode()).hexdigest()
    if text_hash in seen_hashes:
        return False
    seen_hashes.add(text_hash)
    return True

def send_media_safely(chat_id, media_files, status, new_count, post_name):
    sent_count = 0
    for media in media_files:
        local_path = media['local_path']
        media_type = media['type']
        
        if not os.path.exists(local_path):
            print(f"❌ Файл НЕ существует: {local_path}")
            continue
        
        file_size = os.path.getsize(local_path)
        if file_size > 50 * 1024 * 1024:
            print(f"❌ Файл слишком большой: {file_size/1024/1024:.1f}MB")
            continue
        
        try:
            caption = f"{status} 🆕 #{new_count+1}\n{post_name}"
            
            if media_type == 'image':
                with open(local_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=caption)
                    print(f"✅ ОТПРАВЛЕНО ИЗОБРАЖЕНИЕ: {local_path}")
            elif media_type == 'video':
                with open(local_path, 'rb') as video:
                    bot.send_video(chat_id, video, caption=caption, supports_streaming=True)
                    print(f"✅ ОТПРАВЛЕНО ВИДЕО: {local_path}")
            
            sent_count += 1
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Ошибка отправки {media_type}: {e}")
    
    return sent_count

def format_message(post, status, new_count, media_sent):
    full_text = post['text'].strip()
    
    time_match = re.search(r'\s+(\d{2}:\d{2})$', full_text)
    
    if time_match:
        time_str = time_match.group(1)
        main_text = full_text[:time_match.start()].strip()
    else:
        time_str = ""
        main_text = full_text
    
    result = f"{status} 🆕 *{new_count}*\n"
    result += f"*{main_text}*\n"
    result += f"{time_str}"
    
    return result.strip()

# АВТОПАРСИНГ
def parse_max_loop(chat_id):
    """Бесконечный цикл парсинга каждые 20 секунд"""
    global PARSING_ACTIVE
    while PARSING_ACTIVE:
        try:
            print(f"🔄 Автопарсинг для чата {chat_id}...")
            
            posts = parse_max_group_media()
            new_count = 0

            if not posts:
                print("📭 Новых сообщений не найдено")
            else:
                print(f"📢 Найдено {len(posts)} постов")
                
                for post in posts:
                    if is_new_message(post):
                        status = "👤"
                        media_files = post.get('media_files', [])
                        media_sent = send_media_safely(chat_id, media_files, status, new_count+1, post['name'])

                        msg_text = format_message(post, status, new_count+1, media_sent)
                        bot.send_message(chat_id, msg_text, parse_mode='Markdown')
                        new_count += 1
                        print(f"✅ Отправлено: {post['name']} | 📁{media_sent}/{len(media_files)} файлов")

                if new_count > 0:
                    save_cache()
                    result = f"✅ *{new_count} НОВЫХ* из {len(posts)} всего"
                    bot.send_message(chat_id, result, parse_mode='Markdown', reply_markup=comeback111())
            
            time.sleep(20) 
            
        except Exception as e:
            print(f"❌ Ошибка автопарсинга: {e}")
            time.sleep(20)

load_cache()

def menu_button():
    global PARSING_ACTIVE
    status_text = "▶️ Начать парсинг" if not PARSING_ACTIVE else "⏹ Остановить парсинг"
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    button = types.InlineKeyboardButton(text=status_text, callback_data='button')
    button1 = types.InlineKeyboardButton(text='🗑 Очистить кэш', callback_data='button1')
    button2 = types.InlineKeyboardButton(text='📊 Статистика', callback_data='button2')
    button3 = types.InlineKeyboardButton(text='🤖 Тест бота', callback_data='button3')
    button4 = types.InlineKeyboardButton(text='🆕 Обновления', callback_data='button4')
    button5 = types.InlineKeyboardButton(text='📌 О боте', callback_data='button5')
    keyboard.row(button)
    keyboard.row(button1, button2)
    keyboard.row(button4, button5)
    keyboard.row(button3)
    return keyboard

def comeback():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    button01 = types.InlineKeyboardButton(text='Вернуться 🔙', callback_data='button01')
    keyboard.row(button01)
    return keyboard

def comeback111():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    button001 = types.InlineKeyboardButton(text='Удалить 🗑', callback_data='button001')
    keyboard.row(button001)
    return keyboard

@bot.message_handler(commands=['start'])
def start_bot(message):
    status_text = "🟢 Активен" if PARSING_ACTIVE else "🔴 Остановлен"
    bot.send_message(message.chat.id, f"*🚀 MAX_Parser готов!*\nСтатус: {status_text}\n\nВыберите действие:", 
                    reply_markup=menu_button(), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'button')
def parse_max_command(call):
    global PARSING_ACTIVE, PARSING_THREAD, CURRENT_CHAT_ID
    chat_id = call.message.chat.id
    
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="Это команда только для админа 🤓.\n\nИди почитай 📌О боте")
        return
    
    if PARSING_ACTIVE:
        PARSING_ACTIVE = False
        CURRENT_CHAT_ID = None
        bot.edit_message_text("🛑 *Автопарсинг остановлен*", chat_id, call.message.message_id, 
                            reply_markup=comeback(), parse_mode='Markdown')
        print("🛑 Автопарсинг остановлен")
        return
    
    PARSING_ACTIVE = True
    CURRENT_CHAT_ID = chat_id
    bot.edit_message_text("▶️ *Автопарсинг ЗАПУЩЕН*\n⏳ Проверка каждые *20 сек*...", 
                         chat_id, call.message.message_id, reply_markup=comeback(), parse_mode='Markdown')
    print(f"🚀 Автопарсинг запущен для чата {chat_id}")
    
    PARSING_THREAD = threading.Thread(target=parse_max_loop, args=(chat_id,), daemon=True)
    PARSING_THREAD.start()

@bot.callback_query_handler(func=lambda call: call.data == 'button01')
def callback_message(call):
    status_text = "🟢 Активен" if PARSING_ACTIVE else "🔴 Остановлен"
    bot.edit_message_text(f"*🚀 MAX_Parser готов!*\nСтатус: {status_text}\n\nВыберите действие:", 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=menu_button(), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'button001')
def callback_message2(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'button3')
def test(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="Это команда только для админа 🤓.\n\nИди почитай 📌О боте")
        return
    bot.edit_message_text("✅ БОТ РАБОТАЕТ!", call.message.chat.id, call.message.message_id, reply_markup=comeback())

@bot.callback_query_handler(func=lambda call: call.data == 'button1')
def clear_cache(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="Это команда только для админа 🤓.\n\nИди почитай 📌О боте")
        return
    global seen_hashes
    seen_hashes.clear()
    if os.path.exists(CACHE_FILE) and os.path.exists(CACHE_FILE2):
        os.remove(CACHE_FILE)
        os.remove(CACHE_FILE2)
    bot.edit_message_text("🗑 Кэш очищен!", call.message.chat.id, call.message.message_id, reply_markup=comeback())

@bot.callback_query_handler(func=lambda call: call.data == 'button2')
def status(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="Это команда только для админа 🤓.\n\nИди почитай 📌О боте")
        return
    global seen_hashes
    cache_count = len(seen_hashes)
    status_text = "🟢 Активен" if PARSING_ACTIVE else "🔴 Остановлен"
    bot.edit_message_text(f"📊 СТАТИСТИКА:\n📦 Кэш: *{cache_count} сообщений*\n Парсинг: {status_text}", 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=comeback(), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'status_only')
def status_only(call):
    global PARSING_ACTIVE
    status_text = "🟢 Активен" if PARSING_ACTIVE else "🔴 Остановлен"
    bot.answer_callback_query(call.id, text=f"Статус парсинга: {status_text}")

@bot.callback_query_handler(func=lambda call: call.data == 'button4')
def new(call):
    bot.edit_message_text("""*Всем привет 👋*  
    
Представляю вам все обновления *Max_parser!*

🚀 *Что изменилось: * 

🕰️ Бот отправляет правильное время(когда его отправили в максе).  
📸 Отправляет фотографии, сохраняя их качество.  
📲 Каждое новое сообщение доставляется аккуратно и чётко, никаких пропусков или дубликатов.  
💬 Сообщения стали красивыми, более удобными для чтения.
✨ Добавлена удобная кнопка, которая автоматически собирает сообщения каждые 20 секунд.
🔥 Больше никакой ручной работы — информация сама прилетит к вам вовремя!
🚀 Сейчас проводится тестировка хоста Replit, надеюсь, что будет работать штатно.
    """, 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=comeback(), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'button5')
def info(call):
    bot.edit_message_text("""*Всем привет👋*
    
Данный бот специально разработан для удобной пересылки сообщений из Макса сюда👇.
Только админ может управлять им. Если хотите, то можете попробовать:)
Вам доступны только кнопки *🆕Обновления* и *📌О боте*.
                      
*Приятного вам использования!*""", 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=comeback(), parse_mode='Markdown')

try:
    bot.infinity_polling(none_stop=True)
except KeyboardInterrupt:
    print("🛑 Остановлен")
    save_cache()
