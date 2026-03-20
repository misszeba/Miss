import json
import os
import time
import re
from config import MONGO_CLIENT # ✅ আপনার config থেকে মঙ্গো ক্লায়েন্ট ইমপোর্ট

# মঙ্গোডিবি ডাটাবেস ও কালেকশন সেটআপ
db = MONGO_CLIENT['telegram_shop_db'] # ডাটাবেস নাম
shops_col = db['shops']               # কালেকশন নাম

# ==========================================
# 💾 DATABASE CORE (MONGODB VERSION)
# ==========================================

def load_shops():
    """সব শপ লোড করা (শিডিউলার বা গ্লোবাল সার্চের জন্য)"""
    all_shops = list(shops_col.find({}))
    formatted_data = {}
    for s in all_shops:
        uid = str(s['owner_id'])
        s.pop('_id', None) # মঙ্গোডিবির ইন্টারনাল ID সরিয়ে ফেলা
        formatted_data[uid] = s
    return formatted_data

def save_shops(data_or_user_id, updated_data=None):
    """
    ডাটা সেভ করার ফাংশন। এটি পুরানো JSON স্টাইল এবং নতুন Direct Update 
    উভয় পদ্ধতিই সাপোর্ট করে যাতে কোনো হ্যান্ডলার ক্র্যাশ না করে।
    """
    try:
        # ১. যদি পুরো ডিকশনারি আসে (পুরানো লজিক সামঞ্জস্য রাখতে)
        if isinstance(data_or_user_id, dict) and not updated_data:
            for uid, sdata in data_or_user_id.items():
                shops_col.update_one({"owner_id": int(uid)}, {"$set": sdata}, upsert=True)
            return True
        
        # ২. যদি নির্দিষ্ট ইউজার আইডির ডাটা আপডেট করতে বলা হয়
        if updated_data:
            shops_col.update_one({"owner_id": int(data_or_user_id)}, {"$set": updated_data}, upsert=True)
            return True
        return False
    except Exception as e:
        print(f"MongoDB Save Error: {e}")
        return False

def get_shop(user_id):
    """ডাটাবেস থেকে নির্দিষ্ট ইউজারের শপ খুঁজে বের করা"""
    try:
        shop = shops_col.find_one({"owner_id": int(user_id)})
        if shop:
            shop.pop('_id', None)
        return shop
    except:
        return None

def create_shop(user_id, name):
    """নতুন শপ তৈরি করা"""
    if get_shop(user_id): return False
    
    new_shop = {
        "owner_id": int(user_id),
        "name": name,
        "shop_username": None, # ✅ শপ ইউনিক ইউজারনেম
        "description": "Welcome to my store!",
        "banner": None,
        "payment_info": "Contact Admin for payment.",
        "privacy": "public",
        "subscription_price": 0.0,
        "channel_id": None,
        "auto_post": False,
        "approved_users": [],
        "pending_requests": [],
        "scheduled_posts": [],
        "customers": {},
        "categories": {}, 
        "products": {},
        "coupons": {},
        "orders": {} 
    }
    res = shops_col.insert_one(new_shop)
    return True if res.inserted_id else False

def delete_shop(user_id):
    """শপ চিরস্থায়ীভাবে ডাটাবেস থেকে ডিলিট করা"""
    res = shops_col.delete_one({"owner_id": int(user_id)})
    return True if res.deleted_count > 0 else False

# --- Utility: Safe Price Extraction ---
def safe_float(value):
    """দাম থেকে টেক্সট সরিয়ে শুধুমাত্র সংখ্যা বের করার জন্য (উদা: '500 TK' -> 500.0)"""
    try:
        if isinstance(value, (int, float)): return float(value)
        clean_val = re.sub(r'[^\d.]', '', str(value).replace(',', ''))
        return float(clean_val) if clean_val else 0.0
    except:
        return 0.0

# ==========================================
# 🔖 SHOP USERNAME (HANDLES)
# ==========================================

def is_username_taken(username):
    """চেক করবে এই ইউজারনেমটি অন্য কেউ নিয়েছে কি না"""
    search_name = str(username).lower().strip().replace("@", "")
    existing = shops_col.find_one({"shop_username": search_name})
    return True if existing else False

def set_shop_username(user_id, username):
    """শপের জন্য ইউনিক ইউজারনেম সেট করবে"""
    clean_name = str(username).lower().strip().replace("@", "")
    
    if not re.match(r"^[a-z0-9_]{3,20}$", clean_name):
        return False, "Invalid format."
    
    if is_username_taken(clean_name):
        return False, "Username already taken."
    
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"shop_username": clean_name}})
    if res.modified_count > 0:
        return True, clean_name
    return False, "Update error."

def get_shop_by_username(username):
    """ইউজারনেম দিয়ে সপ খুঁজে বের করার জন্য"""
    search_name = str(username).lower().strip().replace("@", "")
    shop = shops_col.find_one({"shop_username": search_name})
    if shop:
        shop.pop('_id', None)
    return shop

# ==========================================
# 📦 PRODUCTS MANAGEMENT
# ==========================================

def add_product_to_shop(user_id, name, price, description, media_list, category_id=None, variants=None):
    shop = get_shop(user_id)
    if not shop: return False
    
    prod_id = f"prod_{int(time.time())}"
    new_product = {
        "name": name, 
        "price": price, 
        "description": description,
        "media": media_list, 
        "category": category_id, 
        "variants": variants or [], 
        "status": "active", 
        "use_thumbnail": True, 
        "reviews": []
    }
    
    # মঙ্গোডিবি ডাইরেক্ট পুশ (মেমোরি সেফ)
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$set": {f"products.{prod_id}": new_product}}
    )
    return True if res.modified_count > 0 else False

def update_product_field(user_id, prod_id, field, value):
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$set": {f"products.{prod_id}.{field}": value}}
    )
    return True if res.modified_count > 0 else False

def toggle_product_thumbnail(user_id, prod_id):
    shop = get_shop(user_id)
    if not shop: return False
    current = shop["products"].get(prod_id, {}).get("use_thumbnail", True)
    return update_product_field(user_id, prod_id, "use_thumbnail", not current)

def delete_product(user_id, prod_id):
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$unset": {f"products.{prod_id}": ""}}
    )
    return True if res.modified_count > 0 else False

def toggle_product_status(user_id, prod_id):
    shop = get_shop(user_id)
    if not shop: return False
    current = shop["products"].get(prod_id, {}).get("status", "active")
    new_status = "sold" if current == "active" else "active"
    return update_product_field(user_id, prod_id, "status", new_status)

# ==========================================
# 📂 CATEGORIES
# ==========================================

def create_category(user_id, name):
    cat_id = f"cat_{int(time.time())}"
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$set": {f"categories.{cat_id}": name}}
    )
    return True if res.modified_count > 0 else False

def delete_category(user_id, cat_id):
    # ক্যাটাগরি ডিলিট এবং ওই ক্যাটাগরির প্রোডাক্ট আপডেট
    shops_col.update_one({"owner_id": int(user_id)}, {"$unset": {f"categories.{cat_id}": ""}})
    shop = get_shop(user_id)
    if shop and "products" in shop:
        for pid, pdata in shop["products"].items():
            if pdata.get("category") == cat_id:
                update_product_field(user_id, pid, "category", None)
    return True

def get_categories(user_id):
    shop = get_shop(user_id)
    return shop.get("categories", {}) if shop else {}

# ==========================================
# 🛒 ORDERS & PAYMENTS
# ==========================================

def create_order(shop_id, buyer_id, buyer_name, item_summary, price, proof_file_id, order_type="product"):
    order_id = f"ord_{int(time.time())}_{buyer_id}"
    order_data = {
        "buyer_id": buyer_id,
        "buyer_name": buyer_name,
        "item": item_summary,
        "price": price,
        "proof": proof_file_id,
        "type": order_type, 
        "status": "pending", 
        "date": int(time.time())
    }
    res = shops_col.update_one(
        {"owner_id": int(shop_id)}, 
        {"$set": {f"orders.{order_id}": order_data}}
    )
    return order_id if res.modified_count > 0 else None

def update_order_status(shop_id, order_id, status):
    res = shops_col.update_one(
        {"owner_id": int(shop_id)}, 
        {"$set": {f"orders.{order_id}.status": status}}
    )
    if res.modified_count > 0:
        shop = get_shop(shop_id)
        return shop["orders"].get(order_id)
    return None

def set_payment_info(user_id, text):
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"payment_info": text}})
    return True if res.modified_count > 0 else False

def set_subscription_price(user_id, price):
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"subscription_price": safe_float(price)}})
    return True if res.modified_count > 0 else False

# ==========================================
# 👥 ACCESS & REQUESTS
# ==========================================

def toggle_shop_privacy(user_id):
    shop = get_shop(user_id)
    if not shop: return False
    current = shop.get("privacy", "public")
    new_privacy = "private" if current == "public" else "public"
    shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"privacy": new_privacy}})
    return True

def add_access_request(shop_owner_id, buyer_id, buyer_info):
    shop = get_shop(shop_owner_id)
    if not shop: return False
    
    if buyer_id not in shop.get("pending_requests", []) and buyer_id not in shop.get("approved_users", []):
        shops_col.update_one(
            {"owner_id": int(shop_owner_id)}, 
            {
                "$push": {"pending_requests": buyer_id},
                "$set": {f"customers.{buyer_id}": buyer_info}
            }
        )
        return True
    return False

def approve_access(shop_owner_id, buyer_id):
    shops_col.update_one(
        {"owner_id": int(shop_owner_id)}, 
        {
            "$pull": {"pending_requests": buyer_id},
            "$addToSet": {"approved_users": buyer_id}
        }
    )
    return True

def deny_access(shop_owner_id, buyer_id):
    shops_col.update_one(
        {"owner_id": int(shop_owner_id)}, 
        {"$pull": {"pending_requests": buyer_id}}
    )
    return True

def manual_add_buyer(shop_owner_id, target_id, name="Manual Add"):
    shops_col.update_one(
        {"owner_id": int(shop_owner_id)}, 
        {
            "$addToSet": {"approved_users": target_id},
            "$set": {f"customers.{target_id}": {'first_name': name, 'username': 'Unknown'}}
        }
    )
    return True

# ==========================================
# 🎫 COUPONS
# ==========================================

def create_coupon(user_id, code, discount_type, value):
    code = code.upper().strip()
    coupon_data = {"type": discount_type, "value": safe_float(value), "created_at": int(time.time())}
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$set": {f"coupons.{code}": coupon_data}}
    )
    return True if res.modified_count > 0 else False

def delete_coupon(user_id, code):
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$unset": {f"coupons.{code.upper().strip()}": ""}}
    )
    return True if res.modified_count > 0 else False

def get_coupons(user_id):
    shop = get_shop(user_id)
    return shop.get("coupons", {}) if shop else {}

def validate_coupon(shop_id, code):
    shop = get_shop(shop_id)
    if not shop: return None
    return shop.get("coupons", {}).get(code.upper().strip())

# ==========================================
# ⭐ REVIEWS & RATINGS
# ==========================================

def add_product_review(shop_id, prod_id, user_id, user_name, rating, text):
    review = {"user_id": user_id, "name": user_name, "rating": rating, "text": text, "date": int(time.time())}
    # মঙ্গোডিবি পুশ লজিক: যদি আগে রিভিউ থাকে তবে তা আপডেট করবে, নয়তো নতুন দেবে
    shop = get_shop(shop_id)
    reviews = shop["products"].get(prod_id, {}).get("reviews", [])
    
    updated_reviews = [r for r in reviews if r['user_id'] != user_id]
    updated_reviews.append(review)
    
    res = shops_col.update_one(
        {"owner_id": int(shop_id)}, 
        {"$set": {f"products.{prod_id}.reviews": updated_reviews}}
    )
    return True if res.modified_count > 0 else False

def get_product_reviews(shop_id, prod_id):
    shop = get_shop(shop_id)
    return shop.get("products", {}).get(prod_id, {}).get("reviews", []) if shop else []

def get_product_rating(shop_id, prod_id):
    reviews = get_product_reviews(shop_id, prod_id)
    if not reviews: return 0.0, 0
    total = sum(r["rating"] for r in reviews)
    return round(total / len(reviews), 1), len(reviews)

# ==========================================
# 📢 CHANNEL & SCHEDULING
# ==========================================

def set_shop_channel(user_id, channel_id):
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"channel_id": channel_id}})
    return True if res.modified_count > 0 else False

def toggle_auto_post(user_id):
    shop = get_shop(user_id)
    if not shop: return False
    curr = shop.get("auto_post", False)
    shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"auto_post": not curr}})
    return True

def schedule_post(user_id, prod_id, post_time):
    res = shops_col.update_one(
        {"owner_id": int(user_id)}, 
        {"$push": {"scheduled_posts": {"prod_id": prod_id, "run_at": post_time}}}
    )
    return True if res.modified_count > 0 else False

def get_and_clear_due_posts():
    data = load_shops()
    now = int(time.time())
    tasks_to_run = []
    
    for uid, shop in data.items():
        if "scheduled_posts" not in shop or not shop["scheduled_posts"]: continue
        due = [t for t in shop["scheduled_posts"] if t["run_at"] <= now]
        remaining = [t for t in shop["scheduled_posts"] if t["run_at"] > now]
        
        if due:
            for task in due:
                prod = shop["products"].get(task["prod_id"])
                if prod and shop.get("channel_id"):
                    tasks_to_run.append({
                        "channel_id": shop["channel_id"], 
                        "product": prod, 
                        "shop_name": shop["name"], 
                        "shop_owner_id": uid
                    })
            shops_col.update_one({"owner_id": int(uid)}, {"$set": {"scheduled_posts": remaining}})
            
    return tasks_to_run

# ==========================================
# 📊 ANALYTICS & BACKUP
# ==========================================

def update_shop_desc(user_id, new_desc):
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"description": new_desc}})
    return True if res.modified_count > 0 else False

def set_shop_banner(user_id, media_data):
    """
    media_data: {"file_id": "...", "type": "photo" or "video"}
    """
    res = shops_col.update_one({"owner_id": int(user_id)}, {"$set": {"banner": media_data}})
    return True if res.modified_count > 0 else False

def get_shop_backup_data(user_id):
    return get_shop(user_id)

def restore_shop_data(user_id, backup_data):
    required_keys = ["owner_id", "name", "products"]
    if not all(key in backup_data for key in required_keys): return False, "Invalid File."
    backup_data["owner_id"] = int(user_id)
    res = shops_col.replace_one({"owner_id": int(user_id)}, backup_data, upsert=True)
    return (True, "Restored!") if res.acknowledged else (False, "Save error.")

def get_shop_analytics(user_id):
    shop = get_shop(user_id)
    if not shop: return None
    orders = shop.get("orders", {})
    products = shop.get("products", {})
    stats = {
        "revenue": 0.0, "total_orders": len(orders), 
        "pending": 0, "paid": 0, "rejected": 0, 
        "members": len(shop.get("approved_users", [])), 
        "total_products": len(products), 
        "best_seller": "None"
    }
    sales_count = {} 
    for oid, o in orders.items():
        status = o.get("status", "pending")
        if status == "pending": stats["pending"] += 1
        elif status == "rejected": stats["rejected"] += 1
        elif status == "paid":
            stats["paid"] += 1
            stats["revenue"] += safe_float(o.get("price", 0))
            p_name = o.get("item", "Unknown")
            sales_count[p_name] = sales_count.get(p_name, 0) + 1
    
    stats["revenue"] = round(stats["revenue"], 2)
    if sales_count:
        top_item = max(sales_count, key=sales_count.get)
        stats["best_seller"] = f"{top_item} ({sales_count[top_item]} sales)"
    return stats
