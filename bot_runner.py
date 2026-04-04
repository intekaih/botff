import os
import sys
import time
import threading
import queue as queue_module
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(BASE_DIR, 'tools', 'bot')
DATA_DIR = os.path.join(BOT_DIR, 'data')

if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def read_tokens():
    _ensure_data_dir()
    token_file = os.path.join(DATA_DIR, 'access.txt')
    if not os.path.exists(token_file):
        return []
    with open(token_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def read_proxies():
    proxy_file = os.path.join(DATA_DIR, 'proxies.txt')
    if not os.path.exists(proxy_file):
        return []
    with open(proxy_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def read_like_log():
    log_file = os.path.join(DATA_DIR, 'like_log.txt')
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def get_stats():
    tokens = read_tokens()
    proxies = read_proxies()
    logs = read_like_log()

    total_ok = 0
    total_fail = 0
    total_runs = len(logs)

    for line in logs:
        try:
            ok_part = [p for p in line.split('|') if 'OK=' in p]
            fail_part = [p for p in line.split('|') if 'Fail=' in p]
            if ok_part:
                total_ok += int(ok_part[0].strip().split('=')[1])
            if fail_part:
                total_fail += int(fail_part[0].strip().split('=')[1])
        except Exception:
            pass

    return {
        'token_count': len(tokens),
        'proxy_count': len(proxies),
        'total_runs': total_runs,
        'total_ok': total_ok,
        'total_fail': total_fail,
    }


def run_like_bot(uid_list, region, num_threads, max_tokens, log_q):
    try:
        from like import like_profile, REGION_URLS
    except ImportError as e:
        log_q.put(f"[ERROR] Không import được like.py: {e}")
        return

    tokens = read_tokens()
    if not tokens:
        log_q.put("[ERROR] access.txt rỗng hoặc không tồn tại. Hãy tạo token trước!")
        return

    if max_tokens and max_tokens > 0:
        tokens = tokens[:max_tokens]

    proxies_list = []
    raw_proxies = read_proxies()
    for p in raw_proxies:
        if not p.startswith('http') and not p.startswith('socks'):
            p = f'http://{p}'
        proxies_list.append({'http': p, 'https': p})

    log_q.put(f"[*] Đã tải {len(tokens)} token")
    if proxies_list:
        log_q.put(f"[*] Sử dụng {len(proxies_list)} proxy (rotation)")
    else:
        log_q.put(f"[*] Không có proxy → dùng IP gốc")
    log_q.put(f"[*] Target UIDs: {', '.join(str(u) for u in uid_list)}")
    log_q.put(f"[*] Region: {region} | Luồng: {num_threads}")
    log_q.put("=" * 50)

    success_count = 0
    fail_count = 0
    lock = threading.Lock()

    import random

    def worker(idx, token, target_uid):
        nonlocal success_count, fail_count
        proxy = random.choice(proxies_list) if proxies_list else None
        try:
            result = like_profile(token.strip(), int(target_uid), region)
        except Exception as ex:
            result = {"success": False, "status": -1, "msg": str(ex)}

        ts = datetime.now().strftime("%H:%M:%S")
        token_short = token[:22] + "..."
        with lock:
            if result["success"]:
                success_count += 1
                log_q.put(f"[{ts}] ✅ #{idx:04d} | UID {target_uid} | LIKE OK | {token_short}")
            else:
                fail_count += 1
                msg = result.get("msg", "")[:38]
                log_q.put(f"[{ts}] ❌ #{idx:04d} | UID {target_uid} | {msg} | {token_short}")

    start_time = time.time()

    for uid in uid_list:
        log_q.put(f"\n>>> Đang buff UID: {uid} <<<")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(worker, idx + 1, token, uid)
                for idx, token in enumerate(tokens)
            ]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    pass

    elapsed = round(time.time() - start_time, 2)
    log_q.put("\n" + "=" * 50)
    log_q.put(f"✅ Like thành công : {success_count}")
    log_q.put(f"❌ Thất bại        : {fail_count}")
    log_q.put(f"⏱ Thời gian        : {elapsed}s")

    log_line = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"UID={','.join(str(u) for u in uid_list)} | Region={region} | "
        f"OK={success_count} | Fail={fail_count} | "
        f"Total={success_count + fail_count} | Time={elapsed}s\n"
    )
    _ensure_data_dir()
    with open(os.path.join(DATA_DIR, 'like_log.txt'), 'a', encoding='utf-8') as f:
        f.write(log_line)


def run_token_generator(num_accounts, num_threads, region, log_q):
    import io
    import contextlib

    log_q.put(f"[*] Bắt đầu tạo {num_accounts} tài khoản | Region: {region} | Luồng: {num_threads}")
    log_q.put("=" * 50)

    _ensure_data_dir()

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("reg", os.path.join(BOT_DIR, "reg.py"))
        reg = importlib.util.load_from_spec(spec) if False else None

        import reg as reg_mod
    except Exception as e:
        log_q.put(f"[ERROR] Không import được reg.py: {e}")
        return

    success = 0
    fail = 0
    lock = threading.Lock()
    file_lock = threading.Lock()

    def worker_task(thread_id):
        nonlocal success, fail
        try:
            res = reg_mod.create_acc(region)
            if res and "uid" in res and "password" in res:
                uid = res["uid"]
                password = res["password"]
                with file_lock:
                    with open(os.path.join(DATA_DIR, 'conbogay.txt'), 'a', encoding='utf-8') as f:
                        f.write(f"{uid}:{password}\n")
                access_token = res.get("jwt_token")
                if access_token:
                    with file_lock:
                        with open(os.path.join(DATA_DIR, 'access.txt'), 'a', encoding='utf-8') as f:
                            f.write(f"{access_token}\n")
                    with lock:
                        success += 1
                    log_q.put(f"[Luồng {thread_id}] ✅ Tạo thành công UID: {uid}")
                else:
                    with lock:
                        fail += 1
                    log_q.put(f"[Luồng {thread_id}] ⚠️ UID {uid} tạo xong nhưng không lấy được JWT")
            else:
                with lock:
                    fail += 1
                log_q.put(f"[Luồng {thread_id}] ❌ Không tạo được tài khoản")
        except Exception as e:
            with lock:
                fail += 1
            log_q.put(f"[Luồng {thread_id}] ❌ Lỗi: {str(e)[:80]}")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_task, i + 1) for i in range(num_accounts)]
        for future in futures:
            try:
                future.result()
            except Exception:
                pass

    log_q.put("\n" + "=" * 50)
    log_q.put(f"✅ Tạo thành công: {success} tài khoản")
    log_q.put(f"❌ Thất bại      : {fail} tài khoản")
    log_q.put(f"📁 Token lưu tại : data/access.txt")


def run_token_checker(num_threads, log_q):
    import base64
    import json as json_mod
    import requests

    log_q.put("[*] Bắt đầu kiểm tra token...")
    log_q.put("=" * 50)

    tokens = read_tokens()
    if not tokens:
        log_q.put("[ERROR] access.txt rỗng hoặc không tồn tại!")
        return

    log_q.put(f"[*] Tổng số token cần kiểm tra: {len(tokens)}")

    live_tokens = []
    dead_tokens = []
    lock = threading.Lock()

    def decode_jwt(token):
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return None
            b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            return json_mod.loads(base64.urlsafe_b64decode(b64).decode("utf-8"))
        except Exception:
            return None

    def check_one(idx, token):
        token = token.strip()
        payload = decode_jwt(token)
        uid = "UNKNOWN"
        if payload:
            uid = payload.get("external_id", "UNKNOWN")
            exp = payload.get("exp")
            if exp and datetime.now().timestamp() > exp:
                with lock:
                    dead_tokens.append(token)
                log_q.put(f"[{idx:04d}] ⚠️  UID {uid} → HẾT HẠN (local check)")
                return

        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI) GarenaMSDK/4.0.19P8",
            "Authorization": f"Bearer {token}",
        }
        url = f"https://account.garena.com/api/account/profile?account_id={uid}&session_key={token}"
        is_live = True
        try:
            res = requests.get(url, headers=headers, timeout=8)
            is_live = res.status_code != 401
        except Exception:
            is_live = True

        with lock:
            if is_live:
                live_tokens.append(token)
                log_q.put(f"[{idx:04d}] ✅ UID {uid} → CÒN SỐNG")
            else:
                dead_tokens.append(token)
                log_q.put(f"[{idx:04d}] ❌ UID {uid} → ĐÃ CHẾT")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(check_one, i + 1, t) for i, t in enumerate(tokens)]
        for future in futures:
            try:
                future.result()
            except Exception:
                pass

    _ensure_data_dir()
    live_file = os.path.join(DATA_DIR, 'access_live.txt')
    dead_file = os.path.join(DATA_DIR, 'access_die.txt')

    with open(live_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(live_tokens) + ('\n' if live_tokens else ''))
    with open(dead_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dead_tokens) + ('\n' if dead_tokens else ''))

    with open(os.path.join(DATA_DIR, 'access.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(live_tokens) + ('\n' if live_tokens else ''))

    log_q.put("\n" + "=" * 50)
    log_q.put(f"✅ Token còn sống : {len(live_tokens)}")
    log_q.put(f"❌ Token đã chết  : {len(dead_tokens)}")
    log_q.put(f"🔄 Đã cập nhật access.txt (chỉ giữ token sống)")
