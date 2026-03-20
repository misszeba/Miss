import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import bot
from . import database

# --- UI কনস্ট্যান্ট ---
LINE = "━━━━━━━━━━━━━━━━━━━━\n"

# ==========================================
# 🎮 ড্যাশবোর্ড এবং বাটন হ্যান্ডলার
# ==========================================

def handle_chat_callback(call, chat_id, action):
    """চ্যাট টুলের কলব্যাক এবং মেনু হ্যান্ডলার"""
    cid = call.message.chat.id
    mid = call.message.message_id
    
    try:
        if action == "home":
            group = database.get_group_data(chat_id)
            if not group: return
            
            settings = group.get("chat_settings", {})
            nick = settings.get("nickname") if settings else None
            nick_display = f"`{nick}`" if nick else "❌ _Not Set_"
            
            text = (
                "💬 **Inbox-to-Chat Tool**\n"
                f"{LINE}"
                f"📍 **Target:** `{group['title']}`\n"
                f"🏷 **Nickname:** {nick_display}\n\n"
                "💡 **ব্যবহারবিধি (Commands):**\n"
                "1️⃣ **Direct:** `/{nick} আপনার মেসেজ`\n"
                "   _(টেক্সট বা মিডিয়ার ক্যাপশনে লিখলে সরাসরি গ্রুপে যাবে)_\n"
                "2️⃣ **Reply:** যেকোনো মিডিয়াতে রিপ্লাই দিয়ে `/{nick}` লিখলে সেটি গ্রুপে যাবে।\n"
                "3️⃣ **Multi:** `/{nick1} /{nick2} মেসেজ` (একসাথে একাধিক গ্রুপে)"
            )
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📝 Set Nickname", callback_data=f"cht_setnick_{chat_id}"))
            markup.row(InlineKeyboardButton("🔓 Open Chat Box", callback_data=f"cht_openbox_{chat_id}"))
            markup.row(InlineKeyboardButton("🔙 Back to Panel", callback_data=f"gman_panel_{chat_id}"))
            
            bot.edit_message_text(text, cid, mid, parse_mode='Markdown', reply_markup=markup)

        elif action == "setnick":
            msg = bot.send_message(cid, "🔤 **এই চ্যাটের জন্য একটি ইউনিক নিকনেম দিন:**\n(অবশ্যই `/` ছাড়া লিখবেন, যেমন: `news` বা `chat1`)")
            bot.register_next_step_handler(msg, lambda m: save_nick(m, chat_id))

        elif action == "openbox":
            msg = bot.send_message(cid, "📝 **এই চ্যাটে পাঠানোর জন্য মেসেজ বা মিডিয়া দিন:**")
            bot.register_next_step_handler(msg, lambda m: send_direct_msg(m, chat_id))

    except Exception as e:
        print(f"Chat Tool UI Error: {e}")

def save_nick(message, chat_id):
    """ডাটাবেসে নিকনেম সেভ করা"""
    cid = message.chat.id
    nick = message.text.strip().lower() if message.text else ""
    
    # ভ্যালিডেশন
    if not nick or " " in nick or len(nick) < 2 or "/" in nick:
        bot.send_message(cid, "⚠️ নিকনেম ভ্যালিড নয়। স্পেস বা '/' ব্যবহার করবেন না এবং টেক্সট হতে হবে।")
        return

    if database.set_nickname(chat_id, nick):
        bot.send_message(cid, f"✅ নিকনেম সেট করা হয়েছে: `{nick}`\nএখন ব্যবহার করুন: `/{nick} hello`")
    else:
        bot.send_message(cid, "❌ এই নিকনেমটি ইতিমধ্যে অন্য চ্যাটে ব্যবহৃত হচ্ছে।")

def send_direct_msg(message, chat_id):
    """ওপেন চ্যাট বক্স (বাটন) থেকে মেসেজ পাঠানো"""
    try:
        # copy_message সব ধরনের মিডিয়া এবং টেক্সট হ্যান্ডেল করে
        bot.copy_message(chat_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ **Message Sent!**")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed to send. Bot might not be admin.\nError: {e}")

# ==========================================
# 🚀 মাল্টি-টার্গেট কমান্ড প্রসেসর (Core Logic)
# ==========================================

def handle_inbox_command(message):
    """
    ইনবক্স থেকে আসা কমান্ড প্রসেস করে।
    রিটার্ন: True (যদি এটি চ্যাট টুলের কমান্ড হয়), False (যদি না হয়)
    """
    # ১. টেক্সট বা ক্যাপশন বের করা
    text = message.text or message.caption
    
    if not text or not text.strip().startswith("/"): 
        return False

    words = text.split()
    targets = [] 
    msg_start_index = 0
    found_any_nick = False
    
    # ২. লুপ চালিয়ে সব ভ্যালিড নিকনেম খুঁজে বের করা
    for i, word in enumerate(words):
        if word.startswith("/"):
            potential_nick = word[1:].lower() # '/' বাদ দিয়ে নাম নেওয়া
            
            # ডাটাবেস চেক
            chat_data = database.get_chat_by_nickname(potential_nick)
            
            if chat_data:
                targets.append(chat_data)
                found_any_nick = True
                msg_start_index = i + 1 
            else:
                break
        else:
            break

    if not found_any_nick:
        return False

    # ৩. আসল মেসেজ কন্টেন্ট আলাদা করা (কমান্ড বাদে বাকি অংশ)
    # যদি শুধু কমান্ড থাকে, তবে content_text হবে "" (ফাঁকা স্ট্রিং)
    content_text = " ".join(words[msg_start_index:])
    
    sent_names = []
    failed_names = []

    # ৪. সব টার্গেটে মেসেজ পাঠানো
    for target in targets:
        chat_id = target.get('chat_id')
        title = target.get('title', 'Unknown Group')
        
        try:
            # 🅰️ [REPLY MODE] - রিপ্লাই করা মেসেজে কমান্ড থাকে না
            if message.reply_to_message:
                bot.copy_message(
                    chat_id, 
                    message.chat.id, 
                    message.reply_to_message.message_id,
                    # রিপ্লাইয়ের ক্ষেত্রে: যদি ইউজার নতুন টেক্সট দেয় তবেই ক্যাপশন চেঞ্জ হবে, না হলে অরিজিনাল থাকবে
                    caption=content_text if content_text else None, 
                    parse_mode='Markdown'
                )
                sent_names.append(title)
            
            # 🅱️ [DIRECT MODE] - এখানে মেসেজের ভেতরেই কমান্ড আছে
            else:
                # যদি মিডিয়া হয় (ফটো, ভিডিও, ডকুমেন্ট ইত্যাদি)
                if message.content_type in ['photo', 'video', 'document', 'audio', 'voice', 'animation']:
                    bot.copy_message(
                        chat_id, 
                        message.chat.id, 
                        message.message_id,
                        # ✅ FIX: এখানে সরাসরি content_text দেওয়া হয়েছে।
                        # ফাঁকা থাকলেও এটি ফাঁকা স্ট্রিং "" পাঠাবে, ফলে অরিজিনাল '/nick' ক্যাপশন মুছে যাবে।
                        caption=content_text, 
                        parse_mode='Markdown'
                    )
                    sent_names.append(title)
                
                # যদি শুধু টেক্সট হয়
                elif content_text:
                    bot.send_message(chat_id, content_text, parse_mode='Markdown')
                    sent_names.append(title)
                
                else:
                    # ইউজার শুধু কমান্ড দিয়েছে কিন্তু কোনো মেসেজ বা মিডিয়া নেই
                    pass 

        except Exception as e:
            print(f"Failed to send to {title} ({chat_id}): {e}")
            failed_names.append(title)

    # ৫. রিপোর্ট
    if sent_names:
        bot.reply_to(message, f"✅ **Sent to:** `{', '.join(sent_names)}`")
    
    if failed_names:
        bot.send_message(message.chat.id, f"❌ **Failed:** `{', '.join(failed_names)}`\n(Make sure bot is Admin)")
        
    # যদি কন্টেন্ট না থাকে এবং রিপ্লাইও না থাকে
    if not sent_names and not failed_names and not message.reply_to_message and not content_text and message.content_type == 'text':
        bot.reply_to(message, "⚠️ **Empty Message!**\nUse: `/nickname message` or Reply to a media.")

    return True
