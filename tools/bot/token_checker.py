import base64
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from colorama import Fore, Style

# Cấu hình màu sắc
red = Fore.RED
lg = Fore.LIGHTGREEN_EX
green = Fore.GREEN
yellow = Fore.YELLOW
bold = Style.BRIGHT
cyan = Fore.CYAN

# Đường dẫn thư mục
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, "data")
access_file = os.path.join(data_dir, "access.txt")
live_file = os.path.join(data_dir, "access_live.txt")
die_file = os.path.join(data_dir, "access_die.txt")

file_lock = threading.Lock()


def decode_jwt_payload(token):
    """Giải mã payload của JWT Token mà không cần signature (Secret Key)"""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None

        payload_b64 = parts[1]
        # Thêm padding cho base64
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        return json.loads(payload_json)
    except Exception:
        return None


def check_token(token, thread_id):
    """Kiểm tra token bằng thời gian thực và ping API Garena"""
    token = token.strip()
    if not token:
        return

    payload = decode_jwt_payload(token)
    if not payload:
        print(
            f"{red}[Luồng {thread_id}] ❌ Token không hợp lệ định dạng JWT{Fore.RESET}"
        )
        return

    exp = payload.get("exp")
    uid = payload.get("external_id", "UNKNOWN")

    # Bước 1: Kiểm tra Hạn sử dụng (Expiration Time - `exp`) ngay trên Local
    if exp:
        exp_time = datetime.fromtimestamp(exp)
        if datetime.now() > exp_time:
            print(
                f"{yellow}[Luồng {thread_id}] ⚠️ Token của UID {uid} đã hết hạn từ {exp_time}{Fore.RESET}"
            )
            with file_lock:
                with open(die_file, "a", encoding="utf-8") as f:
                    f.write(f"{token}\n")
            return

    # Bước 2: Request API để xác thực Token (Xem Garena có thu hồi Token chưa)
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI) GarenaMSDK/4.0.19P8",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"https://account.garena.com/api/account/profile?account_id={uid}&session_key={token}"
    is_live = False

    try:
        res = requests.get(url, headers=headers, timeout=10)
        # Nếu Garena trả về 401 Unauthorized có nghĩa là token đã bị thu hồi hoặc chết.
        # Nếu ra 404 Not Found hoặc khác 401 thì account token vẫn xài được cho Game (FF).
        if res.status_code != 401:
            is_live = True
    except Exception:
        # Nếu có lỗi Timeout, mặc định coi là Sống để tránh xóa nhầm Token tốt
        is_live = True

    # Bước 3: Phân loại và Ghi Log
    with file_lock:
        if is_live:
            print(
                f"{green}[Luồng {thread_id}] ✅ Token của UID {uid} CÒN SỐNG{Fore.RESET}"
            )
            with open(live_file, "a", encoding="utf-8") as f:
                f.write(f"{token}\n")
        else:
            print(
                f"{red}[Luồng {thread_id}] ❌ Token của UID {uid} ĐÃ CHẾT (Bị Garena thu hồi){Fore.RESET}"
            )
            with open(die_file, "a", encoding="utf-8") as f:
                f.write(f"{token}\n")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"{bold}{cyan}=== CÔNG CỤ AUTO-CHECKER: KIỂM TRA & LỌC TOKEN ==={Fore.RESET}\n"
    )

    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    if not os.path.exists(access_file):
        print(f"{red}[!] Không tìm thấy file {access_file}{Fore.RESET}")
        print(
            f"{yellow}Hãy chạy công cụ Get_token.py trước để tạo data chứa Token nhé.{Fore.RESET}"
        )
        return

    with open(access_file, "r", encoding="utf-8") as f:
        tokens = [line.strip() for line in f if line.strip()]

    total_tokens = len(tokens)
    if total_tokens == 0:
        print(f"{yellow}[!] File {access_file} hiện đang rỗng.{Fore.RESET}")
        return

    print(
        f"{lg}[*] Tìm thấy {total_tokens} token trong hệ thống. Chuẩn bị kiểm tra hạn sử dụng và Valid API...{Fore.RESET}\n"
    )

    # Xóa file live/die cũ để tạo kết quả lọc mới hoàn toàn
    if os.path.exists(live_file):
        os.remove(live_file)
    if os.path.exists(die_file):
        os.remove(die_file)

    try:
        num_threads = int(
            input(f"{bold}Nhập số luồng kiểm tra (Nên để 10-20): {Fore.RESET}")
        )
    except ValueError:
        num_threads = 10

    print(f"\n{lg}Sẵn sàng khởi động {num_threads} luồng quét...{Fore.RESET}\n")
    time.sleep(1)

    # Chạy Checker Đa Luồng để tối ưu thời gian
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i, token_str in enumerate(tokens):
            executor.submit(check_token, token_str, i + 1)

    print(f"\n{bold}=== HOÀN TẤT KIỂM TRA ==={Fore.RESET}")

    # Kiểm tra lại số lượng Token Live và đè file
    if os.path.exists(live_file):
        with open(live_file, "r", encoding="utf-8") as f:
            live_count = len(f.readlines())

        print(
            f"{green}[+] Lọc được {live_count}/{total_tokens} token CÒN SỐNG -> Đã xuất ra file: data/access_live.txt{Fore.RESET}"
        )

        # Cập nhật đè danh sách Live lại file chính access.txt để các tool khác dùng
        with open(live_file, "r", encoding="utf-8") as f_live:
            with open(access_file, "w", encoding="utf-8") as f_acc:
                f_acc.write(f_live.read())
        print(
            f"{yellow}[*] Tự động Dọn Rác: Đã update data/access.txt, chỉ giữ lại các Token còn sống để Game Tool chạy mượt!{Fore.RESET}"
        )
    else:
        print(
            f"{red}[-] Rất sầu! Toàn bộ số Token ({total_tokens}) này đều đã die hoặc hết hạn.{Fore.RESET}"
        )
        # Dọn dẹp file bị hỏng
        open(access_file, "w").close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{red}Người dùng đã hủy quá trình Check.{Fore.RESET}")
        sys.exit(0)
