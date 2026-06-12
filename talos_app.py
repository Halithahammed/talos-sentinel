import os
import time
import sqlite3
import threading
import ctypes
from datetime import datetime
import psutil
import pyautogui
import webview

import win32gui
import win32process

# --- HIGH-DPI SCALING FIX FOR WINDOWS ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- CONFIGURATION ---
LOG_DIR = os.path.abspath("talos_logs")
DB_PATH = os.path.join(LOG_DIR, "talos_events.db")
os.makedirs(LOG_DIR, exist_ok=True)

# Stripped out 'cmd.exe', 'powershell', etc. so it only fires on true issues:
ANOMALY_KEYWORDS = [
    "error", "failed", "denied", "exception", "not found", 
    "crash", "warning", "malware", "suspicious", "task manager"
]

ENGINE_ARMED = False

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            window_title TEXT,
            process_name TEXT,
            screenshot_file TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_active_window_details():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "", ""
        window_title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return window_title, proc.name()
    except Exception:
        return "", ""

# --- BACKGROUND MONITOR ENGINE ---
def talos_stealth_loop():
    global ENGINE_ARMED
    init_db()
    last_logged_window = ""
    
    while True:
        try:
            if ENGINE_ARMED:
                win_title, win_proc = get_active_window_details()
                win_title_lower = win_title.lower()

                # Bypass tracking when inside development environments
                if "visual studio code" in win_title_lower or "vscode" in win_title_lower:
                    time.sleep(0.8)
                    continue

                if win_title != last_logged_window:
                    is_anomaly = any(keyword in win_title_lower for keyword in ANOMALY_KEYWORDS)
                    
                    if is_anomaly:
                        last_logged_window = win_title
                        
                        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                        ss_filename = f"stealth_{timestamp_str}.png"
                        ss_path = os.path.join(LOG_DIR, ss_filename)
                        
                        # Take the screen capture safely
                        pyautogui.screenshot().save(ss_path)
                        time_12hr = datetime.now().strftime('%I:%M:%S %p')
                        
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO incidents (timestamp, window_title, process_name, screenshot_file)
                            VALUES (?, ?, ?, ?)
                        ''', (time_12hr, win_title, win_proc, ss_filename))
                        conn.commit()
                        conn.close()
            
            time.sleep(0.5) # Lightweight polling break
        except Exception:
            time.sleep(1)

# --- JAVASCRIPT-TO-PYTHON INTERFACE BRIDGE ---
class ApiBridge:
    def get_status(self):
        global ENGINE_ARMED
        return {"armed": ENGINE_ARMED}

    def toggle_engine(self):
        global ENGINE_ARMED
        ENGINE_ARMED = not ENGINE_ARMED
        return {"armed": ENGINE_ARMED}

    def get_incidents(self):
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents ORDER BY id DESC")
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Map full file structural absolute paths so the native UI can load local file files securely
            for row in rows:
                row['screenshot_path'] = os.path.join(LOG_DIR, row['screenshot_file']).replace('\\', '/')
            return {"incidents": rows}
        except Exception:
            return {"incidents": []}

    def purge_vault(self):
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM incidents")
            conn.commit()
            conn.close()
            for file in os.listdir(LOG_DIR):
                if file.endswith(".png"):
                    try: os.remove(os.path.join(LOG_DIR, file))
                    except Exception: pass
            return {"status": "success"}
        except Exception:
            return {"status": "error"}

    def open_image(self, file_path):
        # Safely open screenshots natively in default Windows system viewer
        if os.path.exists(file_path):
            os.startfile(file_path)

# --- EMBEDDED DASHBOARD HTML UI ---
html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@700;800&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #090b0e; color: #c5d1e2;
            font-family: 'JetBrains Mono', monospace; font-size: 12px;
            padding: 20px; user-select: none;
        }
        .container {
            width: 100%; background: #0f1217;
            border: 1px solid #1c232d; border-radius: 4px; padding: 20px;
        }
        header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid #1c232d; padding-bottom: 12px; margin-bottom: 15px;
        }
        .brand { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 15px; color: #00ff88; }
        .brand span { color: #8899b4; font-size: 10px; font-family: 'JetBrains Mono', sans-serif; }
        .status-badge { padding: 4px 8px; border-radius: 2px; font-weight: bold; font-size: 10px; }
        .status-active { background: rgba(0, 255, 136, 0.1); color: #00ff88; border: 1px solid #00cc6a; }
        .status-idle { background: rgba(136, 153, 180, 0.1); color: #8899b4; border: 1px solid #2a3650; }
        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .btn {
            padding: 12px; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 11px;
            cursor: pointer; border-radius: 3px; text-align: center;
            border: 1px solid #202b3c; background: #141921; color: #00ccff; outline: none;
        }
        .btn:hover { border-color: #00ccff; background: rgba(0, 204, 255, 0.05); }
        .btn-toggle-on { background: #ff3355; color: #fff; border: 1px solid #cc2244; }
        .btn-toggle-on:hover { background: #e02244; border-color: #ff3355; }
        .btn-purge { color: #ff3355; }
        .btn-purge:hover { border-color: #ff3355; background: rgba(255, 51, 85, 0.05); }
        .section-title {
            font-family: 'Syne', sans-serif; font-size: 11px; text-transform: uppercase;
            color: #8899b4; margin-bottom: 10px; display: flex; justify-content: space-between;
        }
        .vault-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 12px; max-height: 380px; overflow-y: auto;
        }
        .screenshot-card { background: #141921; border: 1px solid #1c232d; border-radius: 3px; padding: 10px; }
        .screenshot-card img {
            width: 100%; height: auto; aspect-ratio: 16/9; object-fit: cover;
            border-radius: 2px; border: 1px solid #202b3c; cursor: pointer; margin-top: 6px;
        }
        .screenshot-card img:hover { border-color: #00ccff; }
        .meta-time { color: #00ccff; font-weight: bold; font-size: 10px; }
        .meta-title { color: #ffaa00; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }
    </style>
</head>
<body>

<div class="container">
    <header>
        <div class="brand">TALOS <span>// LOCAL SENTINEL</span></div>
        <div id="status-indicator" class="status-badge status-idle">ENGINE: OFF</div>
    </header>

    <div class="controls">
        <button id="action-toggle" class="btn" onclick="toggleEngine()">Activate Background Sentinel</button>
        <button class="btn btn-purge" onclick="purgeStorage()">Purge Artifact Vault</button>
    </div>

    <div class="section-title">
        <span>📸 Anomaly Capture Vault</span>
        <span id="counter">0 Items</span>
    </div>

    <div class="vault-grid" id="vault-area"></div>
</div>

<script>
    // Safe bridge polling handler to track readiness
    function callNative(funcName, ...args) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api[funcName]) {
            return window.pywebview.api[funcName](...args);
        }
        return Promise.reject("Bridge not ready");
    }

    async function updateStatus() {
        try {
            const data = await callNative('get_status');
            const badge = document.getElementById('status-indicator');
            const btn = document.getElementById('action-toggle');
            
            if(data.armed) {
                badge.textContent = "ENGINE: LIVE (BACKGROUND)";
                badge.className = "status-badge status-active";
                btn.textContent = "Deactivate Sentinel";
                btn.className = "btn btn-toggle-on";
            } else {
                badge.textContent = "ENGINE: OFF (STANDBY)";
                badge.className = "status-badge status-idle";
                btn.textContent = "Activate Background Sentinel";
                btn.className = "btn";
            }
        } catch(e){}
    }

    async function toggleEngine() {
        try {
            await callNative('toggle_engine');
            updateStatus();
        } catch(e){}
    }

    async function loadVault() {
        try {
            const data = await callNative('get_incidents');
            const area = document.getElementById('vault-area');
            document.getElementById('counter').textContent = `${data.incidents.length} Captures`;
            
            if (!data.incidents || data.incidents.length === 0) {
                area.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 30px; color: #506070;">Monitoring background anomalies silently...</div>`;
                return;
            }

            // PyWebView handles loading dynamic native media assets safely using local filesystem references via python binding execution
            area.innerHTML = data.incidents.map(inc => `
                <div class="screenshot-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span class="meta-time">⏱️ ${inc.timestamp}</span>
                        <span style="color:#506070; font-size:9px;">${inc.process_name}</span>
                    </div>
                    <div class="meta-title" title="${inc.window_title}">Ctx: ${inc.window_title}</div>
                    <img src="file://${inc.screenshot_path}" onclick="openImageNatively('${inc.screenshot_path}')">
                </div>
            `).join('');
        } catch(e){}
    }

    function openImageNatively(path) {
        callNative('open_image', path);
    }

    async function purgeStorage() {
        if(confirm("Erase all logged anomalies?")) {
            await callNative('purge_vault');
            loadVault();
        }
    }

    window.addEventListener('pywebviewready', () => {
        updateStatus();
        loadVault();
        setInterval(loadVault, 2500);
    });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    # Launch active stealth structural engine thread loops
    monitor_thread = threading.Thread(target=talos_stealth_loop, daemon=True)
    monitor_thread.start()

    # Create UI Native Frame window instance wrapper
    bridge = ApiBridge()
    window = webview.create_window(
        title='Talos Desktop Sentinel',
        html=html_content,
        width=850,
        height=620,
        resizable=True,
        background_color='#090b0e',
        js_api=bridge  # <--- MOVE IT HERE
    )
    
    # Run loop execution frame smoothly without arguments
    webview.start()     # <--- CLEAN AND EMPTY HERE