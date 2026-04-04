import os
import sys
import json
import time
import uuid
import threading
import socket
import subprocess
import queue as queue_module
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, stream_with_context

from bot_runner import (
    get_stats, read_tokens, read_real_tokens, read_proxies, read_like_log,
    run_like_bot, run_token_generator, run_token_checker,
    DATA_DIR, BASE_DIR
)

sys.path.insert(0, os.path.join(BASE_DIR, 'tools', 'level_bot'))
from lvl import Proxy as LvlProxy

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

SCHEDULER_CONFIG_FILE = os.path.join(BASE_DIR, 'scheduler_config.json')
MITM_IDS_FILE = os.path.join(BASE_DIR, 'tools', 'mitm_scripts', 'extracted_ids.txt')
MITM_SCRIPT = os.path.join(BASE_DIR, 'tools', 'mitm_scripts', 'auto_extract_mitm.py')
mitm_process = None
mitm_lock = threading.Lock()
PROXY_FILE = os.path.join(DATA_DIR, 'proxies.txt')

REGION_URLS = {
    "VN": "https://clientbp.ggblueshark.com/",
    "IND": "https://client.ind.freefiremobile.com/",
    "ID": "https://clientbp.ggblueshark.com/",
    "BR": "https://client.us.freefiremobile.com/",
    "ME": "https://clientbp.common.ggbluefox.com/",
    "TH": "https://clientbp.common.ggbluefox.com/",
    "BD": "https://clientbp.ggblueshark.com/",
    "PK": "https://clientbp.ggblueshark.com/",
    "SG": "https://clientbp.ggblueshark.com/",
    "NA": "https://client.us.freefiremobile.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "EU": "https://clientbp.ggblueshark.com/",
    "CIS": "https://clientbp.ggblueshark.com/",
    "TW": "https://clientbp.ggblueshark.com/",
}

task_queues = {}
task_status = {}
task_lock = threading.Lock()

scheduler_instance = None
scheduler_job = None

# LVL Bot state
lvl_proxy_instance = None
lvl_proxy_thread = None
lvl_proxy_port = 7777
lvl_proxy_lock = threading.Lock()


def _load_scheduler_config():
    if os.path.exists(SCHEDULER_CONFIG_FILE):
        try:
            with open(SCHEDULER_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"enabled": False, "time": "06:00", "uid": "", "region": "VN", "threads": 10, "max_tokens": 0}


def _save_scheduler_config(cfg):
    with open(SCHEDULER_CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def _create_task():
    task_id = str(uuid.uuid4())[:8]
    q = queue_module.Queue()
    with task_lock:
        task_queues[task_id] = q
        task_status[task_id] = 'running'
    return task_id, q


def _finish_task(task_id, q, sentinel='[DONE]'):
    q.put(sentinel)
    with task_lock:
        task_status[task_id] = 'done'


def _run_in_background(fn, task_id, log_q, *args):
    def wrapper():
        try:
            fn(*args, log_q)
        except Exception as e:
            log_q.put(f"[ERROR] {e}")
        finally:
            _finish_task(task_id, log_q)
    t = threading.Thread(target=wrapper, daemon=True)
    t.start()


def _sse_stream(task_id):
    def generate():
        q = task_queues.get(task_id)
        if not q:
            yield "data: [ERROR] Task không tồn tại\n\n"
            yield "data: [DONE]\n\n"
            return
        while True:
            try:
                msg = q.get(timeout=30)
                safe = msg.replace('\n', '<br>')
                yield f"data: {safe}\n\n"
                if msg == '[DONE]':
                    break
            except queue_module.Empty:
                yield "data: [PING]\n\n"
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


def _init_scheduler():
    global scheduler_instance, scheduler_job
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler_instance = BackgroundScheduler()
        scheduler_instance.start()
        cfg = _load_scheduler_config()
        if cfg.get('enabled') and cfg.get('uid') and cfg.get('time'):
            _schedule_job(cfg)
    except Exception as e:
        print(f"[Scheduler] Lỗi khởi động: {e}")


def _schedule_job(cfg):
    global scheduler_job
    if not scheduler_instance:
        return
    if scheduler_job:
        try:
            scheduler_job.remove()
        except Exception:
            pass
    h, m = cfg['time'].split(':')
    uid_list = [u.strip() for u in cfg['uid'].split(',') if u.strip()]

    def scheduled_like():
        task_id, log_q = _create_task()
        _run_in_background(run_like_bot, task_id, log_q,
                           uid_list, cfg['region'],
                           int(cfg.get('threads', 10)),
                           int(cfg.get('max_tokens', 0)))

    scheduler_job = scheduler_instance.add_job(
        scheduled_like, 'cron', hour=int(h), minute=int(m)
    )


@app.route('/')
def dashboard():
    stats = get_stats()
    cfg = _load_scheduler_config()
    return render_template('dashboard.html', stats=stats, scheduler=cfg)


@app.route('/like')
def like_page():
    return render_template('like.html', regions=list(REGION_URLS.keys()))


@app.route('/api/like/start', methods=['POST'])
def api_like_start():
    data = request.json or {}
    uid_raw = data.get('uids', '')
    uid_list = [u.strip() for u in uid_raw.replace('\n', ',').split(',') if u.strip()]
    if not uid_list:
        return jsonify({'error': 'Chưa nhập UID'}), 400
    for uid in uid_list:
        if not uid.isdigit():
            return jsonify({'error': f'UID không hợp lệ: {uid}'}), 400

    region = data.get('region', 'VN').upper()
    num_threads = max(1, min(int(data.get('threads', 10)), 50))
    max_tokens = max(0, int(data.get('max_tokens', 0)))

    task_id, log_q = _create_task()
    _run_in_background(run_like_bot, task_id, log_q, uid_list, region, num_threads, max_tokens)
    return jsonify({'task_id': task_id})


_GOOGLE_CONFIG_FILE  = os.path.join(BASE_DIR, '.local', 'google_config.json')

def _load_google_config():
    cid  = os.environ.get('GOOGLE_CLIENT_ID', '')
    csec = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    if not cid and os.path.exists(_GOOGLE_CONFIG_FILE):
        try:
            cfg  = json.load(open(_GOOGLE_CONFIG_FILE))
            cid  = cfg.get('client_id', '')
            csec = cfg.get('client_secret', '')
        except Exception:
            pass
    return cid, csec

GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET = _load_google_config()

_google_pending = {}   # state → {region, ts}

def _google_redirect_uri():
    # Ưu tiên: X-Forwarded-Host (Replit proxy) → REPLIT_DEV_DOMAIN → request.host
    fwd = request.headers.get('X-Forwarded-Host') or request.headers.get('X-Real-Host')
    dev = os.environ.get('REPLIT_DEV_DOMAIN', '')
    host = fwd or dev or request.host
    return f"https://{host}/auth/google/callback"


@app.route('/api/google/set_credentials', methods=['POST'])
def api_google_set_credentials():
    global GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    data = request.json or {}
    cid  = data.get('client_id', '').strip()
    csec = data.get('client_secret', '').strip()
    if not cid or not csec:
        return jsonify({'ok': False, 'error': 'Thiếu client_id hoặc client_secret'})
    os.makedirs(os.path.dirname(_GOOGLE_CONFIG_FILE), exist_ok=True)
    with open(_GOOGLE_CONFIG_FILE, 'w') as f:
        json.dump({'client_id': cid, 'client_secret': csec}, f)
    os.environ['GOOGLE_CLIENT_ID']     = cid
    os.environ['GOOGLE_CLIENT_SECRET'] = csec
    GOOGLE_CLIENT_ID     = cid
    GOOGLE_CLIENT_SECRET = csec
    return jsonify({'ok': True})


@app.route('/auth/google/start')
def auth_google_start():
    redir = _google_redirect_uri()
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        # Tạo danh sách tất cả redirect URIs cần đăng ký
        uris = [redir]
        prod_domain = "botffkaih.replit.app"
        prod_uri = f"https://{prod_domain}/auth/google/callback"
        if prod_uri != redir:
            uris.append(prod_uri)
        return render_template('google_setup.html', redirect_uri=redir,
                               all_uris=uris), 200

    region = request.args.get('region', 'VN').upper()
    state  = str(uuid.uuid4())
    _google_pending[state] = {'region': region, 'ts': time.time()}

    sys.path.insert(0, os.path.join(BASE_DIR, 'tools', 'bot'))
    from google_login import build_auth_url
    url = build_auth_url(GOOGLE_CLIENT_ID, _google_redirect_uri(), state)
    from flask import redirect as flask_redirect
    return flask_redirect(url)


@app.route('/auth/google/callback')
def auth_google_callback():
    from flask import redirect as flask_redirect
    code  = request.args.get('code')
    state = request.args.get('state', '')
    error = request.args.get('error')

    if error:
        return render_template('google_result.html',
                               success=False, msg=f"Google từ chối: {error}")

    meta = _google_pending.pop(state, {})
    region = meta.get('region', 'VN')

    if not code:
        return render_template('google_result.html',
                               success=False, msg="Không nhận được authorization code")

    _bot_dir = os.path.join(BASE_DIR, 'tools', 'bot')
    if _bot_dir not in sys.path:
        sys.path.insert(0, _bot_dir)
    from google_login import exchange_code, garena_google_exchange, get_google_userinfo
    from web_token_login import major_login

    # 1. Đổi code → Google tokens
    google_tokens = exchange_code(code, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
                                  _google_redirect_uri())
    if not google_tokens:
        return render_template('google_result.html',
                               success=False, msg="Không lấy được Google token")

    id_token     = google_tokens.get('id_token', '')
    access_token = google_tokens.get('access_token', '')

    # Lấy thông tin user
    userinfo   = get_google_userinfo(access_token) if access_token else {}
    email      = userinfo.get('email', 'unknown')
    google_sub = userinfo.get('sub', '')

    task_id, log_q = _create_task()

    def _run():
        log_q.put(f"[*] Email Google: {email}")
        log_q.put(f"[*] Google sub (user_id): {google_sub}")
        log_q.put(f"[*] Region: {region}")
        log_q.put(f"[*] id_token length: {len(id_token)}")

        log_q.put("\n[Bước 1] Đổi Google token → Garena access_token...")
        garena_data = garena_google_exchange(
            id_token,
            google_access_token=access_token,
            google_sub=google_sub,
            log_q=log_q,
        )

        if not garena_data:
            log_q.put("\n❌ Garena từ chối Google token. Xem log để biết chi tiết.")
            log_q.put('[DONE]')
            return

        ga_access = garena_data['access_token']
        open_id   = garena_data['open_id']

        # 3. MajorLogin → game JWT
        log_q.put(f"\n[Bước 2] Gọi MajorLogin (region={region})...")
        jwt = major_login(ga_access, open_id, region, log_q=log_q)

        if jwt:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, 'access_real.txt'), 'a') as f:
                f.write(jwt + '\n')
            log_q.put(f"\n✅ Đã lưu JWT vào access_real.txt")
            log_q.put(f"📋 JWT: {jwt[:60]}...")
        else:
            log_q.put("\n❌ MajorLogin thất bại")

        log_q.put('[DONE]')

    threading.Thread(target=_run, daemon=True).start()
    return render_template('google_result.html',
                           success=True, task_id=task_id, email=email)


@app.route('/api/bookmarklet')
def api_bookmarklet():
    region = request.args.get('region', 'VN').upper()
    server = request.host_url.rstrip('/')
    js = f"""javascript:(function(){{
var r='{region}',s='',o='';
document.cookie.split(';').forEach(function(c){{
  var p=c.trim().split('='),k=p[0],v=decodeURIComponent(p.slice(1).join('='));
  if(k==='session_key')s=v;
  if(k==='open_id')o=v;
}});
if(!s||!o){{alert('[BOT FF] Không tìm thấy session_key/open_id.\\nHãy đăng nhập Garena rồi thử lại!');return;}}
alert('[BOT FF] Đang gửi token...\\nRegion: '+r+'\\nOpen ID: '+o);
fetch('{server}/api/tokens/web_login',{{
  method:'POST',
  headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{session_key:s,open_id:o,region:r}})
}}).then(function(r){{return r.json();}}).then(function(d){{
  if(d.task_id)alert('[BOT FF] ✅ Đang xử lý! Mở dashboard để xem log.');
  else alert('[BOT FF] ❌ Lỗi: '+JSON.stringify(d));
}}).catch(function(e){{alert('[BOT FF] Lỗi kết nối: '+e);}});
}})();"""
    return Response(js, mimetype='application/javascript')


@app.route('/tokens')
def tokens_page():
    tokens = read_tokens()
    real_tokens = read_real_tokens()
    return render_template(
        'tokens.html',
        token_count=len(tokens),
        token_real_count=len(real_tokens),
        regions=list(REGION_URLS.keys()),
        google_ready=bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
    )


@app.route('/api/tokens/web_login', methods=['POST', 'OPTIONS'])
def api_tokens_web_login():
    if request.method == 'OPTIONS':
        return '', 204
    data = request.json or {}
    session_key = (data.get('session_key') or '').strip()
    open_id = (data.get('open_id') or '').strip()
    region = (data.get('region') or 'VN').upper()
    direct = bool(data.get('direct', False))

    if not session_key or not open_id:
        return jsonify({'error': 'Thiếu session_key hoặc open_id'}), 400

    task_id, log_q = _create_task()

    _bot_dir = os.path.join(BASE_DIR, 'tools', 'bot')
    if _bot_dir not in sys.path:
        sys.path.insert(0, _bot_dir)
    from web_token_login import run_web_login

    def _run():
        run_web_login(session_key, open_id, region, DATA_DIR, log_q, direct=direct)
        log_q.put('[DONE]')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'task_id': task_id})


@app.route('/api/tokens/direct_garena', methods=['POST'])
def api_tokens_direct_garena():
    """Nhận Garena access_token + open_id → gọi MajorLogin → lưu JWT vào access_real.txt"""
    data = request.json or {}
    access_token = (data.get('access_token') or '').strip()
    open_id      = (data.get('open_id') or '').strip()
    region       = (data.get('region') or 'VN').upper()

    if not access_token or not open_id:
        return jsonify({'error': 'Thiếu access_token hoặc open_id'}), 400

    task_id, log_q = _create_task()

    _bot_dir = os.path.join(BASE_DIR, 'tools', 'bot')
    if _bot_dir not in sys.path:
        sys.path.insert(0, _bot_dir)

    def _run():
        try:
            from web_token_login import major_login
            log_q.put(f'[*] Bắt đầu MajorLogin cho open_id={open_id} region={region}')
            log_q.put(f'[*] access_token length: {len(access_token)}')
            result = major_login(access_token, open_id, region, log_q=log_q)
            if result:
                # Lưu vào access_real.txt
                real_file = os.path.join(DATA_DIR, 'access_real.txt')
                with open(real_file, 'a', encoding='utf-8') as f:
                    f.write(result + '\n')
                log_q.put(f'\n✅ Thành công! JWT đã lưu vào access_real.txt')
                log_q.put(f'   JWT: {result[:60]}...')
            else:
                log_q.put('\n❌ MajorLogin thất bại — kiểm tra access_token có còn hiệu lực không.')
        except Exception as e:
            import traceback
            log_q.put(f'[!] Lỗi: {e}')
            log_q.put(traceback.format_exc())
        finally:
            log_q.put('[DONE]')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'task_id': task_id})


@app.route('/api/tokens/generate', methods=['POST'])
def api_tokens_generate():
    data = request.json or {}
    num_accounts = max(1, min(int(data.get('num_accounts', 10)), 200))
    num_threads = max(1, min(int(data.get('threads', 5)), 20))
    region = data.get('region', 'VN').upper()

    task_id, log_q = _create_task()
    _run_in_background(run_token_generator, task_id, log_q, num_accounts, num_threads, region)
    return jsonify({'task_id': task_id})


@app.route('/api/tokens/check', methods=['POST'])
def api_tokens_check():
    data = request.json or {}
    num_threads = max(1, min(int(data.get('threads', 10)), 30))

    task_id, log_q = _create_task()
    _run_in_background(run_token_checker, task_id, log_q, num_threads)
    return jsonify({'task_id': task_id})


@app.route('/api/task/<task_id>/stream')
def api_task_stream(task_id):
    return _sse_stream(task_id)


@app.route('/proxies')
def proxies_page():
    content = ''
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    return render_template('proxies.html', proxy_content=content)


@app.route('/api/proxies/save', methods=['POST'])
def api_proxies_save():
    data = request.json or {}
    content = data.get('content', '')
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROXY_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    lines = [l for l in content.split('\n') if l.strip()]
    return jsonify({'success': True, 'count': len(lines)})


@app.route('/scheduler')
def scheduler_page():
    cfg = _load_scheduler_config()
    next_run = None
    if scheduler_job:
        try:
            next_run = scheduler_job.next_run_time.strftime('%Y-%m-%d %H:%M') if scheduler_job.next_run_time else None
        except Exception:
            pass
    return render_template('scheduler.html', cfg=cfg, next_run=next_run, regions=list(REGION_URLS.keys()))


@app.route('/api/scheduler/save', methods=['POST'])
def api_scheduler_save():
    data = request.json or {}
    cfg = {
        'enabled': bool(data.get('enabled', False)),
        'time': data.get('time', '06:00'),
        'uid': data.get('uid', ''),
        'region': data.get('region', 'VN').upper(),
        'threads': max(1, min(int(data.get('threads', 10)), 50)),
        'max_tokens': max(0, int(data.get('max_tokens', 0))),
    }
    _save_scheduler_config(cfg)
    if cfg['enabled'] and cfg['uid']:
        _schedule_job(cfg)
    elif scheduler_job:
        try:
            scheduler_job.remove()
        except Exception:
            pass
    return jsonify({'success': True, 'config': cfg})


@app.route('/stats')
def stats_page():
    logs = read_like_log()
    parsed = []
    for line in logs:
        try:
            parts = {p.split('=')[0].strip(): p.split('=')[1].strip()
                     for p in line.replace('[', '').replace(']', '').split('|')
                     if '=' in p}
            date_part = line[1:20] if line.startswith('[') else ''
            parsed.append({
                'date': date_part,
                'uid': parts.get('UID', '-'),
                'region': parts.get('Region', '-'),
                'ok': parts.get('OK', '0'),
                'fail': parts.get('Fail', '0'),
                'total': parts.get('Total', '0'),
                'time': parts.get('Time', '-'),
            })
        except Exception:
            pass
    parsed.reverse()
    stats = get_stats()
    return render_template('stats.html', logs=parsed, stats=stats)


@app.route('/mitm')
def mitm_page():
    content = ''
    if os.path.exists(MITM_IDS_FILE):
        with open(MITM_IDS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
    return render_template('mitm.html', content=content)


@app.route('/api/mitm/status')
def api_mitm_status():
    global mitm_process
    with mitm_lock:
        running = mitm_process is not None and mitm_process.poll() is None
    return jsonify({'running': running})


@app.route('/api/mitm/start', methods=['POST'])
def api_mitm_start():
    global mitm_process
    with mitm_lock:
        if mitm_process is not None and mitm_process.poll() is None:
            return jsonify({'success': False, 'msg': 'mitmproxy đang chạy rồi!'})
        try:
            log_file = open(os.path.join(BASE_DIR, 'mitm.log'), 'a')
            mitm_process = subprocess.Popen(
                ['mitmdump', '-s', MITM_SCRIPT, '-s', 'dump.py', '--listen-port', '8080',
                 '--set', 'ssl_insecure=true', '--set', 'block_global=false'],
                stdout=log_file, stderr=subprocess.STDOUT,
                cwd=os.path.join(BASE_DIR, 'tools', 'mitm_scripts')
            )
            return jsonify({'success': True, 'msg': 'mitmproxy đã khởi động (port 8080)'})
        except Exception as e:
            return jsonify({'success': False, 'msg': str(e)})


@app.route('/api/mitm/stop', methods=['POST'])
def api_mitm_stop():
    global mitm_process
    with mitm_lock:
        if mitm_process is None or mitm_process.poll() is not None:
            return jsonify({'success': False, 'msg': 'mitmproxy chưa chạy'})
        mitm_process.terminate()
        try:
            mitm_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mitm_process.kill()
        mitm_process = None
    return jsonify({'success': True, 'msg': 'Đã dừng mitmproxy'})


@app.route('/api/mitm/save', methods=['POST'])
def api_mitm_save():
    data = request.json or {}
    content = data.get('content', '')
    os.makedirs(os.path.dirname(MITM_IDS_FILE), exist_ok=True)
    with open(MITM_IDS_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    lines = [l for l in content.split('\n') if l.strip()]
    return jsonify({'success': True, 'count': len(lines)})


@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ── LVL BOT ────────────────────────────────────────────────────────────────

def _lvl_is_running():
    """Kiểm tra xem SOCKS5 proxy có đang chạy không."""
    global lvl_proxy_thread
    return lvl_proxy_thread is not None and lvl_proxy_thread.is_alive()


def _lvl_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


@app.route('/lvl')
def lvl_page():
    running = _lvl_is_running()
    return render_template('lvl.html',
                           running=running,
                           port=lvl_proxy_port,
                           username=lvl_proxy_instance.username if lvl_proxy_instance else 'kaih',
                           password=lvl_proxy_instance.password if lvl_proxy_instance else '123')


@app.route('/api/lvl/start', methods=['POST'])
def api_lvl_start():
    global lvl_proxy_instance, lvl_proxy_thread, lvl_proxy_port
    with lvl_proxy_lock:
        if _lvl_is_running():
            return jsonify({'success': False, 'message': 'Proxy đã đang chạy'})

        data = request.json or {}
        port = int(data.get('port', 7777))

        if _lvl_port_in_use(port):
            return jsonify({'success': False, 'message': f'Port {port} đã được dùng bởi tiến trình khác'})

        lvl_proxy_port = port
        lvl_proxy_instance = LvlProxy()

        def run_proxy():
            try:
                lvl_proxy_instance.run(host='0.0.0.0', port=port)
            except Exception as e:
                print(f'[LVL BOT] Lỗi: {e}')

        lvl_proxy_thread = threading.Thread(target=run_proxy, daemon=True)
        lvl_proxy_thread.start()

        time.sleep(0.8)
        if _lvl_is_running():
            return jsonify({'success': True, 'message': f'SOCKS5 Proxy đã khởi động tại port {port}',
                            'port': port, 'username': lvl_proxy_instance.username,
                            'password': lvl_proxy_instance.password})
        else:
            return jsonify({'success': False, 'message': 'Không thể khởi động proxy'})


@app.route('/api/lvl/stop', methods=['POST'])
def api_lvl_stop():
    global lvl_proxy_instance, lvl_proxy_thread
    with lvl_proxy_lock:
        if not _lvl_is_running():
            return jsonify({'success': False, 'message': 'Proxy chưa chạy'})
        lvl_proxy_thread = None
        lvl_proxy_instance = None
        return jsonify({'success': True, 'message': 'Đã dừng (thread daemon sẽ tự thoát)'})


@app.route('/api/lvl/status')
def api_lvl_status():
    running = _lvl_is_running()
    return jsonify({
        'running': running,
        'port': lvl_proxy_port if running else None,
        'username': lvl_proxy_instance.username if lvl_proxy_instance else 'kaih',
        'password': lvl_proxy_instance.password if lvl_proxy_instance else '123',
    })


if __name__ == '__main__':
    _init_scheduler()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
