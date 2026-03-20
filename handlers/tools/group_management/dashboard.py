import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import bot
from . import database
from . import welcome
from . import antilink
from . import banword
from . import chat_tool  # ✅ নতুন চ্যাট টুল ইমপোর্ট

# --- মর্ডান UI এলিমেন্টস ---
HEADER = "🛡️ **GROUP MANAGER v2.0**\n"
LINE = "━━━━━━━━━━━━━━━━━━━━\n"

def open_gman_dashboard(chat_id, message_id=None):
    """গ্রুপ ও চ্যানেল ম্যানেজমেন্টের মেইন ড্যাশবোর্ড"""
    text = (
        f"{HEADER}{LINE}"
        "👋 **স্বাগতম!** আপনার গ্রুপ ও চ্যানেলগুলোকে এখান থেকে রিমোটলি কন্ট্রোল করুন।\n\n"
        "💡 *নিচের বাটন থেকে আপনার গ্রুপ/চ্যানেল তালিকা চেক করুন:* "
    )
    markup = InlineKeyboardMarkup()
    me = bot.get_me().username
    
    # ✅ গ্রুপ এবং চ্যানেলে অ্যাড করার বাটন
    markup.row(
        InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{me}?startgroup=true"),
        InlineKeyboardButton("📢 Add to Channel", url=f"https://t.me/{me}?startchannel=true")
    )
    markup.row(InlineKeyboardButton("⚙️ Manage My Chats", callback_data="gman_list"))
    markup.row(InlineKeyboardButton("🔙 Back to Tools", callback_data="tools_main"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        except:
            bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

def list_groups(call):
    """ইউজারের অ্যাডমিন থাকা গ্রুপ ও চ্যানেলের তালিকা"""
    user_id = call.from_user.id
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    groups = database.get_user_groups(user_id)
    
    if not groups:
        text = (
            f"{HEADER}{LINE}"
            "❌ **কোনো গ্রুপ বা চ্যানেল খুঁজে পাওয়া যায়নি!**\n\n"
            "• বটকে অ্যাডমিন হিসেবে যুক্ত করুন।\n"
            "• গ্রুপে `/reload` কমান্ড দিন।\n"
            "• তারপর আবার এখানে ফিরে আসুন।"
        )
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🔄 Refresh List", callback_data="gman_list"))
        markup.row(InlineKeyboardButton("🔙 Back", callback_data="gman_main"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)
        return

    text = f"{HEADER}{LINE}📂 **আপনার চ্যাট তালিকা:**\n"
    markup = InlineKeyboardMarkup()
    for g in groups:
        # টাইপ অনুযায়ী ইমোজি সেট করা
        icon = "📢" if g.get('type') == 'channel' else "👥"
        markup.add(InlineKeyboardButton(f"{icon} {g['title']}", callback_data=f"gman_panel_{g['chat_id']}"))
    
    markup.row(InlineKeyboardButton("🔙 Back", callback_data="gman_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

def show_panel(call, target_id):
    """নির্দিষ্ট একটি চ্যাটের সেটিংস প্যানেল"""
    group = database.get_group_data(target_id)
    if not group:
        return

    chat_type = "Channel" if group.get('type') == 'channel' else "Group"
    text = (
        f"🛠 **{chat_type} Settings**\n{LINE}"
        f"📍 **Title:** `{group['title']}`\n"
        f"🆔 **ID:** `{target_id}`\n\n"
        "নিচের মডিউল থেকে সেটিংস পরিবর্তন করুন:"
    )
    markup = InlineKeyboardMarkup()
    
    # ✅ মডিউল বাটনসমূহ
    if chat_type == "Group":
        markup.row(
            InlineKeyboardButton("👋 Welcome", callback_data=f"wlc_home_{target_id}"),
            InlineKeyboardButton("🚫 Antilink", callback_data=f"aln_home_{target_id}")
        )
        markup.row(
            InlineKeyboardButton("🤬 Ban Word", callback_data=f"bnw_home_{target_id}"),
            InlineKeyboardButton("💬 Chat Tool", callback_data=f"cht_home_{target_id}") # ✅ চ্যাট টুল যুক্ত
        )
    else:
        # চ্যানেলের জন্য শুধুমাত্র চ্যাট টুল (অন্যান্য মডিউল চ্যানেলে চলে না)
        markup.row(InlineKeyboardButton("💬 Chat Tool (Inbox-to-Channel)", callback_data=f"cht_home_{target_id}"))
    
    markup.row(InlineKeyboardButton("🔙 Back to List", callback_data="gman_list"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

# ==========================================
# ⚡ কলব্যাক রাউটার (Global Callback Handler)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('gman_', 'wlc_', 'aln_', 'bnw_', 'cht_')))
def handle_callbacks(call):
    data = call.data
    parts = data.split('_')
    prefix = parts[0]
    
    try:
        # ১. ম্যানেজমেন্ট কোর
        if prefix == "gman":
            action = parts[1]
            if action == "main":
                open_gman_dashboard(call.message.chat.id, call.message.message_id)
            elif action == "list":
                list_groups(call)
            elif action == "panel":
                show_panel(call, int(parts[2]))
        
        # ২. অন্যান্য মডিউল
        elif prefix == "wlc":
            welcome.handle_callback(call, int(parts[-1]), parts[1])
            
        elif prefix == "aln":
            antilink.handle_callback(call, int(parts[-1]), parts[1])

        elif prefix == "bnw":
            banword.handle_callback(call, int(parts[-1]), parts[1])

        # ৩. চ্যাট টুল হ্যান্ডলিং ✅
        elif prefix == "cht":
            chat_tool.handle_chat_callback(call, int(parts[-1]), parts[1])
            
    except Exception as e:
        print(f"Callback Error in Dashboard: {e}")
