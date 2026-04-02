import json
import os
import time
from config import DATA_FILE

# Đọc dữ liệu từ file JSON
def load_keys():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = file.read().strip()
            return json.loads(data) if data else {}
    except json.JSONDecodeError:
        return {}

# Lưu dữ liệu vào file JSON
def save_keys(keys):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(keys, file, indent=4, ensure_ascii=False)


def lsgd( data):
    filename = "lsgd.txt"
    with open(filename, "a", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False) + "\n")
# Tạo key mới (chưa có ngày hết hạn)
def create_key(key, hours, creator):
    keys = load_keys()
    keys[key] = {
        "expire": None,  # Chưa có ngày hết hạn
        "hours": hours,  # Lưu thời gian sử dụng để khi kích hoạt sẽ tính
        "time": hours,
        "creator": creator,
        "user": None,
        "ip": None
    }
    save_keys(keys)

# Thêm IP và kích hoạt key (set ngày hết hạn khi có user)
def activate_key(key, user, ip):
    keys = load_keys()
    if key in keys and keys[key]["user"] is None:
        expire_time = int(time.time()) + (keys[key]["hours"] * 3600)  # Tính ngày hết hạn từ lúc kích hoạt
        keys[key]["expire"] = expire_time
        keys[key]["user"] = user
        keys[key]["ip"] = ip
        save_keys(keys)
        return True
    return False

# Xóa key
def remove_key(key):
    keys = load_keys()
    if key in keys:
        del keys[key]
        save_keys(keys)
        return True
    return False
