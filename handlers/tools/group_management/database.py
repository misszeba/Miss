from config import bot, MONGO_CLIENT

# MongoDB Connection Setup
groups_collection = None
if MONGO_CLIENT is not None:
    try:
        db = MONGO_CLIENT["MissZebaBot"]
        groups_collection = db["groups"]
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")

# ==========================================
# 🔄 [CORE SYSTEM FUNCTIONS]
# ==========================================

def sync_group(chat_id):
    """গ্রুপ বা চ্যানেলের অ্যাডমিন লিস্ট এবং টাইটেল ডাটাবেসে আপডেট করে"""
    if groups_collection is None: return False
    try:
        chat = bot.get_chat(chat_id)
        
        # চ্যানেল হলে গেট অ্যাডমিনিস্ট্রেটরস একটু আলাদা কাজ করে, তবে টেলিগ্রাম এপিআইতে এটি সমর্থিত
        admins = bot.get_chat_administrators(chat_id)
        admin_ids = [int(a.user.id) for a in admins]
        
        data = {
            "chat_id": int(chat_id),
            "title": chat.title,
            "admins": admin_ids,
            "type": chat.type # 'group', 'supergroup' অথবা 'channel'
        }
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$set": data}, upsert=True)
        
        # সকল মডিউলের ডিফল্ট সেটিংস তৈরি
        init_welcome(chat_id)
        init_antilink(chat_id)
        init_banword(chat_id)
        init_chat_tool(chat_id) # ✅ নতুন চ্যাট টুল ইনিশিয়ালাইজার
        return True
    except Exception as e:
        print(f"❌ Sync Error: {e}")
        return False

def remove_group(chat_id):
    """চ্যাট ডাটাবেস থেকে রিমুভ করা"""
    if groups_collection is not None:
        groups_collection.delete_one({"chat_id": int(chat_id)})

def get_user_groups(user_id):
    """ইউজার যে সব চ্যাটের অ্যাডমিন তার লিস্ট বের করা"""
    if groups_collection is None: return []
    return list(groups_collection.find({"admins": int(user_id)}))

def get_group_data(chat_id):
    """একটি চ্যাটের সম্পূর্ণ ডাটাবেস রেকর্ড আনা"""
    if groups_collection is None: return None
    return groups_collection.find_one({"chat_id": int(chat_id)})

# ==========================================
# 👋 [WELCOME SETTINGS SECTION]
# ==========================================

def update_welcome_setting(chat_id, key, value):
    if groups_collection is not None:
        groups_collection.update_one(
            {"chat_id": int(chat_id)}, 
            {"$set": {f"welcome_settings.{key}": value}}
        )

def init_welcome(chat_id):
    curr = get_group_data(chat_id)
    if not curr or "welcome_settings" not in curr:
        settings = {
            "state": True,
            "text": "Welcome {MENTION} to {GROUPNAME}!",
            "type": "text",
            "send_mode": "always",
            "delete_last": False,
            "last_msg_id": None,
            "buttons": []
        }
        groups_collection.update_one(
            {"chat_id": int(chat_id)}, 
            {"$set": {"welcome_settings": settings}}
        )

# ==========================================
# 🚫 [ANTILINK SETTINGS SECTION]
# ==========================================

def update_antilink_setting(chat_id, key, value, mode="set"):
    if groups_collection is None: return
    path = f"antilink_settings.{key}"
    
    if mode == "set":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$set": {path: value}})
    elif mode == "push":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$addToSet": {path: value}})
    elif mode == "pull":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$pull": {path: value}})

def init_antilink(chat_id):
    curr = get_group_data(chat_id)
    if not curr or "antilink_settings" not in curr:
        settings = {
            "state": False,
            "action": "delete",
            "auto_delete": True,
            "warn_limit": 3,
            "mute_duration": 60,
            "allow_admin": True,
            "allow_usernames": True,
            "allow_bots": False,
            "whitelist_users": [],
            "whitelist_links": []
        }
        groups_collection.update_one(
            {"chat_id": int(chat_id)}, 
            {"$set": {"antilink_settings": settings}}
        )

# ==========================================
# 🤬 [BAN WORD SETTINGS SECTION]
# ==========================================

def update_banword_setting(chat_id, key, value, mode="set"):
    if groups_collection is None: return
    path = f"banword_settings.{key}"
    
    if mode == "set":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$set": {path: value}})
    elif mode == "push":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$addToSet": {path: value}})
    elif mode == "pull":
        groups_collection.update_one({"chat_id": int(chat_id)}, {"$pull": {path: value}})

def init_banword(chat_id):
    curr = get_group_data(chat_id)
    if not curr or "banword_settings" not in curr:
        settings = {
            "state": False,
            "action": "delete",
            "auto_delete": True,
            "mute_duration": 60,
            "allow_admin": True,
            "strict_mode": True,
            "words": [],
            "whitelist_users": []
        }
        groups_collection.update_one(
            {"chat_id": int(chat_id)}, 
            {"$set": {"banword_settings": settings}}
        )

# ==========================================
# 💬 [NEW: CHAT TOOL SETTINGS SECTION]
# ==========================================

def init_chat_tool(chat_id):
    """চ্যাট টুলের জন্য ডিফল্ট সেটিংস (নিকনেম সাপোর্ট)"""
    curr = get_group_data(chat_id)
    if not curr or "chat_settings" not in curr:
        settings = {
            "nickname": None, # শুরুতে কোনো নিকনেম থাকবে না
            "state": True
        }
        groups_collection.update_one(
            {"chat_id": int(chat_id)}, 
            {"$set": {"chat_settings": settings}}
        )

def set_nickname(chat_id, nickname):
    """নিকনেম ডাটাবেসে সেভ করা (ইউনিক কিনা চেক করে)"""
    if groups_collection is None: return False
    nick = nickname.lower().strip()
    
    # চেক করা এই নিকনেম অন্য চ্যাটে ব্যবহৃত হচ্ছে কি না
    exists = groups_collection.find_one({
        "chat_settings.nickname": nick,
        "chat_id": {"$ne": int(chat_id)}
    })
    
    if exists: return False
    
    groups_collection.update_one(
        {"chat_id": int(chat_id)}, 
        {"$set": {"chat_settings.nickname": nick}}
    )
    return True

def get_chat_by_nickname(nickname):
    """নিকনেম দিয়ে চ্যাট খুঁজে বের করা"""
    if groups_collection is None: return None
    return groups_collection.find_one({"chat_settings.nickname": nickname.lower().strip()})
