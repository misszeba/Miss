import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import update_order_status, approve_access

def register_order_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ord_pay_ok_"))
    def approve_order(call):
        # ✅ Answer callback immediately to stop loading spinner
        bot.answer_callback_query(call.id, "⌛ Processing Approval...")
        
        parts = call.data.split("_")
        shop_id = parts[3]
        order_id = "_".join(parts[4:])
        
        order = update_order_status(shop_id, order_id, "paid")
        
        if order:
            # ✅ Safe caption editing (Prevents crash if message is an album)
            try:
                new_caption = (call.message.caption or "") + "\n\n✅ <b>STATUS: PAID</b>"
                bot.edit_message_caption(
                    caption=new_caption, 
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Caption Edit Error: {e}")
                # If caption edit fails, send a follow-up message instead
                bot.send_message(call.message.chat.id, f"✅ Order #{order_id[-4:]} marked as PAID.")
            
            # --- AUTO MEMBERSHIP GRANT ---
            if order.get("type") == "subscription":
                approve_access(shop_id, order['buyer_id'])
                try:
                    bot.send_message(
                        order['buyer_id'], 
                        f"🎉 <b>Membership Approved!</b>\nYou now have access to the shop.", 
                        parse_mode="HTML"
                    )
                except: pass
            else:
                # Regular Product
                try:
                    bot.send_message(
                        order['buyer_id'], 
                        f"🎉 <b>Payment Accepted!</b>\nYour order for <b>{order['item']}</b> is confirmed.", 
                        parse_mode="HTML"
                    )
                except: pass
        else:
            bot.send_message(call.message.chat.id, "❌ Error updating order status.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ord_pay_no_"))
    def reject_order(call):
        # ✅ Answer callback immediately
        bot.answer_callback_query(call.id, "⌛ Processing Rejection...")
        
        parts = call.data.split("_")
        shop_id = parts[3]
        order_id = "_".join(parts[4:])
        
        order = update_order_status(shop_id, order_id, "rejected")
        
        if order:
            # ✅ Safe caption editing
            try:
                new_caption = (call.message.caption or "") + "\n\n❌ <b>STATUS: REJECTED</b>"
                bot.edit_message_caption(
                    caption=new_caption, 
                    chat_id=call.message.chat.id, 
                    message_id=call.message.message_id, 
                    parse_mode="HTML"
                )
            except:
                bot.send_message(call.message.chat.id, f"❌ Order #{order_id[-4:]} REJECTED.")
            
            try:
                bot.send_message(
                    order['buyer_id'], 
                    f"❌ <b>Payment Rejected</b>\nYour order for <b>{order['item']}</b> was declined.", 
                    parse_mode="HTML"
                )
            except: pass
        else:
            bot.send_message(call.message.chat.id, "❌ Error updating order.")
