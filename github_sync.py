import os
import base64
import requests

# ================== CONFIG ==================
# তোমার দেওয়া ক্রেডেনশিয়াল
GITHUB_TOKEN = "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" 
USERNAME = "zihad-zeba"
REPO = "Miss-Zeba-Final"
BRANCH = "main"

# বর্তমান ফোল্ডার ডিটেক্ট করা
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

API_URL = f"https://api.github.com/repos/{USERNAME}/{REPO}/contents"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ১. ইগনোর লিস্ট: এই ফাইলগুলো কখনোই আপলোড হবে না
IGNORE = {
    ".git", 
    "__pycache__", 
    ".idea", 
    ".vscode", 
    "venv", 
    "env",
    ".env",
    ".DS_Store"
}

# ২. [নতুন অপশন] স্পেসিফিক ফাইল আপলোড লিস্ট
# এখন এই লিস্টে ফাইলের নাম থাকলে সেটি আপলোড হবে (এমনকি এই স্ক্রিপ্ট নিজেও)
ONLY_FILES = {
    # "github_sync.py",
 #    "secrets.py"
}
# ============================================

def upload_file(local_path, repo_path):
    try:
        with open(local_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        url = f"{API_URL}/{repo_path.replace(os.sep, '/')}"

        # ফাইলটি আগে আছে কিনা চেক করা (SHA পাওয়ার জন্য)
        r = requests.get(url, headers=HEADERS)
        sha = r.json().get("sha") if r.status_code == 200 else None

        data = {
            "message": f"Sync {repo_path}",
            "content": content,
            "branch": BRANCH
        }

        if sha:
            data["sha"] = sha

        res = requests.put(url, headers=HEADERS, json=data)

        if res.status_code in (200, 201):
            print(f"✔ Uploaded: {repo_path}")
        else:
            print(f"✖ Failed: {repo_path} | {res.text}")

    except Exception as e:
        print(f"✖ Error uploading {repo_path}: {e}")


def sync():
    print(f"🚀 Starting upload to '{REPO}' ({USERNAME})...")
    
    # মোড চেক করা
    if ONLY_FILES:
        print(f"ℹ️  Mode: ONLY specific files ({len(ONLY_FILES)} files selected)")
    else:
        print("ℹ️  Mode: All files (Syncing everything)")

    for root, dirs, files in os.walk(LOCAL_DIR):
        # ইগনোর করা ফোল্ডার বাদ দেওয়া
        dirs[:] = [d for d in dirs if d not in IGNORE]

        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, LOCAL_DIR)

            # ১. ইগনোর লিস্ট চেকিং (সবার আগে)
            if file in IGNORE or any(p in IGNORE for p in rel_path.split(os.sep)):
                continue

            # ২. স্পেসিফিক ফাইল চেকিং (ONLY_FILES লজিক)
            if ONLY_FILES:
                # ফাইলের নাম অথবা রিলেটিভ পাথ যদি লিস্টে না থাকে, তবে স্কিপ করবে
                if file not in ONLY_FILES and rel_path not in ONLY_FILES:
                    continue

            # (নিজেকে আপলোড না করার কোডটি এখানে ছিল, সেটি সরিয়ে দেওয়া হয়েছে)

            upload_file(full_path, rel_path)

if __name__ == "__main__":
    sync()
    print("\n✅ GitHub sync complete")
