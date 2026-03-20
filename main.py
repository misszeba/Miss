import os
import sys
import asyncio
import threading
import time
import json
import importlib.util
import logging
import inspect # 🕵️‍♂️ সোর্স চেকার
# ✅ মিনি অ্যাপের জন্য Flask এর সাথে render_template, jsonify, send_file এবং requests ইমপোর্ট করা হলো
import requests 
import io 
from flask import Flask, render_template, jsonify, send_file

# =========================================================
# 🚀 0. SYSTEM CONFIGURATION
# =========================================================
os.environ["IMAGEIO_FFMPEG_EXE"] = "/usr/bin/ffmpeg"

try:
    import imageio_ffmpeg
except ImportError:
    pass

import telebot

# --- Telethon ---
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    logger_ub = logging.getLogger("telethon")
    logger_ub.setLevel(logging.WARNING) 
except ImportError:
    print("ERROR: Telethon not found.")

# ✅ MongoDB
try:
    # ✅ get_shop ইমপোর্ট করা হলো মিনি অ্যাপ API এর জন্য
    from utils.db_manager import get_full_config, save_full_config
    from utils.utils_shop import get_shop, get_and_clear_due_posts
except ImportError:
    print("WARNING: db_manager not found.")

# =========================================================
# ⚙️ 1. LOGGING & CONFIGURATION
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from config import BOT_TOKEN, DATA_DIR, USERS_FILE, SHOPS_FILE, CUSTOM_FILE, MONGO_CLIENT, bot
    if not bot: raise ImportError("Bot failed to load.")
    logger.info("✅ Configuration Loaded.")
except ImportError as e:
    logger.error(f"CRITICAL ERROR: {e}")
    sys.exit(1)

USERBOT_SESSIONS_FILE = os.path.join(DATA_DIR, "userbot_sessions.json")
bot.active_clients = {} 
active_clients = bot.active_clients

# =========================================================
# 🛡️ 2. STRICT DELETE PROTECTION (WHITELIST MODE)
# =========================================================
_original_delete = bot.delete_message

# ✅ অনুমোদিত ফাইলের তালিকা (কারা মেসেজ ডিলিট করতে পারবে)
ALLOWED_FILES = [
    "events.py", "core.py", "welcome.py", "admin_panel.py", 
    "callbacks.py", "main.py", "antilink.py", "banword.py", 
    "chat_tool.py", "twitter_dl.py",
    # ✅ শপ সিস্টেমের সব কম্পোনেন্ট হোয়াইটলিস্টে যুক্ত করা হলো
    "shop_seller.py", "shop_buyer.py", "shop_cart.py", 
    "shop_categories.py", "shop_requests.py", "shop_social.py",
    "shop_orders.py", "shop_coupons.py", "shop_analytics.py"
]

def strict_delete_message(chat_id, message_id, *args, **kwargs):
    try:
        # ১. প্রাইভেট চ্যাটে কোনো বাধা নেই
        if int(chat_id) > 0:
            return _original_delete(chat_id, message_id, *args, **kwargs)

        # ২. কলার ফাইল চেক করা
        frame = inspect.currentframe().f_back
        filepath = frame.f_code.co_filename
        filename = os.path.basename(filepath)

        # ৩. হোয়াইটলিস্ট চেক
        is_allowed = False
        for allowed in ALLOWED_FILES:
            if allowed in filename:
                is_allowed = True
                break
        
        # ৪. সিদ্ধান্ত
        if is_allowed:
            return _original_delete(chat_id, message_id, *args, **kwargs)
        else:
            logger.warning(f"🚫 BLOCKED: '{filename}' tried to delete message in Group {chat_id}")
            return False

    except Exception as e:
        logger.error(f"Delete Protection Error: {e}")
        return _original_delete(chat_id, message_id, *args, **kwargs)

bot.delete_message = strict_delete_message
logger.info("✅ Strict Delete Protection Activated (Full Whitelist)")

# =========================================================
# 🛰️ 3. INDEPENDENT USERBOT ENGINE
# =========================================================
def load_userbot_tasks_for_client(client, bot, user_id, user_config):
    task_base_path = "handlers/plugins/userbot_tasks"
    if not os.path.exists(task_base_path): os.makedirs(task_base_path)

    user_tasks = user_config.get("tasks", {})
    for root, dirs, files in os.walk(task_base_path):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                task_id = os.path.basename(root)
                if user_tasks.get(task_id, False):
                    try:
                        spec = importlib.util.spec_from_file_location(f"ub_{user_id}_{task_id}", os.path.join(root, filename))
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        if hasattr(module, "register_userbot_task"):
                            module.register_userbot_task(client, bot, user_id)
                    except: pass

async def start_userbot_engine():
    try:
        sessions = get_full_config() if 'get_full_config' in globals() else {}
        if not sessions: return
        for uid, data in sessions.items():
            if uid in active_clients: continue
            try:
                if 'session' in data and 'api_id' in data:
                    client = TelegramClient(StringSession(data['session']), int(data['api_id']), data['api_hash'])
                    await client.connect()
                    if await client.is_user_authorized():
                        active_clients[uid] = client
                        load_userbot_tasks_for_client(client, bot, uid, data)
                        asyncio.create_task(client.run_until_disconnected())
                        logger.info(f"✅ Userbot Active: {uid}")
            except Exception as e:
                logger.error(f"Userbot Start Error for {uid}: {e}")
    except: pass

# =========================================================
# 🛠 4. PLUGIN LOADER
# =========================================================
def check_and_create_files():
    # ✅ templates ফোল্ডার যুক্ত করা হয়েছে (মিনি অ্যাপ HTML এর জন্য)
    dirs = [DATA_DIR, "handlers/plugins", "handlers/plugins/userbot_tasks", "templates"]
    for d in dirs: 
        if not os.path.exists(d): os.makedirs(d)
    for f in [USERS_FILE, SHOPS_FILE, USERBOT_SESSIONS_FILE]:
        if not os.path.exists(f):
            with open(f, 'w') as file: json.dump({}, file)
    if not os.path.exists(CUSTOM_FILE):
        with open(CUSTOM_FILE, 'w') as f: json.dump({"texts": {}, "banwords": [], "warns": {}, "tools_status": {}}, f)

def load_plugins(bot):
    plugin_base = "handlers/plugins"
    if not os.path.exists(plugin_base): return
    count = 0
    for root, dirs, files in os.walk(plugin_base):
        if "userbot_tasks" in root: continue
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    spec = importlib.util.spec_from_file_location(filename[:-3], os.path.join(root, filename))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "register_handlers"):
                        module.register_handlers(bot)
                        count += 1
                except: pass
    logger.info(f"🔌 Loaded {count} Plugins")

# =========================================================
# 📥 5. HANDLER REGISTRATION (Optimized Order)
# =========================================================
logger.info("📥 Registering Handlers...")

try:
    from handlers.start import register_start
    from handlers.auth import register_auth_handlers
    from handlers.admin_panel import register_admin_handlers
    from handlers.plugin_manager import register_plugin_handler
    from handlers.callbacks import register_callbacks
    
    register_start(bot)
    register_auth_handlers(bot)
    register_admin_handlers(bot)
    register_plugin_handler(bot)

    # 🛒 Shop System Registration (Priority: Highest)
    from handlers.shop_seller import register_seller_handlers
    from handlers.shop_buyer import register_buyer_handlers
    from handlers.shop_categories import register_category_handlers
    from handlers.shop_requests import register_request_handlers 
    from handlers.shop_social import register_social_handlers, post_product_to_channel
    from handlers.shop_coupons import register_coupon_handlers
    from handlers.shop_orders import register_order_handlers
    from handlers.shop_analytics import register_analytics_handlers
    from handlers.shop_cart import register_cart_handlers 
    # get_and_clear_due_posts আগেই ইমপোর্ট করা হয়েছে
    # from utils.utils_shop import get_and_clear_due_posts

    register_seller_handlers(bot)
    register_buyer_handlers(bot)
    register_category_handlers(bot)
    register_request_handlers(bot)
    register_social_handlers(bot)
    register_coupon_handlers(bot)
    register_order_handlers(bot)
    register_analytics_handlers(bot)
    register_cart_handlers(bot)

    load_plugins(bot) 

    from handlers.tools.url_shorten.core import register_url_handlers
    from handlers.tools.watermark.core import register_watermark_handlers
    from handlers.broadcast import register_broadcast_handlers
    
    register_url_handlers(bot)
    register_watermark_handlers(bot)
    register_broadcast_handlers(bot)

    import handlers.tools.group_management.events
    register_callbacks(bot)

except Exception as e:
    logger.error(f"❌ Handlers Import Error: {e}")
    sys.exit(1)

# =========================================================
# ⏰ 6. RUNNER (Scheduler & Polling)
# =========================================================
def scheduler_loop():
    while True:
        try:
            tasks = get_and_clear_due_posts()
            if tasks:
                bot_user = bot.get_me()
                bot_username = bot_user.username if bot_user else "Bot"
                for t in tasks:
                    try:
                        # ✅ Scheduler: পাস করা হচ্ছে t['shop_owner_id']
                        post_product_to_channel(bot, t['channel_id'], t['product'], t['shop_name'], t['shop_owner_id'], bot_username)
                    except Exception as e:
                        logger.error(f"Scheduler Post Error: {e}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Scheduler Loop Error: {e}")
            time.sleep(60)

async def start_all():
    check_and_create_files()
    await start_userbot_engine()

    def run_polling():
        logger.info("🤖 Bot is starting infinity polling on Railway...")
        bot.delete_webhook(drop_pending_updates=True)
        bot.infinity_polling(timeout=60, skip_pending=True)

    threading.Thread(target=run_polling, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    while True:
        await asyncio.sleep(3600)

# =========================================================
# 🌍 7. RAILWAY SERVER (Flask + Mini App)
# =========================================================
app = Flask(__name__, template_folder='templates') # ✅ টেমপ্লেট ফোল্ডার সেট করা হলো

@app.route('/')
def home():
    return "Bot is Running! 🛡️ All Priority Fixed."

# ✅ মিনি অ্যাপের হোমপেজ (HTML রেন্ডার করবে)
@app.route('/shop')
def shop_page():
    return render_template('shop.html')

# ✅ মিনি অ্যাপের জন্য প্রোডাক্ট API
@app.route('/api/products/<shop_id>')
def get_shop_products(shop_id):
    shop = get_shop(shop_id)
    if not shop: return jsonify({"products": []})
    
    prod_list = []
    for pid, p in shop.get("products", {}).items():
        # শুধুমাত্র অ্যাক্টিভ বা সোল্ড প্রোডাক্ট দেখাবে, ডিলিট করা নয়
        if p.get("status") in ["active", "sold"]:
            prod_list.append({"id": pid, **p})
    return jsonify({"products": prod_list})

# ✅ ইমেজ প্রক্সি (Telegram API থেকে ইমেজ নিয়ে ব্রাউজারে দেখানোর জন্য)
@app.route('/api/image/<file_id>')
def get_telegram_image(file_id):
    try:
        # ১. ফাইলের পাথ বের করা
        file_info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        resp = requests.get(file_info_url).json()
        
        if not resp.get('ok'): return "Error", 404
        file_path = resp['result']['file_path']

        # ২. ফাইল ডাউনলোড করে সরাসরি সার্ভ করা
        image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        img_resp = requests.get(image_url)
        
        return send_file(io.BytesIO(img_resp.content), mimetype='image/jpeg')
    except:
        return "Error", 404

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Flask Server Error: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=run_http_server)
    t.daemon = True
    t.start()
    time.sleep(5) 
    try: asyncio.run(start_all())
    except KeyboardInterrupt:
        logger.info("🛑 Bot Stopped.")
    except Exception as e:
        logger.error(f"🛑 Main Loop Error: {e}")
