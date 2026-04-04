from flask import Flask, render_template_string, jsonify
import os
import sys

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BOT FF - Auto Buff Like Free Fire</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #0d0d0d;
            color: #e0e0e0;
            font-family: 'Courier New', monospace;
            min-height: 100vh;
        }
        header {
            background: linear-gradient(135deg, #1a0000 0%, #3a0000 50%, #1a0000 100%);
            border-bottom: 2px solid #ff3300;
            padding: 20px;
            text-align: center;
        }
        header h1 {
            color: #ff3300;
            font-size: 2rem;
            letter-spacing: 4px;
            text-shadow: 0 0 20px #ff3300;
        }
        header p {
            color: #ff9966;
            margin-top: 8px;
            font-size: 0.9rem;
        }
        .container {
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
        }
        .card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-left: 4px solid #ff3300;
            border-radius: 6px;
            padding: 24px;
            margin-bottom: 24px;
        }
        .card h2 {
            color: #ff3300;
            font-size: 1.1rem;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .step {
            background: #111;
            border: 1px solid #2a2a2a;
            border-radius: 4px;
            padding: 16px;
            margin-bottom: 12px;
        }
        .step .label {
            color: #ff9966;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .step code {
            display: block;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 3px;
            padding: 10px 14px;
            color: #66ff66;
            font-size: 0.9rem;
            margin: 6px 0;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .step p {
            color: #aaa;
            font-size: 0.85rem;
            margin-top: 6px;
        }
        .badge {
            display: inline-block;
            background: #ff3300;
            color: white;
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 0.75rem;
            vertical-align: middle;
        }
        .regions {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        .region-tag {
            background: #2a0000;
            border: 1px solid #ff3300;
            color: #ff9966;
            border-radius: 3px;
            padding: 3px 10px;
            font-size: 0.8rem;
        }
        .note {
            background: #0d1a0d;
            border: 1px solid #1a4a1a;
            border-left: 4px solid #33cc33;
            border-radius: 4px;
            padding: 12px 16px;
            color: #66cc66;
            font-size: 0.85rem;
            margin-top: 12px;
        }
        .warn {
            background: #1a1100;
            border: 1px solid #4a3300;
            border-left: 4px solid #ffaa00;
            border-radius: 4px;
            padding: 12px 16px;
            color: #ffaa00;
            font-size: 0.85rem;
            margin-top: 12px;
        }
        footer {
            text-align: center;
            color: #555;
            font-size: 0.8rem;
            padding: 30px 0 20px;
            border-top: 1px solid #222;
        }
    </style>
</head>
<body>
    <header>
        <h1>&#128293; BOT FF</h1>
        <p>Auto Buff Like Free Fire &mdash; Garena Automation Toolkit</p>
    </header>

    <div class="container">
        <div class="card">
            <h2>&#9881; Setup &amp; Installation</h2>
            <div class="step">
                <div class="label">Install dependencies</div>
                <code>pip install requests pycryptodome colorama protobuf-decoder</code>
            </div>
        </div>

        <div class="card">
            <h2>&#128196; Workflow <span class="badge">Step 1 → Step 2</span></h2>
            <div class="step">
                <div class="label">Step 1 &mdash; Generate Tokens (reg.py)</div>
                <code>cd tools/bot
python reg.py</code>
                <p>Creates guest accounts &amp; saves tokens to <strong>data/access.txt</strong></p>
            </div>
            <div class="step">
                <div class="label">Step 2 &mdash; Buff Likes (like.py)</div>
                <code>cd tools/bot
python like.py</code>
                <p>Reads tokens from <strong>data/access.txt</strong>, sends Like requests to a target UID</p>
            </div>
            <div class="step">
                <div class="label">Optional &mdash; Level/Rank Bot (lvl.py)</div>
                <code>cd tools/level_bot
python lvl.py</code>
                <p>SOCKS5 proxy that automates match joining for XP/Rank grinding</p>
            </div>
        </div>

        <div class="card">
            <h2>&#127758; Supported Regions</h2>
            <div class="regions">
                <span class="region-tag">VN (Vietnam)</span>
                <span class="region-tag">IND (India)</span>
                <span class="region-tag">ID (Indonesia)</span>
                <span class="region-tag">BR (Brazil)</span>
                <span class="region-tag">ME (Middle East)</span>
                <span class="region-tag">TH (Thailand)</span>
                <span class="region-tag">BD (Bangladesh)</span>
                <span class="region-tag">PK (Pakistan)</span>
                <span class="region-tag">SG (Singapore)</span>
                <span class="region-tag">NA (North America)</span>
                <span class="region-tag">SAC (South America)</span>
                <span class="region-tag">EU (Europe)</span>
                <span class="region-tag">CIS (Russia/CIS)</span>
                <span class="region-tag">TW (Taiwan)</span>
            </div>
        </div>

        <div class="card">
            <h2>&#128161; Notes</h2>
            <div class="note">Each token can only like once per day (Garena server limit). Run reg.py first to generate enough tokens for more likes.</div>
            <div class="warn">This tool interacts with Garena's servers. Use responsibly and at your own risk. Misuse may result in account bans.</div>
        </div>
    </div>

    <footer>BOT FF &mdash; Auto Buff Like Free Fire &mdash; Running on Replit</footer>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
