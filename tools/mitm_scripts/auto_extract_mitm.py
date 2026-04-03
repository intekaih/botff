import base64
import json
import logging
import os
import re
import subprocess
import sys

from mitmproxy import http

# Cấu hình logging cơ bản cho mitmdump
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class FreeFireTokenExtractor:
    def __init__(self):
        # Thiết lập các đường dẫn động dựa trên vị trí file hiện tại
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.bot_dir = os.path.join(os.path.dirname(self.script_dir), "bot")
        self.data_dir = os.path.join(self.bot_dir, "data")
        self.access_file = os.path.join(self.data_dir, "access.txt")
        self.getinfo_script = os.path.join(self.bot_dir, "get_info.py")

        # Đảm bảo thư mục data tồn tại
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def response(self, flow: http.HTTPFlow):
        # Bắt các Request được gửi về từ máy chủ MajorLogin của Garena (bao gồm cả server chung ggblueshark và ME ggbluefox)
        if (
            "loginbp.ggblueshark.com/MajorLogin" in flow.request.pretty_url
            or "loginbp.common.ggbluefox.com/MajorLogin" in flow.request.pretty_url
        ):
            logging.info(
                "[*] Phát hiện phản hồi đăng nhập từ hệ thống Garena! Đang phân tích..."
            )

            try:
                res_body = flow.response.get_text(strict=False)
                if not res_body:
                    return

                # Phân tích cú pháp lấy JWT. JWT Token chuẩn luôn bắt đầu bằng eyJ và có 2 dấu chấm.
                # Chuỗi cụ thể của Garena thường chứa: eyJhbGciOi...
                jwt_match = re.search(
                    r"(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)", res_body
                )

                if jwt_match:
                    jwt_token = jwt_match.group(1)
                    logging.info(
                        f"[+] Trích xuất thành công JWT Token: {jwt_token[:35]}..."
                    )

                    # Bóc tách Payload của JWT để lấy UID (external_id)
                    parts = jwt_token.split(".")
                    uid = "UNKNOWN_UID"
                    if len(parts) >= 2:
                        payload_b64 = parts[1]
                        # Thêm padding (dấu =) để decode base64 hợp lệ
                        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                        try:
                            payload_json = base64.urlsafe_b64decode(payload_b64).decode(
                                "utf-8"
                            )
                            payload_data = json.loads(payload_json)
                            # Trong payload của Free Fire, UID thường nằm ở biến external_id
                            uid = payload_data.get("external_id", "UNKNOWN_UID")
                        except Exception as e:
                            logging.error(f"[-] Lỗi khi giải mã JWT Payload: {e}")

                    logging.info(f"[+] Lấy được UID tài khoản: {uid}")

                    # 1. Lưu JWT Token vào file access.txt
                    with open(self.access_file, "a", encoding="utf-8") as f:
                        f.write(f"{jwt_token}\n")
                    logging.info(
                        f"[+] Đã lưu Token vào cơ sở dữ liệu ({self.access_file})"
                    )

                    # 2. Tự động bắn dữ liệu qua get_info.py để lấy Email/SDT ngay lúc đăng nhập
                    if uid != "UNKNOWN_UID":
                        logging.info(
                            f"[*] Đang tự động tra cứu thông tin liên kết cho ID {uid}..."
                        )
                        self.trigger_get_info(uid, jwt_token)
                else:
                    logging.info(
                        "[-] Quét Response OK nhưng không tìm thấy cấu trúc JWT Token. Có thể tài khoản sai hoặc bị SSL Pinning chặn."
                    )

            except Exception as e:
                logging.error(
                    f"[-] Lỗi không xác định khi xử lý phản hồi MajorLogin: {e}"
                )

    def trigger_get_info(self, uid, token):
        """Khởi chạy công cụ kiểm tra Email/SDT dưới nền"""
        try:
            # Chạy file get_info.py với 2 đối số <uid> và <token>
            result = subprocess.run(
                [sys.executable, self.getinfo_script, str(uid), token],
                capture_output=True,
                text=True,
                timeout=20,
            )

            # Xuất log đẹp mắt trên màn hình console mitmdump
            print("\n" + "=" * 60)
            print(
                f"🚀 KẾT QUẢ AUTO-EXTRACT (TRÍCH XUẤT TỰ ĐỘNG LÚC ĐĂNG NHẬP UID: {uid})"
            )
            print("-" * 60)
            # In nội dung StdOut từ get_info.py
            print(result.stdout.strip())

            if result.stderr:
                print("\n[CẢNH BÁO/LỖI TỪ GET_INFO]:")
                print(result.stderr.strip())
            print("=" * 60 + "\n")

        except subprocess.TimeoutExpired:
            logging.error(
                "[-] Hết thời gian chờ (Timeout) khi query lên App Center Garena."
            )
        except Exception as e:
            logging.error(f"[-] Lỗi môi trường khi gọi lệnh trích xuất: {e}")


# Kích hoạt Addon trong mitmproxy/mitmdump
addons = [FreeFireTokenExtractor()]
