import telebot
import json
import io
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from utils.utils_shop import (
    get_shop, create_shop, add_product_to_shop, update_shop_desc, 
    set_shop_banner, delete_product, toggle_product_status, 
    update_product_field, toggle_product_thumbnail, get_categories, 
    toggle_shop_privacy, get_shop_backup_data, restore_shop_data,
    set_shop_channel, toggle_auto_post, schedule_post, set_payment_info,
    set_subscription_price, set_shop_username, delete_shop # ✅ প্রয়োজনীয় সব ইমপোর্ট
)
from handlers.shop_social import post_product_to_channel

media_cache = {}
pending_data = {}
seller_sessions = {}
ITEMS_PER_PAGE = 6

def get_session(user_id):
    if user_id not in seller_sessions: seller_sessions[user_id] = {'page': 0, 'search': None, 'cat': None}
    return seller_sessions[user_id]

def register_seller_handlers(bot):

    # --- Utility Functions ---
    def clean_up(user_id):
        if user_id in media_cache: del media_cache[user_id]
        if user_id in pending_data: del pending_data[user_id]

    # ==========================================
    # 🛒 PRODUCT MEDIA LOOP
    # ==========================================

    def process_media_loop(message, bot):
        user_id = message.from_user.id
        
        # ১. /done কমান্ড চেক
        if message.text and message.text.strip().lower() == '/done':
            finalize_product_save(message, bot)
            return

        # ২. মিডিয়া ফাইল প্রসেস করা
        file_data = None
        if message.content_type == 'photo': 
            file_data = {"type": "photo", "file_id": message.photo[-1].file_id}
        elif message.content_type == 'video': 
            file_data = {"type": "video", "file_id": message.video.file_id}
        elif message.content_type == 'animation': 
            file_data = {"type": "video", "file_id": message.animation.file_id}
        
        if file_data:
            if user_id not in media_cache: media_cache[user_id] = []
            media_cache[user_id].append(file_data)
            
            msg = bot.send_message(message.chat.id, f"✅ Added {len(media_cache[user_id])} files.\nSend more or type /done to finish.")
            bot.register_next_step_handler(msg, process_media_loop, bot)
        else:
            msg = bot.send_message(message.chat.id, "⚠️ Invalid file! Please send Photo/Video or type /done.")
            bot.register_next_step_handler(msg, process_media_loop, bot)

    def finalize_product_save(message, bot):
        user_id = message.from_user.id
        data = pending_data.get(user_id)
        files = media_cache.get(user_id, [])

        if not data or not files: 
            bot.send_message(message.chat.id, "❌ Error: No data or files found.")
            clean_up(user_id)
            return

        if data['action'] == 'add':
            if add_product_to_shop(user_id, data['name'], data['price'], data['desc'], files, data.get('category_id'), data.get('variants')):
                bot.send_message(message.chat.id, f"✅ Successfully Added: **{data['name']}**", parse_mode="Markdown")
                
                shop = get_shop(user_id)
                if shop and shop.get("auto_post") and shop.get("channel_id"):
                    prod_dummy = {"name": data['name'], "price": data['price'], "description": data['desc'], "media": files}
                    post_product_to_channel(bot, shop["channel_id"], prod_dummy, shop["name"], user_id, bot.get_me().username)
                
                show_dashboard(bot, message, shop)
        
        elif data['action'] == 'edit':
            if update_product_field(user_id, data['prod_id'], "media", files):
                bot.send_message(message.chat.id, "✅ Media Updated Successfully!")
                # রিডাইরেক্ট
                call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': f"sh_mng_{data['prod_id']}", 'message': message, 'id': '0'})
                manage_single_product(call_obj)
        
        clean_up(user_id)

    # ==========================================
    # 💼 BUSINESS & DASHBOARD
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "my_business")
    def open_business_menu(call):
        bot.answer_callback_query(call.id)
        clean_up(call.from_user.id)
        shop = get_shop(call.from_user.id)
        if not shop:
            msg = bot.send_message(call.message.chat.id, "💼 <b>Start Shop</b>\nEnter Name:")
            bot.register_next_step_handler(msg, process_create_shop, bot)
        else: show_dashboard(bot, call.message, shop)

    def show_dashboard(bot, message, shop):
        user_id = shop['owner_id']
        shop_link = f"https://t.me/{bot.get_me().username}?start=shop_{user_id}"
        
        # ✅ সপ ইউজারনেম ডিসপ্লে লজিক
        s_username = shop.get("shop_username")
        handle_txt = f"🆔 <b>Handle:</b> @{s_username}" if s_username else "🆔 <b>Handle:</b> ❌ Not Set"
        
        banner_status = "✅" if shop.get("banner") else "❌"
        privacy = shop.get("privacy", "public")
        priv_icon = "🔓 Public" if privacy == "public" else "🔒 Private"
        req_count = len(shop.get("pending_requests", []))
        req_btn = f"👥 Buyers ({req_count})" if req_count > 0 else "👥 Buyers"
        chan_status = "📢 ON" if shop.get("channel_id") else "📢 OFF"
        sub_price = shop.get("subscription_price", 0)
        sub_txt = f"💰 Fee: {sub_price}" if sub_price > 0 else "🆓 Free Entry"

        text = (f"🏪 <b>{shop['name']}</b>\n{handle_txt}\n🔗 <code>{shop_link}</code>\n📦 <b>Prods:</b> {len(shop['products'])}\n👁️ <b>Mode:</b> {priv_icon} ({sub_txt})")
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📦 Products", callback_data="shop_manage_menu"), InlineKeyboardButton("📂 Categories", callback_data="shop_cat_menu"))
        kb.add(InlineKeyboardButton("📊 Statistics", callback_data="shop_analytics_menu"), InlineKeyboardButton(f"👁️ {privacy.title()}", callback_data="shop_tog_privacy"))
        kb.add(InlineKeyboardButton(f"💵 {sub_txt}", callback_data="shop_set_fee"), InlineKeyboardButton(req_btn, callback_data="shop_req_menu"))
        kb.add(InlineKeyboardButton("📢 Broadcast", callback_data="shop_broadcast"), InlineKeyboardButton(chan_status, callback_data="shop_channel_menu"))
        kb.add(InlineKeyboardButton("🎫 Coupons", callback_data="shop_coupon_menu"), InlineKeyboardButton("💾 Backup", callback_data="shop_backup_menu"))
        kb.add(InlineKeyboardButton("💰 Pay Info", callback_data="shop_set_pay_info"), InlineKeyboardButton("➕ Add Product", callback_data="shop_add_prod"))
        kb.add(InlineKeyboardButton(f"🖼️ Banner: {banner_status}", callback_data="shop_set_banner"), InlineKeyboardButton("✏️ Desc", callback_data="shop_edit_info"))
        kb.add(InlineKeyboardButton("🆔 Set Username", callback_data="shop_set_username"), InlineKeyboardButton("🗑️ Delete Shop", callback_data="shop_delete_confirm"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu_return"))
        
        try: bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=text, reply_markup=kb, disable_web_page_preview=True, parse_mode="HTML")
        except: bot.send_message(message.chat.id, text, reply_markup=kb, disable_web_page_preview=True, parse_mode="HTML")

    # ==========================================
    # 💰 SETTINGS (FEE, PAY, PRIVACY, USERNAME)
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_username")
    def start_set_username(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🆔 <b>Set Shop Username</b>\n\n- ইউজার শুধু এই নাম লিখে সার্চ করলে আপনার সপ পাবে।\n- এটি ইউনিক হতে হবে (একই নাম ২ জন পাবে না)।\n- শুধুমাত্র অক্ষর (a-z), সংখ্যা (0-9) এবং আন্ডারস্কোর (_) ব্যবহার করুন।\n\n✍️ <b>পছন্দের ইউজারনেমটি লিখুন:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_shop_username, bot)

    def process_shop_username(message, bot):
        user_id = message.from_user.id
        username = message.text.strip()
        
        res, detail = set_shop_username(user_id, username)
        
        if res:
            bot.send_message(message.chat.id, f"✅ <b>সফল হয়েছে!</b>\nআপনার সপের ইউজারনেম এখন: <code>@{detail}</code>", parse_mode="HTML")
            show_dashboard(bot, message, get_shop(user_id))
        else:
            error_msg = "❌ "
            if detail == "Invalid format.": error_msg += "ভুল ফরম্যাট! ৩-২০ অক্ষরের নাম দিন (a-z, 0-9, _)।"
            elif detail == "Username already taken.": error_msg += "দুঃখিত, এই ইউজারনেমটি অন্য কেউ নিয়ে নিয়েছে!"
            else: error_msg += f"সমস্যা হয়েছে: {detail}"
            
            msg = bot.send_message(message.chat.id, f"{error_msg}\n\nআবার চেষ্টা করুন অথবা /cancel লিখে ফিরে যান।")
            bot.register_next_step_handler(msg, process_shop_username, bot)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_fee")
    def start_set_fee(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "💵 <b>Set Entry Fee</b>\nEnter price (0 for free):")
        bot.register_next_step_handler(msg, process_set_fee, bot)

    def process_set_fee(message, bot):
        try:
            price = float(message.text.strip())
            set_subscription_price(message.from_user.id, price)
            bot.reply_to(message, "✅ Fee Set!")
            show_dashboard(bot, message, get_shop(message.from_user.id))
        except: 
            msg = bot.reply_to(message, "❌ Invalid number. Please enter only numbers (e.g. 500):")
            bot.register_next_step_handler(msg, process_set_fee, bot)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_pay_info")
    def start_pay_info(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "💰 <b>Set Payment Instructions</b>")
        bot.register_next_step_handler(msg, process_pay_info, bot)

    def process_pay_info(message, bot):
        if set_payment_info(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Updated!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data == "shop_tog_privacy")
    def toggle_privacy(call):
        bot.answer_callback_query(call.id, "Updating Privacy...")
        toggle_shop_privacy(call.from_user.id)
        show_dashboard(bot, call.message, get_shop(call.from_user.id))

    def process_create_shop(message, bot):
        if create_shop(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Shop Created!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    # ==========================================
    # 🗑️ DELETE SHOP LOGIC
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_delete_confirm")
    def confirm_delete_shop(call):
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Yes, Delete Forever", callback_data="shop_delete_final"),
            InlineKeyboardButton("❌ No, Cancel", callback_data="my_business")
        )
        text = "⚠️ <b>Are you absolutely sure?</b>\n\nThis will permanently delete your shop, all products, categories, and orders from the database. This action cannot be undone!"
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_delete_final")
    def final_delete_shop(call):
        if delete_shop(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ Shop deleted successfully.", show_alert=True)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="👋 <b>Your shop has been deleted.</b>\nYou can create a new one anytime from the Business menu.", parse_mode="HTML")
        else:
            bot.answer_callback_query(call.id, "❌ Error: Could not delete shop.", show_alert=True)

    # ==========================================
    # 📢 CHANNEL INTEGRATION
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_channel_menu")
    def channel_menu(call):
        bot.answer_callback_query(call.id)
        shop = get_shop(call.from_user.id)
        if not shop: return
        chan_id = shop.get("channel_id")
        auto_post = shop.get("auto_post", False)
        status_txt = f"ID: {chan_id}" if chan_id else "❌ Not Connected"
        auto_txt = "✅ ON" if auto_post else "❌ OFF"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✏️ Set Channel ID", callback_data="shop_set_chan"))
        if chan_id: kb.add(InlineKeyboardButton(f"🔄 Auto-Post: {auto_txt}", callback_data="shop_tog_autopost"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        text = (f"📢 <b>Channel Integration</b>\n\n📡 <b>Connected:</b> {status_txt}\n⚡ <b>Auto-Post:</b> {auto_txt}")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_chan")
    def ask_channel_id(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📢 <b>Send Channel ID:</b>\n(e.g. -100123456789)")
        bot.register_next_step_handler(msg, process_channel_id, bot)

    def process_channel_id(message, bot):
        try:
            cid = int(message.text.strip())
            set_shop_channel(message.from_user.id, cid)
            bot.reply_to(message, "✅ Connected!")
            call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': "shop_channel_menu", 'message': message, 'id': '0'})
            channel_menu(call_obj)
        except: 
            msg = bot.reply_to(message, "❌ Invalid ID. Make sure it starts with -100 and has only numbers:")
            bot.register_next_step_handler(msg, process_channel_id, bot)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_tog_autopost")
    def toggle_auto(call):
        bot.answer_callback_query(call.id, "Toggling...")
        toggle_auto_post(call.from_user.id)
        channel_menu(call)

    # ==========================================
    # 🚀 POSTING & SCHEDULING
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("post_menu_"))
    def post_options(call):
        bot.answer_callback_query(call.id)
        prod_id = call.data.replace("post_menu_", "")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🚀 Post Now", callback_data=f"do_post_{prod_id}"))
        kb.add(InlineKeyboardButton("⏰ Schedule", callback_data=f"do_sched_{prod_id}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sh_mng_{prod_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="📢 <b>Post Options</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("do_post_"))
    def execute_post(call):
        prod_id = call.data.replace("do_post_", "")
        shop = get_shop(call.from_user.id)
        if not shop or not shop.get("channel_id"):
            bot.answer_callback_query(call.id, "❌ No Channel Connected!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Posting...")
        prod = shop["products"].get(prod_id)
        if post_product_to_channel(bot, shop["channel_id"], prod, shop["name"], call.from_user.id, bot.get_me().username):
            bot.send_message(call.message.chat.id, "✅ Product Posted Successfully!")
        else: bot.send_message(call.message.chat.id, "❌ Failed to post.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("do_sched_"))
    def ask_schedule_time(call):
        bot.answer_callback_query(call.id)
        prod_id = call.data.replace("do_sched_", "")
        msg = bot.send_message(call.message.chat.id, "⏰ Enter minutes from now to post:")
        bot.register_next_step_handler(msg, process_schedule, bot, prod_id)

    def process_schedule(message, bot, prod_id):
        try:
            mins = int(message.text.strip())
            run_at = int(time.time()) + (mins * 60)
            schedule_post(message.from_user.id, prod_id, run_at)
            bot.reply_to(message, f"✅ Scheduled to post in {mins} minutes.")
        except: 
            msg = bot.reply_to(message, "❌ Please enter a valid number of minutes:")
            bot.register_next_step_handler(msg, process_schedule, bot, prod_id)

    # ==========================================
    # 💾 BACKUP & RESTORE
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_menu")
    def backup_menu(call):
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📥 Download Backup", callback_data="shop_backup_dl"))
        kb.add(InlineKeyboardButton("📤 Restore Backup", callback_data="shop_backup_ul"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="💾 <b>Backup & Restore</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_dl")
    def download_backup(call):
        bot.answer_callback_query(call.id, "Generating file...")
        data = get_shop_backup_data(call.from_user.id)
        if not data: return
        f = io.BytesIO(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8'))
        f.name = f"Backup_{call.from_user.id}.json"
        bot.send_document(call.message.chat.id, f, caption=f"✅ Shop Backup - {time.strftime('%Y-%m-%d')}")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_ul")
    def ask_restore(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📤 Send your backup `.json` file:")
        bot.register_next_step_handler(msg, process_restore, bot)

    def process_restore(message, bot):
        if not message.document:
            bot.reply_to(message, "❌ Please send a valid `.json` file.")
            return
        try:
            f = bot.download_file(bot.get_file(message.document.file_id).file_path)
            res, txt = restore_shop_data(message.from_user.id, json.loads(f.decode()))
            bot.reply_to(message, txt)
            if res: show_dashboard(bot, message, get_shop(message.from_user.id))
        except Exception as e: bot.reply_to(message, f"❌ Error: {str(e)}")

    # ==========================================
    # 📦 MANAGE PRODUCTS (LISTING)
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_manage_menu")
    def init_manage_menu(call):
        bot.answer_callback_query(call.id)
        seller_sessions[call.from_user.id] = {'page': 0, 'search': None, 'cat': None}
        render_manage_list(bot, call)

    def render_manage_list(bot, call):
        user_id = call.from_user.id
        shop = get_shop(user_id)
        session = get_session(user_id)
        if not shop.get('products'):
            bot.answer_callback_query(call.id, "❌ No products found.", show_alert=True)
            return
        products = []
        for pid, data in shop['products'].items():
            if session['search'] and session['search'].lower() not in data['name'].lower(): continue
            products.append({'id': pid, **data})
        products.sort(key=lambda x: x['id'], reverse=True)
        total = len(products)
        start = session['page'] * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = products[start:end]
        kb = InlineKeyboardMarkup(row_width=1)
        for p in page_items:
            status = "🟢" if p.get("status", "active") == "active" else "🔴"
            kb.add(InlineKeyboardButton(f"{status} {p['name']} - {p['price']}", callback_data=f"sh_mng_{p['id']}"))
        
        nav = []
        if session['page'] > 0: nav.append(InlineKeyboardButton("⬅️", callback_data="sell_nav_prev"))
        nav.append(InlineKeyboardButton(f"📄 {session['page']+1}", callback_data="ignore"))
        if end < total: nav.append(InlineKeyboardButton("➡️", callback_data="sell_nav_next"))
        kb.row(*nav)
        kb.row(InlineKeyboardButton(f"🔍 {session['search'] or 'Search'}", callback_data="sell_tool_search"), InlineKeyboardButton("❌ Clear", callback_data="sell_tool_clear"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        
        text = f"🛠 <b>Manage Products</b>\nItems: {len(page_items)}/{total}"
        if session['search']: text += f"\n🔍 Filter: {session['search']}"
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sell_nav_"))
    def seller_nav(call):
        bot.answer_callback_query(call.id)
        session = get_session(call.from_user.id)
        if "next" in call.data: session['page'] += 1
        elif "prev" in call.data and session['page'] > 0: session['page'] -= 1
        render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data == "sell_tool_clear")
    def seller_clear(call):
        bot.answer_callback_query(call.id, "Filters cleared")
        get_session(call.from_user.id)['search'] = None
        render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data == "sell_tool_search")
    def seller_search(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🔍 Enter keyword to search in products:")
        bot.register_next_step_handler(msg, process_seller_search, bot, call)

    def process_seller_search(message, bot, original_call):
        get_session(message.from_user.id)['search'] = message.text
        try: bot.delete_message(message.chat.id, message.message_id); bot.delete_message(message.chat.id, message.message_id-1)
        except: pass
        render_manage_list(bot, original_call)

    # ==========================================
    # 📝 MANAGE SINGLE PRODUCT
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_mng_"))
    def manage_single_product(call):
        bot.answer_callback_query(call.id)
        prod_id = call.data.replace("sh_mng_", "")
        shop = get_shop(call.from_user.id)
        prod = shop['products'].get(prod_id)
        if not prod: 
            bot.send_message(call.message.chat.id, "❌ Product not found.")
            return
        cat_name = shop.get("categories", {}).get(prod.get("category"), "None")
        text = (f"📦 <b>{prod['name']}</b>\n💰 Price: {prod['price']}\n📂 Category: <b>{cat_name}</b>\n🖼️ Thumbnail: {'ON' if prod.get('use_thumbnail', True) else 'OFF'}\nStatus: {prod.get('status', 'active').upper()}")
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("👁️ Preview", callback_data=f"sh_prev_{prod_id}"), InlineKeyboardButton("📢 Post Option", callback_data=f"post_menu_{prod_id}"))
        kb.add(InlineKeyboardButton("✏️ Name", callback_data=f"ed_nm_{prod_id}"), InlineKeyboardButton("✏️ Price", callback_data=f"ed_pr_{prod_id}"))
        kb.add(InlineKeyboardButton("✏️ Category", callback_data=f"ed_cat_{prod_id}"), InlineKeyboardButton("🖼️ Edit Media", callback_data=f"ed_md_{prod_id}"))
        kb.add(InlineKeyboardButton("Toggle Thumb", callback_data=f"sh_tog_th_{prod_id}"), InlineKeyboardButton("Toggle Status", callback_data=f"sh_tog_{prod_id}"))
        kb.add(InlineKeyboardButton("🗑️ Delete", callback_data=f"sh_del_{prod_id}"), InlineKeyboardButton("🔙 Back", callback_data="shop_manage_menu"))
        
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    # ==========================================
    # ➕ ADD PRODUCT FLOW
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data == "shop_add_prod")
    def start_add_product(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📝 <b>Step 1/4:</b> Enter Product Name:")
        bot.register_next_step_handler(msg, process_prod_name, bot)

    def process_prod_name(message, bot):
        name = message.text
        msg = bot.send_message(message.chat.id, f"💰 <b>Step 2/4:</b> Base Price for '{name}':")
        bot.register_next_step_handler(msg, process_prod_price, bot, name)

    def process_prod_price(message, bot, name):
        price = message.text.strip()
        msg = bot.send_message(message.chat.id, "📄 <b>Step 3/4:</b> Enter Product Description:")
        bot.register_next_step_handler(msg, process_prod_desc, bot, name, price)

    def process_prod_desc(message, bot, name, price):
        desc = message.text
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("➕ Add Variant (Package/Size)", callback_data="add_variant_input"),
               InlineKeyboardButton("🚫 No Variant", callback_data="skip_variant"))
        pending_data[message.from_user.id] = {'name': name, 'price': price, 'desc': desc, 'variants': [], 'action': 'add'}
        bot.send_message(message.chat.id, "📦 <b>Step 4/4:</b> Does this product have multiple variants?", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "add_variant_input")
    def ask_variant_name(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📝 Enter Variant Name (e.g. 1 Month, XL, Premium):")
        bot.register_next_step_handler(msg, process_variant_name, bot)

    def process_variant_name(message, bot):
        v_name = message.text
        msg = bot.send_message(message.chat.id, f"💰 Enter Price for **{v_name}**:")
        bot.register_next_step_handler(msg, process_variant_price, bot, v_name)

    def process_variant_price(message, bot, v_name):
        try:
            v_price = float(message.text.strip())
            user_id = message.from_user.id
            if user_id in pending_data:
                pending_data[user_id]['variants'].append({'name': v_name, 'price': v_price})
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("➕ Add Another", callback_data="add_variant_input"),
                       InlineKeyboardButton("✅ Done & Continue", callback_data="skip_variant"))
                bot.send_message(message.chat.id, f"✅ Added: {v_name} - {v_price}\nAdd more variants or continue?", reply_markup=kb)
        except:
            msg = bot.reply_to(message, "❌ Invalid price. Please enter only numbers for the variant price:")
            bot.register_next_step_handler(msg, process_variant_price, bot, v_name)

    @bot.callback_query_handler(func=lambda c: c.data == "skip_variant")
    def finalize_product_step(call):
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        data = pending_data.get(user_id)
        if not data: return
        cats = get_categories(user_id)
        if not cats: ask_for_media(call.message, bot, data['name'], data['price'], data['desc'], None)
        else:
            kb = InlineKeyboardMarkup(row_width=2)
            for cid, cname in cats.items(): kb.add(InlineKeyboardButton(cname, callback_data=f"sel_cat_{cid}"))
            kb.add(InlineKeyboardButton("Skip Category", callback_data="sel_cat_skip"))
            bot.edit_message_text("📂 <b>Select Category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sel_cat_"))
    def category_selected(call):
        bot.answer_callback_query(call.id)
        user_id = call.from_user.id
        data = pending_data.get(user_id)
        if not data: return
        cat_id = call.data.replace("sel_cat_", "")
        if cat_id == "skip": cat_id = None
        ask_for_media(call.message, bot, data['name'], data['price'], data['desc'], cat_id)

    def ask_for_media(message, bot, name, price, desc, cat_id):
        user_id = message.from_user.id
        media_cache[user_id] = [] 
        if user_id in pending_data:
            pending_data[user_id].update({'category_id': cat_id})
        msg = bot.send_message(message.chat.id, "📸 <b>Gallery Upload:</b>\nSend Photos/Videos one by one.\n⚠️ <b>Type /done when finished.</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_media_loop, bot)

    # ==========================================
    # ✏️ EDIT PRODUCT ACTIONS
    # ==========================================

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_del_"))
    def delete_handler(call):
        bot.answer_callback_query(call.id, "Deleting...")
        if delete_product(call.from_user.id, call.data.replace("sh_del_", "")):
            render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_tog_"))
    def toggle_status_handler(call):
        bot.answer_callback_query(call.id, "Toggling...")
        prod_id = call.data.replace("sh_tog_", "")
        if "th_" in call.data: toggle_product_thumbnail(call.from_user.id, prod_id.replace("th_", ""))
        else: toggle_product_status(call.from_user.id, prod_id)
        call.data = f"sh_mng_{prod_id.replace('th_', '')}"
        manage_single_product(call)

    # ✅ ব্যানার সেট করার আপডেট (ভিডিও এবং ফটো সাপোর্ট)
    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_banner")
    def start_set_banner(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🖼️ Send a <b>Photo</b> or <b>Video</b> to set as Shop Banner:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_banner, bot)

    def process_banner(message, bot):
        user_id = message.from_user.id
        media_data = None
        
        if message.photo:
            media_data = {"file_id": message.photo[-1].file_id, "type": "photo"}
        elif message.video:
            media_data = {"file_id": message.video.file_id, "type": "video"}
        elif message.animation:
            media_data = {"file_id": message.animation.file_id, "type": "video"}
            
        if media_data:
            if set_shop_banner(user_id, media_data):
                bot.send_message(message.chat.id, "✅ <b>Banner Updated!</b>", parse_mode="HTML")
                show_dashboard(bot, message, get_shop(user_id))
            else:
                bot.reply_to(message, "❌ ডাটাবেসে সেভ করতে সমস্যা হয়েছে।")
        else:
            bot.reply_to(message, "❌ Please send a Photo or Video.")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_edit_info")
    def start_edit_info(call):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📝 Send new shop description:")
        bot.register_next_step_handler(msg, process_edit_desc, bot)

    def process_edit_desc(message, bot):
        if update_shop_desc(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Description Updated!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_cat_"))
    def edit_cat_start(call):
        bot.answer_callback_query(call.id)
        prod_id = call.data.replace("ed_cat_", "")
        cats = get_categories(call.from_user.id)
        kb = InlineKeyboardMarkup(row_width=2)
        for cid, cname in cats.items(): kb.add(InlineKeyboardButton(cname, callback_data=f"set_cat_{prod_id}_{cid}"))
        kb.add(InlineKeyboardButton("Remove Category", callback_data=f"set_cat_{prod_id}_none"))
        bot.send_message(call.message.chat.id, "Select new category:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("set_cat_"))
    def set_new_cat(call):
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        prod_id, cat_id = parts[2], parts[3]
        if cat_id == "none": cat_id = None
        update_product_field(call.from_user.id, prod_id, "category", cat_id)
        bot.send_message(call.message.chat.id, "✅ Category Updated!")
        call.data = f"sh_mng_{prod_id}"
        manage_single_product(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_md_"))
    def edit_media_start(call):
        bot.answer_callback_query(call.id)
        pid = call.data.replace("ed_md_", "")
        media_cache[call.from_user.id] = []
        pending_data[call.from_user.id] = {'action': 'edit', 'prod_id': pid}
        msg = bot.send_message(call.message.chat.id, "🖼️ Send new Gallery files. Type /done when finished.")
        bot.register_next_step_handler(msg, process_media_loop, bot)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_nm_"))
    def edit_name_start(call):
        bot.answer_callback_query(call.id)
        pid = call.data.replace("ed_nm_", "")
        msg = bot.send_message(call.message.chat.id, "✏️ Enter New Product Name:")
        bot.register_next_step_handler(msg, process_edit_field, bot, pid, "name")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_pr_"))
    def edit_price_start(call):
        bot.answer_callback_query(call.id)
        pid = call.data.replace("ed_pr_", "")
        msg = bot.send_message(call.message.chat.id, "✏️ Enter New Price:")
        bot.register_next_step_handler(msg, process_edit_field, bot, pid, "price")

    def process_edit_field(message, bot, pid, field):
        if update_product_field(message.from_user.id, pid, field, message.text):
            bot.send_message(message.chat.id, f"✅ {field.title()} Updated!")
            call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': f"sh_mng_{pid}", 'message': message, 'id': '0'})
            manage_single_product(call_obj)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_prev_"))
    def preview_product(call):
        bot.answer_callback_query(call.id, "Generating Preview...")
        prod_id = call.data.replace("sh_prev_", "")
        shop = get_shop(call.from_user.id)
        prod = shop['products'].get(prod_id)
        media_list = prod.get("media", [])
        use_thumbnail = prod.get("use_thumbnail", True)
        cat_tag = ""
        if prod.get("category"):
            cat_name = shop.get("categories", {}).get(prod["category"], "")
            if cat_name: cat_tag = f"\n🏷️ <b>#{cat_name}</b>"
        
        caption = (f"📦 <b>{prod['name']}</b>\n💰 Price: {prod['price']}\n\n📝 {prod.get('description', '')}{cat_tag}\n\n🏪 <b>Seller:</b> {shop['name']}")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back to Management", callback_data=f"sh_mng_{prod_id}"))
        
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        
        if use_thumbnail or len(media_list) == 1:
            m = media_list[0]
            if m["type"] == "photo": bot.send_photo(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
            else: bot.send_video(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            album = []
            for i, m in enumerate(media_list):
                cap = caption if i == 0 else ""
                if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"], caption=cap, parse_mode="HTML"))
                elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"], caption=cap, parse_mode="HTML"))
            bot.send_media_group(call.message.chat.id, album)
            bot.send_message(call.message.chat.id, "🔼 Preview Gallery above.", reply_markup=kb)
