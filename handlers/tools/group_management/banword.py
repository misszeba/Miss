import telebot
import re
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import bot
from . import database

LINE = "━━━━━━━━━━━━━━━━━━━━\n"

# --- ১. ১০০% কার্যকর স্ক্যানিং এবং ডিলিট লজিক ---
def scan_message(message):
    chat_id = message.chat.id
    user_id = int(message.from_user.id)
    
    group = database.get_group_data(chat_id)
    if not group: return
    
    bnw = group.get("banword_settings", {})
    if not bnw.get("state", False) or not bnw.get("words"): return

    # অ্যাডমিন চেক
    if bnw.get("allow_admin", True) and user_id in group.get("admins", []): return
    
    # হোয়াইটলিস্ট চেক
    whitelist = bnw.get("whitelist_users", [])
    whitelist_ids = [u['id'] for u in whitelist if isinstance(u, dict)]
    if user_id in whitelist_ids: return

    raw_text = (message.text or message.caption or "").lower()
    if not raw_text: return

    # Anti-Bypass: সিম্বল সরিয়ে চেক করা
    clean_text = re.sub(r'[^a-zA-Z0-9\u0980-\u09FF]', '', raw_text) 

    found_word = None
    strict = bnw.get("strict_mode", True)

    for word in bnw.get("words", []):
        word = word.lower()
        if strict:
            if word in raw_text or word in clean_text:
                found_word = word
                break
        else:
            if re.search(rf"\b{re.escape(word)}\b", raw_text):
                found_word = word
                break

    if found_word:
        if bnw.get("auto_delete", True):
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
        execute_action(message, bnw, found_word)

def execute_action(message, settings, word):
    chat_id = message.chat.id
    user_id = message.from_user.id
    action = settings.get("action", "delete")
    try:
        if action == "warn":
            bot.send_message(chat_id, f"⚠️ **{message.from_user.first_name}**, নিষিদ্ধ শব্দ ব্যবহার করবেন না!")
        elif action == "mute":
            duration = int(settings.get("mute_duration", 60)) * 60
            bot.restrict_chat_member(chat_id, user_id, until_date=time.time() + duration)
            bot.send_message(chat_id, f"🔇 **{message.from_user.first_name}** কে মিউট করা হয়েছে।")
        elif action == "kick":
            bot.unban_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"👞 **{message.from_user.first_name}** কে কিক করা হয়েছে।")
        elif action == "ban":
            bot.ban_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"🔨 **{message.from_user.first_name}** কে ব্যান করা হয়েছে।")
    except: pass

# --- ২. হোয়াইটলিস্ট ম্যানেজমেন্ট মেনু (নতুন) ---
def show_whitelist_manager(call, target_id):
    group = database.get_group_data(target_id)
    whitelist = group.get("banword_settings", {}).get("whitelist_users", [])
    
    text = f"⚪ **Whitelist Manager**\n{LINE}নিচের ইউজারদের ব্যানওয়ার্ড ফিল্টার থেকে মুক্তি দেওয়া হয়েছে:\n\n"
    markup = InlineKeyboardMarkup()
    
    if not whitelist:
        text += "❌ তালিকা বর্তমানে খালি।"
    else:
        for user in whitelist:
            markup.row(
                InlineKeyboardButton(f"👤 {user['name']}", callback_data="none"),
                InlineKeyboardButton("🗑 Remove", callback_data=f"bnw_rmwhite_{user['id']}_{target_id}")
            )
    
    markup.row(InlineKeyboardButton("➕ Add New User", callback_data=f"bnw_addwhite_{target_id}"))
    markup.row(InlineKeyboardButton("🔙 Back", callback_data=f"bnw_home_{target_id}"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# --- ৩. মেইন কনফিগারেশন মেনু ---
def show_banword_menu(call, target_id, direct_chat_id=None):
    group = database.get_group_data(target_id)
    if not group: return
    bnw = group.get("banword_settings", {})
    
    state = "🟢 ON" if bnw.get("state") else "🔴 OFF"
    strict_state = "🔥 Strict" if bnw.get("strict_mode", True) else "🔍 Normal"
    del_state = "✅ ON" if bnw.get("auto_delete", True) else "❌ OFF"

    text = (
        f"🤬 **Ban Word Manager**\n{LINE}"
        f"📊 **Status:** {state}\n"
        f"🗑 **Auto Delete:** {del_state}\n"
        f"⚡ **Penalty:** `{str(bnw.get('action')).upper()}`\n"
        f"📝 **Words:** `{len(bnw.get('words', []))}` | ⚪ **White:** `{len(bnw.get('whitelist_users', []))}`\n\n"
        "নিচের বাটন থেকে কনফিগার করুন:"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f"Status: {state}", callback_data=f"bnw_toggle_{target_id}"),
               InlineKeyboardButton(f"Delete: {del_state}", callback_data=f"bnw_autodel_{target_id}"))
    
    markup.row(InlineKeyboardButton("📄 View Word List", callback_data=f"bnw_viewwords_{target_id}"),
               InlineKeyboardButton("⚪ Manage Whitelist", callback_data=f"bnw_manwhite_{target_id}"))

    markup.row(InlineKeyboardButton("➕ Add Words", callback_data=f"bnw_add_{target_id}"),
               InlineKeyboardButton("🔍 Mode: {strict_state}", callback_data=f"bnw_strict_{target_id}"))
    
    markup.row(InlineKeyboardButton("⚠️ Warn", callback_data=f"bnw_setact_warn_{target_id}"),
               InlineKeyboardButton("🔇 Mute", callback_data=f"bnw_setact_mute_{target_id}"),
               InlineKeyboardButton("👞 Kick", callback_data=f"bnw_setact_kick_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔨 Ban", callback_data=f"bnw_setact_ban_{target_id}"),
               InlineKeyboardButton("🗑 Clear All", callback_data=f"bnw_clear_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔙 Back to Panel", callback_data=f"gman_panel_{target_id}"))
    
    cid = direct_chat_id if direct_chat_id else call.message.chat.id
    if direct_chat_id:
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# --- ৪. কলব্যাক হ্যান্ডলার ---
def handle_callback(call, target_id, action_type):
    try: bot.answer_callback_query(call.id)
    except: pass

    bnw = database.get_group_data(target_id).get("banword_settings", {})

    if action_type == "home":
        show_banword_menu(call, target_id)
    elif action_type == "viewwords":
        words = bnw.get("words", [])
        bot.send_message(call.message.chat.id, f"📝 **নিষিদ্ধ শব্দ তালিকা:**\n<code>{', '.join(words) if words else 'খালি'}</code>", parse_mode='HTML')
    elif action_type == "manwhite":
        show_whitelist_manager(call, target_id)
    elif action_type == "toggle":
        database.update_banword_setting(target_id, "state", not bnw.get("state", False))
        show_banword_menu(call, target_id)
    elif action_type == "autodel":
        database.update_banword_setting(target_id, "auto_delete", not bnw.get("auto_delete", True))
        show_banword_menu(call, target_id)
    elif action_type == "strict":
        database.update_banword_setting(target_id, "strict_mode", not bnw.get("strict_mode", True))
        show_banword_menu(call, target_id)
    elif action_type == "add":
        msg = bot.send_message(call.message.chat.id, "📝 **নিষিদ্ধ শব্দগুলো পাঠান (কমা দিয়ে আলাদা করুন):**")
        bot.register_next_step_handler(msg, lambda m: save_data(m, target_id, "words"))
    elif action_type == "addwhite":
        msg = bot.send_message(call.message.chat.id, "🆔 **হোয়াইটলিস্ট করতে ইউজার আইডিটি পাঠান:**")
        bot.register_next_step_handler(msg, lambda m: save_data(m, target_id, "whitelist_users"))
    elif action_type.startswith("rmwhite_"):
        uid = int(call.data.split('_')[2])
        database.update_banword_setting(target_id, "whitelist_users", {"id": uid}, mode="pull")
        show_whitelist_manager(call, target_id)
    elif action_type.startswith("setact_"):
        act = action_type.replace("setact_", "")
        database.update_banword_setting(target_id, "action", act)
        show_banword_menu(call, target_id)
    elif action_type == "clear":
        database.update_banword_setting(target_id, "words", [])
        show_banword_menu(call, target_id)

def save_data(m, tid, key):
    if not m.text: return
    if key == "words":
        new_items = [w.strip() for w in m.text.split(',') if w.strip()]
        for w in new_items: database.update_banword_setting(tid, key, w, mode="push")
    elif key == "whitelist_users":
        if m.text.isdigit():
            uid = int(m.text)
            try: name = bot.get_chat_member(tid, uid).user.first_name
            except: name = f"User:{uid}"
            database.update_banword_setting(tid, key, {"id": uid, "name": name}, mode="push")
    
    bot.send_message(m.chat.id, "✅ ডাটা সেভ হয়েছে।")
    show_banword_menu(None, tid, direct_chat_id=m.chat.id)
