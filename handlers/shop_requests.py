import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop, approve_access, deny_access, manual_add_buyer

def register_request_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_req_menu")
    def request_menu(call):
        # ✅ Answer callback to stop loading spinner
        bot.answer_callback_query(call.id)
        shop = get_shop(call.from_user.id)
        if not shop: return
        
        pending = shop.get("pending_requests", [])
        approved = shop.get("approved_users", [])
        
        text = (f"👥 <b>Buyer Management</b>\n\n"
                f"⏳ Pending Requests: {len(pending)}\n"
                f"✅ Approved Buyers: {len(approved)}")
        
        kb = InlineKeyboardMarkup(row_width=1)
        if pending: 
            kb.add(InlineKeyboardButton("🔔 View Pending Requests", callback_data="shop_view_pending"))
        kb.add(InlineKeyboardButton("📜 View Buyer List", callback_data="shop_view_buyers"))
        kb.add(InlineKeyboardButton("➕ Manually Add User", callback_data="shop_add_manual"))
        kb.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="my_business"))
        
        try: 
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: 
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_view_pending")
    def view_pending(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        shop = get_shop(call.from_user.id)
        pending = shop.get("pending_requests", [])
        
        if not pending:
            # If no requests, return to main request menu
            bot.answer_callback_query(call.id, "✅ No pending requests left.", show_alert=True)
            request_menu(call)
            return
            
        target_id = pending[0]
        info = shop.get("customers", {}).get(str(target_id), {})
        name = info.get('first_name', 'Unknown')
        username = f"@{info.get('username')}" if info.get('username') else "No Username"
        
        text = (f"🔔 <b>New Access Request</b>\n\n"
                f"👤 <b>Name:</b> {name}\n"
                f"🔗 <b>User:</b> {username}\n"
                f"🆔 <b>ID:</b> <code>{target_id}</code>")
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Approve", callback_data=f"req_ok_{target_id}"), 
            InlineKeyboardButton("❌ Deny", callback_data=f"req_no_{target_id}")
        )
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_req_menu"))
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_ok_"))
    def approve_handler(call):
        # ✅ Answer callback immediately
        bot.answer_callback_query(call.id, "Processing Approval...")
        target_id = int(call.data.replace("req_ok_", ""))
        
        if approve_access(call.from_user.id, target_id):
            try: 
                bot.send_message(target_id, "🎉 <b>Access Granted!</b>\nYou can now browse the shop.", parse_mode="HTML")
            except: pass
            
            # Refresh to show next request
            view_pending(call)
        else: 
            bot.answer_callback_query(call.id, "❌ Error approving request.", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_no_"))
    def deny_handler(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id, "Processing Denial...")
        target_id = int(call.data.replace("req_no_", ""))
        
        if deny_access(call.from_user.id, target_id):
            # Refresh to show next request
            view_pending(call)
        else:
            bot.answer_callback_query(call.id, "❌ Error denying request.", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_view_buyers")
    def view_buyers_list(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        shop = get_shop(call.from_user.id)
        approved = shop.get("approved_users", [])
        customers = shop.get("customers", {})
        
        if not approved:
            bot.answer_callback_query(call.id, "No approved buyers yet.", show_alert=True)
            return
            
        msg = "📜 <b>Approved Buyers List:</b>\n\n"
        count = 1
        for uid in approved:
            info = customers.get(str(uid), {})
            name = info.get('first_name', 'Unknown')
            username = info.get('username', 'None')
            msg += f"{count}. <b>{name}</b> (@{username}) - <code>{uid}</code>\n"
            count += 1
            if count > 30: 
                msg += "\n<i>...showing first 30 buyers.</i>"
                break
                
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_req_menu"))
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_add_manual")
    def start_manual_add(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "➕ <b>Add Buyer Manually</b>\nPlease send the User ID (Telegram ID) of the person:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_manual_add, bot)

    def process_manual_add(message, bot):
        try:
            target_id = int(message.text.strip())
            if manual_add_buyer(message.from_user.id, target_id):
                bot.reply_to(message, f"✅ User <code>{target_id}</code> has been approved!", parse_mode="HTML")
                # Return to menu
                call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': "shop_req_menu", 'message': message, 'id': '0'})
                request_menu(call_obj)
            else: 
                bot.reply_to(message, "❌ User is already approved or an error occurred.")
        except ValueError:
            msg = bot.reply_to(message, "❌ Invalid ID! Please send numbers only (User ID):")
            bot.register_next_step_handler(msg, process_manual_add, bot)
