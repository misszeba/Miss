import os
import traceback
from telebot import types
from io import BytesIO

from .data import get_wm_settings, save_wm_settings

try:
    from .engine import apply_watermark_image, apply_watermark_video, generate_font_preview_image, blur_faces_in_image
except ImportError:
    from .engine import apply_watermark_image, apply_watermark_video, generate_font_preview_image
    def blur_faces_in_image(path, style="smooth", s=None): pass

from .menus import *

try:
    from utils.utils import delete_msg, StatusMsg, is_admin
except ImportError:
    def delete_msg(bot, m): pass
    class StatusMsg:
        def __init__(self, bot, cid): pass
        def send(self, t): pass
        def done(self): pass
    def is_admin(uid): return False

try:
    from handlers.tools.url_shorten.core import user_state_url
except ImportError:
    user_state_url = {}

try:
    from handlers.shop_seller import media_cache, pending_data
except ImportError:
    try:
        from Handlers.shop_seller import media_cache, pending_data
    except ImportError:
        media_cache = {}
        pending_data = {}

FONTS_DIR = "data/fonts"
LOGOS_DIR = "data/logos"
MAX_MEDIA_SIZE = 20 * 1024 * 1024

if not os.path.exists(FONTS_DIR): os.makedirs(FONTS_DIR)
if not os.path.exists(LOGOS_DIR): os.makedirs(LOGOS_DIR)

user_states_watermark = {}
last_menu_ids = {}

def update_wm(cid, k, v): save_wm_settings(cid, k, v)

def send_menu(bot, cid, txt, mk, mid=None):
    if mid:
        try:
            bot.edit_message_text(txt, cid, mid, reply_markup=mk, parse_mode="Markdown")
            last_menu_ids[cid] = mid
            return
        except: pass
            
    if cid in last_menu_ids:
        try: bot.delete_message(cid, last_menu_ids[cid])
        except: pass
    
    try:
        sent = bot.send_message(cid, txt, reply_markup=mk, parse_mode="Markdown")
        last_menu_ids[cid] = sent.message_id
    except Exception as e:
        print(f"Send Menu Error: {e}")

def refresh_main_menu(bot, cid, mid=None):
    s = get_wm_settings(cid)
    
    blur_status = "✅" if s.get('face_blur') else "❌"
    if s.get('face_blur'):
        blur_status += f" ({s.get('blur_style', 'smooth').title()})"

    only_blur = s.get('only_blur', False)
    mode_text = "💧 **Only Cover ON** (No Watermark)" if only_blur else f"📝 Text: `{s.get('text','Watermark')}`"

    txt = (f"🎛️ **Watermark Studio**\n"
           f"{mode_text}\n"
           f"🎨 Font: `{s.get('font_name','Default')}`\n"
           f"🕵️ Face Cover: {blur_status}\n\n"
           f"👇 **Send Photo, Video or GIF to process.**")
    send_menu(bot, cid, txt, get_main_menu(s), mid)

def process_media(bot, m, file_type, custom_settings=None):
    cid = m.chat.id
    status = StatusMsg(bot, cid)
    status.send(f"⏳ Processing {file_type.title()}... Please wait.")
    
    t_in = None
    t_out = None

    try:
        if file_type == 'photo': file_id = m.photo[-1].file_id
        elif file_type == 'video': file_id = m.video.file_id
        elif file_type == 'gif': file_id = m.animation.file_id

        file_info = bot.get_file(file_id)
        if file_info.file_size > MAX_MEDIA_SIZE:
            status.done()
            bot.send_message(cid, f"⚠️ File too big! Max size: 20MB")
            return

        downloaded = bot.download_file(file_info.file_path)
        ext_in = ".mp4" if file_type == 'video' else (".gif" if file_type == 'gif' else ".jpg")
        
        t_in = f"wm_in_{cid}{ext_in}"
        t_out = f"wm_out_{cid}{ext_in}"
        
        with open(t_in, 'wb') as f: f.write(downloaded)
        
        s = get_wm_settings(cid)
        
        if custom_settings:
            if 'text' in custom_settings: s['text'] = custom_settings['text']
            if 'size' in custom_settings: s['size_pct'] = custom_settings['size']
            if 'opacity' in custom_settings: s['opacity'] = custom_settings['opacity']
            if 'position' in custom_settings: s['position'] = custom_settings['position']
            s.update({k: v for k, v in custom_settings.items() if k not in ['text', 'size', 'opacity', 'position']})

        if s.get('face_blur') and file_type == 'photo':
            b_style = s.get('blur_style', 'smooth')
            status.send(f"🕵️ Applying {b_style.title()} Cover...")
            # ✅ FIX: Passing settings 's' to engine for sticker support
            blur_faces_in_image(t_in, style=b_style, s=s)

        action_text = "Covering Only..." if s.get('only_blur') else "Applying Watermark..."
        status.send(f"🎨 {action_text}")
        
        if file_type == 'photo':
            success = apply_watermark_image(t_in, t_out, s)
        else:
            success = apply_watermark_video(t_in, t_out, s, is_gif=(file_type=='gif'))

        if success:
            s = get_wm_settings(cid)
            is_silent = s.get('silent_mode', False)
            caption_text = m.caption if (is_silent and m.caption) else ("✅ Done" if not is_silent else "")

            with open(t_out, 'rb') as f:
                if file_type == 'photo': bot.send_photo(cid, f, caption=caption_text)
                elif file_type == 'video': bot.send_video(cid, f, caption=caption_text)
                elif file_type == 'gif': bot.send_animation(cid, f, caption=caption_text)
        else:
            bot.send_message(cid, "❌ Processing Failed (Engine Error).")
        
        if int(cid) > 0 and not s.get('silent_mode', False):
            refresh_main_menu(bot, cid)

    except Exception as e:
        traceback.print_exc()
        bot.send_message(cid, f"❌ Error: {e}")
    
    finally:
        status.done() 
        if t_in and os.path.exists(t_in): os.remove(t_in)
        if t_out and os.path.exists(t_out): os.remove(t_out)

def register_watermark_handlers(bot):

    def safe_handle(call, func):
        try:
            bot.answer_callback_query(call.id)
            func()
        except Exception as e:
            traceback.print_exc()

    def wm_input_filter(m):
        cid = m.chat.id
        user_id = m.from_user.id
        if (m.text and m.text.startswith("/")) or (m.caption and m.caption.strip().startswith("/")): return False
        if user_id in media_cache or user_id in pending_data: return False
        if user_state_url.get(cid, {}).get('action') is not None: return False
        return True

    @bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document'], func=wm_input_filter)
    def handle_wm_inputs(m):
        cid = m.chat.id
        st = user_states_watermark.get(cid)
        
        if m.caption and m.caption.strip().startswith("/"): return
        delete_msg(bot, m)
        
        if m.content_type == 'text':
            if st == "waiting_text":
                update_wm(cid, "text", m.text)
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid)
            elif st and st.startswith("waiting_col_"):
                update_wm(cid, "text_color" if "text" in st else "bg_color", m.text)
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid)
            elif st == "waiting_val_size":
                try:
                    val = int(m.text)
                    if 1 <= val <= 100:
                        update_wm(cid, "size_pct", val)
                        user_states_watermark[cid] = "waiting_media"
                        refresh_main_menu(bot, cid)
                    else: bot.send_message(cid, "⚠️ Enter value between 1-100")
                except: bot.send_message(cid, "⚠️ Invalid number!")
            elif st == "waiting_val_opacity":
                try:
                    val = int(m.text)
                    if 0 <= val <= 255:
                        update_wm(cid, "opacity", val)
                        user_states_watermark[cid] = "waiting_media"
                        refresh_main_menu(bot, cid)
                    else: bot.send_message(cid, "⚠️ Enter value between 0-255")
                except: bot.send_message(cid, "⚠️ Invalid number!")
            elif st == "waiting_rot":
                try:
                    val = int(m.text)
                    update_wm(cid, "rotation", val % 360)
                    user_states_watermark[cid] = "waiting_media"
                    refresh_main_menu(bot, cid)
                except: bot.send_message(cid, "⚠️ Invalid number!")
            return

        if st == "waiting_font":
            if m.document and m.document.file_name and m.document.file_name.lower().endswith(('.ttf', '.otf')):
                try:
                    path = os.path.join(FONTS_DIR, m.document.file_name)
                    with open(path, 'wb') as f:
                        f.write(bot.download_file(bot.get_file(m.document.file_id).file_path))
                    update_wm(cid, "font_name", m.document.file_name)
                    update_wm(cid, "font_path", path)
                    update_wm(cid, "font_custom", True)
                    user_states_watermark[cid] = "waiting_media"
                    bot.send_message(cid, "✅ Font Uploaded!")
                    refresh_main_menu(bot, cid)
                    return
                except: 
                    bot.send_message(cid, "❌ Upload Failed!")
                    return
            else:
                bot.send_message(cid, "⚠️ Please send a valid .ttf or .otf document file.")
                return

        elif st == "waiting_logo":
            target_file_id = None
            if m.photo:
                target_file_id = m.photo[-1].file_id
            elif m.document and m.document.mime_type and 'image' in m.document.mime_type:
                target_file_id = m.document.file_id

            if target_file_id:
                try:
                    path = os.path.join(LOGOS_DIR, f"logo_{cid}.png")
                    file_info = bot.get_file(target_file_id)
                    downloaded = bot.download_file(file_info.file_path)
                    
                    with open(path, 'wb') as f: f.write(downloaded)

                    update_wm(cid, "logo_path", path)
                    update_wm(cid, "mode", "logo")
                    user_states_watermark[cid] = "waiting_media"
                    bot.send_message(cid, "✅ Logo Uploaded and set!")
                    refresh_main_menu(bot, cid)
                    return
                except: 
                    bot.send_message(cid, "❌ Logo Upload Failed!")
                    return
            else:
                bot.send_message(cid, "⚠️ Please send an Image (Photo or Document PNG/JPG).")
                return

        if m.photo: process_media(bot, m, 'photo')
        elif m.video: process_media(bot, m, 'video')
        elif m.animation: process_media(bot, m, 'gif')
        elif m.document and m.document.mime_type and 'video' in m.document.mime_type:
            process_media(bot, m, 'video')

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_") or c.data == "tool_img")
    def handle_wm_callbacks(c):
        cid, mid = c.message.chat.id, c.message.message_id
        data = c.data
        u_id = c.from_user.id

        def action():
            s = get_wm_settings(cid)
            
            if data == "tool_img" or data == "wm_menu_main":
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid, mid if data=="wm_menu_main" else None)
            
            elif data == "wm_menu_fonts":
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(s, u_id, "main"), mid)
            
            elif data.startswith("wm_font_list_"):
                view = data.replace("wm_font_list_", "")
                bot.answer_callback_query(c.id, "⌛ Loading Previews...")
                target_fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith(('.ttf', '.otf'))] if view=="all" else s.get('favorites', [])
                preview_img = generate_font_preview_image(FONTS_DIR, target_fonts)
                markup = get_font_menu(s, u_id, view)
                if preview_img:
                    try: bot.delete_message(cid, mid)
                    except: pass
                    sent = bot.send_photo(cid, preview_img, caption=f"🌐 **Library Preview ({view})**", reply_markup=markup)
                    last_menu_ids[cid] = sent.message_id
                else: send_menu(bot, cid, "📂 No fonts found.", markup, mid)

            elif data.startswith("wm_fset_"):
                fname = data.replace("wm_fset_", "")
                update_wm(cid, "font_name", fname)
                update_wm(cid, "font_path", os.path.join(FONTS_DIR, fname))
                update_wm(cid, "font_custom", True)
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), u_id, "main"), mid)

            elif data.startswith("wm_ffav_"):
                fname = data.replace("wm_ffav_", "")
                favs = s.get('favorites', [])
                if fname in favs: favs.remove(fname)
                else: favs.append(fname)
                update_wm(cid, "favorites", favs)
                bot.answer_callback_query(c.id, "✨ Favorites Updated")
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), u_id, "all"), mid)
                
            elif data == "wm_font_set_default":
                update_wm(cid, "font_name", "Default")
                update_wm(cid, "font_path", None)
                update_wm(cid, "font_custom", False)
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), u_id, "main"), mid)
                
            elif data.startswith("wm_fdel_"):
                if is_admin(u_id):
                    fname = data.replace("wm_fdel_", "")
                    fpath = os.path.join(FONTS_DIR, fname)
                    if os.path.exists(fpath): os.remove(fpath)
                    favs = s.get('favorites', [])
                    if fname in favs:
                        favs.remove(fname)
                        update_wm(cid, "favorites", favs)
                    bot.answer_callback_query(c.id, f"🗑️ {fname} Deleted")
                    send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), u_id, "all"), mid)
                else:
                    bot.answer_callback_query(c.id, "⚠️ Admin Only!", show_alert=True)

            elif data == "wm_font_upload":
                user_states_watermark[cid] = "waiting_font"
                bot.send_message(cid, "📤 **Send .ttf/.otf file (Max 3MB):**")

            elif data.startswith("wm_rot_"):
                val = data.replace("wm_rot_", "")
                if val == "cust":
                    user_states_watermark[cid] = "waiting_rot"
                    bot.send_message(cid, "📐 **Enter rotation angle (0-360):**")
                else:
                    update_wm(cid, "rotation", int(val))
                    refresh_main_menu(bot, cid, mid)

            elif data == "wm_menu_size":
                user_states_watermark[cid] = "waiting_val_size"
                bot.send_message(cid, "📏 **Enter size percentage (1-100):**")
            
            elif data == "wm_menu_op":
                user_states_watermark[cid] = "waiting_val_opacity"
                bot.send_message(cid, "👻 **Enter opacity (0-255):**")

            elif data == "wm_up_logo":
                user_states_watermark[cid] = "waiting_logo"
                bot.send_message(cid, "🖼️ **Send Logo (Photo or Document PNG):**")
                
            elif data == "wm_logo_inc":
                curr = s.get('logo_scale', 1.0)
                update_wm(cid, "logo_scale", round(min(5.0, curr + 0.1), 1))
                refresh_main_menu(bot, cid, mid)
                
            elif data == "wm_logo_dec":
                curr = s.get('logo_scale', 1.0)
                update_wm(cid, "logo_scale", round(max(0.1, curr - 0.1), 1))
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_do_preview":
                from PIL import Image
                t_in, t_out = f"p_in_{cid}.jpg", f"p_out_{cid}.jpg"
                Image.new('RGB', (1280, 720), (200, 200, 200)).save(t_in)
                apply_watermark_image(t_in, t_out, get_wm_settings(cid))
                with open(t_out, 'rb') as f: bot.send_photo(cid, f, caption="👁️ Preview")
                os.remove(t_in); os.remove(t_out)
                refresh_main_menu(bot, cid)

            elif data == "wm_toggle_mode":
                curr = get_wm_settings(cid).get('mode', 'text')
                update_wm(cid, "mode", "logo" if curr=="text" else "text")
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_tog_bg":
                curr = get_wm_settings(cid).get('bg_enabled', True)
                update_wm(cid, "bg_enabled", not curr)
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_menu_style":
                send_menu(bot, cid, "✨ **Style & Rotation**", get_style_menu(), mid)

            elif data == "wm_menu_tile":
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)
                
            elif data == "wm_gap_inc":
                curr = s.get('tile_gap', 20)
                update_wm(cid, "tile_gap", curr + 10)
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)
                
            elif data == "wm_gap_dec":
                curr = s.get('tile_gap', 20)
                update_wm(cid, "tile_gap", max(0, curr - 10))
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)

            elif data == "wm_toggle_silent":
                curr = get_wm_settings(cid).get('silent_mode', False)
                update_wm(cid, "silent_mode", not curr)
                bot.answer_callback_query(c.id, f"Silent Mode {'Enabled' if not curr else 'Disabled'}")
                refresh_main_menu(bot, cid, mid)
            
            elif data == "wm_toggle_blur":
                curr = get_wm_settings(cid).get('face_blur', False)
                update_wm(cid, "face_blur", not curr)
                bot.answer_callback_query(c.id, f"Face Cover {'Enabled' if not curr else 'Disabled'}")
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_toggle_only_blur":
                curr = get_wm_settings(cid).get('only_blur', False)
                update_wm(cid, "only_blur", not curr)
                if not curr: update_wm(cid, "face_blur", True)
                bot.answer_callback_query(c.id, f"Only Cover {'Enabled' if not curr else 'Disabled'}")
                refresh_main_menu(bot, cid, mid)
            
            # ✅ FIX: Sticker added to Style rotation
            elif data == "wm_toggle_blur_style":
                curr_style = s.get('blur_style', 'smooth')
                if curr_style == "smooth": new_style = "pixelate"
                elif curr_style == "pixelate": new_style = "sticker"
                else: new_style = "smooth"
                
                update_wm(cid, "blur_style", new_style)
                bot.answer_callback_query(c.id, f"Cover Style: {new_style.title()}")
                refresh_main_menu(bot, cid, mid)

            elif data.startswith("wm_set_pattern:"):
                action_type = data.split(":")[-1]
                is_on = (action_type == "on")
                update_wm(cid, "pattern_enabled", is_on)
                if is_on: update_wm(cid, "position", "tile")
                bot.answer_callback_query(c.id, f"🔳 Pattern {'Enabled' if is_on else 'Disabled'}")
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)

            elif data.startswith("wm_set_pos:"):
                pos = data.split(":")[-1]
                update_wm(cid, "position", pos)
                update_wm(cid, "pattern_enabled", False)
                bot.answer_callback_query(c.id, f"📍 Position set to {pos}")
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)

            elif data == "wm_menu_col_target":
                send_menu(bot, cid, "🎨 **Select Target:**", get_color_target_menu(), mid)

            elif data.startswith("wm_col_menu_"):
                target = data.split("_")[-1]
                send_menu(bot, cid, f"🎨 **Pick {target.title()} Color:**", get_color_palette_menu(target), mid)

            elif data.startswith("wm_setcol_"):
                p = data.split("_"); t, v = p[2], p[3]
                if v == "cust":
                    user_states_watermark[cid] = f"waiting_col_{t}"
                    bot.send_message(cid, f"🎨 **Send Hex for {t}:**")
                else:
                    update_wm(cid, "text_color" if t=="text" else "bg_color", v)
                    refresh_main_menu(bot, cid, mid)

            elif data == "wm_set_text":
                user_states_watermark[cid] = "waiting_text"
                bot.send_message(cid, "✍️ **Send Watermark Text:**")

        safe_handle(c, action)
