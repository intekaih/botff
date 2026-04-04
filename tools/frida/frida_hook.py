import frida
import sys
import requests

# URL của endpoint `check_account_info` bên trong file app.py của bot
API_URL = "http://127.0.0.1:5000/api/tokens/account_info"
REGION = "VN" # Có thể thay đổi tới khu vực bạn cần

extracted_data = {
    "access_token": None,
    "open_id": None
}

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        key = payload.get('key')
        value = payload.get('value')
        
        print(f"[*] Bắt được dữ liệu từ RAM: {key} = {value[:20]}...")
        
        if key == 'access_token':
            extracted_data['access_token'] = value
        elif key == 'open_id':
            extracted_data['open_id'] = value
            
        # Nếu đã bắt được đồng thời cả token và open_id, ta gửi sang cho check_account_info
        if extracted_data['access_token'] and extracted_data['open_id']:
            print("\n[+] ĐÃ LẤY ĐỦ TOKEN & OPEN_ID TỪ RAM.")
            print("[+] Đang ném thẳng sang API /check_account_info...")
            try:
                resp = requests.post(API_URL, json={
                    "token": extracted_data['access_token'],
                    "open_id": extracted_data['open_id'],
                    "region": REGION
                }, timeout=5)
                
                print(f"[>] Trạng thái gửi: {resp.status_code}")
                # Log thử phản hồi từ task queue
                dataJSON = resp.json()
                print(f"[>] API Task ID: {dataJSON.get('task_id')}")
                print("[*] Bạn có thể kiểm tra log backend (app.py) để xem chi tiết account.")
            except Exception as e:
                print(f"[!] Lỗi khi gửi request: {e}")
            
            print("\n[*] Tiếp tục chờ lượt đăng nhập tiếp theo...")
            # Reset cho lượt bắt token tiếp theo
            extracted_data['access_token'] = None
            extracted_data['open_id'] = None

    elif message['type'] == 'error':
        print(f"[!] Frida Error: {message['stack']}")

# Mã Javascript độc lập bơm thẳng vào RAM của máy ảo/điện thoại
FRIDA_JS_SCRIPT = """
Java.perform(function() {
    // SharedPreferencesImpl$EditorImpl là class gốc lưu thiết lập trên phần lớn Android
    var Editor = Java.use('android.app.SharedPreferencesImpl$EditorImpl');
    
    // Móc (Hook) vào hàm putString(). Cứ mỗi khi game chuẩn bị ghi string xuống bộ nhớ, ta sẽ kiểm tra.
    Editor.putString.overload('java.lang.String', 'java.lang.String').implementation = function(key, value) {
        // Chỉ bám sát access_token và open_id
        if (key === 'access_token' || key === 'open_id') {
            send({ "key": key, "value": value });
        }
        
        // Vẫn phải trả về thực thi gốc để game không bị lỗi/nghi ngờ
        return this.putString(key, value);
    };

    console.log("[*] [Frida] Script đã được bơm (inject) thành công vào RAM của Game!");
    console.log("[*] [Frida] Đang trực chờ lúc vòng đời đăng nhập diễn ra...");
});
"""

def main():
    package_name = "com.dts.freefireth" # Có thể thay bằng com.dts.freefiremax nếu xài bản max
    
    print("[*] Đang tìm kiếm thiết bị Android (qua USB/ADB)...")
    try:
        device = frida.get_usb_device(timeout=5)
    except Exception as e:
        print("[!] Không tìm thấy thiết bị kết nối USB. Hãy chắc chắn bật Gỡ Lỗi USB và kết nối.")
        print(f"[Lỗi]: {e}")
        sys.exit(1)
        
    print(f"[+] Đã bắt tay bộ phận thiết bị: {device.name}")
    print(f"[*] Đang đính kèm (attach) vào luồng tiến trình (process): {package_name}...")
    
    try:
        session = device.attach(package_name)
    except frida.ProcessNotFoundError:
        print(f"[!] Tiến trình '{package_name}' hiện không hoạt động!")
        print("[Mẹo] Bật game Free Fire lên trước khi chạy tool này.")
        sys.exit(1)
        
    # Tạo luồng chứa mã script và load thẳng vào session đã attach
    script = session.create_script(FRIDA_JS_SCRIPT)
    script.on('message', on_message)
    script.load()
    
    print("\n--------------------------------------------------------------")
    print("[+] HOOK HOÀN TẤT, BẬT GAME VÀ ĐĂNG NHẬP")
    print("--------------------------------------------------------------")
    print("[*] Nhấn Ctrl+C để thoát...\n")
    
    # Để luồng python giữ sống mà theo dõi
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        print("[*] Đang gỡ kẹp Hook và thoát...")
        session.detach()
        sys.exit(0)

if __name__ == '__main__':
    main()
