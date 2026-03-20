import telebot
import re
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import bot
from . import database

# মর্ডান UI ডিভাইডার
LINE = "━━━━━━━━━━━━━━━━━━━━\n"

# --- ১. মেসেজ স্ক্যানিং লজিক ---
def scan_message(message):
    chat_id = message.chat.id
    user_id = int(message.from_user.id)
    group = database.get_group_data(chat_id)
    if not group: return
    
    aln = group.get("antilink_settings", {})
    if not aln.get("state", False): return

    # অ্যাডমিন এবং হোয়াইটলিস্ট চেক
    if aln.get("allow_admin", True) and user_id in group.get("admins", []): return
    if user_id in aln.get("whitelist_users", []): return

    text = (message.text or message.caption or "").lower()
    is_spam = False
    reason = ""

    # (ক) লিংক ডিটেকশন
    url_pattern = r"(https?://\S+|t\.me/\S+|www\.\S+)"
    if re.search(url_pattern, text):
        is_spam = True
        for safe_link in aln.get("whitelist_links", []):
            if safe_link.lower() in text:
                is_spam = False
                break
        reason = "External Link"

    # (খ) ইউজারনেম/ট্যাগ ডিটেকশন (Antispam)
    if not is_spam and not aln.get("allow_usernames", True):
        if "@" in text:
            is_spam = True
            reason = "Username Tag"

    # (গ) বট ডিটেকশন
    if not is_spam and not aln.get("allow_bots", False):
        if message.from_user.is_bot and user_id != bot.get_me().id:
            is_spam = True
            reason = "Bot Spam"

    if is_spam:
        # অটো ডিলিট টগল চেক
        if aln.get("auto_delete", True):
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
        
        # পেনাল্টি অ্যাকশন এক্সিকিউট
        execute_antilink_action(message, aln, reason)

# --- ২. অ্যাকশন এক্সিকিউশন ---
def execute_antilink_action(message, settings, reason):
    chat_id = message.chat.id
    user_id = message.from_user.id
    action = settings.get("action", "none")

    try:
        if action == "warn":
            bot.send_message(chat_id, f"⚠️ **{message.from_user.first_name}**, স্প্যাম করবেন না!\n🚫 কারণ: `{reason}`")
        elif action == "mute":
            duration = int(settings.get("mute_duration", 60)) * 60
            bot.restrict_chat_member(chat_id, user_id, until_date=time.time() + duration)
            bot.send_message(chat_id, f"🔇 **{message.from_user.first_name}** কে {settings.get('mute_duration', 60)}m মিউট করা হয়েছে।")
        elif action == "kick":
            bot.unban_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"👞 **{message.from_user.first_name}** কে কিক করা হয়েছে।")
        elif action == "ban":
            bot.ban_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"🔨 **{message.from_user.first_name}** কে ব্যান করা হয়েছে।")
    except: pass

# --- ৩. মেইন কনফিগারেশন মেনু ---
def show_antilink_menu(call, target_id, direct_chat_id=None):
    group = database.get_group_data(target_id)
    if not group: return
    aln = group.get("antilink_settings", {})
    
    state = "🟢 ON" if aln.get("state") else "🔴 OFF"
    del_state = "✅ Enabled" if aln.get("auto_delete", True) else "❌ Disabled"
    curr_action = str(aln.get("action", "none")).upper()

    text = (
        f"🚫 **Antilink Manager**\n{LINE}"
        f"📊 **Status:** {state}\n"
        f"🗑 **Auto Delete:** {del_state}\n"
        f"⚡ **Penalty Action:** `{curr_action}`\n"
        f"⏳ **Mute Time:** `{aln.get('mute_duration', 60)}m`\n\n"
        "নিচের মেনু থেকে সেটিংস পরিবর্তন করুন:"
    )
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f"Master: {state}", callback_data=f"aln_toggle_{target_id}"),
               InlineKeyboardButton(f"Delete: {del_state}", callback_data=f"aln_autodel_{target_id}"))
    
    markup.row(InlineKeyboardButton("⚠️ Warn", callback_data=f"aln_setact_warn_{target_id}"),
               InlineKeyboardButton("🔇 Mute", callback_data=f"aln_setact_mute_{target_id}"),
               InlineKeyboardButton("👞 Kick", callback_data=f"aln_setact_kick_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔨 Ban", callback_data=f"aln_setact_ban_{target_id}"),
               InlineKeyboardButton("🚫 None", callback_data=f"aln_setact_none_{target_id}"))

    markup.row(InlineKeyboardButton("🔒 Security", callback_data=f"aln_sec_{target_id}"),
               InlineKeyboardButton("⚪ Whitelist", callback_data=f"aln_white_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔙 Back to Panel", callback_data=f"gman_panel_{target_id}"))
    
    cid = direct_chat_id if direct_chat_id else call.message.chat.id
    if direct_chat_id:
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# --- ৪. সিকিউরিটি এবং হোয়াইটলিস্ট মেনু ---
def show_security_menu(call, target_id):
    aln = database.get_group_data(target_id).get("antilink_settings", {})
    adm = "✅ Allowed" if aln.get("allow_admin", True) else "❌ Blocked"
    bot_p = "✅ Protect On" if not aln.get("allow_bots", False) else "❌ Off"
    tag_p = "✅ Protect On" if not aln.get("allow_usernames", True) else "❌ Off"

    text = f"🔒 **Security Settings**\n{LINE}অ্যাডমিন এবং অন্যান্য স্প্যাম প্রটেকশন টগল করুন:"
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton(f"Admin Allow: {adm}", callback_data=f"aln_tgsec_allow_admin_{target_id}"))
    markup.row(InlineKeyboardButton(f"Bot Antispam: {bot_p}", callback_data=f"aln_tgsec_allow_bots_{target_id}"))
    markup.row(InlineKeyboardButton(f"Tag Antispam: {tag_p}", callback_data=f"aln_tgsec_allow_usernames_{target_id}"))
    markup.row(InlineKeyboardButton("🔙 Back", callback_data=f"aln_home_{target_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

def show_whitelist_menu(call, target_id):
    aln = database.get_group_data(target_id).get("antilink_settings", {})
    text = (
        f"⚪ **Whitelist Manager**\n{LINE}"
        f"👥 **Users:** `{len(aln.get('whitelist_users', []))}`\n"
        f"🔗 **Domains:** `{len(aln.get('whitelist_links', []))}`"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("➕ User ID", callback_data=f"aln_adduser_{target_id}"),
               InlineKeyboardButton("➕ Domain", callback_data=f"aln_addlink_{target_id}"))
    markup.row(InlineKeyboardButton("🗑 Clear All", callback_data=f"aln_clearwhite_{target_id}"))
    markup.row(InlineKeyboardButton("🔙 Back", callback_data=f"aln_home_{target_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# --- ৫. কলব্যাক হ্যান্ডলার ---
def handle_callback(call, target_id, action_type):
    chat_id = call.message.chat.id
    aln = database.get_group_data(target_id).get("antilink_settings", {})

    if action_type == "home": show_antilink_menu(call, target_id)
    elif action_type == "sec": show_security_menu(call, target_id)
    elif action_type == "white": show_whitelist_menu(call, target_id)
    elif action_type == "toggle":
        database.update_antilink_setting(target_id, "state", not aln.get("state", False))
        show_antilink_menu(call, target_id)
    elif action_type == "autodel":
        database.update_antilink_setting(target_id, "auto_delete", not aln.get("auto_delete", True))
        show_antilink_menu(call, target_id)
    elif action_type.startswith("setact_"):
        new_act = action_type.replace("setact_", "")
        database.update_antilink_setting(target_id, "action", new_act)
        show_antilink_menu(call, target_id)
    elif action_type.startswith("tgsec_"):
        key = action_type.replace("tgsec_", "")
        database.update_antilink_setting(target_id, key, not aln.get(key))
        show_security_menu(call, target_id)
    elif action_type == "adduser":
        msg = bot.send_message(chat_id, "🆔 **ইউজার আইডি পাঠান:**")
        bot.register_next_step_handler(msg, lambda m: save_whitelist(m, target_id, "whitelist_users"))
    elif action_type == "addlink":
        msg = bot.send_message(chat_id, "🌐 **ডোমেইন পাঠান (উদা: youtube.com):**")
        bot.register_next_step_handler(msg, lambda m: save_whitelist(m, target_id, "whitelist_links"))
    elif action_type == "clearwhite":
        database.update_antilink_setting(target_id, "whitelist_users", [])
        database.update_antilink_setting(target_id, "whitelist_links", [])
        show_whitelist_menu(call, target_id)

def save_whitelist(m, tid, key):
    val = m.text.strip()
    if key == "whitelist_users" and val.isdigit(): val = int(val)
    database.update_antilink_setting(tid, key, val, mode="push")
    bot.send_message(m.chat.id, f"✅ `{val}` যোগ করা হয়েছে।")
    show_antilink_menu(None, tid, direct_chat_id=m.chat.id)
