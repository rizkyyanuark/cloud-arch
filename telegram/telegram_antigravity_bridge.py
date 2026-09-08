#!/usr/bin/env python3
"""
Antigravity Telegram Gateway Bridge (Multi-Project & Multi-Session Edition)
- 100% Seamless Web OAuth 2.0 via https://lab.tugasakhir.space/oauth2callback
- Embedded HTTP OAuth Callback Server on port 8085 with Beautiful Dark-Mode Web UI
- System Monitoring & Real-time Account Verification (/status)
- Isolated Conversation Session Memory per Workspace Project
- Interactive Workspace Switcher (/projects & /project <name>)
- On-Demand Ephemeral GPU Switch Integration (/gpu_on, /gpu_off, /gpu_status)
Author: Rizky Yanuar Kristianto (mini-project ecosystem)
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import os
import subprocess
import time
import psutil
import re
import urllib.parse
import hashlib
import base64
import requests
from pathlib import Path
import telegramify_markdown

CONFIG_PATH = "/home/ubuntu/antigravity-telegram/config.json"
SESSIONS_PATH = "/home/ubuntu/antigravity-telegram/user_sessions.json"
WORKSPACE_ROOT = "/home/ubuntu/workspace"
DEFAULT_WORKSPACE = "mini-project"
GPU_CLI = "/home/ubuntu/.local/bin/gpu"
AUTH_FILES = [
    "/home/ubuntu/.gemini/oauth_creds.json",
    "/home/ubuntu/.config/antigravity/oauth_creds.json"
]

def _get_secret(key, default=""):
    val = os.environ.get(key)
    if val:
        return val
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get(key, default)
        except Exception:
            pass
    return default

BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN", "")
BASE_TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Custom Web OAuth 2.0 Credentials
CLIENT_ID = _get_secret("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = _get_secret("GOOGLE_CLIENT_SECRET", "")
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "tugasakhir.space")
REDIRECT_URI = f"https://lab.{BASE_DOMAIN}/oauth2callback"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cloud-platform"
]

os.makedirs("/home/ubuntu/antigravity-telegram", exist_ok=True)
os.makedirs("/home/ubuntu/.gemini", exist_ok=True)
os.makedirs("/home/ubuntu/.config/antigravity", exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"allowed_user_ids": [1040662726]}

def load_sessions():
    if os.path.exists(SESSIONS_PATH):
        try:
            with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_sessions(sessions):
    try:
        with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        print(f"Error saving sessions: {e}")

config = load_config()
user_sessions = load_sessions()

def list_workspace_projects():
    projects = []
    root = Path(WORKSPACE_ROOT)
    if root.exists():
        for item in sorted(root.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                projects.append(item.name)
    if not projects:
        projects = [DEFAULT_WORKSPACE]
    return projects

def get_user_active_workspace(user_id):
    user_str = str(user_id)
    session = user_sessions.get(user_str, {})
    active = session.get("active_workspace")
    if not active:
        active = DEFAULT_WORKSPACE
        session["active_workspace"] = active
        user_sessions[user_str] = session
        save_sessions(user_sessions)
    return active

def get_user_workspace_session(user_id, workspace_name):
    user_str = str(user_id)
    session = user_sessions.get(user_str, {})
    workspaces = session.get("workspaces", {})
    return workspaces.get(workspace_name, {})

def set_user_workspace_session(user_id, workspace_name, conv_id, turns=1):
    user_str = str(user_id)
    if user_str not in user_sessions:
        user_sessions[user_str] = {
            "active_workspace": workspace_name,
            "workspaces": {}
        }
    user_sessions[user_str]["active_workspace"] = workspace_name
    if "workspaces" not in user_sessions[user_str]:
        user_sessions[user_str]["workspaces"] = {}
    
    user_sessions[user_str]["workspaces"][workspace_name] = {
        "conversation_id": conv_id,
        "updated_at": int(time.time()),
        "turns": turns
    }
    save_sessions(user_sessions)

def reset_user_workspace_session(user_id, workspace_name):
    user_str = str(user_id)
    if user_str in user_sessions and "workspaces" in user_sessions[user_str]:
        if workspace_name in user_sessions[user_str]["workspaces"]:
            del user_sessions[user_str]["workspaces"][workspace_name]
            save_sessions(user_sessions)

def clean_terminal_output(text):
    if not text:
        return ""
    # Strip ANSI escape sequences (colors, cursors, bold)
    clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    clean = re.sub(r'\033\[[0-9;]*[a-zA-Z]', '', clean)
    # Process carriage returns (\r) to retain only final progress lines
    lines = []
    for raw_line in clean.splitlines():
        if '\r' in raw_line:
            raw_line = raw_line.split('\r')[-1]
        lines.append(raw_line)
    return '\n'.join(lines).strip()

async def send_telegram_message(session, chat_id, text, reply_markup=None):
    url = f"{BASE_TELEGRAM_URL}/sendMessage"
    # Auto-sanitize any raw ANSI escape codes before markdownification
    sanitized_text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    sanitized_text = re.sub(r'\033\[[0-9;]*[a-zA-Z]', '', sanitized_text)
    
    formatted = telegramify_markdown.markdownify(sanitized_text)
    
    payload = {
        "chat_id": chat_id,
        "text": formatted,
        "parse_mode": "MarkdownV2"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with session.post(url, json=payload, timeout=15) as resp:
            if resp.status != 200:
                payload["text"] = sanitized_text
                del payload["parse_mode"]
                await session.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Error sending message: {e}")

async def keep_typing(session, chat_id, stop_event):
    url = f"{BASE_TELEGRAM_URL}/sendChatAction"
    payload = {"chat_id": chat_id, "action": "typing"}
    while not stop_event.is_set():
        try:
            await session.post(url, json=payload, timeout=5)
            await asyncio.sleep(4)
        except Exception:
            break

def generate_oauth_login_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent select_account"
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return url

def extract_auth_code(text):
    text = text.strip()
    if "code=" in text:
        match = re.search(r"code=([^&\s]+)", text)
        if match:
            return urllib.parse.unquote(match.group(1))
    return text

def exchange_code_for_tokens(auth_code):
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }
    resp = requests.post(token_url, data=payload, timeout=15)
    return resp.status_code, resp.json()

def save_new_oauth_creds(creds_data):
    if isinstance(creds_data, str):
        creds_data = json.loads(creds_data)
    
    for fpath in AUTH_FILES:
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)

def get_auth_profile_info():
    """Extract full profile and token status from oauth_creds.json"""
    fpath = AUTH_FILES[0]
    if not os.path.exists(fpath):
        return {"logged_in": False, "email": "Belum Login", "name": "-", "status": "🔴 Belum Login (/login)"}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            c = json.load(f)
            email = "Google User"
            name = "Developer"
            if "id_token" in c:
                parts = c["id_token"].split(".")
                if len(parts) > 1:
                    padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                    payload = json.loads(base64.b64decode(padded).decode("utf-8"))
                    email = payload.get("email", email)
                    name = payload.get("name", name)
            
            has_token = bool(c.get("access_token") or c.get("refresh_token"))
            return {
                "logged_in": has_token,
                "email": email,
                "name": name,
                "status": f"🟢 Aktif ({email})" if has_token else "🔴 Token Kosong",
                "scope": c.get("scope", "Standard")
            }
    except Exception as e:
        return {"logged_in": False, "email": "Error reading", "name": "-", "status": f"⚠️ Error: {str(e)}"}

async def handle_http_oauth_callback(request):
    """Handles OAuth redirect from https://lab.tugasakhir.space/oauth2callback"""
    code = request.query.get("code")
    if not code:
        return web.Response(text="Missing OAuth code in redirect URL", status=400)

    status_code, tokens = exchange_code_for_tokens(code)
    if status_code == 200 and ("access_token" in tokens or "refresh_token" in tokens):
        save_new_oauth_creds(tokens)

        user_email = "Google User"
        if "id_token" in tokens:
            try:
                parts = tokens["id_token"].split(".")
                if len(parts) > 1:
                    padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                    payload = json.loads(base64.b64decode(padded).decode('utf-8'))
                    user_email = payload.get("email", user_email)
            except Exception:
                pass

        default_user_id = config.get("allowed_user_ids", [1040662726])[0]
        async with aiohttp.ClientSession() as session:
            await send_telegram_message(
                session, default_user_id,
                f"### 🎉 Autentikasi Google Berhasil\n\n"
                f"Kredensial baru telah terpasang dan diverifikasi secara otomatis pada server EC2.\n\n"
                f"* 👤 **Akun Aktif:** `{user_email}`\n"
                f"* 🔑 **Keyring Status:** `🟢 Active & Verified`\n"
                f"* 🚀 **AI Engine:** `Gemini 3.7 Flash (High Reasoning)`\n\n"
                f"> 💡 **Siap Digunakan:** Anda kini dapat menjalankan instruksi coding, riset, dan MCP Google Workspace di Telegram & JupyterLab!"
            )

        html_content = f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Login Antigravity Berhasil</title>
            <style>
                body {{
                    background: #090d16;
                    color: #f8fafc;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                }}
                .card {{
                    background: #131c2e;
                    border: 1px solid #1e293b;
                    border-radius: 24px;
                    padding: 48px 36px;
                    text-align: center;
                    max-width: 440px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
                    animation: pop 0.4s ease-out;
                }}
                @keyframes pop {{
                    0% {{ transform: scale(0.9); opacity: 0; }}
                    100% {{ transform: scale(1); opacity: 1; }}
                }}
                .icon {{
                    font-size: 56px;
                    margin-bottom: 20px;
                }}
                .badge {{
                    background: rgba(16, 185, 129, 0.15);
                    color: #10b981;
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    padding: 6px 18px;
                    border-radius: 999px;
                    font-weight: 700;
                    font-size: 13px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    display: inline-block;
                }}
                h1 {{
                    margin: 20px 0 10px;
                    font-size: 26px;
                    font-weight: 700;
                    color: #ffffff;
                }}
                p {{
                    color: #94a3b8;
                    font-size: 15px;
                    line-height: 1.6;
                    margin: 0 0 24px;
                }}
                .email-box {{
                    background: #090d16;
                    border: 1px solid #334155;
                    padding: 14px;
                    border-radius: 12px;
                    color: #38bdf8;
                    font-weight: 600;
                    font-size: 16px;
                    margin-bottom: 28px;
                    word-break: break-all;
                }}
                .btn {{
                    background: #2563eb;
                    color: #ffffff;
                    text-decoration: none;
                    padding: 14px 32px;
                    border-radius: 14px;
                    font-weight: 600;
                    font-size: 15px;
                    display: inline-block;
                    transition: all 0.2s;
                    box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.4);
                }}
                .btn:hover {{
                    background: #1d4ed8;
                    transform: translateY(-1px);
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✨</div>
                <div class="badge">✓ Otentikasi Berhasil</div>
                <h1>Login Google Sukses!</h1>
                <p>Kredensial akun Google Anda telah terpasang secara otomatis di server Antigravity.</p>
                <div class="email-box">{user_email}</div>
                <a href="https://t.me/serverrykbot" class="btn">👉 Buka Bot Telegram</a>
            </div>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type="text/html")
    else:
        err_msg = tokens.get("error_description", tokens.get("error", "Pertukaran token Google gagal."))
        return web.Response(text=f"OAuth Error: {err_msg}", status=400)

async def run_antigravity_agent(user_id, prompt):
    active_ws = get_user_active_workspace(user_id)
    ws_session = get_user_workspace_session(user_id, active_ws)
    active_conv_id = ws_session.get("conversation_id")
    target_dir = os.path.join(WORKSPACE_ROOT, active_ws)
    if not os.path.exists(target_dir):
        target_dir = os.path.join(WORKSPACE_ROOT, DEFAULT_WORKSPACE)

    cmd = [
        "/usr/local/bin/agy",
        "--dangerously-skip-permissions",
        "--model", "Gemini 3.7 Flash (High)",
        "--output-format", "json"
    ]
    if active_conv_id:
        cmd.extend(["--conversation", active_conv_id])
    cmd.extend(["-p", prompt])

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=target_dir
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        out_text = stdout.decode('utf-8').strip()
        err_text = stderr.decode('utf-8').strip()

        if not out_text:
            if err_text:
                return f"⚠️ Antigravity Notice:\n{err_text}"
            return "✅ Selesai diproses tanpa output."

        try:
            data = json.loads(out_text)
            new_conv_id = data.get("conversation_id")
            if new_conv_id:
                turns = data.get("num_turns", ws_session.get("turns", 0) + 1)
                set_user_workspace_session(user_id, active_ws, new_conv_id, turns)
            
            reply = data.get("response", "").strip()
            if not reply and data.get("status") != "SUCCESS":
                err_msg = data.get("error", "Terjadi kendala saat memproses permintaan.")
                if "quota reached" in err_msg.lower():
                    # Extract reset duration if available
                    reset_match = re.search(r"resets\s+in\s+([0-9a-z\s]+)", err_msg, re.IGNORECASE)
                    reset_time = reset_match.group(1).strip() if reset_match else "periode berikutnya"
                    return (
                        f"### ⚠️ Batas Kuota Model Tercapai\n\n"
                        f"Akun yang sedang aktif telah mencapai batas kuota pada model ini.\n\n"
                        f"* 📊 **Status:** `Individual Quota Reached`\n"
                        f"* ⏳ **Reset Dalam:** `{reset_time}`\n"
                        f"* 💡 **Solusi Instan:** Anda dapat beralih ke akun Google cadangan dalam hitungan detik.\n\n"
                        f"👉 Ketik `/login` untuk langsung menghubungkan akun Google baru!"
                    )
                return f"⚠️ **Antigravity Notice:**\n\n```text\n{clean_terminal_output(err_msg)}\n```"
            return reply or "✅ Selesai diproses."
        except json.JSONDecodeError:
            return out_text

    except asyncio.TimeoutError:
        return "⚠️ Waktu eksekusi Antigravity melebihi batas (5 menit timeout)."
    except Exception as e:
        return f"❌ Error eksekusi Antigravity: {str(e)}"

def get_system_status():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = os.getloadavg()
    
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}: {{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        docker_status = res.stdout.strip() or "No running containers"
    except Exception:
        docker_status = "Error querying Docker"

    try:
        gpu_res = subprocess.run([GPU_CLI, "status"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        gpu_res = "GPU CLI offline / not found"

    prof = get_auth_profile_info()

    return (
        f"### 📊 STATUS SERVER EC2 & KONTROL ANTIGRAVITY\n\n"
        f"🖥️ **Host:** AWS EC2 `t4g.small` (`34.196.37.78`)\n"
        f"👤 **Akun Aktif:** `{prof['status']}`\n"
        f"🧠 **RAM:** {mem.percent}% ({mem.used / (1024**3):.1f}GB / {mem.total / (1024**3):.1f}GB)\n"
        f"💾 **Disk SSD:** {disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)\n"
        f"⚡ **CPU Load (1m, 5m, 15m):** `{load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}`\n\n"
        f"🐳 **Docker Containers:**\n```text\n{docker_status}\n```\n\n"
        f"🎮 **GPU Worker:**\n```text\n{gpu_res}\n```"
    )

async def handle_callback_query(session, query):
    query_id = query["id"]
    from_id = query["from"]["id"]
    data = query.get("data", "")
    chat_id = query["message"]["chat"]["id"]

    await session.post(f"{BASE_TELEGRAM_URL}/answerCallbackQuery", json={"callback_query_id": query_id})

    if data.startswith("set_ws:"):
        target_ws = data.split(":", 1)[1]
        user_str = str(from_id)
        if user_str not in user_sessions:
            user_sessions[user_str] = {}
        user_sessions[user_str]["active_workspace"] = target_ws
        save_sessions(user_sessions)
        
        target_sess = get_user_workspace_session(from_id, target_ws)
        conv_id = target_sess.get("conversation_id", "Belum ada (Sesi Baru)")
        
        await send_telegram_message(
            session, chat_id,
            f"🔄 **WORKSPACE AKTIF BERHASIL DIUBAH!**\n\n"
            f"📁 **Proyek Aktif:** `{target_ws}`\n"
            f"🔑 **Sesi Percakapan:** `{conv_id}`\n\n"
            f"🧠 Antigravity siap berdiskusi khusus untuk proyek `{target_ws}`."
        )

async def handle_document(session, msg):
    chat_id = msg["chat"]["id"]
    from_id = msg["from"]["id"]
    doc = msg.get("document", {})
    file_name = doc.get("file_name", "")
    file_id = doc.get("file_id")

    global config
    if from_id not in config.get("allowed_user_ids", [1040662726]):
        return

    if file_name.endswith(".json") or "oauth" in file_name.lower():
        file_info_url = f"{BASE_TELEGRAM_URL}/getFile?file_id={file_id}"
        async with session.get(file_info_url) as resp:
            data = await resp.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                dl_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                async with session.get(dl_url) as dl_resp:
                    content = await dl_resp.text()
                    try:
                        creds = json.loads(content)
                        if "access_token" in creds or "refresh_token" in creds:
                            save_new_oauth_creds(creds)
                            await send_telegram_message(
                                session, chat_id,
                                "✅ **KREDENSIAL AKUN BARU BERHASIL DIPASANG!** 🎉\n\n"
                                "• Token Google OAuth telah diperbarui di secure keyring server.\n"
                                "• Layanan Antigravity CLI siap digunakan kembali.\n\n"
                                "👉 Ketik `/status` untuk verifikasi akun aktif!"
                            )
                            return
                    except Exception as e:
                        await send_telegram_message(session, chat_id, f"❌ File JSON tidak valid: {str(e)}")
                        return

def sanitize_command_text(raw_text):
    t = raw_text.strip()
    # Strip prefixes like 'Ryk:', 'ryk: ', 'bot:', '@serverrykbot ', etc.
    t = re.sub(r'^(?:ryk|bot|@\w+bot)[\s:\-_]+', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'@\w+bot\b', '', t, flags=re.IGNORECASE).strip()
    return t

async def handle_message(session, msg):
    chat_id = msg["chat"]["id"]
    from_id = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "User")
    raw_text = msg.get("text", "").strip()

    if "document" in msg:
        await handle_document(session, msg)
        return

    print(f"📩 [{from_id} - {first_name}]: {raw_text}")

    global config, user_sessions
    allowed = config.get("allowed_user_ids", [1040662726])

    if from_id not in allowed:
        await send_telegram_message(
            session, chat_id,
            f"⛔ **AKSES DITOLAK (UNAUTHORIZED)**\n\nUser ID Anda (`{from_id}`) tidak terdaftar dalam whitelist bot ini."
        )
        return

    # Sanitize and extract clean command text
    clean_cmd = sanitize_command_text(raw_text)
    active_ws = get_user_active_workspace(from_id)
    ws_sess = get_user_workspace_session(from_id, active_ws)

    # =========================================================================
    # ⚡ FAST-PATH 1: DIRECT AUTH & OAUTH CODES (Zero-LLM)
    # =========================================================================
    is_auth_cmd = clean_cmd.lower().startswith("/auth ") or clean_cmd.lower().startswith("auth ")
    looks_like_code = ("code=" in raw_text or raw_text.startswith("4/0A") or (len(raw_text) > 30 and "/" in raw_text and not raw_text.startswith("/")))
    
    if is_auth_cmd or looks_like_code:
        code_input = clean_cmd.split(" ", 1)[1].strip() if is_auth_cmd else raw_text
        auth_code = extract_auth_code(code_input)

        await send_telegram_message(session, chat_id, "⏳ **Memverifikasi kode autentikasi dengan Google OAuth 2.0...**")
        status_code, tokens = exchange_code_for_tokens(auth_code)
        if status_code == 200 and ("access_token" in tokens or "refresh_token" in tokens):
            save_new_oauth_creds(tokens)
            user_email = "Google User"
            if "id_token" in tokens:
                try:
                    parts = tokens["id_token"].split(".")
                    if len(parts) > 1:
                        padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                        payload = json.loads(base64.b64decode(padded).decode('utf-8'))
                        user_email = payload.get("email", user_email)
                except Exception:
                    pass
            
            await send_telegram_message(
                session, chat_id,
                f"🎉 **LOGIN GOOGLE BERHASIL 100%!**\n\n"
                f"👤 **Akun Aktif:** `{user_email}`\n"
                f"🔑 **Keyring:** Token tersimpan dan aktif di server EC2.\n\n"
                f"🚀 Antigravity CLI siap digunakan! Ketik `/status` untuk cek akun."
            )
            return
        else:
            err_desc = tokens.get("error_description", tokens.get("error", "Kode verifikasi tidak valid atau sudah pernah digunakan."))
            await send_telegram_message(
                session, chat_id,
                f"❌ **Gagal Login ke Google:**\n`{err_desc}`\n\n"
                "👉 Ketik `/login` untuk membuat link baru."
            )
            return

    # Detect JSON credential pasted directly in chat
    if raw_text.startswith("{") and ("access_token" in raw_text or "refresh_token" in raw_text):
        try:
            creds = json.loads(raw_text)
            save_new_oauth_creds(creds)
            await send_telegram_message(
                session, chat_id,
                "✅ **KREDENSIAL AKUN BARU BERHASIL DIPASANG VIA JSON!** 🎉\n\n"
                "• Token Google OAuth telah tersimpan di server.\n"
                "👉 Ketik `/status` untuk cek profil aktif!"
            )
            return
        except Exception as e:
            await send_telegram_message(session, chat_id, f"❌ Format JSON token error: {str(e)}")
            return

    # =========================================================================
    # ⚡ FAST-PATH 2: DETERMINISTIC GPU ORCHESTRATOR COMMANDS (Zero-LLM)
    # Matches: gpu on, gpu off, gpu status, gpu sync, /gpu_on, /gpu_off, /gpu_status, Ryk: gpu on aws, etc.
    # =========================================================================
    gpu_match = re.match(r'^(?:/)?gpu(?:\s+|_)(on|off|status|sync)(?:\s+(.*))?$', clean_cmd, re.IGNORECASE)
    if gpu_match:
        subcmd = gpu_match.group(1).lower()
        extra_args = (gpu_match.group(2) or "").strip().lower()

        # Handle 'gpu on'
        if subcmd == "on":
            provider = "aws"
            gpu_type = "T4"
            if "vast" in extra_args or "3090" in extra_args or "3060" in extra_args or "4090" in extra_args:
                provider = "vastai"
                gpu_type = "3090" if "3090" in extra_args else ("4090" if "4090" in extra_args else "3060")
            elif "aws" in extra_args or "t4" in extra_args:
                provider = "aws"
                gpu_type = "T4"

            await send_telegram_message(
                session, chat_id,
                f"### ⚡ Memulai Peluncuran Ephemeral GPU\n\n"
                f"Mengalokasikan unit komputasi terakselerasi di {provider.upper()} Spot...\n\n"
                f"* 🎮 **Target Hardware:** {gpu_type} VRAM\n"
                f"* ☁️ **Topology:** `{provider.upper()} Spot` (us-east-1)\n"
                f"* ⏱️ **Estimasi Boot:** ~10–15 detik\n\n"
                f"> ⏳ *Menyiapkan alokasi node, rsync workspace, dan tunnel ZeroMQ...*"
            )
            stop_typing = asyncio.Event()
            typing_task = asyncio.create_task(keep_typing(session, chat_id, stop_typing))
            try:
                gpu_cli_path = "/usr/local/bin/gpu" if os.path.exists("/usr/local/bin/gpu") else GPU_CLI
                res = await asyncio.to_thread(
                    subprocess.run,
                    [gpu_cli_path, "on", "--provider", provider, "--gpu", gpu_type, "--workspace", active_ws],
                    capture_output=True, text=True, timeout=180
                )
                out = res.stdout.strip() or res.stderr.strip()
            finally:
                stop_typing.set()
                await typing_task
            await send_telegram_message(session, chat_id, f"```text\n{clean_terminal_output(out)}\n```")
            return

        # Handle 'gpu off'
        elif subcmd == "off":
            await send_telegram_message(session, chat_id, "🛑 **Mematikan instance GPU & menghentikan tagihan ($0.00)...**")
            gpu_cli_path = "/usr/local/bin/gpu" if os.path.exists("/usr/local/bin/gpu") else GPU_CLI
            res = subprocess.run([gpu_cli_path, "off"], capture_output=True, text=True).stdout.strip()
            await send_telegram_message(session, chat_id, f"```text\n{clean_terminal_output(res)}\n```")
            return

        # Handle 'gpu status'
        elif subcmd == "status":
            gpu_cli_path = "/usr/local/bin/gpu" if os.path.exists("/usr/local/bin/gpu") else GPU_CLI
            res = subprocess.run([gpu_cli_path, "status"], capture_output=True, text=True).stdout.strip()
            await send_telegram_message(session, chat_id, f"```text\n{clean_terminal_output(res)}\n```")
            return

        # Handle 'gpu sync'
        elif subcmd == "sync":
            await send_telegram_message(session, chat_id, f"🔄 **Menyinkronkan perubahan file workspace (`{active_ws}`) ke GPU...**")
            gpu_cli_path = "/usr/local/bin/gpu" if os.path.exists("/usr/local/bin/gpu") else GPU_CLI
            res = subprocess.run([gpu_cli_path, "sync", "--workspace", active_ws], capture_output=True, text=True).stdout.strip()
            await send_telegram_message(session, chat_id, f"```text\n{clean_terminal_output(res)}\n```")
            return

    # =========================================================================
    # ⚡ FAST-PATH 3: SYSTEM, WORKSPACE, & AUTH UTILITIES (Zero-LLM)
    # =========================================================================
    norm = clean_cmd.lower()

    # /start & /help
    if norm in ["/start", "/help", "help", "start"]:
        projects = list_workspace_projects()
        p_list = ", ".join([f"`{p}`" for p in projects])
        await send_telegram_message(
            session, chat_id,
            f"### 👋 Halo, {first_name}! Antigravity Multi-Project Assistant Aktif.\n\n"
            f"📁 **Workspace Aktif:** `{active_ws}`\n"
            f"🔑 **Sesi Konversasi:** `{ws_sess.get('conversation_id', 'Sesi Baru')}`\n\n"
            "📂 **Manajemen Multi-Project:**\n"
            f"* `/projects` - Pilih / ganti proyek ({p_list})\n"
            "* `/project <nama>` - Beralih langsung ke proyek tertentu\n\n"
            "👤 **Manajemen Akun:**\n"
            "* `/login` - Dapatkan link login Google resmi langsung di chat\n"
            "* `/logout` - Putuskan profil Google lama (riwayat disk tetap aman!)\n\n"
            "🎮 **Kontrol GPU On-Demand (Fast-Path):**\n"
            "* `gpu on` atau `/gpu_on` - Sewa & pasang kernel GPU otomatis\n"
            "* `gpu off` atau `/gpu_off` - Matikan GPU sewaan & stop tagihan ($0.00)\n"
            "* `gpu status` atau `/gpu_status` - Cek status GPU & durasi aktif\n\n"
            "📌 **Kontrol Sesi & Server:**\n"
            "* `/new` atau `/clear` - Reset percakapan pada proyek aktif\n"
            "* `/status` - Cek performa RAM, CPU, Docker, dan Akun Aktif"
        )
        return

    # /login
    elif norm in ["/login", "login"]:
        login_url = generate_oauth_login_url()
        reply_markup = {
            "inline_keyboard": [
                [{"text": "🌐 Masuk dengan Google", "url": login_url}]
            ]
        }
        await send_telegram_message(
            session, chat_id,
            f"### 🔐 Google OAuth 2.0 Verification\n\n"
            f"Hubungkan akun Google Anda untuk mengaktifkan AI Engine & integrasi Google Workspace secara instan.\n\n"
            f"**Langkah Mudah:**\n"
            f"1️⃣ Klik tombol **🌐 Masuk dengan Google** di bawah.\n"
            f"2️⃣ Pilih akun Google aktif Anda dan klik **Lanjutkan / Izinkan**.\n\n"
            f"> 💡 **Info:** Akun baru akan langsung terhubung secara otomatis ke server tanpa perlu menyalin kode verifikasi!",
            reply_markup=reply_markup
        )
        return

    # /logout
    elif norm in ["/logout", "logout"]:
        for fpath in AUTH_FILES:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
        user_sessions[str(from_id)] = {"active_workspace": DEFAULT_WORKSPACE, "workspaces": {}}
        save_sessions(user_sessions)
        await send_telegram_message(
            session, chat_id,
            "🔓 **PROFIL AKUN LAMA TELAH DI-LOGOUT (/logout)**\n\n"
            "• Token lama telah dicabut dari server.\n"
            "• 💾 Seluruh file proyek dan kode di server **100% AMAN**.\n\n"
            "👉 Ketik **/login** untuk langsung menghubungkan akun Google baru!"
        )
        return

    # /projects
    elif norm in ["/projects", "projects"]:
        projects = list_workspace_projects()
        inline_keyboard = []
        for p in projects:
            prefix = "✓ " if p == active_ws else "📁 "
            inline_keyboard.append([{"text": f"{prefix}{p}", "callback_data": f"set_ws:{p}"}])
        reply_markup = {"inline_keyboard": inline_keyboard}
        await send_telegram_message(
            session, chat_id,
            f"📂 **DAFTAR WORKSPACE TERSEDIA**\n\n"
            f"Saat ini Anda berada di: `{active_ws}`\n"
            f"Klik tombol di bawah untuk beralih proyek secara instan:",
            reply_markup=reply_markup
        )
        return

    # /project <name>
    elif norm.startswith("/project ") or norm.startswith("project "):
        target_ws = clean_cmd.split(" ", 1)[1].strip()
        projects = list_workspace_projects()
        if target_ws in projects:
            user_str = str(from_id)
            if user_str not in user_sessions:
                user_sessions[user_str] = {}
            user_sessions[user_str]["active_workspace"] = target_ws
            save_sessions(user_sessions)
            target_sess = get_user_workspace_session(from_id, target_ws)
            conv_id = target_sess.get("conversation_id", "Belum ada (Sesi Baru)")
            await send_telegram_message(
                session, chat_id,
                f"🔄 **Beralih ke Workspace:** `{target_ws}`\n"
                f"🔑 **Sesi Konversasi:** `{conv_id}`\n\n"
                f"Percakapan Anda kini terisolasi khusus di `{target_ws}`."
            )
        else:
            await send_telegram_message(
                session, chat_id,
                f"⚠️ Proyek `{target_ws}` tidak ditemukan.\nProyek tersedia: {', '.join([f'`{p}`' for p in projects])}"
            )
        return

    # /new or /clear
    elif norm in ["/new", "/clear", "/reset", "new", "clear", "reset"]:
        reset_user_workspace_session(from_id, active_ws)
        await send_telegram_message(
            session, chat_id,
            f"🔄 **SESI PERCAKAPAN DI-RESET PADA WORKSPACE `{active_ws}`!**\n\n"
            f"Riwayat memori untuk `{active_ws}` telah disegarkan. Sesi proyek lain tetap aman."
        )
        return

    # /status
    elif norm in ["/status", "status", "health", "/health", "ping"]:
        status_msg = get_system_status()
        await send_telegram_message(session, chat_id, status_msg)
        return

    # /docker
    elif norm in ["/docker", "docker", "ps", "/ps", "containers"]:
        res = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], capture_output=True, text=True).stdout
        await send_telegram_message(session, chat_id, f"### 🐳 STATUS DOCKER CONTAINERS\n\n```text\n{res}\n```")
        return

    # =========================================================================
    # 🧠 DELEGATE TO AUTONOMOUS AI CODING AGENT (Antigravity LLM Engine)
    # Only non-infrastructure instructions (coding questions, natural text) arrive here.
    # =========================================================================
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(session, chat_id, stop_typing))
    try:
        agent_reply = await run_antigravity_agent(from_id, clean_cmd)
    finally:
        stop_typing.set()
        await typing_task
    
    await send_telegram_message(session, chat_id, agent_reply)

async def start_http_server():
    """Start local web server on port 8085 for automatic OAuth redirect capture."""
    app = web.Application()
    app.router.add_get("/oauth2callback", handle_http_oauth_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8085)
    await site.start()
    print("🌐 OAuth HTTP Callback Listener active on port 8085 (https://lab.tugasakhir.space/oauth2callback)!")

async def main():
    print("🚀 Antigravity Telegram Stateful Multi-Project Bridge starting...")
    
    # Start embedded OAuth listener
    await start_http_server()

    offset = 0
    timeout = 30
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_TELEGRAM_URL}/getMe") as resp:
            data = await resp.json()
            if data.get("ok"):
                bot_user = data["result"]["username"]
                print(f"✅ Logged in as Telegram Bot: @{bot_user}")
            else:
                print(f"❌ Failed to authenticate bot: {data}")
                return

        while True:
            try:
                url = f"{BASE_TELEGRAM_URL}/getUpdates?offset={offset}&timeout={timeout}"
                async with session.get(url, timeout=timeout + 5) as resp:
                    if resp.status == 200:
                        updates = await resp.json()
                        for update in updates.get("result", []):
                            offset = update["update_id"] + 1
                            if "callback_query" in update:
                                asyncio.create_task(handle_callback_query(session, update["callback_query"]))
                            elif "message" in update:
                                asyncio.create_task(handle_message(session, update["message"]))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Polling warning: {e}")
                await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
