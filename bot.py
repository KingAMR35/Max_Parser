import telebot
import hashlib
import json
import os
import time
import re
from max_playwright_parser import parse_max_group_media
from config import BOT_TOKEN
from telebot import types

print("🚀 MAX Parser Bot запущен")
bot = telebot.TeleBot(BOT_TOKEN)

ADMIN_ID = 5213315899
CACHE_FILE = "seen_messages.json"
seen_hashes = set()

def escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\\\{char}')
    return text

def load_cache():
    global seen_hashes
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                seen_hashes = set(json.load(f).get('hashes', []))
            print(f"📦 Кэш: {len(seen_hashes)} сообщений")
        except:
            seen_hashes = set()

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
    
    result = f"{status} 🆕 #{new_count}\n"
    result += f"{post['name']} :\n"
    result += f"{main_text}\n"
    result += f"{time_str}"
    
    return result.strip()

load_cache()

def menu_button():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    button = types.InlineKeyboardButton(text='▶️ Начать парсинг', callback_data='button')
    button1 = types.InlineKeyboardButton(text='🗑 Очистить кэш', callback_data='button1')
    button2 = types.InlineKeyboardButton(text='📊 Статистика', callback_data='button2')
    button3 = types.InlineKeyboardButton(text='🤖Тест бота', callback_data='button3')
    keyboard.row(button)
    keyboard.row(button1, button2)
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
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Это команда только для админа 🤓. И даже не вздумай клянчить админку😁.\n\nИди почитай инструкцию --> /help", reply_markup=comeback111())
        return
    bot.send_message(message.chat.id, "А вот и менюшка😊", reply_markup=menu_button())

@bot.message_handler(commands=['help'])
def start(message):
    bot.reply_to(message, "Всем привет! 👋 Этот бот парсит сообщения из MAX (фото+видео+текст). Только для админа!")

@bot.callback_query_handler(func=lambda call: call.data == 'button01')
def callback_message(call):
    bot.edit_message_text("А вот и менюшка😊", call.message.chat.id, call.message.message_id, reply_markup=menu_button())

@bot.callback_query_handler(func=lambda call: call.data == 'button001')
def callback_message2(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'button3')
def test(call):
    if call.from_user.id != ADMIN_ID:
        bot.send_message(call.message.chat.id, "Это команда только для админа 🤓.\n\nИди почитай инструкцию --> /help", reply_markup=comeback111())
        return
    bot.edit_message_text("✅ БОТ РАБОТАЕТ!", call.message.chat.id, call.message.message_id, reply_markup=comeback())

@bot.callback_query_handler(func=lambda call: call.data == 'button')
def parse_max_command(call):
    chat_id = call.message.chat.id
    if call.from_user.id != ADMIN_ID:
        bot.send_message(chat_id, "Это команда только для админа 🤓.\n\nИди почитай инструкцию --> /help", reply_markup=comeback111())
        return
    
    print(f"🔍 /parsemax от {chat_id}")
    bot.edit_message_text("⏳ Парсю MAX...", chat_id, call.message.message_id, reply_markup=comeback())

    try:
        posts = parse_max_group_media()
        new_count = 0

        if not posts:
            bot.send_message(chat_id, "📭 Сообщений не найдено")
            return

        print(f"📢 Найдено {len(posts)} постов")

        for post in posts:
            if is_new_message(post):
                status = "👤"  

                media_files = post.get('media_files', [])
                media_sent = send_media_safely(chat_id, media_files, status, new_count+1, post['name'])

                msg_text = format_message(post, status, new_count+1, media_sent)
                bot.send_message(chat_id, msg_text)
                
                new_count += 1
                print(f"✅ Отправлено: {post['name']} | 📁{media_sent}/{len(media_files)} файлов")

        result = f"✅ {new_count} НОВЫХ из {len(posts)}" if new_count else "📭 Новых сообщений нету"
        bot.send_message(chat_id, result)
        if new_count > 0:
            save_cache()

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == 'button1')
def clear_cache(call):
    if call.from_user.id != ADMIN_ID:
        bot.send_message(call.message.chat.id, "Это команда только для админа 🤓.\n\nИди почитай инструкцию --> /help", reply_markup=comeback111())
        return
    global seen_hashes
    seen_hashes.clear()
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    bot.edit_message_text("🗑 Кэш очищен!", call.message.chat.id, call.message.message_id, reply_markup=comeback())

@bot.callback_query_handler(func=lambda call: call.data == 'button2')
def status(call):
    if call.from_user.id != ADMIN_ID:
        bot.send_message(call.message.chat.id, "Это команда только для админа 🤓.\n\nИди почитай инструкцию --> /help", reply_markup=comeback111())
        return
    cache_count = len(seen_hashes)
    bot.edit_message_text(f"📊 СТАТИСТИКА:\n📦 Кэш: {cache_count} сообщений", call.message.chat.id, call.message.message_id, reply_markup=comeback())

try:
    bot.infinity_polling(none_stop=True)
except KeyboardInterrupt:
    print("🛑 Остановлен")
    save_cache()
