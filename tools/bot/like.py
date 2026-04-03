"""
╔══════════════════════════════════════════════════════════════╗
║         BUFF LIKE FREE FIRE - AUTO SPAM LIKE PROFILE         ║
║         Tool đọc access.txt → gọi API LikeProfile Garena     ║
║         Tác giả: Dinh Hoang  |  Region: VN (mặc định)        ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import json
import time
import random
import threading
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from colorama import Fore, Style, init

init(autoreset=True)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── MÀU SẮC ────────────────────────────────────────────────
RED    = Fore.RED
GREEN  = Fore.GREEN
LG     = Fore.LIGHTGREEN_EX
YELLOW = Fore.YELLOW
CYAN   = Fore.CYAN
BLUE   = Fore.LIGHTBLUE_EX
MAG    = Fore.MAGENTA
BOLD   = Style.BRIGHT
RESET  = Style.RESET_ALL

# ─── REGION CONFIG ───────────────────────────────────────────
REGION_URLS = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID":  "https://clientbp.ggblueshark.com/",
    "BR":  "https://client.us.freefiremobile.com/",
    "ME":  "https://clientbp.common.ggbluefox.com/",
    "VN":  "https://clientbp.ggblueshark.com/",
    "TH":  "https://clientbp.common.ggbluefox.com/",
    "CIS": "https://clientbp.ggblueshark.com/",
    "BD":  "https://clientbp.ggblueshark.com/",
    "PK":  "https://clientbp.ggblueshark.com/",
    "SG":  "https://clientbp.ggblueshark.com/",
    "NA":  "https://client.us.freefiremobile.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "EU":  "https://clientbp.ggblueshark.com/",
    "TW":  "https://clientbp.ggblueshark.com/",
}

# ─── CRYPTO (Giống hệt reg.py) ───────────────────────────────
_AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
_AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69,  51, 121, 99, 104, 106, 77, 37])

def aes_encrypt(plain_hex: str) -> bytes:
    """AES-128-CBC encrypt (giống encrypt_api trong reg.py)."""
    raw = bytes.fromhex(plain_hex)
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(raw, AES.block_size))

# ─── PROTOBUF HELPERS (Giống reg.py) ─────────────────────────
def _enc_varint(n: int) -> bytes:
    H = []
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        H.append(b)
        if not n: break
    return bytes(H)

def _field_varint(field: int, value: int) -> bytes:
    return _enc_varint((field << 3) | 0) + _enc_varint(value)

def _field_length(field: int, value) -> bytes:
    if isinstance(value, str):
        value = value.encode()
    return _enc_varint((field << 3) | 2) + _enc_varint(len(value)) + value

def build_proto(fields: dict) -> bytes:
    """Build protobuf từ dict {field_number: value}."""
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = build_proto(value)
            packet.extend(_field_length(field, nested))
        elif isinstance(value, int):
            packet.extend(_field_varint(field, value))
        else:
            packet.extend(_field_length(field, value))
    return bytes(packet)

# ─── HEADERS CHUNG ───────────────────────────────────────────
def make_headers(jwt_token: str) -> dict:
    return {
        "Authorization":   f"Bearer {jwt_token}",
        "Content-Type":    "application/x-www-form-urlencoded",
        "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 10; G011A Build/PI)",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA":            "v1 1",
        "ReleaseVersion":  "OB52",
        "Connection":      "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Expect":          "100-continue",
    }

# ─── BƯỚC 1: Lấy JWT token từ access_token (Guest Login nhanh) ─
def get_jwt_from_access_token(access_token: str, region: str) -> str | None:
    """
    Gọi GetPlayerPersonalShow hoặc tái dùng access_token làm Bearer.
    Với guest acc đã đăng ký đầy đủ (reg.py xong), access_token chính là
    Bearer JWT của session — ta dùng thẳng luôn.
    """
    return access_token  # access.txt đã chứa JWT (Bearer token) từ MajorLogin

# ─── BƯỚC 2: Build payload LikeProfile ───────────────────────
def build_like_payload(target_uid: int, jwt_token: str) -> bytes:
    """
    Protobuf cho endpoint LikeProfile:
      field 1 = target_uid (varint)
    Sau đó AES encrypt trước khi gửi.
    """
    fields = {1: target_uid}
    proto_bytes = build_proto(fields)
    encrypted = aes_encrypt(proto_bytes.hex())
    return encrypted

# ─── BƯỚC 3: Gọi endpoint LikeProfile ───────────────────────
def like_profile(jwt_token: str, target_uid: int, region: str) -> dict:
    """
    Gọi API LikeProfile của Free Fire server.
    Returns: {"success": bool, "status": int, "msg": str}
    """
    base_url = REGION_URLS.get(region.upper(), "https://clientbp.ggblueshark.com/")
    url = f"{base_url}LikeProfile"

    payload = build_like_payload(target_uid, jwt_token)
    headers = make_headers(jwt_token)

    try:
        resp = requests.post(url, headers=headers, data=payload,
                             timeout=10, verify=False)
        if resp.status_code == 200:
            return {"success": True,  "status": 200, "msg": "OK"}
        elif resp.status_code == 429:
            return {"success": False, "status": 429, "msg": "Rate-limit — token này đã like hôm nay"}
        elif resp.status_code == 401:
            return {"success": False, "status": 401, "msg": "Token hết hạn / không hợp lệ"}
        else:
            return {"success": False, "status": resp.status_code,
                    "msg": f"HTTP {resp.status_code}: {resp.text[:80]}"}
    except requests.exceptions.Timeout:
        return {"success": False, "status": 0, "msg": "Timeout"}
    except Exception as e:
        return {"success": False, "status": -1, "msg": str(e)}

# ─── COUNTER ─────────────────────────────────────────────────
success_count = 0
fail_count    = 0
counter_lock  = threading.Lock()

def inc_success():
    global success_count
    with counter_lock:
        success_count += 1

def inc_fail():
    global fail_count
    with counter_lock:
        fail_count += 1

# ─── WORKER (chạy từng token) ────────────────────────────────
def like_worker(idx: int, jwt_token: str, target_uid: int,
                region: str, delay_range: tuple):
    """Một luồng: đợi delay nhỏ ngẫu nhiên rồi thả like."""
    # Delay ngẫu nhiên nhẹ để tránh rate-limit đồng loạt
    time.sleep(random.uniform(*delay_range))

    result = like_profile(jwt_token.strip(), target_uid, region)

    ts = datetime.now().strftime("%H:%M:%S")
    token_short = jwt_token[:28] + "..."

    if result["success"]:
        inc_success()
        print(f"{LG}[{ts}][+] #{idx:04d} | ✅ LIKE OK          | {token_short}")
    else:
        inc_fail()
        msg = result["msg"]
        color = YELLOW if result["status"] == 429 else RED
        print(f"{color}[{ts}][-] #{idx:04d} | ❌ {msg[:40]:<40} | {token_short}")

# ─── BANNER ──────────────────────────────────────────────────
BANNER = f"""
{RED+BOLD}
 ██████╗ ██╗   ██╗███████╗███████╗    ██╗     ██╗██╗  ██╗███████╗
 ██╔══██╗██║   ██║██╔════╝██╔════╝    ██║     ██║██║ ██╔╝██╔════╝
 ██████╔╝██║   ██║█████╗  █████╗      ██║     ██║█████╔╝ █████╗  
 ██╔══██╗██║   ██║██╔══╝  ██╔══╝      ██║     ██║██╔═██╗ ██╔══╝  
 ██████╔╝╚██████╔╝██║     ██║         ███████╗██║██║  ██╗███████╗
 ╚═════╝  ╚═════╝ ╚═╝     ╚═╝         ╚══════╝╚═╝╚═╝  ╚═╝╚══════╝
{CYAN}          AUTO BUFF LIKE FREE FIRE  |  @Dinh Hoang
{RESET}"""

# ─── MAIN ────────────────────────────────────────────────────
def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(BANNER)

    # ── Đọc access.txt ──────────────────────────────────────
    token_file = os.path.join(os.path.dirname(__file__), "data", "access.txt")
    if not os.path.exists(token_file):
        print(f"{RED}[!] Không tìm thấy file {token_file}")
        print(f"{YELLOW}[!] Hãy chạy reg.py trước để sinh token.")
        sys.exit(1)

    with open(token_file, "r", encoding="utf-8") as f:
        tokens = [line.strip() for line in f if line.strip()]

    if not tokens:
        print(f"{RED}[!] File {token_file} rỗng. Chạy reg.py trước!")
        sys.exit(1)

    print(f"{LG}[*] Đã tải {len(tokens)} token từ {token_file}\n")

    # ── Nhập thông tin mục tiêu ─────────────────────────────
    try:
        target_uid_str = input(f"{CYAN}[?] Nhập UID mục tiêu cần buff Like: {RESET}").strip()
        target_uid = int(target_uid_str)
    except ValueError:
        print(f"{RED}[!] UID phải là số nguyên!")
        sys.exit(1)

    region_input = input(
        f"{CYAN}[?] Region server (VN/IND/ID/BR/ME/TH... mặc định VN): {RESET}"
    ).strip().upper() or "VN"

    if region_input not in REGION_URLS:
        print(f"{YELLOW}[!] Region không hợp lệ → dùng VN")
        region_input = "VN"

    try:
        num_threads = int(input(
            f"{CYAN}[?] Số luồng chạy song song (1-50, khuyên 10): {RESET}"
        ).strip() or "10")
        num_threads = max(1, min(num_threads, 50))
    except ValueError:
        num_threads = 10

    try:
        max_tokens = int(input(
            f"{CYAN}[?] Dùng tối đa bao nhiêu token? (0 = tất cả {len(tokens)}): {RESET}"
        ).strip() or "0")
    except ValueError:
        max_tokens = 0

    if max_tokens > 0:
        tokens = tokens[:max_tokens]

    delay_min = 0.1
    delay_max = 1.5

    print(f"""
{BOLD}{BLUE}══════════════════════════════════════════════════
  🎯  Target UID : {target_uid}
  🌏  Region     : {region_input}  →  {REGION_URLS[region_input]}
  🪙  Tokens     : {len(tokens)}
  ⚡  Threads    : {num_threads}
  ⏳  Delay      : {delay_min}s – {delay_max}s / luồng
{BLUE}══════════════════════════════════════════════════{RESET}
""")
    confirm = input(f"{YELLOW}[?] Bắt đầu buff like? (y/N): {RESET}").strip().lower()
    if confirm != "y":
        print(f"{RED}[!] Đã huỷ.")
        sys.exit(0)

    print(f"\n{LG}[*] Đang chạy... bấm Ctrl+C để dừng sớm.\n")
    start_time = time.time()

    # ── Chạy đa luồng ───────────────────────────────────────
    try:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(
                    like_worker,
                    idx + 1,
                    token,
                    target_uid,
                    region_input,
                    (delay_min, delay_max)
                )
                for idx, token in enumerate(tokens)
            ]
            # Chờ hoàn thành
            for f in futures:
                try:
                    f.result()
                except Exception:
                    pass
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!] Người dùng dừng — đang tổng kết...")

    elapsed = round(time.time() - start_time, 2)

    # ── Tổng kết ────────────────────────────────────────────
    total = success_count + fail_count
    print(f"""
{BOLD}{BLUE}══════════════════ KẾT QUẢ ══════════════════════
  ✅  Like thành công : {success_count}
  ❌  Thất bại        : {fail_count}
  📊  Tổng đã xử lý  : {total} / {len(tokens)}
  ⏱   Thời gian       : {elapsed}s
{BLUE}══════════════════════════════════════════════════{RESET}
""")

    # Ghi log
    log_line = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"UID={target_uid} | Region={region_input} | "
        f"OK={success_count} | Fail={fail_count} | "
        f"Total={total} | Time={elapsed}s\n"
    )
    with open(os.path.join(os.path.dirname(__file__), "data", "like_log.txt"), "a", encoding="utf-8") as lf:
        lf.write(log_line)
    print(f"{LG}[*] Đã ghi log vào data/like_log.txt")


if __name__ == "__main__":
    main()
