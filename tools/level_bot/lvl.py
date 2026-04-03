import socket
import threading
import select
import time
import random

SOCKS_VERSION = 5

# Global state
MainS = None
StartData = None
StopData = b'\x03\x15\x00\x00\x00\x10\t\x1e\xb7N\xef9\xb7WN5\x96\x02\xb0g\x0c\xa8'  # Thêm lại StopData như yêu cầu
Increase = True
TotalGame = 0
active_lvl_thread = None
lvl_lock = threading.Lock()

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
            except:
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
        except:
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
                            if len(data) >= 400 and data[:2].hex() == "0301":
                                StartData = data
                                print("Đã capture StartData mới")
                            remote.sendall(data)

                        else:
                            data_hex = data.hex()

                            if data_hex[:4] == "0300" and len(data) >= 50 and Increase:
                                if b"Ranked Mode" in data:
                                    print("=== Out Lobby → Auto queue trận mới ngay ===")
                                    TotalGame = 0
                                    Increase = True
                                    # Auto gửi StartData để queue ranked liên tục
                                    threading.Thread(target=self.auto_queue).start()
                                else:
                                    TotalGame += 1
                                    print(f"=== Bắt đầu trận mới: {TotalGame} ===")
                                    if active_lvl_thread is None or not active_lvl_thread.is_alive():
                                        active_lvl_thread = threading.Thread(target=self.lvl_up, args=(TotalGame,))
                                        active_lvl_thread.start()
                                    threading.Thread(target=self.check_start, args=(TotalGame,)).start()

                            if data_hex[:4] == "1200" and b"lv" in data:
                                Increase = True
                                print("Level up hoàn tất → Cho phép tăng tiếp")

                            client.sendall(data)
                    except:
                        return
        except Exception:
            pass
        finally:
            client.close()
            remote.close()

    def safe_send(self, data):
        try:
            with lvl_lock:
                if MainS:
                    MainS.sendall(data)
                    return True
        except:
            print("Socket đã chết → không gửi được")
            return False
        return False

    def auto_queue(self):
        """Khi out lobby → auto gửi StartData vài lần để queue ranked ngay"""
        time.sleep(3 + random.uniform(0, 2))  # Delay nhỏ tránh spam ngay lập tức
        for i in range(3):  # Gửi 3 lần như người thật bấm tìm trận
            if self.safe_send(StartData):
                print(f"Auto queue lần {i+1}/3")
                time.sleep(1 + random.uniform(0, 1))
            else:
                break

    def lvl_up(self, current_match):
        global MainS, StartData, StopData, TotalGame, active_lvl_thread
        if not StartData:
            print("Không có StartData → bỏ qua lvl_up")
            active_lvl_thread = None
            return

        print(f"Level up trận {current_match} bắt đầu (có gửi StopData)")

        # Thêm lại gửi StopData (nhẹ nhàng, ít lần, có delay + random)
        for i in range(4):
            if self.safe_send(StopData):
                print(f"Gửi StopData lần {i+1}/4")
                time.sleep(0.8 + random.uniform(0, 0.5))
            else:
                active_lvl_thread = None
                return

        time.sleep(12 + random.uniform(0, 4))  # Chờ load trận

        if self.safe_send(StartData):
            print("Đã gửi packet start đầu tiên")

        # Spam nhẹ StartData
        spam_count = 0
        max_spam = 18
        while TotalGame == current_match and spam_count < max_spam:
            delay = random.uniform(20, 30)  # Delay rất lớn để an toàn
            time.sleep(delay)
            if self.safe_send(StartData):
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
            self.safe_send(StartData)

    def run(self, host="0.0.0.0", port=7777):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"Proxy chạy tại {host}:{port} - Đã thêm lại StopData + Auto queue khi out lobby")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    Proxy().run()