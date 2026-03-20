import logging
from config import MONGO_CLIENT 

# লগার সেটআপ
logger = logging.getLogger(__name__)

# ==========================================
# DATABASE & COLLECTION SETUP
# ==========================================
# আমরা config.py থেকে তৈরি করা কানেকশন ব্যবহার করবো
if MONGO_CLIENT:
    try:
        db = MONGO_CLIENT["MissZebaBot"] # ডাটাবেস নাম একই রাখা হলো
        sessions_col = db["userbot_sessions"] # কালেকশন নাম
        print("✅ DB Manager linked with Config")
    except Exception as e:
        print(f"❌ DB Selection Error: {e}")
        sessions_col = None
else:
    sessions_col = None
    print("⚠️ MONGO_CLIENT is None in db_manager")

# ==========================================
# 1. GET CONFIG (Load All Sessions)
# ==========================================
def get_full_config():
    """ডাটাবেস থেকে সকল ইউজারের ইউজারবট সেশন লোড করা"""
    if sessions_col is None:
        return {}

    data = {}
    try:
        # সকল ডকুমেন্ট খুঁজে বের করা
        cursor = sessions_col.find({})
        for doc in cursor:
            user_id = doc.get("user_id")
            if user_id:
                # MongoDB এর ইন্টারনাল '_id' অবজেক্টটি বাদ দেওয়া
                doc.pop('_id', None)
                data[str(user_id)] = doc
    except Exception as e:
        logger.error(f"⚠️ MongoDB Read Error: {e}")
    
    return data

# ==========================================
# 2. SAVE CONFIG (Save/Update Sessions)
# ==========================================
def save_full_config(data):
    """
    ডাটাবেসে ইউজারের কনফিগারেশন সেভ বা আপডেট করা।
    'data' হলো পুরো ডিকশনারি { 'user_id': {session_data}, ... }
    """
    if sessions_col is None:
        return

    try:
        for u_id, u_data in data.items():
            # নিশ্চিত করা যে user_id ইন্টিজার/স্ট্রিং কনসিস্টেন্ট আছে
            u_id_int = int(u_id)
            u_data["user_id"] = u_id_int
            
            # ডাটাবেসে আপডেট করা (Upsert: না থাকলে তৈরি হবে, থাকলে আপডেট হবে)
            sessions_col.update_one(
                {"user_id": u_id_int}, 
                {"$set": u_data}, 
                upsert=True
            )
    except Exception as e:
        logger.error(f"⚠️ MongoDB Write Error: {e}")

# ==========================================
# 3. DELETE CONFIG
# ==========================================
def delete_user_config(user_id):
    """প্রয়োজন হলে নির্দিষ্ট ইউজারের ডাটা ডিলিট করা"""
    if sessions_col is None: return

    try:
        sessions_col.delete_one({"user_id": int(user_id)})
        logger.info(f"🗑️ Deleted session for user {user_id}")
    except Exception as e:
        logger.error(f"⚠️ MongoDB Delete Error: {e}")

# ==========================================
# 4. SINGLE USER HELPER (Better Performance)
# ==========================================
def save_single_user_session(user_id, session_data):
    """শুধুমাত্র একজন ইউজারের সেশন সেভ করার জন্য (ফাস্ট)"""
    if sessions_col is None: return False

    try:
        session_data["user_id"] = int(user_id)
        sessions_col.update_one(
            {"user_id": int(user_id)},
            {"$set": session_data},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"❌ Single Save Error: {e}")
        return False
