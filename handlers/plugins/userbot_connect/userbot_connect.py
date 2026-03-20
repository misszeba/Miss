import os
import json
import asyncio
import threading
import logging
from telebot import types
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError

# ✅ MongoDB Manager ইমপোর্ট
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("Error: utils/db_manager.py not found")

logger = logging.getLogger(__name__)

temp_auth_data = {}
_loop = None
_loop_thread = None

def get_event_loop():
    global _loop, _loop_thread
    if _loop is None:
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _loop

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, get_event_loop())
    return future.result()

def save_session_to_db(user_id, api_id, api_hash, session_str):
    data = get_full_config()
    data[str(user_id)] = {
        "user_id": str(user_id),
        "api_id": api_id,
        "api_hash": api_hash,
        "session": session_str,
        "session_string": session_str,
        "tasks": {} 
    }
    save_full_config(data)

def force_open_userbot_menu(bot, message):
    try:
        from handlers.plugins.userbot_menu.userbot_menu import userbot_main_panel
        class FakeCall:
            def __init__(self, message):
                self.message = message
                self.from_user = message.from_user
                self.id = "0"
                self.data = "gm_userbot"
        userbot_main_panel(FakeCall(message))
    except Exception as e:
        logger.error(f"Menu redirect error: {e}")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛰 Open Userbot Tools", callback_data="gm_userbot"))
        bot.send_message(message.chat.id, "✅ কানেক্টেড! নিচের বাটনে ক্লিক করে টুলস ওপেন করুন:", reply_markup=markup)

def register_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "connect_userbot")
    def start_connection(call):
        msg = (
            "🔗 **Userbot Connection**\n\n"
            "নিচের ফরম্যাটে স্পেস দিয়ে তথ্যগুলো পাঠান:\n"
            "`API_ID` `API_HASH` `PHONE_NUMBER`\n\n"
            "অথবা সরাসরি সেশন স্ট্রিং পাঠান:\n"
            "`session string_here`"
        )
        try:
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            bot.register_next_step_handler(call.message, process_input_step, bot)
        except Exception as e:
            bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

    async def connect_via_session(message, session_str, bot):
        chat_id = message.chat.id
        try:
            client = TelegramClient(StringSession(session_str), 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e")
            await client.connect()
            
            if await client.is_user_authorized():
                save_session_to_db(chat_id, 6, "eb06d4abfb49dc3eeb1aeb98ae0f581e", session_str)
                
                # ✅ ইউজারকে সেশন স্ট্রিং পাঠানো
                bot.send_message(chat_id, f"✅ **সেশন সফল!** এটি সংরক্ষণ করে রাখুন:\n\n`{session_str}`", parse_mode="Markdown")
                
                import main
                threading.Thread(target=lambda: asyncio.run(main.start_userbot_engine()), daemon=True).start()
                force_open_userbot_menu(bot, message)
            else:
                bot.send_message(chat_id, "❌ সেশন অকার্যকর (Invalid)।")
            await client.disconnect()
        except Exception as e:
            bot.send_message(chat_id, f"❌ সেশন এরর: {str(e)}")

    def process_input_step(message, bot):
        text = message.text.strip()
        if text.lower().startswith("session"):
            try:
                session_str = text.split(" ", 1)[1]
                run_async(connect_via_session(message, session_str, bot))
            except: 
                bot.send_message(message.chat.id, "❌ ফরম্যাট ভুল। লিখুন: `session your_string`")
        else:
            try:
                parts = text.split()
                if len(parts) < 3: 
                    bot.send_message(message.chat.id, "❌ সব তথ্য দিন: `API_ID API_HASH PHONE`")
                    return
                api_id, api_hash, phone = int(parts[0]), parts[1], parts[2]
                run_async(init_client_logic(message, api_id, api_hash, phone, bot))
                bot.register_next_step_handler(message, process_otp_step, bot)
            except ValueError:
                bot.send_message(message.chat.id, "❌ API ID অবশ্যই সংখ্যা হতে হবে।")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ এরর: {e}")

    async def init_client_logic(message, api_id, api_hash, phone, bot):
        chat_id = message.chat.id
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
            temp_auth_data[chat_id] = {
                "client": client, "phone": phone, "hash": sent.phone_code_hash, 
                "api_id": api_id, "api_hash": api_hash
            }
            bot.send_message(chat_id, "📩 টেলিগ্রাম অ্যাপে যাওয়া কোডটি এখানে লিখুন:")
        except Exception as e: 
            bot.send_message(chat_id, f"❌ ওটিপি পাঠানো যায়নি: {e}")
            await client.disconnect()

    async def verify_otp_logic(message, otp_code, bot):
        chat_id = message.chat.id
        data = temp_auth_data.get(chat_id)
        if not data: return
        client = data["client"]
        try:
            if not client.is_connected(): await client.connect()
            await client.sign_in(data["phone"], otp_code, phone_code_hash=data["hash"])
            
            session_str = client.session.save()
            save_session_to_db(chat_id, data["api_id"], data["api_hash"], session_str)
            
            # ✅ ইউজারকে সেশন স্ট্রিং পাঠানো (ভবিষ্যতের জন্য)
            success_msg = (
                "✅ **লগইন সফল!** ইউজারবট কানেক্টেড।\n\n"
                "⚠️ **আপনার সেশন স্ট্রিং (এটি সেভ রাখুন):**\n"
                f"`{session_str}`"
            )
            bot.send_message(chat_id, success_msg, parse_mode="Markdown")
            
            import main
            threading.Thread(target=lambda: asyncio.run(main.start_userbot_engine()), daemon=True).start()
            force_open_userbot_menu(bot, message)
            
            await client.disconnect()
            del temp_auth_data[chat_id]
        except SessionPasswordNeededError:
            bot.send_message(chat_id, "🔐 টু-স্টেপ পাসওয়ার্ড দিন: (লিখুন: `pass password`)", parse_mode="Markdown")
            bot.register_next_step_handler(message, process_password_step, bot)
        except Exception as e: 
            bot.send_message(chat_id, f"❌ লগইন এরর: {e}")

    def process_otp_step(message, bot):
        otp = "".join(filter(str.isdigit, message.text))
        run_async(verify_otp_logic(message, otp, bot))

    async def verify_password_logic(message, password, bot):
        chat_id = message.chat.id
        data = temp_auth_data.get(chat_id)
        client = data["client"]
        try:
            if not client.is_connected(): await client.connect()
            await client.sign_in(password=password)
            
            session_str = client.session.save()
            save_session_to_db(chat_id, data["api_id"], data["api_hash"], session_str)
            
            # ✅ ইউজারকে সেশন স্ট্রিং পাঠানো
            success_msg = (
                "✅ **লগইন সফল!** (Password Verified)\n\n"
                "⚠️ **আপনার সেশন স্ট্রিং (এটি সেভ রাখুন):**\n"
                f"`{session_str}`"
            )
            bot.send_message(chat_id, success_msg, parse_mode="Markdown")
            
            import main
            threading.Thread(target=lambda: asyncio.run(main.start_userbot_engine()), daemon=True).start()
            force_open_userbot_menu(bot, message)
            
            await client.disconnect()
            del temp_auth_data[chat_id]
        except Exception as e: 
            bot.send_message(chat_id, f"❌ পাসওয়ার্ড এরর: {e}")

    def process_password_step(message, bot):
        pwd = message.text.replace("pass", "").strip()
        run_async(verify_password_logic(message, pwd, bot))
