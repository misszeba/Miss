import os
import requests

MODEL_DIR = "data/models"
if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)

files = {
    "deploy.prototxt": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
    "res10_300x300_ssd_iter_140000.caffemodel": "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
}

print("⏳ Downloading Face Detection Models...")
for name, url in files.items():
    path = os.path.join(MODEL_DIR, name)
    if not os.path.exists(path):
        try:
            r = requests.get(url)
            with open(path, 'wb') as f: f.write(r.content)
            print(f"✅ {name} Downloaded")
        except: print(f"❌ Failed: {name}")
    else: print(f"✅ {name} Exists")
