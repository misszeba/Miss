from telebot import types

# ==========================================
# 🧩 কনফিগারেশন
# ==========================================

# ⚠️ আপনার নেটলিফাই সাইটের লিংক এখানে দিন (শেষে / না থাকলেও চলবে)
WEBAPP_URL = "https://miss-zeba-file.netlify.app/" 

TOOL_INFO = {
    "label": "📝 Text to File (Unlimited)",
    "callback": "plugin_txt2file_start"
}

# ==========================================
# 🎮 হ্যান্ডলার ফাংশন
# ==========================================

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda c: c.data == "plugin_txt2file_start")
    def open_tool_menu(call):
        chat_id = call.message.chat.id
        
        msg = (
            "📝 **Unlimited Text to File Maker**\n\n"
            "এখন আপনি যত বড় খুশি কোড বা টেক্সট ফাইল বানাতে পারবেন।\n"
            "নিচের **'🚀 Open Maker'** বাটনে ক্লিক করুন।"
        )
        
        # WebApp বাটন কনফিগারেশন
        markup = types.InlineKeyboardMarkup()
        web_app_info = types.WebAppInfo(url=WEBAPP_URL)
        
        markup.add(types.InlineKeyboardButton("🚀 Open Maker", web_app=web_app_info))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="gm_tools"))
        
        # আগের মেসেজ এডিট করে মেনু দেখানো (Clean UI)
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except:
            # যদি এডিট সম্ভব না হয় (পুরানো মেসেজ), নতুন করে পাঠানো
            bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)

    # ℹ️ নোট: আমাদের আর @message_handler(content_types=['web_app_data']) লাগবে না।
    # কারণ ওয়েব পেজ এখন সরাসরি টেলিগ্রাম API তে ফাইল পাঠিয়ে দিবে।
