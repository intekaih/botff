import os
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import urllib3
from colorama import Fore, Style
from reg import token  # Import thẳng hàm gọi token từ tool cũ

# Disable insecure request warnings do không dùng verify=True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

red = Fore.RED
lg = Fore.LIGHTGREEN_EX
green = Fore.GREEN
bold = Style.BRIGHT
yellow = Fore.YELLOW

file_lock = threading.Lock()


def worker(item, thread_id, region, proxy_dict=None):
    try:
        if ":" not in item:
            return

        uid, password = item.split(":", 1)
        uid = uid.strip()
        password = password.strip()

        proxy_str = proxy_dict.get("http", "Direct") if proxy_dict else "Direct"
        print(f"[*] Luồng {thread_id}: Đang xử lý UID {uid} qua proxy {proxy_str}...")

        # Gọi hàm lấy token từ reg.py (Tái sử dụng code gốc mà không làm hỏng cấu trúc)
        res = token(uid, password, region, proxy=proxy_dict)

        if res and "jwt_token" in res:
            access_token = res["jwt_token"]

            token_short = access_token[:30] + "..."

            with file_lock:
                with open(
                    os.path.join(os.path.dirname(__file__), "data", "access.txt"),
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(f"{access_token}\n")
            print(
                f"{green}[Luồng {thread_id}] ✅ Lấy token thành công | UID: {uid} -> {token_short} -> data/access.txt{Fore.RESET}"
            )
        else:
            print(
                f"{red}[Luồng {thread_id}] ❌ UID {uid} - Không lấy được JWT_TOKEN{Fore.RESET}"
            )

    except Exception as e:
        print(f"{red}[Luồng {thread_id}] Lỗi với {item.strip()}: {e}{Fore.RESET}")


if __name__ == "__main__":
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{bold}=== CÔNG CỤ GET TOKEN TỪ ACCOUNT ĐÃ TẠO ==={Fore.RESET}")

    region = input("Nhập region (VN, ID, SG, IND, etc.) [Mặc định: VN]: ").strip()
    if not region:
        region = "VN"

    # Đường dẫn file dữ liệu
    script_dir = os.path.dirname(__file__)
    data_dir = os.path.join(script_dir, "data")
    file_path = os.path.join(data_dir, "conbogay.txt")
    proxy_path = os.path.join(data_dir, "proxies.txt")

    # Tạo thư mục data nếu chưa tồn tại
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    if not os.path.exists(file_path):
        print(f"{red}[!] Không tìm thấy file {file_path}")
        print(
            f"{yellow}Hãy tạo file 'conbogay.txt' trong thư mục 'data' với định dạng uid:password để tiến hành.{Fore.RESET}"
        )
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        # Lọc các dòng hợp lệ có định dạng uid:pass
        accounts = [line.strip() for line in f if line.strip() and ":" in line]

    total_acc = len(accounts)

    if total_acc == 0:
        print(
            f"{red}[!] File {file_path} rỗng hoặc không có định dạng uid:password hợp lệ.{Fore.RESET}"
        )
        sys.exit(1)

    print(
        f"\n{yellow}Tìm thấy {total_acc} accounts trong data/conbogay.txt.{Fore.RESET}"
    )

    proxies_list = []
    if os.path.exists(proxy_path):
        with open(proxy_path, "r", encoding="utf-8") as f:
            for line in f:
                p = line.strip()
                if p:
                    if not p.startswith("http") and not p.startswith("socks"):
                        p = f"http://{p}"
                    proxies_list.append({"http": p, "https": p})
        if proxies_list:
            print(
                f"{green}[+] Đã tải {len(proxies_list)} Proxy từ {proxy_path}.{Fore.RESET}"
            )
    else:
        print(
            f"{yellow}[-] Không có file Proxy ({proxy_path}). Dùng IP gốc.{Fore.RESET}"
        )

    try:
        num_threads = int(input(f"Số luồng chạy cùng lúc (Khuyên dùng 5-20): "))
    except ValueError:
        num_threads = 5

    print(f"\n{lg}Đang khởi chạy {num_threads} luồng...{Fore.RESET}\n")

    # Sử dụng ThreadPool chạy đa luồng cho tốc độ cao
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i, acc in enumerate(accounts):
            proxy_dict = random.choice(proxies_list) if proxies_list else None
            executor.submit(worker, acc, i + 1, region, proxy_dict)

    print(f"\n{bold}=== HOÀN THÀNH ==={Fore.RESET}")
    print(f"{lg}Các Token hợp lệ đã được lưu nối vào file: data/access.txt{Fore.RESET}")
