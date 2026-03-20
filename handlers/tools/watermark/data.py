# handlers/tools/watermark/data.py

try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("⚠️ Warning: utils/db_manager.py not found. Data will not be persistent.")

# ডিফল্ট সেটিংস
DEFAULT_WM_SETTINGS = {
    "mode": "text",             
    "text": "Watermark",
    "text_color": "#FFFFFF",
    "bg_color": "#000000",
    "position": "bottom_right", 
    "opacity": 255,             
    "bg_opacity": 150,          
    "size_pct": 5,              
    "bg_enabled": True, 
    "silent_mode": False,
    
    # ✅ Face Blur & Sticker Feature
    "face_blur": False,         
    "blur_style": "smooth",     # অপশন: 'smooth', 'pixelate', অথবা 'sticker'
    
    # Font Settings
    "font_path": None,          
    "font_name": "Default",
    "font_custom": False,
    "favorites": [], 
    
    # Logo Settings
    "logo_path": None,          
    "logo_scale": 1.0,          
    
    # Advanced
    "rotation": 0,              
    "pattern_enabled": False, 
    "tile_gap": 20,             
    "tile_mode": "grid",        
    
    # Custom Position
    "pos_x": 0,
    "pos_y": 0
}

def get_wm_settings(chat_id):
    cid = str(chat_id)
    try:
        all_data = get_full_config()
        if cid not in all_data:
            all_data[cid] = {}
        
        if "wm_settings" not in all_data[cid]:
            all_data[cid]["wm_settings"] = DEFAULT_WM_SETTINGS.copy()
            save_full_config(all_data)
        
        current_settings = all_data[cid]["wm_settings"]
        
        if "face_blur" not in current_settings:
            current_settings["face_blur"] = False
        if "blur_style" not in current_settings:
            current_settings["blur_style"] = "smooth"
            
        return current_settings
    except Exception as e:
        print(f"❌ Error fetching WM settings: {e}")
        return DEFAULT_WM_SETTINGS.copy()

def save_wm_settings(chat_id, key, value):
    cid = str(chat_id)
    try:
        all_data = get_full_config()
        if cid not in all_data:
            all_data[cid] = {}
        if "wm_settings" not in all_data[cid]:
            all_data[cid]["wm_settings"] = DEFAULT_WM_SETTINGS.copy()
            
        all_data[cid]["wm_settings"][key] = value
        save_full_config(all_data)
        return True
    except Exception as e:
        print(f"❌ Error saving WM settings: {e}")
        return False
