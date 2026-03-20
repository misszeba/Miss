import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop_analytics

def register_analytics_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_analytics_menu")
    def show_analytics(call):
        # ✅ Answer callback to stop loading spinner
        bot.answer_callback_query(call.id, "📊 Fetching latest stats...")
        
        stats = get_shop_analytics(call.from_user.id)
        if not stats:
            bot.answer_callback_query(call.id, "❌ Analytics data not available.", show_alert=True)
            return
            
        text = (
            f"📊 <b>Shop Analytics Overview</b>\n\n"
            f"💰 <b>Total Revenue:</b> {stats['revenue']} BDT\n"
            f"📦 <b>Orders Breakdown:</b>\n"
            f"   ├ ✅ Paid: {stats['paid']}\n"
            f"   ├ ⏳ Pending: {stats['pending']}\n"
            f"   └ ❌ Rejected: {stats['rejected']}\n\n"
            f"👥 <b>Total Members:</b> {stats['members']}\n"
            f"🛍️ <b>Total Products:</b> {stats['total_products']}\n\n"
            f"🏆 <b>Top Selling Item:</b>\n   └ {stats['best_seller']}"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔄 Refresh Stats", callback_data="shop_analytics_menu"))
        kb.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="my_business"))
        
        try: 
            bot.edit_message_text(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                text=text, 
                reply_markup=kb, 
                parse_mode="HTML"
            )
        except telebot.apihelper.ApiTelegramException as e:
            # If the data hasn't changed, Telegram throws an error. We handle it gracefully.
            if "message is not modified" in str(e).lower():
                bot.answer_callback_query(call.id, "✅ Stats are already up-to-date.")
            else:
                bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
