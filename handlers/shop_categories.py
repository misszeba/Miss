import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop, create_category, delete_category, get_categories

def register_category_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_cat_menu")
    def category_menu(call):
        # ✅ Answer callback to stop loading spinner
        bot.answer_callback_query(call.id)
        show_category_menu(bot, call.message.chat.id, call.from_user.id, message_id=call.message.message_id)

    def show_category_menu(bot, chat_id, user_id, message_id=None):
        cats = get_categories(user_id)
        kb = InlineKeyboardMarkup(row_width=1)
        for cid, name in cats.items():
            kb.add(InlineKeyboardButton(f"🗑️ Delete: {name}", callback_data=f"del_cat_{cid}"))
        kb.add(InlineKeyboardButton("➕ Create New Category", callback_data="add_new_cat"))
        kb.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="my_business"))
        
        text = f"📂 <b>Manage Categories</b>\nYou have {len(cats)} categories."
        
        if message_id:
            try: 
                bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="HTML")
            except: 
                bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
        else: 
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "add_new_cat")
    def start_add_cat(call):
        # ✅ Answer callback
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📂 <b>Enter Category Name:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_add_cat, bot)

    def process_add_cat(message, bot):
        if not message.text or message.text.startswith('/'):
            msg = bot.send_message(message.chat.id, "❌ Invalid name. Please enter a valid category name:")
            bot.register_next_step_handler(msg, process_add_cat, bot)
            return

        if create_category(message.from_user.id, message.text):
            bot.send_message(message.chat.id, f"✅ Category '<b>{message.text}</b>' created!", parse_mode="HTML")
            show_category_menu(bot, message.chat.id, message.from_user.id, message_id=None)
        else: 
            bot.send_message(message.chat.id, "❌ Error creating category.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_cat_"))
    def process_del_cat(call):
        cat_id = call.data.replace("del_cat_", "")
        if delete_category(call.from_user.id, cat_id):
            bot.answer_callback_query(call.id, "✅ Category Deleted")
            show_category_menu(bot, call.message.chat.id, call.from_user.id, message_id=call.message.message_id)
        else: 
            bot.answer_callback_query(call.id, "❌ Error deleting category.", show_alert=True)
