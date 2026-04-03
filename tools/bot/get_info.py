import json
import os
import sys

import requests
from colorama import Fore, Style

# Cấu hình màu cho log
red = Fore.RED
lg = Fore.LIGHTGREEN_EX
green = Fore.GREEN
bold = Style.BRIGHT
yellow = Fore.YELLOW
cyan = Fore.CYAN


def get_account_info(uid, access_token):
    """
    Hàm này dùng để lấy thông tin tài khoản (email, sđt) từ UID và Access Token.
    Sử dụng các endpoint Garena (SSO/Connect/Account profile API).
    """
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI) GarenaMSDK/4.0.19P8",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Các endpoint tiềm năng của hệ thống Garena Connect / Auth
    # Ghi chú: Garena sử dụng nhiều endpoint khác nhau, một số yêu cầu JWT token hoặc Session Key tương ứng
    endpoints = [
        f"https://account.garena.com/api/account/profile?account_id={uid}&session_key={access_token}",
        f"https://auth.garena.com/api/user/info?access_token={access_token}&open_id={uid}",
        f"https://connect.garena.com/api/user/info?access_token={access_token}&open_id={uid}",
        f"https://100067.connect.garena.com/oauth/user/info?access_token={access_token}&open_id={uid}",
    ]

    for url in endpoints:
        try:
            # Thực thi GET request với Authorization Bearer
            response = requests.get(url, headers=headers, timeout=10)

            # Kiểm tra HTTP response
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Logic trích xuất tuỳ thuộc vào payload thực tế của Garena
                    # Thông thường structure sẽ nằm trong data['email'], hoặc data['reply']['email']
                    email = (
                        data.get("email")
                        or data.get("reply", {}).get("email")
                        or data.get("account", {}).get("email", "Không có hoặc ẩn")
                    )
                    phone = (
                        data.get("phone")
                        or data.get("reply", {}).get("phone")
                        or data.get("account", {}).get("phone", "Không có hoặc ẩn")
                    )

                    username = data.get("username", "Không rõ")

                    return {
                        "status": "success",
                        "email": email,
                        "phone": phone,
                        "username": username,
                        "raw": data,
                    }
                except json.JSONDecodeError:
                    continue
            elif response.status_code == 401:
                # Token không hợp lệ hoặc hết hạn tại endpoint này
                pass

        except requests.exceptions.RequestException as e:
            # Bỏ qua lỗi timeout/connection để thử URL tiếp theo
            continue

    # Nếu tất cả các endpoint đều không trả về kết quả
    return {
        "status": "error",
        "message": "Token hết hạn, không hợp lệ hoặc API không thể truy cập.",
    }


def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(
        f"{bold}{cyan}=== CÔNG CỤ TRÍCH XUẤT THÔNG TIN TÀI KHOẢN BẰNG ACCESS TOKEN ==={Fore.RESET}"
    )
    print(
        f"{yellow}Lưu ý: Bạn cần điền UID và Access Token hợp lệ (JWT) lấy được từ tính năng Get Token.{Fore.RESET}\n"
    )

    uid = input(f"{bold}Nhập Account ID (UID): {Fore.RESET}").strip()
    if not uid:
        print(f"{red}[!] UID không được để trống!{Fore.RESET}")
        sys.exit(1)

    token = input(f"{bold}Nhập Access Token: {Fore.RESET}").strip()
    if not token:
        print(f"{red}[!] Access Token không được để trống!{Fore.RESET}")
        sys.exit(1)

    print(
        f"\n{lg}[*] Đang gửi yêu cầu trích xuất dữ liệu cho UID: {uid}...{Fore.RESET}"
    )

    result = get_account_info(uid, token)

    print("-" * 50)
    if result["status"] == "success":
        print(f"{green}SUCCESS: Đã lấy thông tin Liên kết thành công!{Fore.RESET}")
        print(f"{bold}UID:{Fore.RESET} {uid}")
        print(f"{bold}Username:{Fore.RESET} {result.get('username')}")
        print(f"{bold}Email Liên Kết:{Fore.RESET} {result.get('email')}")
        print(f"{bold}SĐT Liên Kết:{Fore.RESET} {result.get('phone')}")

    else:
        print(f"{red}FAILED: {result['message']}{Fore.RESET}")
        print(
            f"{yellow}Gợi ý: Đảm bảo Access Token thuộc về UID được cung cấp và vẫn còn hiệu lực.{Fore.RESET}"
        )
    print("-" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{red}Chương trình đã bị hủy.{Fore.RESET}")
        sys.exit(0)
