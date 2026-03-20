import re
import json
import requests
from telebot import types
from io import BytesIO

# ✅ Database Manager ইমপোর্ট
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("Error: utils/db_manager.py not found!")

# টুলস ইনফো (আগের মতোই থাকবে)
TOOL_INFO = {
    "label": "🌀 Webflow GSAP Pro",
    "callback": "wbgsap_menu"
}

def register_handlers(bot):

    # মেমোরিতে ডাটা রাখার জন্য ডিকশনারি
    if not hasattr(bot, 'ix3_temp_store'):
        bot.ix3_temp_store = {}

    def clear_steps(chat_id):
        try: bot.clear_step_handler_by_chat_id(chat_id)
        except: pass

    # ---------------------------------------------
    # 🌀 MAIN MENU (UI আগের মতোই রাখা হয়েছে)
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "wbgsap_menu")
    def wbgsap_menu(call):
        try: bot.answer_callback_query(call.id)
        except: pass
        clear_steps(call.message.chat.id)
        
        u_id = str(call.from_user.id)
        all_data = get_full_config()
        stored_url = all_data.get(u_id, {}).get('wb_js_url', '')

        text = "🚀 **Webflow GSAP Pro Generator**\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if stored_url:
            text += f"🔗 **Current JS URL:**\n`{stored_url}`\n\n"
            text += "✅ *আউটপুট এখন Pure IX3 JSON (v18) ফরম্যাটে আসবে।*"
        else:
            text += "⚠️ **JS URL Set করা নেই!**\nদয়া করে প্রথমে লিংক সেট করুন।"

        mk = types.InlineKeyboardMarkup(row_width=1)
        if stored_url:
            # বাটনটি এখন সরাসরি এক্সট্র্যাক্ট করবে
            mk.add(types.InlineKeyboardButton("📤 Extract JSON Data", callback_data="wbgsap_extract"))
        mk.add(types.InlineKeyboardButton("⚙️ Set / Change JS URL", callback_data="wbgsap_set_url"))
        mk.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="gm_tools"))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk, parse_mode="Markdown", disable_web_page_preview=True)
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=mk, parse_mode="Markdown", disable_web_page_preview=True)

    # ---------------------------------------------
    # ⚙️ URL SET HANDLER
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "wbgsap_set_url")
    def ask_url(call):
        try: bot.answer_callback_query(call.id)
        except: pass
        mk = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Cancel", callback_data="wbgsap_menu"))
        msg = bot.send_message(call.message.chat.id, "🔗 **Webflow JS লিংকটি দিন:**", reply_markup=mk)
        bot.register_next_step_handler(msg, save_url)

    def save_url(message):
        if message.text and message.text.startswith('/'): return
        u_id = str(message.from_user.id)
        url = message.text.strip()
        all_data = get_full_config()
        if u_id not in all_data: all_data[u_id] = {}
        all_data[u_id]['wb_js_url'] = url
        save_full_config(all_data)
        bot.send_message(message.chat.id, "✅ URL সফলভাবে সেভ হয়েছে!", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="wbgsap_menu")))

    # ---------------------------------------------
    # 📤 EXTRACTION LOGIC (Follows v18 UserScript Output)
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "wbgsap_extract")
    def start_extraction(call):
        try: bot.answer_callback_query(call.id)
        except: pass
        
        u_id = str(call.from_user.id)
        url = get_full_config().get(u_id, {}).get('wb_js_url', '')
        status_msg = bot.send_message(call.message.chat.id, "⏳ **Extracting Pure IX3 Data...**")

        try:
            response = requests.get(url, timeout=30)
            script_text = response.text

            # ১. ix3 Hunting (v18 Logic)
            ix3_match = re.search(r'require\((["\'])ix3\1\)', script_text)
            if not ix3_match: raise Exception("require('ix3') খুঁজে পাওয়া যায়নি!")

            register_idx = script_text.find('.register(', ix3_match.start())
            if register_idx == -1: raise Exception(".register() পাওয়া যায়নি!")

            # ২. Bracket Counting (Exact UserScript Implementation)
            start_idx = register_idx + len(".register(")
            bracket_count, end_idx, inside_string, string_char = 1, -1, False, ''
            
            for i in range(start_idx, len(script_text)):
                char = script_text[i]
                prev_char = script_text[i-1] if i > 0 else ''
                if char in ['"', "'", '`'] and prev_char != '\\':
                    if not inside_string: inside_string, string_char = True, char
                    elif string_char == char: inside_string = False
                if not inside_string:
                    if char == '(': bracket_count += 1
                    elif char == ')':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_idx = i
                            break
            
            if end_idx == -1: raise Exception("Parsing Error: Bracket mismatch.")
            raw_args = script_text[start_idx:end_idx]

            # ৩. Triggers & Timelines Splitting
            parts, current_part, depth, in_str, s_char = [], "", 0, False, ""
            for c in raw_args:
                if c in ['"', "'", '`'] and (not current_part or current_part[-1] != '\\'):
                    if not in_str: in_str, s_char = True, c
                    elif s_char == c: in_str = False
                if not in_str:
                    if c in ['{', '[', '(']: depth += 1
                    elif c in ['}', ']', ')']: depth -= 1
                    elif c == ',' and depth == 0:
                        parts.append(current_part.strip())
                        current_part = ""
                        continue
                current_part += c
            parts.append(current_part.strip())

            # ৪. JSON Formatting (Indent=4 for Pretty Output)
            def js_to_json(js_str):
                # Keys এর চারপাশে কোট দেওয়া
                js_str = re.sub(r'(\s*?)([a-zA-Z0-9_]+)(\s*?):', r'\1"\2"\3:', js_str)
                js_str = js_str.replace("'", '"')
                js_str = re.sub(r',\s*([\]}])', r'\1', js_str)
                return json.loads(js_str)

            try:
                final_dict = {
                    "triggers": js_to_json(parts[0]) if len(parts) > 0 else [],
                    "timelines": js_to_json(parts[1]) if len(parts) > 1 else []
                }
                final_json = json.dumps(final_dict, indent=4, ensure_ascii=False)
            except:
                # Fallback যদি JSON পার্সিং এরর হয়
                final_json = f"{{\n    \"triggers\": {parts[0] if len(parts)>0 else '[]'},\n    \"timelines\": {parts[1] if len(parts)>1 else '[]'}\n}}"

            # মেমোরিতে ফাইল সেভ করা
            bot.ix3_temp_store[call.message.chat.id] = final_json

            # বাটন লেআউট
            mk = types.InlineKeyboardMarkup(row_width=1)
            mk.add(
                types.InlineKeyboardButton("📥 Download JSON File", callback_data="wbgsap_dl_file"),
                types.InlineKeyboardButton("🔄 Extract Again", callback_data="wbgsap_extract"),
                types.InlineKeyboardButton("🔙 Back to Menu", callback_data="wbgsap_menu")
            )

            # ৫. রেজাল্ট আউটপুট (কপিযোগ্য কোড ব্লক + বাটন)
            if len(final_json) > 3800:
                bot.edit_message_text("✅ **Extraction Success!**\n\n⚠️ কোডটি বড় হওয়ায় নিচে ফাইল হিসেবে দেওয়া হলো।", call.message.chat.id, status_msg.message_id, reply_markup=mk)
            else:
                formatted_msg = f"✅ **Pure IX3 JSON Output:**\n\n```json\n{final_json}\n```"
                bot.edit_message_text(formatted_msg, call.message.chat.id, status_msg.message_id, reply_markup=mk, parse_mode="Markdown")

        except Exception as e:
            bot.edit_message_text(f"❌ **Error:** {str(e)}", call.message.chat.id, status_msg.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="wbgsap_menu")))

    # ---------------------------------------------
    # 📥 DOWNLOAD HANDLER
    # ---------------------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "wbgsap_dl_file")
    def download_handler(call):
        chat_id = call.message.chat.id
        if chat_id in bot.ix3_temp_store:
            data = bot.ix3_temp_store[chat_id]
            bio = BytesIO(data.encode('utf-8'))
            bio.name = "webflow_ix3_pretty.json"
            bot.send_document(chat_id, bio, caption="💎 **Zd Pure Pretty IX3 JSON**")
            bot.answer_callback_query(call.id, "✅ File Sent!")
        else:
            bot.answer_callback_query(call.id, "⚠️ Data not found.", show_alert=True)
