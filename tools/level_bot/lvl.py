import socket
import threading
import select
import time
import random

SOCKS_VERSION = 5

# Global state
MainS = None
StartData = None
StopData = b'\x03\x15\x00\x00\x00\x10\t\x1e\xb7N\xef9\xb7WN5\x96\x02\xb0g\x0c\xa8'
Increase = True
TotalGame = 0
active_lvl_thread = None
lvl_lock = threading.Lock()
state_lock = threading.Lock()  # Lock riêng cho state variables


class Proxy:
    def __init__(self):
        self.username = "Mtuandz"
        self.password = "Mtuandz"

    def handle_client(self, conn):
        try:
            version = conn.recv(1)[0]
            if version != SOCKS_VERSION:
                conn.close()
                return

            nmethods = conn.recv(1)[0]
            methods = [conn.recv(1)[0] for _ in range(nmethods)]

            if 2 not in methods:
                conn.close()
                return

            conn.sendall(bytes([SOCKS_VERSION, 2]))

            if not self.verify_credentials(conn):
                conn.close()
                return

            version, cmd, _, address_type = conn.recv(4)
            if cmd != 1:
                conn.close()
                return

            if address_type == 1:
                address = socket.inet_ntoa(conn.recv(4))
            elif address_type == 3:
                domain_len = conn.recv(1)[0]
                domain = conn.recv(domain_len)
                address = socket.gethostbyname(domain)
            else:
                conn.close()
                return

            port = int.from_bytes(conn.recv(2), 'big')

            try:
                remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote.connect((address, port))
                bind_address = remote.getsockname()
                reply = b'\x05\x00\x00\x01' + socket.inet_aton(bind_address[0]) + bind_address[1].to_bytes(2, 'big')
                conn.sendall(reply)
            except Exception:
                conn.sendall(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
                conn.close()
                return

            self.exchange_loop(conn, remote, port)

        except Exception:
            conn.close()

    def verify_credentials(self, conn):
        try:
            version = conn.recv(1)[0]
            ulen = conn.recv(1)[0]
            username = conn.recv(ulen).decode('utf-8', errors='ignore')
            plen = conn.recv(1)[0]
            password = conn.recv(plen).decode('utf-8', errors='ignore')

            if username == self.username and password == self.password:
                conn.sendall(bytes([version, 0]))
                return True
            else:
                conn.sendall(bytes([version, 0xFF]))
                return False
        except Exception:
            return False

    def exchange_loop(self, client, remote, port):
        global MainS, StartData, Increase, TotalGame, active_lvl_thread

        if port == 39698:
            with lvl_lock:
                MainS = remote
            print("=== Đã cập nhật socket game mới (reconnect) ===")

        try:
            while True:
                r, _, _ = select.select([client, remote], [], [])
                for sock in r:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            return

                        if sock is client:
                            # FIX: Capture StartData với lock để tránh race condition
                            if len(data) >= 400 and data[:2].hex() == "0301":
                                with state_lock:
                                    StartData = data
                                print("Đã capture StartData mới")
                            remote.sendall(data)

                        else:
                            data_hex = data.hex()

                            if data_hex[:4] == "0300" and len(data) >= 50 and Increase:
                                if b"Ranked Mode" in data:
                                    print("=== Out Lobby → Auto queue trận mới ngay ===")
                                    with state_lock:
                                        TotalGame = 0
                                        Increase = True
                                    threading.Thread(target=self.auto_queue, daemon=True).start()
                                else:
                                    with state_lock:
                                        TotalGame += 1
                                        current = TotalGame
                                        # FIX: Set Increase=False khi trận bắt đầu để tránh trigger lặp
                                        Increase = False

                                    print(f"=== Bắt đầu trận mới: {current} ===")
                                    if active_lvl_thread is None or not active_lvl_thread.is_alive():
                                        active_lvl_thread = threading.Thread(
                                            target=self.lvl_up, args=(current,), daemon=True
                                        )
                                        active_lvl_thread.start()
                                    threading.Thread(
                                        target=self.check_start, args=(current,), daemon=True
                                    ).start()

                            # Khi phát hiện level up → cho phép detect trận tiếp
                            if data_hex[:4] == "1200" and b"lv" in data:
                                with state_lock:
                                    Increase = True
                                print("Level up hoàn tất → Cho phép tăng tiếp")

                            client.sendall(data)
                    except Exception:
                        return
        except Exception:
            pass
        finally:
            client.close()
            remote.close()

    def safe_send(self, data):
        """Gửi data đến MainS socket an toàn. Trả về True nếu thành công."""
        # FIX: Kiểm tra data không None trước khi gửi
        if data is None:
            print("[safe_send] Không có data để gửi (StartData chưa được capture)")
            return False
        try:
            with lvl_lock:
                if MainS:
                    MainS.sendall(data)
                    return True
                else:
                    print("[safe_send] MainS chưa sẵn sàng")
                    return False
        except Exception as e:
            print(f"Socket đã chết → không gửi được: {e}")
            return False

    def auto_queue(self):
        """Khi out lobby → auto gửi StartData vài lần để queue ranked ngay"""
        time.sleep(3 + random.uniform(0, 2))
        for i in range(3):
            # FIX: Lấy snapshot StartData trong lock để tránh race condition
            with state_lock:
                snap = StartData
            if snap is None:
                print("[auto_queue] StartData chưa có → bỏ qua")
                break
            if self.safe_send(snap):
                print(f"Auto queue lần {i+1}/3")
                time.sleep(1 + random.uniform(0, 1))
            else:
                break

    def lvl_up(self, current_match):
        global active_lvl_thread

        # FIX: Kiểm tra StartData tồn tại trước khi bắt đầu
        with state_lock:
            snap_start = StartData
        if not snap_start:
            print("Không có StartData → bỏ qua lvl_up")
            active_lvl_thread = None
            return

        print(f"Level up trận {current_match} bắt đầu (có gửi StopData)")

        for i in range(4):
            if self.safe_send(StopData):
                print(f"Gửi StopData lần {i+1}/4")
                time.sleep(0.8 + random.uniform(0, 0.5))
            else:
                active_lvl_thread = None
                return

        time.sleep(12 + random.uniform(0, 4))

        with state_lock:
            snap_start = StartData
        if self.safe_send(snap_start):
            print("Đã gửi packet start đầu tiên")

        spam_count = 0
        max_spam = 18
        while TotalGame == current_match and spam_count < max_spam:
            delay = random.uniform(20, 30)
            time.sleep(delay)
            with state_lock:
                snap_start = StartData
            if self.safe_send(snap_start):
                spam_count += 1
                print(f"Spam StartData lần {spam_count}/{max_spam} trận {current_match}")
            else:
                break

        print(f"Kết thúc lvl_up trận {current_match}")
        active_lvl_thread = None

    def check_start(self, current_match):
        time.sleep(8)
        if current_match == TotalGame:
            print("Trận chưa start → Auto fix")
            # FIX: Lấy snapshot StartData an toàn
            with state_lock:
                snap = StartData
            self.safe_send(snap)

    def run(self, host="0.0.0.0", port=7777):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"[LVL BOT] SOCKS5 Proxy chạy tại {host}:{port}")
        print(f"[LVL BOT] Username: {self.username} | Password: {self.password}")
        print(f"[LVL BOT] Cấu hình game SOCKS5: {host}:{port} với tài khoản trên")
        print(f"[LVL BOT] Đang chờ kết nối từ game...")
        while True:
            conn, addr = s.accept()
            print(f"[LVL BOT] Kết nối mới từ {addr}")
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    Proxy().run()
