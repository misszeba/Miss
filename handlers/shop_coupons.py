import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import create_coupon, delete_coupon, get_coupons

coupon_cache = {}

def register_coupon_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_coupon_menu")
    def coupon_menu(call):
        # ✅ Answer callback to stop loading spinner
        bot.answer_callback_query(call.id)
        show_coupon_menu(bot, call.message.chat.id, call.from_user.id, call.message.message_id)

    def show_coupon_menu(bot, chat_id, user_id, message_id=None):
        coupons = get_coupons(user_id)
        kb = InlineKeyboardMarkup(row_width=1)
        for code, data in coupons.items():
            val = f"{data['value']}%" if data['type'] == 'percent' else f"{data['value']} BDT"
            kb.add(InlineKeyboardButton(f"🗑️ {code} ({val})", callback_data=f"del_coup_{code}"))
        
        kb.add(InlineKeyboardButton("➕ Create New Coupon", callback_data="add_coupon_start"))
        kb.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="my_business"))
        
        text = f"🎫 <b>Manage Coupons</b>\nYou have {len(coupons)} active coupons."
        
        try: 
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: 
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_coup_"))
    def delete_handler(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id, "Deleting...")
        code = call.data.replace("del_coup_", "")
        delete_coupon(call.from_user.id, code)
        show_coupon_menu(bot, call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "add_coupon_start")
    def start_add(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "🎫 <b>Step 1/3:</b> Send Coupon Code (e.g. SALE50):", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_code, bot)

    def process_code(message, bot):
        code = message.text.upper().strip()
        if len(code) < 2:
            msg = bot.reply_to(message, "❌ Coupon code too short. Please enter a valid code:")
            bot.register_next_step_handler(msg, process_code, bot)
            return

        coupon_cache[message.from_user.id] = {'code': code}
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("Percent (%)", callback_data="coup_type_percent"), 
            InlineKeyboardButton("Flat Amount", callback_data="coup_type_flat")
        )
        bot.send_message(message.chat.id, f"🎫 <b>Step 2/3:</b> Choose Discount Type for <b>{code}</b>:", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("coup_type_"))
    def type_handler(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        ctype = call.data.replace("coup_type_", "")
        if call.from_user.id in coupon_cache:
            coupon_cache[call.from_user.id]['type'] = ctype
            label = "Percentage (e.g. 10 for 10%)" if ctype == "percent" else "Amount (e.g. 50 for 50 BDT)"
            msg = bot.send_message(call.message.chat.id, f"🎫 <b>Step 3/3:</b> Enter Discount {label}:", parse_mode="HTML")
            bot.register_next_step_handler(msg, process_value, bot)

    def process_value(message, bot):
        user_id = message.from_user.id
        data = coupon_cache.get(user_id)
        if not data: return
        
        try:
            val = float(message.text.strip())
            create_coupon(user_id, data['code'], data['type'], val)
            bot.send_message(message.chat.id, f"✅ Coupon <b>{data['code']}</b> created successfully!", parse_mode="HTML")
            show_coupon_menu(bot, message.chat.id, user_id, None)
            if user_id in coupon_cache:
                del coupon_cache[user_id]
        except ValueError:
            # ✅ Fixed: Re-registering step handler on invalid input
            msg = bot.reply_to(message, "❌ Invalid number! Please enter only digits (e.g. 10 or 100):")
            bot.register_next_step_handler(msg, process_value, bot)
