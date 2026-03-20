import telebot
import io
import json
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils import get_data, save_data, CUSTOM_FILE, load_users
from config import SUPER_ADMINS

# প্লাগিন ম্যানেজার ইমপোর্ট
try:
    from handlers.plugin_manager import initiate_add_tool, get_dynamic_tools
except ImportError:
    initiate_add_tool = None
    def get_dynamic_tools(only_active=True): return []

# স্টেট এবং ক্যাশ
ADMIN_STATE = {}
SPY_CACHE = {"channel_id": None, "forward_mode": "all"}

# =================================================
# 🕵️ SPY SYSTEM: THE HOOK METHOD (Updated with Mode Logic)
# =================================================
def load_spy_cache():
    data = get_data("spy_settings", {})
    SPY_CACHE["channel_id"] = data.get("channel_id")
    SPY_CACHE["forward_mode"] = data.get("forward_mode", "all")

def register_spy_system(bot):
    load_spy_cache()
    
    original_process_new_messages = bot.process_new_messages

    def custom_process_new_messages(messages):
        for message in messages:
            try:
                channel_id = SPY_CACHE["channel_id"]
                mode = SPY_CACHE["forward_mode"]
                
                if channel_id:
                    # ✅ Only File Mode Logic
                    if mode == "only_file":
                        # চেক করছি মেসেজে কোনো ফাইল/মিডিয়া আছে কি না
                        media_types = ['photo', 'video', 'document', 'audio', 'voice', 'video_note', 'sticker', 'animation']
                        is_media = any(getattr(message, t) for t in media_types if hasattr(message, t))
                        
                        if not is_media:
                            continue # শুধু টেক্সট হলে ফরওয়ার্ড হবে না

                    bot.forward_message(
                        chat_id=channel_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
            except Exception:
                pass
        
        original_process_new_messages(messages)

    bot.process_new_messages = custom_process_new_messages
    print("✅ Spy System (Hook Mode) Activated with Mode Support.")


# =================================================
# 🖥️ ADMIN PANEL UI
# =================================================
def send_admin_panel(bot, chat_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🕵️ Spy Setup (CCTV)", callback_data="open_spy_menu"))
    kb.add(InlineKeyboardButton("📂 Edit Menu Labels", callback_data="adm_menu_edit_list"))
    kb.add(
        InlineKeyboardButton("🐙 GitHub Editor", callback_data="gh_home"),
        InlineKeyboardButton("🔌 Plugin Manager", callback_data="plugin_manager")
    )
    kb.add(InlineKeyboardButton("➕ Create Tool", callback_data="adm_create_tool"))
    kb.add(InlineKeyboardButton("🔇 Manage Tools Visibility", callback_data="adm_manage_tools"))
    kb.add(
        InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
        InlineKeyboardButton("📊 Analytics", callback_data="adm_analytics")
    )
    kb.add(
        InlineKeyboardButton("⬇️ Backup Data", callback_data="adm_backup_dl"),
        InlineKeyboardButton("⬆️ Restore Data", callback_data="adm_backup_ul")
    )
    kb.add(InlineKeyboardButton("❌ Close Panel", callback_data="adm_close"))
    bot.send_message(chat_id, "👮 <b>Admin Panel</b>\n\nSelect an option:", reply_markup=kb, parse_mode="HTML")

# =================================================
# 🎮 HANDLERS REGISTRATION
# =================================================
def register_admin_handlers(bot):
    register_spy_system(bot)

    def safe_run(call, func):
        try:
            if call.message: pass
            func()
        except Exception: pass

    @bot.callback_query_handler(func=lambda c: c.data in ["admin", "admin_panel", "open_admin_panel", "admin_home", "main_btn_admin"])
    def open_admin_panel_handler(call):
        if call.from_user.id not in SUPER_ADMINS:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        safe_run(call, lambda: send_admin_panel(bot, call.message.chat.id))

    @bot.message_handler(commands=['admin', 'panel'])
    def admin_command(message):
        if message.from_user.id in SUPER_ADMINS:
            send_admin_panel(bot, message.chat.id)

    # =================================================
    # 🕵️ SPY CONFIGURATION (Updated)
    # =================================================
    @bot.callback_query_handler(func=lambda c: c.data == "open_spy_menu")
    def spy_menu_ui(call):
        data = get_data("spy_settings", {})
        current_id = data.get("channel_id", "❌ Not Set")
        mode = data.get("forward_mode", "all")
        
        # ক্যাশ আপডেট
        SPY_CACHE["channel_id"] = current_id
        SPY_CACHE["forward_mode"] = mode
        
        mode_label = "🔄 All Content" if mode == "all" else "📁 Only Files"
        
        text = (
            f"🕵️ <b>Spy System Config</b>\n\n"
            f"📡 <b>Monitoring Channel:</b> <code>{current_id}</code>\n"
            f"⚙️ <b>Current Mode:</b> <code>{mode.upper()}</code>\n\n"
            f"All messages are secretly forwarded here using Hook Method."
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton(f"🎯 Mode: {mode_label}", callback_data="spy_toggle_mode"))
        kb.add(InlineKeyboardButton("✏️ Set Channel ID", callback_data="set_spy_id"))
        kb.add(InlineKeyboardButton("🔔 Test Connection", callback_data="test_spy_conn"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="open_admin_panel"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "spy_toggle_mode")
    def toggle_spy_mode(call):
        data = get_data()
        if "spy_settings" not in data: data["spy_settings"] = {}
        
        current_mode = data["spy_settings"].get("forward_mode", "all")
        new_mode = "only_file" if current_mode == "all" else "all"
        
        data["spy_settings"]["forward_mode"] = new_mode
        save_data(data)
        
        # ক্যাশ আপডেট
        SPY_CACHE["forward_mode"] = new_mode
        
        bot.answer_callback_query(call.id, f"✅ Mode set to: {new_mode.upper()}")
        spy_menu_ui(call)

    @bot.callback_query_handler(func=lambda c: c.data == "test_spy_conn")
    def test_spy(call):
        cid = SPY_CACHE["channel_id"]
        if not cid or cid == "❌ Not Set":
            bot.answer_callback_query(call.id, "❌ ID Not Set!", show_alert=True)
            return
        try:
            bot.send_message(cid, "✅ <b>Spy System Active!</b>", parse_mode="HTML")
            bot.answer_callback_query(call.id, "✅ Test Passed!")
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ Failed! Check Logs.", show_alert=True)
            bot.send_message(call.message.chat.id, f"❌ Error: {e}")

    @bot.callback_query_handler(func=lambda c: c.data == "set_spy_id")
    def ask_spy_id(call):
        ADMIN_STATE[call.from_user.id] = "waiting_spy_id"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="open_spy_menu"))
        bot.edit_message_text("👉 Send <b>Channel ID</b> (e.g., -100xxxx).", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.from_user.id in SUPER_ADMINS and ADMIN_STATE.get(m.from_user.id) == "waiting_spy_id")
    def save_spy_id(message):
        try:
            new_id = int(message.text.strip())
            data = get_data()
            if "spy_settings" not in data: data["spy_settings"] = {}
            data["spy_settings"]["channel_id"] = new_id
            save_data(data)
            SPY_CACHE["channel_id"] = new_id
            del ADMIN_STATE[message.from_user.id]
            bot.reply_to(message, f"✅ Updated! ID: <code>{new_id}</code>", parse_mode="HTML")
        except:
            bot.reply_to(message, "❌ Invalid ID!")

    # ... [বাকি সব হ্যান্ডলার আগের মতোই থাকবে] ...
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_create_tool")
    def handle_tool_creation(call):
        if initiate_add_tool: safe_run(call, lambda: initiate_add_tool(bot, call.message.chat.id, call.from_user.id))
        else: bot.answer_callback_query(call.id, "Missing Plugin Manager!")

    @bot.callback_query_handler(func=lambda c: c.data == "adm_manage_tools")
    def manage_tools_ui(call):
        status_db = get_data("tools_status", {})
        kb = InlineKeyboardMarkup(row_width=1)
        all_tools = [("🔗 URL Shortener", "tool_url_shortener"), ("💧 Watermark", "tool_img"), ("🛡 Group Manager", "open_management"), ("☁️ Weather", "tool_weather")] + get_dynamic_tools(only_active=False)
        for label, code in all_tools:
            if not label: continue 
            icon = "✅" if status_db.get(code, True) else "❌"
            kb.add(InlineKeyboardButton(f"{icon} {label}", callback_data=f"adm_toggle_{code}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="open_admin_panel"))
        bot.edit_message_text("🔇 <b>Tool Visibility Manager</b>", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("adm_toggle_"))
    def toggle_tool(call):
        code = call.data.replace("adm_toggle_", "")
        data = get_data()
        if "tools_status" not in data: data["tools_status"] = {}
        data["tools_status"][code] = not data["tools_status"].get(code, True)
        save_data(data)
        manage_tools_ui(call) 

    @bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
    def start_broadcast(call):
        ADMIN_STATE[call.from_user.id] = "waiting_broadcast"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel"))
        bot.edit_message_text("📢 Send message to broadcast.", call.message.chat.id, call.message.message_id, reply_markup=kb)

    @bot.message_handler(func=lambda m: m.from_user.id in SUPER_ADMINS and ADMIN_STATE.get(m.from_user.id) == "waiting_broadcast")
    def process_broadcast(message):
        users = load_users()
        c = 0
        msg_wait = bot.reply_to(message, "⏳ Sending...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                c+=1
            except: pass
        del ADMIN_STATE[message.from_user.id]
        bot.edit_message_text(f"✅ Sent to {c} users.", message.chat.id, msg_wait.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "adm_backup_ul")
    def restore_ui(call):
        ADMIN_STATE[call.from_user.id] = "waiting_restore"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel"))
        bot.edit_message_text("⬆️ Send `custom_data.json`.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.message_handler(content_types=['document'], func=lambda m: m.from_user.id in SUPER_ADMINS and ADMIN_STATE.get(m.from_user.id) == "waiting_restore")
    def process_restore(message):
        try:
            downloaded = bot.download_file(bot.get_file(message.document.file_id).file_path)
            json.loads(downloaded)
            with open(CUSTOM_FILE, 'wb') as f: f.write(downloaded)
            bot.reply_to(message, "✅ Restored! Restarting...")
            os.execl(os.sys.executable, os.sys.executable, *os.sys.argv)
        except: bot.reply_to(message, "❌ Invalid JSON.")

    @bot.callback_query_handler(func=lambda c: c.data == "adm_analytics")
    def analytics(call):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📜 List", callback_data="adm_export"), InlineKeyboardButton("🔙 Back", callback_data="open_admin_panel"))
        bot.edit_message_text(f"📊 Users: {len(load_users())}", call.message.chat.id, call.message.message_id, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "adm_export")
    def export_users(call):
        out = "\n".join([f"{u} | {d.get('first_name')}" for u, d in load_users().items()])
        bot.send_document(call.message.chat.id, io.BytesIO(out.encode()), visible_file_name="users.txt")

    @bot.callback_query_handler(func=lambda c: c.data == "adm_backup_dl")
    def dl_backup(call):
        if os.path.exists(CUSTOM_FILE):
            with open(CUSTOM_FILE, 'rb') as f: bot.send_document(call.message.chat.id, f, visible_file_name="custom_data.json")
        else: bot.answer_callback_query(call.id, "No data!")

    @bot.callback_query_handler(func=lambda c: c.data in ["adm_close", "adm_cancel"])
    def close(call):
        if call.from_user.id in ADMIN_STATE: del ADMIN_STATE[call.from_user.id]
        if call.data == "adm_cancel": send_admin_panel(bot, call.message.chat.id)
        else: bot.delete_message(call.message.chat.id, call.message.message_id)
