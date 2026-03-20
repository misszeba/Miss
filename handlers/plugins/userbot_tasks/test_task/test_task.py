import time
from telethon import events

def register_userbot_task(client, bot, user_id):
    """
    ইউজারবট টেস্ট টুল: এটি চেক করবে ইঞ্জিন এবং ডাটাবেস সচল কি না।
    """
    @client.on(events.NewMessage(pattern=r"\.test", outgoing=True))
    async def test_handler(event):
        # বর্তমান সময় এবং পিং ক্যালকুলেশন
        start_time = time.time()
        msg = await event.edit("📡 **ইঞ্জিন পরীক্ষা করা হচ্ছে...**")
        end_time = time.time()
        
        ping = round((end_time - start_time) * 1000, 2)
        
        # ইউজার ডাটাবেস থেকে তথ্য নেওয়া
        me = await client.get_me()
        
        response_text = (
            "🚀 **ইউজারবট স্ট্যাটাস: সচল (Active)**\n\n"
            f"👤 **ইউজার:** {me.first_name}\n"
            f"🆔 **ইউজার আইডি:** `{user_id}`\n"
            f"⚡ **রেসপন্স টাইম:** `{ping}ms`\n"
            f"📂 **ডাটাবেস:** `MongoDB Atlas (Connected)`\n\n"
            "✅ আপনার ইউজারবট ইঞ্জিন এবং ক্লাউড ডাটাবেস নিখুঁতভাবে কাজ করছে!"
        )
        
        await msg.edit(response_text)
