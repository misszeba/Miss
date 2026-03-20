import os
from telebot import types
try:
    from utils.utils import is_admin 
except ImportError:
    def is_admin(uid): return False

FONTS_DIR = "data/fonts"

def get_main_menu(s):
    markup = types.InlineKeyboardMarkup(row_width=2)
    mode = s.get('mode', 'text')
    
    markup.add(types.InlineKeyboardButton(f"🔤 Mode: {mode.upper()}", callback_data="wm_toggle_mode"),
               types.InlineKeyboardButton("👁️ Preview", callback_data="wm_do_preview"))

    is_only_blur = s.get('only_blur', False)

    if not is_only_blur:
        if mode == 'text':
            markup.add(types.InlineKeyboardButton(f"✍️ Text: {s.get('text', 'Watermark')[:15]}...", callback_data="wm_set_text"))
            markup.row(types.InlineKeyboardButton(f"🔠 Font ({s.get('font_name','Def')})", callback_data="wm_menu_fonts"),
                       types.InlineKeyboardButton("🎨 Colors", callback_data="wm_menu_col_target"))
            markup.row(types.InlineKeyboardButton(f"🔳 Box: {'ON' if s.get('bg_enabled') else 'OFF'}", callback_data="wm_tog_bg"),
                       types.InlineKeyboardButton("📐 Style", callback_data="wm_menu_style"))
            markup.row(types.InlineKeyboardButton("📏 Size", callback_data="wm_menu_size"),
                       types.InlineKeyboardButton("👻 Opacity", callback_data="wm_menu_op"))
        else:
            markup.add(types.InlineKeyboardButton("📤 Change Logo", callback_data="wm_up_logo"))
            markup.row(types.InlineKeyboardButton("➖ Smaller", callback_data="wm_logo_dec"),
                       types.InlineKeyboardButton(f"🔍 Scale: {int(s.get('logo_scale', 1.0)*100)}%", callback_data="ignore"),
                       types.InlineKeyboardButton("➕ Bigger", callback_data="wm_logo_inc"))
            markup.row(types.InlineKeyboardButton("👻 Opacity", callback_data="wm_menu_op"),
                       types.InlineKeyboardButton("📐 Style", callback_data="wm_menu_style"))

    # ✅ Face Cover / Sticker Menu Logic
    is_blur = s.get('face_blur', False)
    
    blur_text = "🕵️ Face Cover: ON" if is_blur else "🕵️ Face Cover: OFF"
    only_blur_text = "💧 Only Blur/Sticker: ON" if is_only_blur else "💧 Only Blur/Sticker: OFF"

    markup.row(
        types.InlineKeyboardButton(blur_text, callback_data="wm_toggle_blur"),
        types.InlineKeyboardButton(only_blur_text, callback_data="wm_toggle_only_blur")
    )

    if is_blur:
        current_style = s.get('blur_style', 'smooth').title()
        markup.add(types.InlineKeyboardButton(f"🎨 Cover Style: {current_style}", callback_data="wm_toggle_blur_style"))

    is_silent = s.get('silent_mode', False)
    silent_text = "🔇 Only Media: ON" if is_silent else "🔈 Only Media: OFF"
    markup.add(types.InlineKeyboardButton(silent_text, callback_data="wm_toggle_silent"))

    if not is_only_blur:
        markup.add(types.InlineKeyboardButton("💠 Pattern / Position", callback_data="wm_menu_tile"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="tools_main"))
    return markup

def get_font_menu(settings, user_id, view="main"):
    markup = types.InlineKeyboardMarkup(row_width=2)
    curr = settings.get('font_name', 'Default')
    favs = settings.get('favorites', [])
    
    if view == "main":
        markup.add(types.InlineKeyboardButton(f"✅ Current: {curr}", callback_data="ignore"))
        markup.add(types.InlineKeyboardButton(f"❤️ My Favorites ({len(favs)})", callback_data="wm_font_list_fav"),
                   types.InlineKeyboardButton("🌐 All Global Fonts", callback_data="wm_font_list_all"))
        markup.add(types.InlineKeyboardButton("💾 System Default", callback_data="wm_font_set_default"))
        markup.add(types.InlineKeyboardButton("➕ Upload New Font", callback_data="wm_font_upload"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Studio", callback_data="wm_menu_main"))
        return markup

    all_fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith((".ttf", ".otf"))] if os.path.exists(FONTS_DIR) else []
    target_list = favs if view == "favorites" else all_fonts
    
    if not target_list:
        markup.add(types.InlineKeyboardButton("📂 No fonts found.", callback_data="ignore"))
    else:
        for font in target_list:
            row = []
            prefix = "✅" if font == curr else "🔤"
            row.append(types.InlineKeyboardButton(f"{prefix} {font}", callback_data=f"wm_fset_{font}"))
            icon = "💔" if view=="favorites" else ("❤️" if font in favs else "🤍")
            row.append(types.InlineKeyboardButton(icon, callback_data=f"wm_ffav_{font}"))
            if view == "all" and is_admin(user_id):
                row.append(types.InlineKeyboardButton("🗑️", callback_data=f"wm_fdel_{font}"))
            markup.row(*row)

    if view == "favorites": markup.add(types.InlineKeyboardButton("🌐 Browse All Fonts", callback_data="wm_font_list_all"))
    else: markup.add(types.InlineKeyboardButton("❤️ Go to Favorites", callback_data="wm_font_list_fav"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_fonts"))
    return markup

def get_color_target_menu():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("🅰️ Text Color", callback_data="wm_col_menu_text"),
           types.InlineKeyboardButton("⬛ Box Color", callback_data="wm_col_menu_box"))
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
    return mk

def get_color_palette_menu(target):
    mk = types.InlineKeyboardMarkup(row_width=3)
    colors = {"⚪": "#FFFFFF", "⚫": "#000000", "🔴": "#FF0000", "🟢": "#00FF00", "🔵": "#0000FF", "🟡": "#FFFF00", "🟣": "#800080", "🟠": "#FFA500"}
    btns = [types.InlineKeyboardButton(i, callback_data=f"wm_setcol_{target}_{c}") for i, c in colors.items()]
    mk.add(*btns)
    mk.add(types.InlineKeyboardButton("✏️ Custom Hex", callback_data=f"wm_setcol_{target}_cust"))
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_col_target"))
    return mk

def get_style_menu():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("📐 0°", callback_data="wm_rot_0"), types.InlineKeyboardButton("📐 90°", callback_data="wm_rot_90"),
           types.InlineKeyboardButton("✏️ Angle", callback_data="wm_rot_cust"), types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
    return mk

def get_tile_menu(s):
    mk = types.InlineKeyboardMarkup(row_width=2)
    tiled = s.get('pattern_enabled', False)
    status_icon = "✅" if tiled else "❌"
    next_action = "off" if tiled else "on"
    mk.add(types.InlineKeyboardButton(f"{status_icon} Pattern Mode", callback_data=f"wm_set_pattern:{next_action}"))
    
    if tiled:
        mk.add(types.InlineKeyboardButton("Gap +", callback_data="wm_gap_inc"), 
               types.InlineKeyboardButton("Gap -", callback_data="wm_gap_dec"))
    else:
        mk.row(types.InlineKeyboardButton("↖️", callback_data="wm_set_pos:top_left"), 
               types.InlineKeyboardButton("↗️", callback_data="wm_set_pos:top_right"))
        mk.row(types.InlineKeyboardButton("⏺️", callback_data="wm_set_pos:center"))
        mk.row(types.InlineKeyboardButton("↙️", callback_data="wm_set_pos:bottom_left"), 
               types.InlineKeyboardButton("↘️", callback_data="wm_set_pos:bottom_right"))
               
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
    return mk
