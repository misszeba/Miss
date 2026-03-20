import os
import json
import time
import shutil
import yt_dlp
import requests
import subprocess
import re
from deep_translator import GoogleTranslator
from telebot import types
from telebot.types import InputMediaPhoto, InputMediaVideo

# ==================== CONFIG ====================
TOOL_INFO = {
    "label": "🐦 Twitter/X DL",
    "callback": "plugin_twitter_menu"
}

SETTINGS_FILE = "plugin_data_twitter.json"
COOKIES_FILE = "cookies.txt" 
MAX_SIZE_MB = 45  # ৫০ এমবি-র নিচে নিরাপদ সীমা
# ================================================

def get_user_config(chat_id):
    # ডিফল্ট সেটিংসে show_link: True রাখা হয়েছে
    default = {"trans": False, "power": True, "show_link": True}
    if not os.path.exists(SETTINGS_FILE): return default
    try:
        with open(SETTINGS_FILE, 'r') as f: 
            data = json.load(f)
            return data.get(str(chat_id), default)
    except: return default

def update_user_config(chat_id, key, value):
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f: data = json.load(f)
        except: pass
    
    current = data.get(str(chat_id), {"trans": False, "power": True, "show_link": True})
    current[key] = value
    data[str(chat_id)] = current
    with open(SETTINGS_FILE, 'w') as f: json.dump(data, f)

# 🎞 ভিডিও স্প্লিট করার ফাংশন (অপরিবর্তিত)
def split_video(file_path, output_dir):
    try:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return []
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        if file_size <= MAX_SIZE_MB: return [file_path]
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file_path}"'
        duration_output = subprocess.check_output(cmd, shell=True).decode().strip()
        if not duration_output: return [file_path]
        duration = float(duration_output)
        parts_count = int(file_size / MAX_SIZE_MB) + 1
        part_duration = duration / parts_count
        split_files = []
        for i in range(parts_count):
            start_time = i * part_duration
            output_file = os.path.join(output_dir, f"part_{i+1}_{os.path.basename(file_path)}")
            split_cmd = f'ffmpeg -ss {start_time} -t {part_duration} -i "{file_path}" -c copy -avoid_negative_ts 1 "{output_file}" -y -loglevel quiet'
            subprocess.run(split_cmd, shell=True)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                split_files.append(output_file)
        return split_files if split_files else [file_path]
    except Exception as e:
        print(f"Split Error: {e}")
        return [file_path]

# 🔄 VxTwitter API
def fetch_vxtwitter_api(url):
    try:
        match = re.search(r'status/(\d+)', url)
        if not match: return None
        tweet_id = match.group(1)
        api_url = f"https://api.vxtwitter.com/Twitter/status/{tweet_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200: return r.json()
    except Exception as e:
        print(f"VxAPI Error: {e}")
    return None

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda c: c.data == "plugin_twitter_menu")
    def twitter_menu(call):
        conf = get_user_config(call.message.chat.id)
        msg = "🐦 **Twitter/X Downloader**\n\nলিঙ্ক পাঠানোর পর স্পেস দিয়ে কিছু লিখলে সেটি কাস্টম ক্যাপশন হিসেবে সেট হবে।"
        mk = types.InlineKeyboardMarkup(row_width=2)
        
        # বাটন লজিক
        p_status = "🔴 OFF" if conf.get('power') else "🟢 ON"
        t_status = "❌ Trans" if conf.get('trans') else "✅ Trans"
        l_status = "✅ Show URL" if conf.get('show_link', True) else "❌ Show URL"
        
        mk.add(types.InlineKeyboardButton(p_status, callback_data="tw_toggle_power"),
               types.InlineKeyboardButton(t_status, callback_data="tw_toggle_trans"))
        mk.add(types.InlineKeyboardButton(l_status, callback_data="tw_toggle_show_link"))
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="gm_tools"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("tw_toggle_"))
    def toggles(call):
        key = call.data.replace("tw_toggle_", "")
        conf = get_user_config(call.message.chat.id)
        update_user_config(call.message.chat.id, key, not conf.get(key))
        twitter_menu(call)

    @bot.message_handler(func=lambda m: m.text and ("twitter.com" in m.text or "x.com" in m.text))
    def start_download(message):
        chat_id = message.chat.id
        conf = get_user_config(chat_id)
        if not conf.get('power', True): return

        parts = message.text.split(maxsplit=1)
        url = parts[0].strip()
        custom_cap = parts[1].strip() if len(parts) > 1 else None

        status = bot.send_message(chat_id, "⏳ **Analyzing Twitter Post...**")
        dl_dir = f"temp_tw_{chat_id}_{int(time.time())}"
        os.makedirs(dl_dir, exist_ok=True)
        
        final_caption = ""
        media_list = [] 

        # --- চেষ্টা ১: yt-dlp ---
        ydl_opts = {
            'outtmpl': f'{dl_dir}/%(id)s_%(index)s.%(ext)s',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None
        }

        success_ydl = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    files = [os.path.join(dl_dir, f) for f in os.listdir(dl_dir)]
                    valid_files = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 0]
                    if valid_files:
                        success_ydl = True
                        text = info.get('description') or info.get('title') or "Twitter Media"
                        if conf.get('trans') and text:
                            try: text = GoogleTranslator(source='auto', target='bn').translate(text)
                            except: pass
                        
                        # ক্যাপশন লজিক
                        final_caption = text
                        if conf.get('show_link', True):
                            final_caption += f"\n\n🔗 **Source:** {url}"

                        for f_path in sorted(valid_files):
                            if f_path.lower().endswith(('.mp4', '.mov', '.webm', '.mkv')):
                                parts = split_video(f_path, dl_dir)
                                for p in parts: media_list.append(('video_file', p))
                            elif f_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                media_list.append(('photo_file', f_path))
        except: pass

        # --- চেষ্টা ২: VxTwitter API ---
        if not success_ydl:
            api_data = fetch_vxtwitter_api(url)
            if api_data:
                text = api_data.get('text', 'Twitter Media')
                if conf.get('trans') and text:
                    try: text = GoogleTranslator(source='auto', target='bn').translate(text)
                    except: pass
                
                final_caption = text
                if conf.get('show_link', True):
                    final_caption += f"\n\n🔗 **Source:** {url}"

                media_extended = api_data.get('media_extended', [])
                for idx, m in enumerate(media_extended):
                    m_url, m_type = m.get('url'), m.get('type')
                    if m_type == 'image': media_list.append(('photo_url', m_url))
                    elif m_type in ['video', 'gif']:
                        try:
                            r = requests.get(m_url, stream=True)
                            f_path = os.path.join(dl_dir, f"vx_vid_{idx}.mp4")
                            with open(f_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                            if os.path.exists(f_path) and os.path.getsize(f_path) > 0:
                                parts = split_video(f_path, dl_dir)
                                for p in parts: media_list.append(('video_file', p))
                        except: pass

        # --- কাস্টম ক্যাপশন হ্যান্ডলিং ---
        if custom_cap:
            final_caption = f"📝 **Caption:** {custom_cap}"
            if conf.get('show_link', True):
                final_caption += f"\n\n🔗 **Source:** {url}"

        # --- ফাইনাল সেন্ডিং ---
        if media_list:
            try:
                tg_media = []
                for m_type, m_source in media_list:
                    if 'file' in m_type:
                        if not os.path.exists(m_source) or os.path.getsize(m_source) == 0: continue
                        f_handle = open(m_source, 'rb')
                        if m_type == 'video_file': tg_media.append(InputMediaVideo(f_handle))
                        else: tg_media.append(InputMediaPhoto(f_handle))
                    elif m_type == 'photo_url':
                        tg_media.append(InputMediaPhoto(m_source))

                if not tg_media:
                    bot.edit_message_text("❌ Media is empty or corrupted.", chat_id, status.message_id)
                    return

                tg_media[0].caption = final_caption[:1024]
                tg_media[0].parse_mode = "Markdown"

                if len(tg_media) == 1:
                    m = tg_media[0]
                    if isinstance(m, InputMediaVideo):
                        bot.send_video(chat_id, m.media, caption=m.caption, parse_mode=m.parse_mode)
                    else:
                        bot.send_photo(chat_id, m.media, caption=m.caption, parse_mode=m.parse_mode)
                else:
                    bot.send_media_group(chat_id, tg_media)
                
                bot.delete_message(chat_id, status.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ Error: {str(e)}", chat_id, status.message_id)
        else:
            bot.edit_message_text("❌ No media found.", chat_id, status.message_id)

        if os.path.exists(dl_dir): shutil.rmtree(dl_dir, ignore_errors=True)
