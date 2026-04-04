import base64
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests
from colorama import Fore, Style, init

init(autoreset=True)

# Vô hiệu hóa InsecureRequestWarning khi gọi requests verify=False
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

red = Fore.RED
green = Fore.GREEN
yellow = Fore.YELLOW
bold = Style.BRIGHT
lg = Fore.LIGHTGREEN_EX

script_dir = os.path.dirname(__file__)
access_file = os.path.join(script_dir, "data", "access.txt")
account_file = os.path.join(script_dir, "data", "conbogay.txt")

# Chèn đường dẫn script để import tool gốc một cách an toàn
sys.path.append(script_dir)
try:
    # Function `token` từ reg.py để tạo accessToken mới nếu có thông tin uid/password
    from reg import token
except ImportError:
    pass


def decode_jwt(jwt_token):
    """Tiến hành decode token JWT lấy thông tin Payload"""
    try:
        parts = jwt_token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_data = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
        return json.loads(payload_data)
    except Exception:
        return None


def get_accounts():
    """Lấy kho Acc từ Data để tiện re-login (nếu JWT chết)"""
    accounts = {}
    if os.path.exists(account_file):
        with open(account_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":" in line:
                    uid, pwd = line.split(":", 1)
                    accounts[uid.strip()] = pwd.strip()
    return accounts


def check_and_refresh_tokens():
    print(
        f"\n{bold}=== ♻️ BẮT ĐẦU KIỂM TRA & LÀM MỚI TOKEN ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ==={Fore.RESET}"
    )

    if not os.path.exists(access_file):
        print(f"{yellow}[-] Không tìm thấy file {access_file}. Đã bỏ qua.{Fore.RESET}")
        return

    with open(access_file, "r", encoding="utf-8") as f:
        tokens = [line.strip() for line in f if line.strip()]

    if not tokens:
        print(f"{yellow}[-] CSDL Token hiện tại đang rỗng.{Fore.RESET}")
        return

    accounts_db = get_accounts()
    valid_tokens = []
    stats = {"removed": 0, "refreshed": 0, "saved": 0}
    now = datetime.now()
    lock = threading.Lock()

    def process_token(jwt_token):
        payload = decode_jwt(jwt_token)
        if not payload:
            print(
                f"{red}[-] Định dạng Token thất bại: {jwt_token[:25]}... (Xóa Khỏi Data).{Fore.RESET}"
            )
            with lock:
                stats["removed"] += 1
            return

        exp = payload.get("exp", 0)

        # Mấu chốt: Lấy external_uid (dạng số) thay vì external_id (dạng hash mã hóa)
        uid = str(payload.get("external_uid", ""))

        if not uid or uid == "":
            uid = payload.get("sub", "Unknown")

        exp_time = datetime.fromtimestamp(exp)
        time_left = exp_time - now

        # Logic lọc & refresh Token
        if time_left.total_seconds() < 0:
            print(
                f"{red}[-] MÃ TOKEN (UID {uid}) QUÁ HẠN. Đang xóa hoặc gọi api lấy mới...{Fore.RESET}"
            )
            if uid in accounts_db:
                try:
                    # Mặc định xin API tại server VN để lấy token (Không break region list)
                    res = token(uid, accounts_db[uid], "VN")
                    if res and "jwt_token" in res:
                        with lock:
                            valid_tokens.append(res["jwt_token"])
                            stats["refreshed"] += 1
                        print(
                            f"{green}[+] Cấp lại token thành công cho hệ sinh thái Mới : UID {uid}{Fore.RESET}"
                        )
                        return
                except Exception as e:
                    print(
                        f"{red}[!] Bypass thất bại đối với UID {uid}: {e}{Fore.RESET}"
                    )

            with lock:
                stats["removed"] += 1

        elif time_left.total_seconds() < 86400 * 3:  # Remaining less than 3 days
            print(
                f"{yellow}[!] Token (UID {uid}) cảnh báo sắp tàn. (%d Ngày). Đang chạy Refresher...{Fore.RESET}"
                % time_left.days
            )
            if uid in accounts_db:
                try:
                    res = token(uid, accounts_db[uid], "VN")
                    if res and "jwt_token" in res:
                        with lock:
                            valid_tokens.append(res["jwt_token"])
                            stats["refreshed"] += 1
                        print(
                            f"{green}[+] Gia hạn Token thành công cho UID {uid}. Vòng đời vĩnh viễn!{Fore.RESET}"
                        )
                        return
                except Exception as e:
                    print(
                        f"{red}[!] Garena Server Refresh Lỗi với vòng {uid}: {e}{Fore.RESET}"
                    )

            # Nếu thất bại vẫn backup Token cũ (đề phòng)
            with lock:
                valid_tokens.append(jwt_token)
                stats["saved"] += 1

        else:
            # Token vòng đời hoàn toàn khỏe mạnh
            print(
                f"{green}[+] Tín hiệu Active mạnh. Token (UID {uid}) còn hạn khả dụng: {time_left.days} Ngày.{Fore.RESET}"
            )
            with lock:
                valid_tokens.append(jwt_token)
                stats["saved"] += 1

    # Chạy đa luồng (multi-threading) thay vì xử lý tuần tự
    with ThreadPoolExecutor(max_workers=10) as executor:
        for jwt_token in tokens:
            executor.submit(process_token, jwt_token)

    # Cập nhật chuẩn hóa không ghi trùng Data Base
    valid_tokens = list(set(valid_tokens))

    # Re-write an toàn mảng Token còn sống
    with open(access_file, "w", encoding="utf-8") as f:
        for t in valid_tokens:
            f.write(t + "\n")

    print(f"\n{lg}=== ♻️ TỔNG KẾT REFRESHER ==={Fore.RESET}")
    print(f"🛡️ Tổng token ban đầu trong Data : {len(tokens)}")
    print(f"✅ Active khỏe/Sống    : {stats['saved']}")
    print(f"🗑️ Khai Tử (Hỏng)      : {stats['removed']}")
    print(f"🔄 Re-Login / Gia hạn  : {stats['refreshed']}")
    print(f"🛡️ Kho token sinh thái hiện tại  : {len(valid_tokens)}")
    print(f"{bold}===================================={Fore.RESET}")


def run_daemon():
    print(f"\n{lg}[*] DAEMON CHẠY NGẦM SERVER ĐÃ KÍCH HOẠT.{Fore.RESET}")
    print(
        f"{yellow}[*] Bot sẽ ngủ đông và gọi API dọn dẹp, cấp cứu tự động lúc đúng 12 giờ đêm hằng ngày.{Fore.RESET}"
    )

    while True:
        now = datetime.now()
        # Daemon hẹn thức dậy lúc 00:00:00 (12h Đêm Mai)
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        wait_seconds = (next_run - now).total_seconds()

        print(
            f"[*] Hẹn giờ quét API & Refresher tiếp theo vào lúc: {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"[*] Sleep Thread Bot: {int(wait_seconds)}s...")

        time.sleep(wait_seconds)

        try:
            check_and_refresh_tokens()
        except Exception as e:
            print(f"{red}[!] Cảnh báo Daemon đụng độ Exception: {e}{Fore.RESET}")
            time.sleep(30)  # Delay loop lỡ bị infinite error


if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"{bold}=== AUTO CHECKER & REFRESHER (Garena Accounts Ecosystem) ==={Fore.RESET}"
    )

    print("1. Chạy Kiểm Tra Thủ Công (Run Scan Target now 1 Lần duy nhất)")
    print("2. Chạy Tiến Trình Ngầm Xuyên Đêm (Daemon Server 12h đêm hàng ngày)")
    choice = input("\nVui lòng chọn Module (1/2): ").strip()

    if choice == "1":
        check_and_refresh_tokens()
    else:
        run_daemon()
