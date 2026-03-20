import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import bot
from . import database
import html
from datetime import datetime

# মর্ডান UI ডিভাইডার
LINE = "━━━━━━━━━━━━━━━━━━━━\n"

# --- ১. ওয়েলকাম মেসেজ জেনারেটর (ইউনিক ডাটা সহ) ---
def generate_welcome_data(chat_id, user, chat_title):
    group = database.get_group_data(chat_id)
    wlc = group.get("welcome_settings", {})
    
    first = html.escape(user.first_name or "")
    last = html.escape(user.last_name or "")
    now = datetime.now()

    # ভেরিয়েবল লিস্ট
    replacements = {
        "{ID}": str(user.id),
        "{NAME}": first,
        "{SURNAME}": last,
        "{NAMESURNAME}": f"{first} {last}".strip(),
        "{LANG}": user.language_code or "bn",
        "{DATE}": now.strftime("%d/%m/%Y"),
        "{TIME}": now.strftime("%H:%M:%S"),
        "{WEEKDAY}": now.strftime("%A"),
        "{MENTION}": f'<a href="tg://user?id={user.id}">{first}</a>',
        "{USERNAME}": f"@{user.username}" if user.username else "N/A",
        "{GROUPNAME}": html.escape(chat_title or "Group"),
        "{RULES}": "গ্রুপের নিয়ম মেনে চলুন।"
    }

    text = wlc.get("text", "Welcome {MENTION} to {GROUPNAME}!")
    for key, val in replacements.items():
        text = text.replace(key, val)
    
    # বাটন জেনারেটর
    markup = InlineKeyboardMarkup()
    btn_list = wlc.get("buttons", [])
    for row in btn_list:
        row_btns = []
        for btn in row:
            if len(btn) == 2:
                row_btns.append(InlineKeyboardButton(text=btn[0], url=btn[1]))
        markup.row(*row_btns)

    return text, markup, wlc.get("type"), wlc.get("media_id")

# --- ২. মেম্বার জয়েন হ্যান্ডলার (Real Event) ---
def send_welcome(message):
    chat_id = message.chat.id
    user = message.new_chat_members[0]
    group = database.get_group_data(chat_id)
    if not group: return
    wlc = group.get("welcome_settings", {})
    
    if not wlc.get("state", True): return

    # Always vs 1st Join লজিক (সিম্পল ইমপ্লিমেন্টেশন)
    # নোট: 'first' মুড কাজ করার জন্য ইউজারের জয়েন হিস্ট্রি চেক প্রয়োজন
    
    text, markup, m_type, media = generate_welcome_data(chat_id, user, message.chat.title)

    # Delete Last Message লজিক
    if wlc.get("delete_last", False):
        last_msg_id = wlc.get("last_msg_id")
        if last_msg_id:
            try: bot.delete_message(chat_id, last_msg_id)
            except: pass

    try:
        sent_msg = None
        if m_type == "photo" and media:
            sent_msg = bot.send_photo(chat_id, media, caption=text, parse_mode='HTML', reply_markup=markup)
        elif m_type == "video" and media:
            sent_msg = bot.send_video(chat_id, media, caption=text, parse_mode='HTML', reply_markup=markup)
        else:
            sent_msg = bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)
        
        # নতুন মেসেজ আইডি সেভ রাখা (পরবর্তীতে ডিলিট করার জন্য)
        if sent_msg:
            database.update_welcome_setting(chat_id, "last_msg_id", sent_msg.message_id)
    except Exception as e:
        print(f"Welcome Send Error: {e}")

# --- ৩. মেইন কনফিগারেশন মেনু UI ---
def show_welcome_menu(call, target_id, direct_chat_id=None):
    group = database.get_group_data(target_id)
    if not group: return
    wlc = group.get("welcome_settings", {})
    
    state_icon = "🟢 Status: ON" if wlc.get("state", True) else "🔴 Status: OFF"
    mode_text = "🔄 Always" if wlc.get("send_mode", "always") == "always" else "👤 1st Join"
    del_last_icon = "✅ Delete Last: Yes" if wlc.get("delete_last", False) else "❌ Delete Last: No"
    
    btn_list = wlc.get("buttons", [])
    btn_count = sum(len(row) for row in btn_list) if btn_list else 0

    text = (
        f"👋 **Welcome Configuration**\n{LINE}"
        f"👥 **Group:** `{group['title']}`\n"
        f"📊 **Current State:** {state_icon}\n"
        f"⚙️ **Mode:** {mode_text}\n"
        f"🗑 **Clean Up:** {del_last_icon}\n"
        f"🔗 **Buttons:** {btn_count}\n\n"
        "নিচের বাটন ব্যবহার করে কনফিগার করুন:"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(state_icon, callback_data=f"wlc_toggle_{target_id}"),
               InlineKeyboardButton(f"Mode: {mode_text}", callback_data=f"wlc_mode_{target_id}"))
    
    markup.row(InlineKeyboardButton("📝 Edit Text", callback_data=f"wlc_text_{target_id}"),
               InlineKeyboardButton("🖼 Set Media", callback_data=f"wlc_media_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔗 Buttons", callback_data=f"wlc_btn_{target_id}"),
               InlineKeyboardButton(del_last_icon, callback_data=f"wlc_dellast_{target_id}"))
    
    markup.row(InlineKeyboardButton("👁‍🗨 Full Preview", callback_data=f"wlc_preview_{target_id}"))
    markup.row(InlineKeyboardButton("🔙 Back to Panel", callback_data=f"gman_panel_{target_id}"))
    
    cid = direct_chat_id if direct_chat_id else call.message.chat.id
    if direct_chat_id:
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# --- ৪. কলব্যাক এবং ডাটা হ্যান্ডলার ---
def handle_callback(call, target_id, action):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    group_data = database.get_group_data(target_id)
    wlc = group_data.get("welcome_settings", {})

    if action == "home":
        show_welcome_menu(call, target_id)
    elif action == "toggle":
        database.update_welcome_setting(target_id, "state", not wlc.get("state", True))
        show_welcome_menu(call, target_id)
    elif action == "mode":
        new_mode = "first" if wlc.get("send_mode", "always") == "always" else "always"
        database.update_welcome_setting(target_id, "send_mode", new_mode)
        show_welcome_menu(call, target_id)
    elif action == "dellast":
        database.update_welcome_setting(target_id, "delete_last", not wlc.get("delete_last", False))
        show_welcome_menu(call, target_id)
    elif action == "preview":
        bot.answer_callback_query(call.id, "👁‍🗨 Generating Preview...")
        p_text, p_markup, p_type, p_media = generate_welcome_data(target_id, call.from_user, group_data.get('title'))
        preview_header = "👁‍🗨 **WELCOME PREVIEW**\n" + LINE
        if p_type == "photo" and p_media:
            bot.send_photo(chat_id, p_media, caption=f"{preview_header}{p_text}", parse_mode='HTML', reply_markup=p_markup)
        else:
            bot.send_message(chat_id, f"{preview_header}{p_text}", parse_mode='HTML', reply_markup=p_markup, disable_web_page_preview=True)
    
    elif action == "text":
        help_text = (
            "📝 **নতুন ওয়েলকাম টেক্সট পাঠান:**\n\n"
            "আপনি HTML ব্যবহার করতে পারেন। ট্যাগ কপির জন্য ক্লিক করুন:\n"
            "• `{ID}` • `{NAME}` • `{SURNAME}`\n"
            "• `{NAMESURNAME}` • `{LANG}`\n"
            "• `{DATE}` • `{TIME}` • `{WEEKDAY}`\n"
            "• `{MENTION}` • `{USERNAME}`\n"
            "• `{GROUPNAME}` • `{RULES}`"
        )
        msg = bot.send_message(chat_id, help_text, parse_mode='Markdown')
        bot.register_next_step_handler(msg, lambda m: save_text(m, target_id, chat_id))
    
    elif action == "media":
        msg = bot.send_message(chat_id, "🖼 **ফটো বা ভিডিও পাঠান** (মিডিয়া সরাতে `text` লিখে পাঠান)")
        bot.register_next_step_handler(msg, lambda m: save_media(m, target_id, chat_id))
    
    elif action == "btn":
        btn_guide = (
            "👉🏻 **মেসেজের নিচে বাটন সেট করুন**\n"
            "নিচের ফরম্যাটে বাটনগুলো লিখে পাঠান:\n\n"
            "• **একটি বাটন:**\n"
            "Button title - t.me/LinkExample\n\n"
            "• **একই লাইনে একাধিক বাটন:**\n"
            "Title 1 - Link1 && Title 2 - Link2\n\n"
            "• **একাধিক সারি:**\n"
            "Row 1 Button - Link1\n"
            "Row 2 Button - Link2\n\n"
            "❌ মুছতে `clear` লিখে পাঠান।"
        )
        msg = bot.send_message(chat_id, btn_guide, parse_mode='Markdown')
        bot.register_next_step_handler(msg, lambda m: save_btn(m, target_id, chat_id))

# --- ৫. সেভার ফাংশনসমূহ ---
def save_text(m, tid, cid):
    if m.text:
        database.update_welcome_setting(tid, "text", m.text)
        bot.send_message(cid, "✅ **ওয়েলকাম টেক্সট সেভ করা হয়েছে!**")
        show_welcome_menu(None, tid, direct_chat_id=cid)

def save_media(m, tid, cid):
    if m.photo:
        database.update_welcome_setting(tid, "type", "photo")
        database.update_welcome_setting(tid, "media_id", m.photo[-1].file_id)
        bot.send_message(cid, "✅ **ফটো সেভ করা হয়েছে!**")
    elif m.video:
        database.update_welcome_setting(tid, "type", "video")
        database.update_welcome_setting(tid, "media_id", m.video.file_id)
        bot.send_message(cid, "✅ **ভিডিও সেভ করা হয়েছে!**")
    elif m.text and m.text.lower() == "text":
        database.update_welcome_setting(tid, "type", "text")
        database.update_welcome_setting(tid, "media_id", None)
        bot.send_message(cid, "✅ **মিডিয়া রিমুভ করা হয়েছে!**")
    show_welcome_menu(None, tid, direct_chat_id=cid)

def save_btn(m, tid, cid):
    if not m.text: return
    if m.text.lower() == "clear":
        database.update_welcome_setting(tid, "buttons", [])
        bot.send_message(cid, "✅ **বাটন মুছে ফেলা হয়েছে!**")
    else:
        final_buttons = []
        lines = m.text.split('\n')
        for line in lines:
            row = []
            parts = line.split('&&')
            for part in parts:
                if '-' in part:
                    btn_data = [x.strip() for x in part.split('-', 1)]
                    if len(btn_data) == 2: row.append(btn_data)
            if row: final_buttons.append(row)
        database.update_welcome_setting(tid, "buttons", final_buttons)
        bot.send_message(cid, "✅ **বাটন কনফিগারেশন সেভ করা হয়েছে!**")
    show_welcome_menu(None, tid, direct_chat_id=cid)
