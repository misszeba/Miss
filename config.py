import os
import sys
import telebot
from dotenv import load_dotenv
from pymongo import MongoClient

# =========================================================
# ⚙️ MAIN CONFIGURATION
# =========================================================

load_dotenv()

# ১. এনভায়রনমেন্ট ভেরিয়েবল (রেলওয়ে/সার্ভার)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")  # ✅ MongoDB URL
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# 👇 GitHub Config
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAME = os.environ.get("REPO_NAME")
GITHUB_USER = os.environ.get("GITHUB_USER")

# ব্যাকআপ চ্যানেল
BACKUP_CHANNEL_ID = os.environ.get("BACKUP_CHANNEL_ID")

super_admins_env = os.environ.get("SUPER_ADMINS")
if super_admins_env:
    try: 
        SUPER_ADMINS = [int(x.strip()) for x in super_admins_env.split(",") if x.strip()]
    except: 
        SUPER_ADMINS = []
else:
    SUPER_ADMINS = []

# ২. লোকাল ফোলব্যাক (secrets.py)
try:
    import secrets as S
except ImportError:
    class S:
        BOT_TOKEN = None
        MONGO_URL = None
        ADMIN_PASSWORD = None
        SUPER_ADMINS = []
        GITHUB_TOKEN = None
        REPO_NAME = None
        GITHUB_USER = None
        BACKUP_CHANNEL_ID = None

# ভ্যালু অ্যাসাইনমেন্ট (Priority: Env Var > secrets.py)
if not BOT_TOKEN: BOT_TOKEN = getattr(S, 'BOT_TOKEN', None)
if not MONGO_URL: MONGO_URL = getattr(S, 'MONGO_URL', None)
if not ADMIN_PASSWORD: ADMIN_PASSWORD = getattr(S, 'ADMIN_PASSWORD', None)
if not SUPER_ADMINS: SUPER_ADMINS = getattr(S, 'SUPER_ADMINS', [])
if not GITHUB_TOKEN: GITHUB_TOKEN = getattr(S, 'GITHUB_TOKEN', None)
if not REPO_NAME: REPO_NAME = getattr(S, 'REPO_NAME', None)
if not GITHUB_USER: GITHUB_USER = getattr(S, 'GITHUB_USER', None)

# ব্যাকআপ চ্যানেল হ্যান্ডলিং
if not BACKUP_CHANNEL_ID: 
    BACKUP_CHANNEL_ID = getattr(S, 'BACKUP_CHANNEL_ID', -1001550472719)

if BACKUP_CHANNEL_ID:
    try: 
        BACKUP_CHANNEL_ID = int(BACKUP_CHANNEL_ID)
    except: 
        BACKUP_CHANNEL_ID = -1001550472719

# ৩. ক্রিটিক্যাল ভ্যালিডেশন
if not BOT_TOKEN:
    print("\n❌ CRITICAL: BOT_TOKEN missing! Set it in Environment Variables or 'secrets.py'.")
    sys.exit(1)

# ডেটা ডিরেক্টরি সেটআপ
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CUSTOM_FILE = os.path.join(DATA_DIR, "custom.json")
SHOPS_FILE = os.path.join(DATA_DIR, "shops.json")

if not os.path.exists(DATA_DIR): 
    os.makedirs(DATA_DIR)

# =========================================================
# 🔌 DATABASE & BOT INITIALIZATION (CRITICAL FIX)
# =========================================================

# ১. MongoDB কানেকশন
if MONGO_URL:
    try:
        # ✅ tlsAllowInvalidCertificates=True যোগ করা হয়েছে (সার্ভার এরর এড়াতে)
        MONGO_CLIENT = MongoClient(MONGO_URL, tlsAllowInvalidCertificates=True)
        # পিং করে চেক করা কানেকশন ঠিক আছে কিনা
        MONGO_CLIENT.admin.command('ping')
        print("✅ MongoDB Connected Successfully from config.py")
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        MONGO_CLIENT = None
else:
    MONGO_CLIENT = None
    print("⚠️ MONGO_URL not found. Database features may fail.")

# ২. Bot Instance তৈরি
# এখন অন্য ফাইলগুলো `from config import bot` করতে পারবে এবং Import Error হবে না।
try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", use_class_middlewares=True)
    # বটের ইউজারনেম বের করা (অপশনাল, নেটওয়ার্ক স্লো থাকলে এটি স্কিপ করতে পারেন)
    try:
        BOT_USERNAME = bot.get_me().username
    except:
        BOT_USERNAME = "MissZebaBot"
except Exception as e:
    print(f"❌ Bot Initialization Error: {e}")
    sys.exit(1)

print(f"✅ Configuration loaded. Backup Channel: {BACKUP_CHANNEL_ID}")
