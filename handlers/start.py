from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.main_menu import main_menu
from utils.utils import get_text, track_user, delete_msg # New Import
from utils.utils_shop import get_shop

def register_start(bot):
    @bot.message_handler(commands=["start"])
    def start(message):
        # 🧹 Auto Clean: Delete User's Command
        delete_msg(bot, message)
        
        user_id = message.from_user.id
        track_user(message.from_user)
        
        args = message.text.split()
        
        # --- SHOP DEEP LINK ---
        if len(args) > 1 and args[1].startswith("shop_"):
            shop_owner_id = args[1].replace("shop_", "")
            shop = get_shop(shop_owner_id)
            
            if shop:
                text = (
                    f"🏪 <b>Welcome to {shop['name']}</b>\n"
                    f"<i>{shop['description']}</i>\n\n"
                    f"👇 <b>Browse our products below:</b>"
                )
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("📦 Browse Products", callback_data=f"view_prods_{shop_owner_id}"))
                kb.add(InlineKeyboardButton("🏠 Create My Own Shop", callback_data="main_menu_return"))
                
                # --- CHECK FOR BANNER (FIXED FOR VIDEO & DICT SUPPORT) ---
                banner = shop.get("banner")
                if banner:
                    try:
                        # যদি ব্যানার নতুন ডিকশনারি ফরম্যাটে থাকে
                        if isinstance(banner, dict):
                            file_id = banner.get("file_id")
                            b_type = banner.get("type", "photo")
                            
                            if b_type == "video":
                                bot.send_video(
                                    message.chat.id,
                                    file_id,
                                    caption=text,
                                    reply_markup=kb,
                                    parse_mode="HTML"
                                )
                            else:
                                bot.send_photo(
                                    message.chat.id,
                                    file_id,
                                    caption=text,
                                    reply_markup=kb,
                                    parse_mode="HTML"
                                )
                        # যদি ব্যানার পুরানো স্ট্রিং (File ID) ফরম্যাটে থাকে
                        else:
                            bot.send_photo(
                                message.chat.id,
                                banner,
                                caption=text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                    except Exception as e:
                        # মিডিয়া পাঠাতে ব্যর্থ হলে শুধু টেক্সট পাঠানো হবে
                        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
                else:
                    # ব্যানার না থাকলে সরাসরি টেক্সট
                    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
                return
            else:
                bot.send_message(message.chat.id, "❌ <b>Error:</b> Shop not found.", parse_mode="HTML")
                return
        
        # --- NORMAL START ---
        welcome_text = get_text("start_message", "👋 Welcome!")
        bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(user_id))
