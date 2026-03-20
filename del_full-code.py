import requests

# আপনার তথ্য
TOKEN = "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"
REPO = "zebabot/Miss-Zeba"
BRANCH = "main"

headers = {"Authorization": f"token {TOKEN}"}

def delete_all_files():
    print(f"🚀 {REPO} রিপোজিটরির ফাইলগুলো ডিলিট করার প্রক্রিয়া শুরু হচ্ছে...\n")
    
    # ১. রিপোজিটরির সব ফাইলের লিস্ট নেওয়া (Recursive)
    url = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
    r = requests.get(url, headers=headers)
    
    if r.status_code != 200:
        print(f"❌ এরর: ফাইল লিস্ট পাওয়া যায়নি। টোকেন বা রিপো নাম চেক করুন।")
        return

    tree = r.json().get("tree", [])
    
    # ২. ফাইলগুলো ডিলিট করা (উল্টো দিক থেকে যাতে ফোল্ডার আগে ডিলিট না হয়)
    files_to_delete = [item for item in tree if item["type"] == "blob"]
    
    if not files_to_delete:
        print("ℹ️ ডিলিট করার মতো কোনো ফাইল পাওয়া যায়নি।")
        return

    for item in files_to_delete:
        path = item["path"]
        sha = item["sha"]
        
        delete_url = f"https://api.github.com/repos/{REPO}/contents/{path}"
        data = {
            "message": f"Deleted {path} to clear repository",
            "sha": sha,
            "branch": BRANCH
        }
        
        print(f"🗑️ ডিলিট করা হচ্ছে: {path}...")
        res = requests.delete(delete_url, json=data, headers=headers)
        
        if res.status_code == 200:
            print(f"✅ সফল: {path}")
        else:
            print(f"❌ ব্যর্থ: {path} | কারণ: {res.json().get('message')}")

    print("\n🎉 রিপোজিটরির সকল ফাইল ডিলিট করা সম্পন্ন হয়েছে!")

if __name__ == "__main__":
    confirm = input("আপনি কি নিশ্চিত যে আপনি রিপোর সব ফাইল মুছে ফেলতে চান? (yes/no): ")
    if confirm.lower() == "yes":
        delete_all_files()
    else:
        print("প্রক্রিয়া বাতিল করা হয়েছে।")
