import telebot
from config import bot
from . import database
from . import welcome
from . import antilink
from . import banword
from . import chat_tool  # ✅ চ্যাট টুল ইমপোর্ট

# ==========================================
# 🤖 1. বটের স্ট্যাটাস পরিবর্তন হ্যান্ডলার (Group & Channel)
# ==========================================
@bot.my_chat_member_handler()
def on_bot_status_change(update):
    chat = update.chat
    new_status = update.new_chat_member.status
    
    # বট অ্যাডমিন হলে ডাটাবেসে গ্রুপ/চ্যানেল সিঙ্ক করবে
    if new_status == 'administrator':
        if database.sync_group(chat.id):
            bot.send_message(chat.id, f"✅ **Connected!** I am now your {chat.type} manager.")
    
    # বট শুধু মেম্বার হিসেবে থাকলে (শুধুমাত্র গ্রুপের জন্য প্রযোজ্য)
    elif new_status == 'member' and chat.type != 'channel':
        bot.send_message(chat.id, "👋 **Hello!** Please make me an **Admin** to activate management features.")
    
    # বটকে বের করে দিলে বা এডমিন থেকে সরিয়ে দিলে ডাটাবেস থেকে মুছে ফেলবে
    elif new_status in ['left', 'kicked']:
        database.remove_group(chat.id)

# ==========================================
# 👋 2. নতুন মেম্বার জয়েন হ্যান্ডলার
# ==========================================
@bot.message_handler(content_types=['new_chat_members'])
def on_new_member(message):
    try:
        # মেম্বার জয়েন করলে ওয়েলকাম মেসেজ পাঠাবে
        welcome.send_welcome(message)
    except Exception as e:
        print(f"Welcome Event Error: {e}")

# ==========================================
# 💬 3. ইনবক্স চ্যাট টুল (মাল্টি-টার্গেট সাপোর্ট)
# ==========================================

# ✅ [NEW FILTER] টেক্সট অথবা ক্যাপশন চেক করার কাস্টম ফাংশন
def is_chat_command(m):
    # ১. অবশ্যই প্রাইভেট চ্যাট হতে হবে
    if m.chat.type != 'private': return False
    
    # ২. টেক্সট অথবা ক্যাপশন বের করা
    content = m.text or m.caption
    if not content: return False
    
    # ৩. যদি '/' দিয়ে শুরু হয় এবং সাধারণ কমান্ড (start/help) না হয়
    # তাহলেই এটি চ্যাট টুলের জন্য ভ্যালিড কমান্ড
    if content.strip().startswith('/') and not content.strip().startswith(('/start', '/help', '/reload', '/login', '/panel', '/auth')):
        return True
        
    return False

# হ্যান্ডলার এখন সব ধরণের মিডিয়া কন্টেন্ট সাপোর্ট করবে
@bot.message_handler(func=is_chat_command, content_types=['text', 'photo', 'video', 'document', 'animation', 'audio', 'voice'])
def handle_inbox_chat_commands(message):
    try:
        # চ্যাট টুলের মাল্টি-টার্গেট প্রসেসরে পাঠানো হচ্ছে
        chat_tool.handle_inbox_command(message)
    except Exception as e:
        print(f"Inbox Chat Tool Error: {e}")

# ==========================================
# 🛡️ 4. মেসেজ স্ক্যানার (শুধুমাত্র গ্রুপের জন্য)
# ==========================================
@bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'], 
                     content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation'])
def scan_incoming_messages(message):
    try:
        # ১. এন্টিলিংক চেক
        antilink.scan_message(message)
        
        # ২. ব্যানওয়ার্ড চেক
        banword.scan_message(message)
            
    except Exception as e:
        print(f"Message Scan Error: {e}")

# ==========================================
# 🛠 5. ম্যানুয়াল রিলোড কমান্ড
# ==========================================
@bot.message_handler(commands=['reload'])
def cmd_reload(message):
    if message.chat.type in ['group', 'supergroup', 'channel']:
        if database.sync_group(message.chat.id):
            bot.reply_to(message, "✅ **Database Refreshed!**\nAdmin list and settings have been updated.")
        else:
            bot.reply_to(message, "❌ **Sync Failed!** Make sure I am an Admin.")
