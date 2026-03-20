import telebot
import json # ✅ NEW: JSON ইমপোর্ট (মিনি অ্যাপ ডাটা পার্স করার জন্য)
# ✅ NEW: WebAppInfo ইমপোর্ট করা হলো
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, WebAppInfo
# ✅ get_shop_by_username ইমপোর্ট করা হয়েছে
from utils.utils_shop import get_shop, add_access_request, get_product_rating, validate_coupon, create_order, get_shop_by_username

# ✅ NEW: আপনার রেলওয়ে অ্যাপের লিংক (এখানে আপনার আসল লিংক বসান)
WEB_APP_URL = "worker-production-1256.up.railway.app"

buyer_sessions = {}
ITEMS_PER_PAGE = 6

def get_session(user_id):
    if user_id not in buyer_sessions:
        buyer_sessions[user_id] = {'page': 0, 'cat': None, 'sort': 'new', 'search': None}
    return buyer_sessions[user_id]

def register_buyer_handlers(bot):

    # =========================================================
    # ✅ NEW: MINI APP DATA RECEIVER (অর্ডার রিসিভ করার জন্য)
    # =========================================================
    @bot.message_handler(content_types=['web_app_data'])
    def web_app_data_receive(message):
        try:
            data = json.loads(message.web_app_data.data)
            if data.get('action') == 'web_order':
                shop_id = data.get('shop_id')
                cart = data.get('cart', {})
                
                # অর্ডার ডিটেইলস তৈরি
                total_price = 0
                items_summary = []
                for pid, item in cart.items():
                    items_summary.append(f"{item['name']} (x{item['qty']})")
                    total_price += (item['price'] * item['qty'])
                
                item_text = ", ".join(items_summary)
                shop = get_shop(shop_id)
                pay_info = shop.get("payment_info", "Contact Seller")

                # পেমেন্ট মেসেজ পাঠানো (সরাসরি পেমেন্ট প্রুফ চাওয়া হচ্ছে)
                msg = (f"🛒 <b>Mini App Order Received!</b>\n\n"
                       f"📦 <b>Items:</b> {item_text}\n"
                       f"💰 <b>Total Amount: {total_price}</b>\n\n"
                       f"🧾 <b>Payment Info:</b>\n{pay_info}\n\n"
                       f"📸 <b>Please send your payment screenshot now.</b>")
                
                sent = bot.send_message(message.chat.id, msg, parse_mode="HTML")
                
                # প্রুফ প্রসেসিং এর জন্য নেক্সট স্টেপ (আলাদা ফাংশন ব্যবহার করা হলো যাতে আগের লজিক ব্রেক না করে)
                bot.register_next_step_handler(sent, process_web_proof, bot, shop_id, item_text, total_price)
        except Exception as e:
            print(f"Web App Error: {e}")

    def process_web_proof(message, bot, shop_id, item_text, price):
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            # অর্ডার তৈরি (Web Order হিসেবে)
            order_id = create_order(shop_id, message.from_user.id, message.from_user.first_name, item_text, price, file_id, order_type="product")
            
            bot.reply_to(message, "✅ <b>Proof Submitted!</b>\nWaiting for seller approval.", parse_mode="HTML")
            
            # সেলারের কাছে নোটিফিকেশন
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ord_pay_ok_{shop_id}_{order_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"ord_pay_no_{shop_id}_{order_id}"))
            
            caption = (f"🔔 <b>New Mini App Order #{order_id[-4:]}</b>\n"
                       f"👤 Buyer: {message.from_user.first_name}\n"
                       f"📦 Items: {item_text}\n"
                       f"💰 Price: {price}\n"
                       f"👇 <b>Payment Proof:</b>")
            bot.send_photo(shop_id, file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Please send a photo.")

    # =========================================================
    # END NEW CODE
    # =========================================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("view_prods_"))
    def list_shop_content(call):
        # ✅ Answer callback only if it is a callback query object
        if hasattr(call, 'id'):
            bot.answer_callback_query(call.id)
            
        # Handle both direct shop_id (from deep link) and callback data
        shop_id = call.data.replace("view_prods_", "") if hasattr(call, 'data') else str(call)
        shop = get_shop(shop_id)
        if not shop: 
            target_chat = call.message.chat.id if hasattr(call, 'message') else call.chat.id
            bot.send_message(target_chat, "❌ Shop not found.")
            return
            
        user_id = call.from_user.id
        privacy = shop.get("privacy", "public")
        approved_users = shop.get("approved_users", [])
        
        if privacy == "private" and str(user_id) != str(shop['owner_id']) and user_id not in approved_users:
            pending = shop.get("pending_requests", [])
            sub_price = shop.get("subscription_price", 0)
            kb = InlineKeyboardMarkup()
            if user_id in pending: kb.add(InlineKeyboardButton("⏳ Pending", callback_data="ignore"))
            else:
                if sub_price > 0: kb.add(InlineKeyboardButton(f"💳 Buy Access ({sub_price})", callback_data=f"buy_sub_start_{shop_id}_{sub_price}"))
                else: kb.add(InlineKeyboardButton("✋ Request Access", callback_data=f"req_access_{shop_id}"))
            kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu_return"))
            
            chat_id = call.message.chat.id if hasattr(call, 'message') else call.chat.id
            msg_id = call.message.message_id if hasattr(call, 'message') else None
            
            text = f"🔒 <b>Private Shop: {shop['name']}</b>"
            if msg_id:
                try: bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb, parse_mode="HTML")
                except: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            return

        # ✅ FIXED: অটো ব্যানার ডিসপ্লে লজিক (ডিকশনারি ইরোর সমাধান)
        banner = shop.get("banner")
        chat_id = call.message.chat.id if hasattr(call, 'message') else call.chat.id
        if banner:
            caption = f"👋 Welcome to <b>{shop['name']}</b>"
            try:
                if isinstance(banner, dict):
                    file_id = banner.get("file_id")
                    b_type = banner.get("type", "photo")
                    if b_type == "video":
                        bot.send_video(chat_id, file_id, caption=caption, parse_mode="HTML")
                    else:
                        bot.send_photo(chat_id, file_id, caption=caption, parse_mode="HTML")
                else:
                    # পুরানো স্ট্রিং আইডি থাকলে সরাসরি ফটো হিসেবে পাঠানো
                    bot.send_photo(chat_id, banner, caption=caption, parse_mode="HTML")
            except Exception as e:
                print(f"Banner Display Error: {e}")

        buyer_sessions[user_id] = {'page': 0, 'cat': None, 'sort': 'new', 'search': None}
        render_shop_list(bot, call, shop_id)

    def render_shop_list(bot, call, shop_id):
        user_id = call.from_user.id
        session = get_session(user_id)
        shop = get_shop(shop_id)
        all_products = []
        for pid, data in shop.get("products", {}).items():
            if session['cat'] and data.get("category") != session['cat']: continue
            if session['search'] and session['search'].lower() not in data['name'].lower(): continue
            all_products.append({'id': pid, **data})
        
        if session['sort'] == 'price_asc':
            all_products.sort(key=lambda x: float(str(x.get('price', 0)).replace(',','').split()[0]) if str(x.get('price',0)).replace('.','',1).isdigit() else 0)
        elif session['sort'] == 'price_desc':
            all_products.sort(key=lambda x: float(str(x.get('price', 0)).replace(',','').split()[0]) if str(x.get('price',0)).replace('.','',1).isdigit() else 0, reverse=True)
        elif session['sort'] == 'old':
            all_products.sort(key=lambda x: x['id'])
        else: 
            all_products.sort(key=lambda x: x['id'], reverse=True)
            
        total = len(all_products)
        start = session['page'] * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = all_products[start:end]
        kb = InlineKeyboardMarkup(row_width=2)
        
        # ✅ NEW: Mini App Button (Hybrid Mode)
        # এটি সবার উপরে থাকবে যাতে ইউজাররা সহজে দেখতে পায়
        kb.add(InlineKeyboardButton(
            text="🛍️ Open Visual Shop (App View)", 
            web_app=WebAppInfo(url=f"{WEB_APP_URL}/shop?id={shop_id}")
        ))
        # ✅ END NEW CODE
        
        for p in page_items:
            icon = "🔴" if p.get("status") == "sold" else "🟢"
            kb.add(InlineKeyboardButton(f"{icon} {p['name']} - {p['price']}", callback_data=f"sh_view_{shop_id}_{p['id']}"))
        
        nav = []
        if session['page'] > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"buy_nav_{shop_id}_prev"))
        nav.append(InlineKeyboardButton(f"📄 {session['page']+1}", callback_data="ignore"))
        if end < total: nav.append(InlineKeyboardButton("➡️", callback_data=f"buy_nav_{shop_id}_next"))
        kb.row(*nav)
        
        filter_status = f"Cat: {shop.get('categories', {}).get(session['cat'], 'All')}" if session['cat'] else "📂 Cats"
        kb.row(InlineKeyboardButton(f"🔍 {session['search'] or 'Search'}", callback_data=f"buy_tool_{shop_id}_search"), 
               InlineKeyboardButton(filter_status, callback_data=f"buy_tool_{shop_id}_cat"), 
               InlineKeyboardButton("Sort", callback_data=f"buy_tool_{shop_id}_sort"))
        
        kb.add(InlineKeyboardButton("🛒 View Cart", callback_data="view_cart_main"))
        if session['cat'] or session['search']: kb.add(InlineKeyboardButton("❌ Clear Filters", callback_data=f"buy_tool_{shop_id}_clear"))
        kb.add(InlineKeyboardButton("❌ Close Shop", callback_data="main_menu_return"))
        
        text = f"🏪 <b>{shop['name']}</b>\n📦 <b>Products:</b> {total} found"
        
        chat_id = call.message.chat.id if hasattr(call, 'message') else call.chat.id
        message_id = call.message.message_id if hasattr(call, 'message') else None

        if message_id:
            try: bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=kb, parse_mode="HTML")
            except: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_nav_"))
    def handle_nav(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id, action = parts[2], parts[3]
        session = get_session(call.from_user.id)
        if action == "next": session['page'] += 1
        elif action == "prev" and session['page'] > 0: session['page'] -= 1
        render_shop_list(bot, call, shop_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_tool_"))
    def handle_tools(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id, tool = parts[2], parts[3]
        session = get_session(call.from_user.id)
        if tool == "sort":
            cycle = {'new': 'price_asc', 'price_asc': 'price_desc', 'price_desc': 'new'}
            session['sort'] = cycle.get(session['sort'], 'new')
            render_shop_list(bot, call, shop_id)
        elif tool == "clear":
            session['cat'] = None; session['search'] = None; session['page'] = 0
            render_shop_list(bot, call, shop_id)
        elif tool == "cat":
            shop = get_shop(shop_id)
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("📦 All", callback_data=f"buy_setcat_{shop_id}_all"))
            for cid, cname in shop.get('categories', {}).items(): kb.add(InlineKeyboardButton(cname, callback_data=f"buy_setcat_{shop_id}_{cid}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"view_prods_{shop_id}"))
            bot.edit_message_text("📂 <b>Select Category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        elif tool == "search":
            msg = bot.send_message(call.message.chat.id, "🔍 <b>Enter search keyword:</b>")
            bot.register_next_step_handler(msg, process_search, bot, shop_id, call)

    def process_search(message, bot, shop_id, original_call):
        session = get_session(message.from_user.id)
        session['search'] = message.text; session['page'] = 0
        try: bot.delete_message(message.chat.id, message.message_id); bot.delete_message(message.chat.id, message.message_id-1)
        except: pass
        render_shop_list(bot, original_call, shop_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_setcat_"))
    def set_category(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id, cat_id = parts[2], parts[3]
        session = get_session(call.from_user.id)
        session['cat'] = None if cat_id == "all" else cat_id
        session['page'] = 0
        render_shop_list(bot, call, shop_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_view_"))
    def view_product(call):
        bot.answer_callback_query(call.id)
        try:
            parts = call.data.split("_")
            shop_id = parts[2]
            prod_id = "_".join(parts[3:]) 
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            if not prod: return
            
            avg_rating, count_rating = get_product_rating(shop_id, prod_id)
            rating_txt = f"⭐ {avg_rating} ({count_rating} reviews)" if count_rating > 0 else "⭐ New"
            
            media_list = prod.get("media", [])
            use_thumbnail = prod.get("use_thumbnail", True)
            cat_tag = ""
            if prod.get("category"):
                cat_name = shop.get("categories", {}).get(prod["category"], "")
                if cat_name: cat_tag = f"\n🏷️ <b>#{cat_name}</b>"
            
            caption = (f"📦 <b>{prod['name']}</b>\n💰 <b>Price:</b> {prod['price']}\n{rating_txt}\n\n📝 <b>Description:</b>\n{prod.get('description', 'No desc')}{cat_tag}\n\n🏪 <b>Seller:</b> {shop['name']}")
            
            kb = InlineKeyboardMarkup()
            if use_thumbnail and len(media_list) > 1: kb.add(InlineKeyboardButton("📂 View Full Gallery", callback_data=f"sh_gallery_{shop_id}_{prod_id}"))
            
            if prod.get("status") == "sold": 
                kb.add(InlineKeyboardButton("❌ SOLD OUT", callback_data="sh_alert_sold"))
            else:
                kb.row(
                    InlineKeyboardButton("⚡ Buy Now", callback_data=f"pre_buy_{shop_id}_{prod_id}"),
                    InlineKeyboardButton("🛒 Add to Cart", callback_data=f"add_cart_{shop_id}_{prod_id}")
                )
                
            kb.add(InlineKeyboardButton(f"⭐ Reviews ({count_rating})", callback_data=f"view_revs_{shop_id}_{prod_id}"), InlineKeyboardButton("✍️ Rate", callback_data=f"rate_prod_{shop_id}_{prod_id}"))
            kb.add(InlineKeyboardButton("🔙 Back to List", callback_data=f"view_prods_{shop_id}"))
            
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            
            if use_thumbnail or len(media_list) == 1:
                m = media_list[0]
                if m["type"] == "photo": bot.send_photo(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
                else: bot.send_video(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                album = []
                for m in media_list:
                    if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"]))
                    elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"]))
                bot.send_media_group(call.message.chat.id, album)
                bot.send_message(call.message.chat.id, caption, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            print(f"Product View Error: {e}")
            bot.send_message(call.message.chat.id, "❌ Error viewing product.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("pre_buy_"))
    def pre_buy_check(call):
        bot.answer_callback_query(call.id)
        try:
            parts = call.data.split("_")
            shop_id = parts[2]
            prod_id = f"{parts[3]}_{parts[4]}" if len(parts) > 4 and parts[3] == "prod" else "_".join(parts[3:])
            
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            if not prod:
                bot.send_message(call.message.chat.id, "❌ Product not found.")
                return
            
            variants = prod.get("variants", [])
            if variants:
                kb = InlineKeyboardMarkup(row_width=1)
                for v in variants:
                    kb.add(InlineKeyboardButton(f"✨ {v['name']} - {v['price']}", callback_data=f"buy_v_{shop_id}_{prod_id}_{v['name']}"))
                kb.add(InlineKeyboardButton("🔙 Cancel", callback_data=f"sh_view_{shop_id}_{prod_id}"))
                
                text = f"💎 <b>Select a Variant for {prod['name']}:</b>"
                if call.message.content_type in ['photo', 'video']:
                    bot.edit_message_caption(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                else:
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            else:
                call.data = f"buy_step1_{shop_id}_{prod_id}"
                buy_step1(call)
        except:
            bot.send_message(call.message.chat.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_v_"))
    def handle_variant_buy(call):
        bot.answer_callback_query(call.id)
        try:
            parts = call.data.split("_")
            shop_id = parts[2]
            prod_id = f"{parts[3]}_{parts[4]}" # prod_timestamp
            v_name = "_".join(parts[5:]) 
            
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            v_price = prod['price']
            for v in prod.get('variants', []):
                if v['name'] == v_name:
                    v_price = v['price']
                    break
            
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton(f"⚡ Buy Now ({v_price})", callback_data=f"fin_buy_{shop_id}_{prod_id}_{v_price}_NONE_{v_name}"),
                InlineKeyboardButton("🛒 Add to Cart", callback_data=f"add_cart_v_{shop_id}_{prod_id}_{v_name}_{v_price}")
            )
            kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sh_view_{shop_id}_{prod_id}"))
            caption = f"📦 <b>{prod['name']}</b>\n💎 <b>Selected:</b> {v_name}\n💰 <b>Price:</b> {v_price}\n\n👇 <b>Select Action:</b>"
            if call.message.content_type in ['photo', 'video']:
                bot.edit_message_caption(caption, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            else:
                bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_sub_start_"))
    def buy_sub_step1(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id, price = parts[3], parts[4]
        msg = f"🔐 <b>Unlock Shop Access</b>\n\n💰 Price: {price}\n\n👇 Do you have a coupon?"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟️ Apply Coupon", callback_data=f"sub_ask_coup_{shop_id}_{price}"))
        kb.add(InlineKeyboardButton("✅ Proceed to Pay", callback_data=f"sub_fin_{shop_id}_{price}_NONE"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="main_menu_return"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sub_ask_coup_"))
    def sub_ask_coupon(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id, price = parts[3], parts[4]
        msg = bot.send_message(call.message.chat.id, "🎟️ <b>Enter Coupon Code:</b>")
        bot.register_next_step_handler(msg, process_sub_coupon, bot, shop_id, price)

    def process_sub_coupon(message, bot, shop_id, price):
        code = message.text.strip()
        coupon = validate_coupon(shop_id, code)
        try:
            original = float(price)
            if coupon:
                if coupon['type'] == 'percent': final = original - ((original * coupon['value']) / 100)
                else: final = original - coupon['value']
                if final < 0: final = 0
                msg = f"✅ <b>Coupon Applied!</b>\nOriginal: {original}\n<b>New Price: {final}</b>"
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Proceed to Pay", callback_data=f"sub_fin_{shop_id}_{final}_{code}"))
                bot.send_message(message.chat.id, msg, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Invalid Coupon.")
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Pay Original", callback_data=f"sub_fin_{shop_id}_{price}_NONE"))
                bot.send_message(message.chat.id, f"💰 Price: {price}", reply_markup=kb, parse_mode="HTML")
        except: bot.send_message(message.chat.id, "Error")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_step1_"))
    def buy_step1(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id = parts[2]
        prod_id = "_".join(parts[3:])
        shop = get_shop(shop_id)
        prod = shop["products"].get(prod_id)
        try: price = float(str(prod['price']).replace(',','').split()[0])
        except: price = 0
        msg = f"🛒 <b>Checkout</b>\n\n📦 <b>{prod['name']}</b>\n💰 Price: {prod['price']}\n\n👇 Do you have a coupon?"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟️ Apply Coupon", callback_data=f"ask_coup_{shop_id}_{prod_id}_{price}"))
        kb.add(InlineKeyboardButton("✅ Confirm Order", callback_data=f"fin_buy_{shop_id}_{prod_id}_{price}_NONE"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"sh_view_{shop_id}_{prod_id}"))
        bot.send_message(call.message.chat.id, msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("fin_buy_"))
    def ask_payment_proof(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        shop_id = parts[2]
        prod_id = f"{parts[3]}_{parts[4]}" # prod_timestamp
        price = parts[5]
        v_name = "_".join(parts[7:]) if len(parts) > 7 else "Standard"
        shop = get_shop(shop_id)
        pay_info = shop.get("payment_info", "Contact Seller")
        msg = (f"🧾 <b>Payment Instructions</b>\n{pay_info}\n\n💰 <b>Total to Pay: {price}</b>\n📦 Item: {v_name}\n\n📸 <b>Send Payment Screenshot now.</b>")
        sent = bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_proof, bot, shop_id, prod_id, price, v_name)

    def process_proof(message, bot, shop_id, prod_id, price, v_name):
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            order_id = create_order(shop_id, message.from_user.id, message.from_user.first_name, f"{prod['name']} ({v_name})", price, file_id, order_type="product")
            bot.reply_to(message, "✅ <b>Proof Submitted!</b>\nWaiting for seller approval.")
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ord_pay_ok_{shop_id}_{order_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"ord_pay_no_{shop_id}_{order_id}"))
            caption = (f"🔔 <b>New Order #{order_id[-4:]}</b>\n👤 Buyer: {message.from_user.first_name}\n📦 Item: {prod['name']} ({v_name})\n💰 Price: {price}\n👇 <b>Payment Proof:</b>")
            bot.send_photo(shop_id, file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else: bot.reply_to(message, "❌ Please send a screenshot.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_access_"))
    def handle_access_request(call):
        bot.answer_callback_query(call.id)
        shop_id = call.data.replace("req_access_", "")
        user_info = {"first_name": call.from_user.first_name, "username": call.from_user.username or "None"}
        if add_access_request(shop_id, call.from_user.id, user_info):
            bot.answer_callback_query(call.id, "✅ Sent!", show_alert=True)
            try:
                seller_kb = InlineKeyboardMarkup(row_width=2)
                seller_kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"req_ok_{call.from_user.id}"), InlineKeyboardButton("❌ Deny", callback_data=f"req_no_{call.from_user.id}"))
                bot.send_message(shop_id, f"🔔 <b>Request from {user_info['first_name']}</b>\nID: {call.from_user.id}", reply_markup=seller_kb, parse_mode="HTML")
            except: pass
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⏳ Pending", callback_data="ignore"), InlineKeyboardButton("🏠 Main", callback_data="main_menu_return"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🔒 <b>Request Sent</b>", reply_markup=kb, parse_mode="HTML")
        else: bot.answer_callback_query(call.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_gallery_"))
    def view_full_gallery(call):
        bot.answer_callback_query(call.id, "📂 Opening Gallery...")
        try:
            parts = call.data.split("_")
            shop_id, prod_id = parts[2], "_".join(parts[3:])
            prod = get_shop(shop_id)["products"].get(prod_id)
            media_list = prod.get("media", [])
            album = []
            for m in media_list:
                if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"]))
                elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"]))
            bot.send_media_group(call.message.chat.id, album)
        except: pass

    @bot.callback_query_handler(func=lambda c: c.data == "sh_alert_sold")
    def alert_sold(call):
        bot.answer_callback_query(call.id, "🚫 Sold out!", show_alert=True)

    # ==========================================
    # 🔍 SHOP SEARCH COMMAND (/shop user_name)
    # ==========================================

    @bot.message_handler(commands=['shop'])
    def search_shop_command(message):
        """ইউজার যখন /shop shop_username লিখে পাঠাবে"""
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ <b>ব্যবহার পদ্ধতি:</b>\n<code>/shop shop_username</code>\n\nউদাহরণ: <code>/shop my_store</code>", parse_mode="HTML")
            return
            
        query = parts[1].strip().replace("@", "")
        shop = get_shop_by_username(query)
        
        if shop:
            shop_id = str(shop['owner_id'])
            user_id = message.from_user.id
            privacy = shop.get("privacy", "public")
            approved_users = shop.get("approved_users", [])
            
            # ✅ প্রাইভেসি চেক
            if privacy == "private" and str(user_id) != shop_id and user_id not in approved_users:
                pending = shop.get("pending_requests", [])
                sub_price = shop.get("subscription_price", 0)
                kb = InlineKeyboardMarkup()
                if user_id in pending: kb.add(InlineKeyboardButton("⏳ Pending", callback_data="ignore"))
                else:
                    if sub_price > 0: kb.add(InlineKeyboardButton(f"💳 Buy Access ({sub_price})", callback_data=f"buy_sub_start_{shop_id}_{sub_price}"))
                    else: kb.add(InlineKeyboardButton("✋ Request Access", callback_data=f"req_access_{shop_id}"))
                kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu_return"))
                bot.send_message(message.chat.id, f"🔒 <b>{shop['name']} (Private)</b>\nYou need access to view this shop.", reply_markup=kb, parse_mode="HTML")
                return

            # ✅ FIXED: অটো ব্যানার ডিসপ্লে (ডিকশনারি ইরোর সমাধান)
            banner = shop.get("banner")
            if banner:
                caption = f"👋 Welcome to <b>{shop['name']}</b>"
                try:
                    if isinstance(banner, dict):
                        file_id = banner.get("file_id")
                        if banner.get("type") == "video":
                            bot.send_video(message.chat.id, file_id, caption=caption, parse_mode="HTML")
                        else:
                            bot.send_photo(message.chat.id, file_id, caption=caption, parse_mode="HTML")
                    elif isinstance(banner, str):
                        bot.send_photo(message.chat.id, banner, caption=caption, parse_mode="HTML")
                except: pass

            # ✅ সেশন সেট এবং শপ রেন্ডার
            buyer_sessions[user_id] = {'page': 0, 'cat': None, 'sort': 'new', 'search': None}
            render_shop_list(bot, message, shop_id)
        else:
            bot.reply_to(message, f"❌ <b>দুঃখিত!</b>\n'<code>{query}</code>' নামে কোনো শপ পাওয়া যায়নি।", parse_mode="HTML")
