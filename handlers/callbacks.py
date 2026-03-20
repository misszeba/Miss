import telebot
from telebot import types
import traceback
from config import bot

# =========================================================
# 👇 TOOL REGISTRY & IMPORTS
# =========================================================
tool_registry = {}

# 1. Group Management Import (FIXED for System 2.0)
try:
    # 🚨 আপডেট: এখন dashboard.py থেকে open_gman_dashboard ইমপোর্ট করা হচ্ছে
    from handlers.tools.group_management.dashboard import open_gman_dashboard
    print("✅ Callbacks: GM System 2.0 Linked Successfully")
except ImportError as e:
    print(f"❌ Callbacks: GM Import Failed -> {e}")
    open_gman_dashboard = None

# 2. URL Tool Import
try:
    from handlers.tools.url_shorten.core import open_url_tool
    tool_registry['tool_url_shortener'] = lambda bot, call: open_url_tool(bot, call.message, is_edit=True)
except ImportError: pass

# 3. Menu Import
try:
    from keyboards.main_menu import main_menu, tools_layout
except ImportError:
    def main_menu(uid): return None
    def tools_layout(): return "⚠️ Menu Error", None

# =========================================================
# 🎮 CALLBACK HANDLER
# =========================================================
def register_callbacks(bot):

    # ফিল্টার: gman_ এবং wlc_ যুক্ত কলব্যাকগুলো এই গ্লোবাল হ্যান্ডলার ইগনোর করবে 
    # কারণ সেগুলো dashboard.py নিজে হ্যান্ডেল করে।
    @bot.callback_query_handler(func=lambda call: not (
        call.data.startswith("wm_") or 
        call.data.startswith("url_") or 
        call.data.startswith("gman_") or 
        call.data.startswith("wlc_") or 
        call.data == "tool_img"
    ))
    def handle_global_callbacks(call):
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        try:
            # 🚨 ১. গ্রুপ ম্যানেজমেন্ট মেইন এন্ট্রি (টুলস মেনু থেকে আসে)
            if data == "open_group_manager":
                if open_gman_dashboard:
                    # কলব্যাক উত্তর দিয়ে লোডিং আইকন সরানো হলো
                    bot.answer_callback_query(call.id)
                    open_gman_dashboard(chat_id, message_id)
                else:
                    bot.answer_callback_query(call.id, "⚠️ Error: GM Module not loaded properly.", show_alert=True)
                return

            # ২. অন্যান্য টুলস (যেমন: URL Shortener)
            if data in tool_registry:
                bot.answer_callback_query(call.id)
                tool_registry[data](bot, call)
                return

            # ৩. টুলস মেনু নেভিগেশন
            if data in ["tools", "back_to_tools", "open_tools_menu"]:
                bot.answer_callback_query(call.id)
                text, kb = tools_layout()
                if kb:
                    if call.message.content_type == 'text':
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="Markdown")
                    else:
                        try: bot.delete_message(chat_id, message_id)
                        except: pass
                        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
                return

            # ৪. মেইন মেনু রিটার্ন
            if data == "main_menu_return":
                bot.answer_callback_query(call.id)
                kb = main_menu(call.from_user.id)
                if kb:
                    if call.message.content_type == 'text':
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🏠 **Main Menu**\n\nSelect an option:", reply_markup=kb, parse_mode="Markdown")
                    else:
                        try: bot.delete_message(chat_id, message_id)
                        except: pass
                        bot.send_message(chat_id, "🏠 **Main Menu**\n\nSelect an option:", reply_markup=kb, parse_mode="Markdown")
                return
            
            # ৫. ক্লোজ বাটন
            if data == "close":
                try: bot.delete_message(chat_id, message_id)
                except: pass
                return

            # অজানা বাটন হ্যান্ডলিং
            try: bot.answer_callback_query(call.id)
            except: pass

        except Exception as e:
            print(f"Callback Logic Error: {e}")
            traceback.print_exc()
            try: bot.answer_callback_query(call.id, "❌ Error Occurred")
            except: pass
