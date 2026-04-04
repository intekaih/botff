import os
import sys
import subprocess
import shutil

def run_adb(cmd):
    result = subprocess.run(f"adb {cmd}", shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def install_deps_if_needed():
    try:
        from cryptography import x509
        import hashlib
    except ImportError:
        print("[*] Phát hiện thiếu thư viện mã hóa, đang tự động cài đặt cryptography...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])

def get_cert_hash_old(cert_path):
    from cryptography import x509
    import hashlib
    with open(cert_path, 'rb') as f:
        cert_data = f.read()
        
    cert = x509.load_pem_x509_certificate(cert_data)
    # Lấy định dạng DER của Subject (Thông tin chứng chỉ)
    subject_der = cert.subject.public_bytes()
    
    # Hàm băm MD5 lấy 4 bytes đầu tiên và đảo ngược Little-Endian (chuẩn subject_hash_old của OpenSSL)
    m = hashlib.md5(subject_der).digest()
    hash_hex = f"{m[3]:02x}{m[2]:02x}{m[1]:02x}{m[0]:02x}"
    return hash_hex

def main():
    print("---------------------------------------------------------")
    print(" CÔNG CỤ TỰ ĐỘNG CHÈN CHỨNG CHỈ MITMPROXY VÀO LÕI ANDROID")
    print("---------------------------------------------------------")
    
    install_deps_if_needed()
    
    # 1. Tìm tệp tin chứng chỉ ở máy Windows của user
    user_profile = os.environ.get('USERPROFILE', '')
    cert_folder = os.path.join(user_profile, '.mitmproxy')
    cert_file = os.path.join(cert_folder, 'mitmproxy-ca-cert.pem')
    
    if not os.path.exists(cert_file):
        cert_file = os.path.join(cert_folder, 'mitmproxy-ca-cert.cer')
        if not os.path.exists(cert_file):
            print(f"[!] Không tìm thấy chứng chỉ ở {cert_folder}.")
            print("[!] Hãy chắc chắn bạn đã chạy 'mitmdump' ít nhất 1 lần trên máy tính này!")
            sys.exit(1)
            
    print(f"[+] Tìm thấy chứng chỉ MitmProxy tại: {cert_file}")
    
    # 2. Xây dựng Hash MD5
    try:
        hash_str = get_cert_hash_old(cert_file)
        hash_file_name = f"{hash_str}.0"
        print(f"[+] Đã giải mã thành công Hash của chứng chỉ: {hash_file_name}")
    except Exception as e:
        print(f"[!] Gặp lỗi khi tính Hash: {e}")
        sys.exit(1)
        
    # Chuẩn bị file đẩy qua ADB
    local_tmp_cert = os.path.join(cert_folder, hash_file_name)
    shutil.copy2(cert_file, local_tmp_cert)
    
    # 3. Kết nối thiết bị qua ADB
    print()
    print("[*] Đang kết nối với thiết bị và lấy quyền ROOT...")
    run_adb("root") 
    import time; time.sleep(1)
    
    # Kiểm tra kẹp ADB
    code, out, err = run_adb("devices")
    if "device" not in out:
         print("[!] Không tìm thấy thiết bị kết nối. Vui lòng kiểm tra USB Debugging.")
         sys.exit(1)
         
    # Đẩy chứng chỉ vào thư mục tạm của hệ thống
    print(f"[*] Đẩy file '{hash_file_name}' vào mục Tạm của Android (/data/local/tmp/)...")
    run_adb(f"push \"{local_tmp_cert}\" /data/local/tmp/{hash_file_name}")
    
    # 4. Kỹ thuật đưa vào Hệ Thống bằng OverlayFS (Không sợ bị lỗi System Read-Only của Android 10/11/12/13)
    print("[*] Đang tiến hành tiêm mã chứng chỉ thẳng vào phân vùng Lõi của Android...")
    
    inject_script = f"""#!/system/bin/sh
# 1. Tạo một thư mục mô phỏng tạm thời trên data
mkdir -p /data/local/tmp/cacerts-overlay
rm -f /data/local/tmp/cacerts-overlay/*

# 2. Chép toàn bộ chứng chỉ gốc từ ROM sang để không hỏng máy
cp -r /system/etc/security/cacerts/* /data/local/tmp/cacerts-overlay/

# 3. Ghép chứng chỉ mitmproxy mới vào chung
cp /data/local/tmp/{hash_file_name} /data/local/tmp/cacerts-overlay/

# 4. Cấp quyền chuẩn Android (644 và sở hữu root)
chown root:root /data/local/tmp/cacerts-overlay/*
chmod 644 /data/local/tmp/cacerts-overlay/*
chcon u:object_r:system_file:s0 /data/local/tmp/cacerts-overlay/*

# 5. Phủ đè chớp nhoáng (Tricks bypass Read-Only System file)
mount -t tmpfs tmpfs /system/etc/security/cacerts
cp -r /data/local/tmp/cacerts-overlay/* /system/etc/security/cacerts/
chmod 644 /system/etc/security/cacerts/*
chown root:root /system/etc/security/cacerts/*
chcon u:object_r:system_file:s0 /system/etc/security/cacerts/*

# Dọn dẹp
rm -rf /data/local/tmp/cacerts-overlay
rm -f /data/local/tmp/{hash_file_name}
rm -f /data/local/tmp/inject_script.sh
"""
    
    with open("inject_script.sh", "w", encoding="utf-8") as f:
        f.write(inject_script)

    # Đẩy script vào thư mục tmp
    run_adb("push inject_script.sh /data/local/tmp/inject_script.sh")
    
    # Thực thi script Inject trên root
    res_code, res_out, res_err = run_adb('shell "su -c \'sh /data/local/tmp/inject_script.sh\'"')
    
    # Xoa file tạm trên PC
    if os.path.exists("inject_script.sh"):
        os.remove("inject_script.sh")
    
    print("\n---------------------------------------------------------")
    if res_err and 'error' in res_err.lower():
        print(f"[!] Cảnh báo trong quá trình đưa vào: {res_err}")
    else:
         print(f"[+] THÀNH CÔNG! Chứng chỉ Mitmproxy (Hash: {hash_str}) đã được ăn sâu vào lõi Android.")
         print("[+] Bạn có thể vào (Cài đặt Điện Thoại -> Bảo mật -> Chứng chỉ Tin Cậy -> Sang mục Hệ Thống) để tìm chứng chỉ Mitmproxy.")
         
    print("---------------------------------------------------------")
    print("✅ BƯỚC TIẾP THEO DÀNH CHO BẠN:")
    print("1. Hãy mở kết nối Wifi trên điện thoại -> Chọn Sửa đổi mạng -> Chọn Tùy chọn nâng cao proxy.")
    print("2. Đặt IP theo IP của máy tính (thường là 192.168.1.xxx) và Cổng là 8080.")
    print("3. Bật 'mitmdump' hoặc chạy Backend (app.py) trên PC chứa công cụ mạng ngầm.")
    print("4. Vào lại Game Free Fire đăng nhập, máy chủ sẽ hoàn toàn bị đánh lừa mạng!\n")

if __name__ == '__main__':
    main()
