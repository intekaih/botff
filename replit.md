# BOT FF – Auto Buff Like Free Fire v2.0

## Tổng quan
Bộ công cụ tự động hóa Garena Free Fire với giao diện web đầy đủ. Bao gồm: tạo token hàng loạt, buff like profile, kiểm tra token, quản lý proxy, lên lịch chạy tự động, thống kê và MITM Mod.

## Cấu trúc dự án
- `app.py` — Flask web app (port 5000), điều phối toàn bộ routes và API
- `bot_runner.py` — Logic chạy bot, capture log realtime, đọc/ghi data
- `templates/` — Giao diện web (Jinja2 templates)
  - `base.html` — Layout chung với sidebar
  - `dashboard.html` — Tổng quan, thống kê, thao tác nhanh
  - `like.html` — Buff Like với log realtime (SSE)
  - `tokens.html` — Tạo token (reg.py) & kiểm tra token
  - `proxies.html` — Quản lý danh sách proxy
  - `scheduler.html` — Lên lịch buff like hàng ngày
  - `stats.html` — Thống kê lịch sử chạy
  - `mitm.html` — Quản lý extracted_ids.txt cho MITM mod
- `tools/bot/` — Scripts gốc (reg.py, like.py, token_checker.py, get_info.py, Get_token.py)
- `tools/level_bot/lvl.py` — SOCKS5 proxy level bot
- `tools/mitm_scripts/` — dump.py, auto_extract_mitm.py
- `mods/` — Xmodz mod archives
- `scheduler_config.json` — Lưu cấu hình lên lịch
- `requirements.txt` — Python dependencies

## Dependencies
- `flask` — Web framework
- `apscheduler` — Scheduler hàng ngày
- `requests` — HTTP requests
- `pycryptodome` — AES encryption cho Garena protocol
- `colorama` — Terminal colors
- `protobuf-decoder` — Decode Garena protobuf
- `gunicorn` — Production WSGI server

## Các chức năng web
1. **Dashboard** — Thống kê token, like, proxy, trạng thái scheduler
2. **Buff Like** — Nhập UID (nhiều UID), chọn region, số luồng → log realtime qua SSE
3. **Quản lý Token** — Tạo tài khoản mới (reg.py) + kiểm tra/lọc token hết hạn
4. **Proxy Manager** — Thêm/xoá/lưu danh sách proxy (HTTP/SOCKS)
5. **Lên Lịch** — Cài giờ chạy buff like tự động hàng ngày
6. **Thống Kê** — Bảng lịch sử, tỷ lệ thành công từ like_log.txt
7. **MITM Mod** — Quản lý extracted_ids.txt cho mod skin/emote

## API Endpoints
- `POST /api/like/start` — Bắt đầu buff like, trả về task_id
- `POST /api/tokens/generate` — Tạo token mới
- `POST /api/tokens/check` — Kiểm tra & lọc token
- `GET /api/task/<id>/stream` — SSE stream log realtime
- `GET/POST /api/proxies/save` — Lưu proxy list
- `POST /api/scheduler/save` — Lưu cấu hình scheduler
- `POST /api/mitm/save` — Lưu extracted_ids.txt
- `GET /api/stats` — Stats JSON (live polling)

## Workflow
- **Start application**: `python app.py` on port 5000 (webview)
- **Deployment**: `gunicorn --bind=0.0.0.0:5000 --reuse-port app:app`
