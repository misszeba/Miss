import os
import json
import importlib.util
import asyncio
import threading
from telebot import types

# ✅ MongoDB Manager থেকে ফাংশন ইমপোর্ট
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("Error: utils/db_manager.py not found in userbot_menu.py")

USERBOT_TASKS_DIR = "handlers/plugins/userbot_tasks"

TOOL_INFO = {
    "label": "🛰 Userbot Panel",
    "callback": "gm_userbot"
}

def register_handlers(bot):
    
    # ---------------------------------------------
    # 🛰 MAIN USERBOT PANEL
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "gm_userbot")
    def userbot_main_panel(call):
        # কলব্যাক উত্তর দেওয়া জরুরি
        try: bot.answer_callback_query(call.id)
        except: pass
        
        u_id = str(call.from_user.id)
        
        # ১. ডাটাবেস থেকে কনফিগ নেওয়া
        all_data = get_full_config()
        u_data = all_data.get(u_id, {})
        
        # ২. চেক করা হচ্ছে ইউজার কানেক্টেড কিনা (Memory Check First)
        is_connected_memory = False
        if hasattr(bot, 'active_clients') and u_id in bot.active_clients:
            if bot.active_clients[u_id].is_connected():
                is_connected_memory = True

        # ❌ যদি ডাটাবেসে ডাটা না থাকে = লগইন পেজ দেখান
        if not u_data:
            show_login_page(bot, call)
            return
        
        # ✅ কানেক্টেড আছে = ড্যাশবোর্ড দেখান
        mk = types.InlineKeyboardMarkup(row_width=1)
        api_id = u_data.get('api_id', 'N/A')
        status_text = "🟢 Online" if is_connected_memory else "🔴 Offline (Need Restart)"
        
        text = (
            f"🛰 **Userbot Dashboard**\n\n"
            f"🆔 **API ID:** `{api_id}`\n"
            f"📡 **Status:** {status_text}\n\n"
            f"👇 **Active Tools / Plugins:**"
        )

        # --- টাস্ক লিস্ট জেনারেশন (FIXED) ---
        task_found = False
        if os.path.exists(USERBOT_TASKS_DIR):
            for task_folder in os.listdir(USERBOT_TASKS_DIR):
                folder_path = os.path.join(USERBOT_TASKS_DIR, task_folder)
                
                # শুধু ফোল্ডার চেক করবে
                if os.path.isdir(folder_path):
                    # ফোল্ডারের ভেতর যেকোনো .py ফাইল খুঁজবে
                    for filename in os.listdir(folder_path):
                        if filename.endswith(".py") and filename != "__init__.py":
                            try:
                                # মডিউল লোড করার চেষ্টা
                                spec = importlib.util.spec_from_file_location("t_mod", os.path.join(folder_path, filename))
                                mod = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(mod)
                                
                                # ডাটাবেস থেকে স্ট্যাটাস চেক
                                is_on = u_data.get("tasks", {}).get(task_folder, False)
                                status_icon = "🟢" if is_on else "🔴"
                                next_action = "off" if is_on else "on"
                                
                                # ⚠️ TOOL_INFO না থাকলেও যাতে নাম দেখায় (Fallback)
                                if hasattr(mod, "TOOL_INFO"):
                                    label = mod.TOOL_INFO.get('label', task_folder)
                                else:
                                    label = task_folder.replace("_", " ").title() # ফোল্ডারের নাম ব্যবহার করবে
                                
                                btn_text = f"{label} [{status_icon}]"
                                mk.add(types.InlineKeyboardButton(btn_text, callback_data=f"utog:{task_folder}:{next_action}"))
                                task_found = True
                                break # একটা ফোল্ডারে একটা মেইন ফাইল পেলেই হবে
                            except Exception as e:
                                print(f"Error loading task {task_folder}: {e}")
                                continue
        
        if not task_found:
            mk.add(types.InlineKeyboardButton("⚠️ No Tools Found", callback_data="ignore"))

        # --- কন্ট্রোল বাটন ---
        row_btns = []
        row_btns.append(types.InlineKeyboardButton("🔄 Refresh", callback_data="gm_userbot"))
        mk.add(types.InlineKeyboardButton("🚪 Logout / Disconnect", callback_data="ub_logout_confirm"))
        mk.row(*row_btns)
        mk.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="gm_tools"))
        
        # মেসেজ আপডেট
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    # ---------------------------------------------
    # 🆕 FORCE SHOW LOGIN PAGE (আলাদা ফাংশন)
    # ---------------------------------------------
    def show_login_page(bot, call):
        mk = types.InlineKeyboardMarkup(row_width=1)
        mk.add(types.InlineKeyboardButton("➕ Connect Userbot", callback_data="connect_userbot"))
        mk.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="gm_tools"))
        
        text = (
            "🛰 **Userbot Manager**\n\n"
            "❌ **Disconnected**\n"
            "আপনার কোনো একাউন্ট কানেক্ট করা নেই।\n"
            "ফিচারগুলো ব্যবহার করতে নিচের বাটনে ক্লিক করে কানেক্ট করুন।"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown")

    # ---------------------------------------------
    # 🔄 TOGGLE TASK (ON/OFF)
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data.startswith("utog:"))
    def toggle_task(call):
        u_id = str(call.from_user.id)
        all_data = get_full_config()
        _, task_id, next_action = call.data.split(":")
        
        if u_id not in all_data:
            bot.answer_callback_query(call.id, "❌ একাউন্ট কানেক্ট নেই!")
            userbot_main_panel(call) # রিফ্রেশ
            return

        is_active = (next_action == "on")
        if "tasks" not in all_data[u_id]: all_data[u_id]["tasks"] = {}
        all_data[u_id]["tasks"][task_id] = is_active
        
        save_full_config(all_data)
        
        # ইঞ্জিন রিলোড
        try:
            import main
            threading.Thread(target=lambda: asyncio.run(main.start_userbot_engine())).start()
            bot.answer_callback_query(call.id, f"✅ {task_id} {next_action.upper()}...")
        except:
            bot.answer_callback_query(call.id, "✅ Saved.")
        
        userbot_main_panel(call)

    # ---------------------------------------------
    # 🚪 LOGOUT HANDLER (FIXED)
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "ub_logout_confirm")
    def logout_handler(call):
        u_id = str(call.from_user.id)
        
        # ১. মেমোরি থেকে ডিস্কানেক্ট করা
        if hasattr(bot, 'active_clients') and u_id in bot.active_clients:
            try:
                client = bot.active_clients[u_id]
                client.disconnect() # Async হলেও এখানে কল করে দিচ্ছি
                del bot.active_clients[u_id]
            except: pass

        # ২. ডাটাবেস থেকে রিমুভ করা
        all_data = get_full_config()
        if u_id in all_data:
            del all_data[u_id]
            save_full_config(all_data)
            
            bot.answer_callback_query(call.id, "✅ সফলভাবে লগ আউট করা হয়েছে!", show_alert=True)
            
            # ⚠️ এখানে userbot_main_panel কল না করে সরাসরি লগইন পেজ দেখাচ্ছি
            # এতে লুপ হওয়ার সম্ভাবনা নেই
            show_login_page(bot, call)
        else:
            bot.answer_callback_query(call.id, "⚠️ আপনি ইতিমধ্যে লগ আউট অবস্থায় আছেন।")
            show_login_page(bot, call)
