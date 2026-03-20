import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageColor
from io import BytesIO

VIDEO_SUPPORT = False

try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    VIDEO_SUPPORT = True
    print(f"✅ Video Engine Active: FFmpeg found at {ffmpeg_path}")
        
except Exception as e:
    print(f"⚠️ Video Engine Disabled: {e}")

def get_color_rgb(hex_code):
    try: return ImageColor.getrgb(hex_code)
    except: return (255, 255, 255)

def apply_opacity_pil(image, opacity_val):
    if opacity_val >= 255: return image
    if image.mode != 'RGBA': image = image.convert('RGBA')
    alpha = image.split()[3]
    factor = opacity_val / 255.0
    alpha = ImageEnhance.Brightness(alpha).enhance(factor)
    image.putalpha(alpha)
    return image

MODEL_DIR = "data/models"
PROTO_PATH = os.path.join(MODEL_DIR, "deploy.prototxt")
MODEL_PATH = os.path.join(MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
CONFIDENCE_THRESHOLD = 0.5

net = None
try:
    if os.path.exists(PROTO_PATH) and os.path.exists(MODEL_PATH):
        net = cv2.dnn.readNetFromCaffe(PROTO_PATH, MODEL_PATH)
        print("✅ DNN Face Detection Model Loaded.")
    else:
        print("⚠️ DNN Model missing. Run setup_models.py")
except Exception as e:
    print(f"❌ Error loading DNN model: {e}")

# ✅ FIX: Sticker Engine Integration
def process_blur_on_array(img_array, style="smooth", is_rgb=False, s=None, cached_logo=None):
    try:
        if net is None: return img_array
        
        img = img_array.copy()
        if is_rgb: img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        (h, w) = img.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        net.setInput(blob)
        detections = net.forward()
        
        face_found = False

        for i in range(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > CONFIDENCE_THRESHOLD:
                face_found = True
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                
                startX, startY = max(0, startX), max(0, startY)
                endX, endY = min(w, endX), min(h, endY)
                
                face_w = endX - startX
                face_h = endY - startY
                if face_w == 0 or face_h == 0: continue

                # 🌟 STICKER LOGIC
                if style == "sticker" and cached_logo is not None:
                    user_scale = s.get("logo_scale", 1.0) if s else 1.0
                    sticker_w = int(face_w * 1.5 * user_scale)
                    sticker_h = int(face_h * 1.5 * user_scale)
                    
                    if sticker_w <= 0 or sticker_h <= 0: continue
                    
                    cx, cy = startX + face_w // 2, startY + face_h // 2
                    
                    ideal_x1 = cx - sticker_w // 2
                    ideal_y1 = cy - sticker_h // 2
                    
                    s_x1 = max(0, ideal_x1)
                    s_y1 = max(0, ideal_y1)
                    s_x2 = min(w, ideal_x1 + sticker_w)
                    s_y2 = min(h, ideal_y1 + sticker_h)
                    
                    actual_w = s_x2 - s_x1
                    actual_h = s_y2 - s_y1
                    
                    if actual_w > 0 and actual_h > 0:
                        resized_logo = cv2.resize(cached_logo, (sticker_w, sticker_h))
                        logo_x1 = s_x1 - ideal_x1
                        logo_y1 = s_y1 - ideal_y1
                        logo_crop = resized_logo[logo_y1:logo_y1+actual_h, logo_x1:logo_x1+actual_w]
                        
                        if logo_crop.shape[2] == 4: # PNG with Alpha
                            alpha_s = logo_crop[:, :, 3] / 255.0
                            alpha_l = 1.0 - alpha_s
                            for c in range(0, 3):
                                img[s_y1:s_y2, s_x1:s_x2, c] = (alpha_s * logo_crop[:, :, c] + alpha_l * img[s_y1:s_y2, s_x1:s_x2, c])
                        else:
                            img[s_y1:s_y2, s_x1:s_x2] = logo_crop
                    continue # Skip normal blur

                # Normal Blur Logic
                face_roi = img[startY:endY, startX:endX]
                if style == "pixelate":
                    temp = cv2.resize(face_roi, (10, 10), interpolation=cv2.INTER_LINEAR)
                    blurred = cv2.resize(temp, (face_w, face_h), interpolation=cv2.INTER_NEAREST)
                else:
                    k_size = (w // 15) | 1
                    blurred = cv2.GaussianBlur(face_roi, (k_size, k_size), 30)
                
                img[startY:endY, startX:endX] = blurred
        
        if is_rgb and face_found:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
        return img if face_found else img_array
        
    except Exception as e:
        print(f"Blur Array Error: {e}")
        return img_array

def blur_faces_in_image(image_path, style="smooth", s=None):
    try:
        img = cv2.imread(image_path) 
        if img is None: return False
        
        cached_logo = None
        if style == "sticker" and s and s.get("logo_path") and os.path.exists(s["logo_path"]):
            cached_logo = cv2.imread(s["logo_path"], cv2.IMREAD_UNCHANGED)
            if cached_logo is None: style = "smooth" # Fallback if image corrupted
            
        result_img = process_blur_on_array(img, style, is_rgb=False, s=s, cached_logo=cached_logo)
        cv2.imwrite(image_path, result_img)
        return True
    except Exception as e:
        print(f"Face Blur Error: {e}")
        return False

def generate_watermark_layer(target_size, s):
    width, height = target_size
    layer = Image.new("RGBA", (width, height), (0,0,0,0))
    
    wm_img = None
    if s.get("mode") == "logo" and s.get("logo_path") and os.path.exists(s["logo_path"]):
        try:
            wm_img = Image.open(s["logo_path"]).convert("RGBA")
            scale = s.get("logo_scale", 1.0)
            target_w = int(min(width, height) * 0.3 * scale)
            ratio = target_w / float(wm_img.size[0])
            target_h = int(float(wm_img.size[1]) * float(ratio))
            wm_img = wm_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        except: pass
    else: 
        text = s.get("text", "Watermark")
        font_size = int(min(width, height) * (s.get("size_pct", 5) / 100))
        try: font = ImageFont.truetype(s.get("font_path", "arial.ttf"), font_size)
        except: font = ImageFont.load_default()
        
        dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = dummy.textbbox((0, 0), text, font=font)
        w_txt, h_txt = bbox[2]-bbox[0], bbox[3]-bbox[1]
        
        wm_img = Image.new("RGBA", (w_txt + 40, h_txt + 40), (0,0,0,0))
        d = ImageDraw.Draw(wm_img)
        
        if s.get("bg_enabled", True):
            bg_c = get_color_rgb(s.get("bg_color", "#000000")) + (150,)
            d.rectangle([0, 0, w_txt + 40, h_txt + 40], fill=bg_c)
            
        txt_c = get_color_rgb(s.get("text_color", "#FFFFFF")) + (255,)
        d.text((20, 20), text, font=font, fill=txt_c)

    if not wm_img: return None

    wm_img = apply_opacity_pil(wm_img, s.get("opacity", 255))
    if s.get("rotation", 0) != 0:
        wm_img = wm_img.rotate(s["rotation"], expand=True, resample=Image.BICUBIC)

    wm_w, wm_h = wm_img.size
    padding = 20
    
    if s.get("pattern_enabled", False): 
        gap = s.get("tile_gap", 20)
        for y in range(0, height, wm_h + gap):
            for x in range(0, width, wm_w + gap):
                layer.paste(wm_img, (x, y), wm_img)
    else:
        pos = s.get("position", "bottom_right")
        x, y = width - wm_w - padding, height - wm_h - padding 
        
        if pos == "top_left": x, y = padding, padding
        elif pos == "top_right": x, y = width - wm_w - padding, padding
        elif pos == "bottom_left": x, y = padding, height - wm_h - padding
        elif pos == "center": x, y = (width - wm_w)//2, (height - wm_h)//2
        elif pos == "top_center": x, y = (width - wm_w)//2, padding
        elif pos == "bottom_center": x, y = (width - wm_w)//2, height - wm_h - padding
        
        layer.paste(wm_img, (x, y), wm_img)

    return layer

def apply_watermark_image(input_path, output_path, s):
    try:
        img = Image.open(input_path).convert("RGBA")
        if s.get("only_blur", False):
            img.convert("RGB").save(output_path, "JPEG", quality=95)
            return True
        wm_layer = generate_watermark_layer(img.size, s)
        if wm_layer:
            final = Image.alpha_composite(img, wm_layer)
            final.convert("RGB").save(output_path, "JPEG", quality=95)
        else:
            img.convert("RGB").save(output_path, "JPEG")
        return True
    except Exception as e:
        print(f"WM Image Error: {e}")
        return False

def apply_watermark_video(input_path, output_path, s, is_gif=False):
    if not VIDEO_SUPPORT: return False
    try:
        clip = VideoFileClip(input_path)
        
        if s.get("face_blur", False):
            style = s.get("blur_style", "smooth")
            cached_logo = None
            if style == "sticker" and s.get("logo_path") and os.path.exists(s["logo_path"]):
                cached_logo = cv2.imread(s["logo_path"], cv2.IMREAD_UNCHANGED)
                if cached_logo is None: style = "smooth"
                
            clip = clip.fl_image(lambda frame: process_blur_on_array(frame, style=style, is_rgb=True, s=s, cached_logo=cached_logo))

        if not s.get("only_blur", False):
            wm_layer = generate_watermark_layer(clip.size, s)
            if wm_layer:
                wm_clip = ImageClip(np.array(wm_layer)).set_duration(clip.duration)
                final = CompositeVideoClip([clip, wm_clip])
            else:
                final = clip
        else:
            final = clip 
            
        if is_gif:
            final.write_gif(output_path, fps=10, verbose=False, logger=None)
        else:
            final.write_videofile(output_path, codec="libx264", audio_codec="aac", preset="ultrafast", verbose=False, logger=None)
            
        clip.close()
        return True
    except Exception as e:
        print(f"WM Video Error: {e}")
        return False

def generate_font_preview_image(font_dir, font_list=None):
    if not os.path.exists(font_dir): return None
    fonts = [f for f in (font_list or os.listdir(font_dir)) if f.endswith(('.ttf', '.otf'))]
    if not fonts: return None
    
    w, h_line = 800, 80
    h = len(fonts) * h_line + 40
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    y = 20
    for fname in fonts:
        try:
            f = ImageFont.truetype(os.path.join(font_dir, fname), 40)
            draw.text((20, y), fname, font=f, fill=(0,0,0))
            y += h_line
        except: pass
        
    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio
