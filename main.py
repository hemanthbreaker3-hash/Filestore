import asyncio
import concurrent.futures
import json
import os
import random
import re
import sys
import time
import traceback
import urllib.parse
from threading import Thread

import hydrogram
import hydrogram.enums
import hydrogram.errors
import hydrogram.filters
import hydrogram.handlers
import hydrogram.raw
import hydrogram.raw.base
import hydrogram.raw.types
import hydrogram.types
import pyrogram.utils
import requests
from flask import Flask, jsonify, redirect, render_template, request
from hydrogram.parser.html import Parser
from hydrogram.raw import types as raw_types

MAIN_LOOP = None

def run_async(coro):
    """
    Executes async coroutine on main bot event loop if running, or isolated loop otherwise.
    """
    global MAIN_LOOP
    if MAIN_LOOP and MAIN_LOOP.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)
        return future.result(timeout=10)
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Pyrogram module compatibility mapping
sys.modules["pyrogram"] = hydrogram
for name, module in list(sys.modules.items()):
    if name == "hydrogram" or name.startswith("hydrogram."):
        pyrogram_name = name.replace("hydrogram", "pyrogram", 1)
        sys.modules[pyrogram_name] = module

# Patch InlineKeyboardButton for style attributes
original_init = hydrogram.types.InlineKeyboardButton.__init__

def patched_init(self, *args, style=None, **kwargs):
    original_init(self, *args, **kwargs)
    self.style = style

hydrogram.types.InlineKeyboardButton.__init__ = patched_init

original_write = hydrogram.types.InlineKeyboardButton.write

async def patched_write(self, client):
    style_type = getattr(self, "style", None)
    text = self.text
    if text and "#" in text:
        for keyword, s_type in [("#primary", "primary"), ("#danger", "danger"), ("#success", "success"), ("#succes", "success")]:
            if keyword in text.lower():
                style_type = s_type
                self.text = text.replace(keyword, "").replace(keyword.upper(), "").strip()
                break

    res_btn = await original_write(self, client)

    if style_type and hasattr(res_btn, "style"):
        bg_primary = style_type == "primary"
        bg_danger = style_type == "danger"
        bg_success = style_type == "success"
        res_btn.style = raw_types.KeyboardButtonStyle(
            bg_primary=bg_primary or None,
            bg_danger=bg_danger or None,
            bg_success=bg_success or None
        )
    return res_btn

hydrogram.types.InlineKeyboardButton.write = patched_write

# Patch HTML Parser for blockquote expandable
original_handle_starttag = Parser.handle_starttag

def patched_handle_starttag(self, tag, attrs):
    original_handle_starttag(self, tag, attrs)
    if tag == "blockquote" and "expandable" in dict(attrs):
        if tag in self.tag_entities and self.tag_entities[tag]:
            self.tag_entities[tag][-1].collapsed = True

Parser.handle_starttag = patched_handle_starttag

# Patch message effect support
from hydrogram.types import Message

original_invoke = hydrogram.Client.invoke

async def patched_invoke(self, query, *args, **kwargs):
    effect_id = getattr(self, "_current_message_effect_id", None)
    if effect_id is not None and hasattr(query, "effect"):
        query.effect = int(effect_id)
    return await original_invoke(self, query, *args, **kwargs)

hydrogram.Client.invoke = patched_invoke

original_send_photo = hydrogram.Client.send_photo
async def patched_send_photo(self, *args, **kwargs):
    effect_id = kwargs.pop("message_effect_id", None)
    if effect_id is not None:
        self._current_message_effect_id = effect_id
    try:
        return await original_send_photo(self, *args, **kwargs)
    finally:
        self._current_message_effect_id = None

hydrogram.Client.send_photo = patched_send_photo

original_send_message = hydrogram.Client.send_message
async def patched_send_message(self, *args, **kwargs):
    effect_id = kwargs.pop("message_effect_id", None)
    if effect_id is not None:
        self._current_message_effect_id = effect_id
    try:
        return await original_send_message(self, *args, **kwargs)
    finally:
        self._current_message_effect_id = None

hydrogram.Client.send_message = patched_send_message

from bot import Bot
from config import OWNER_ID, TG_BOT_TOKEN
from database.database import db
from pyrogram.errors import FloodWait

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

app = Flask(__name__)

def is_supported_chrome_browser(user_agent: str) -> bool:
    """
    Check if the user-agent belongs to a legitimate user web browser.
    Allows Chrome, Safari, Firefox, Edge, Opera, Samsung Internet, Mobile Safari/Chrome, etc.
    Blocks automated scrapers, headless tools, bots, crawlers, or missing User-Agents.
    """
    if not user_agent:
        return False
    ua = user_agent.lower()

    bot_keywords = [
        "python", "curl", "wget", "puppeteer", "selenium", "headless",
        "phantomjs", "bot", "crawler", "spider", "scrapy", "httpclient",
        "requests", "axios", "postman", "go-http-client", "java/",
        "libwww-perl", "golang", "aiohttp", "urllib", "httpx", "playwright"
    ]
    for b in bot_keywords:
        if b in ua:
            return False

    valid_tokens = [
        "mozilla/", "chrome/", "crios", "safari/", "firefox/", "fxios",
        "edg/", "edge/", "opr/", "opera/", "samsungbrowser/", "duckduckgo",
        "applewebkit/", "gecko/", "trident/"
    ]
    return any(token in ua for token in valid_tokens)

def is_legitimate_browser(user_agent: str) -> bool:
    return is_supported_chrome_browser(user_agent)

def is_explicit_bot_or_scraper(user_agent: str) -> bool:
    if not user_agent:
        return True
    return not is_supported_chrome_browser(user_agent)

@app.route('/')
def hello_world():
    return 'AniZoneFlix'

@app.route('/v/<path:full_token>')
@app.route('/verify')
@app.route('/link/<path:subpath>')
def verify_frontend(full_token=None, subpath=None):
    token_key = full_token or subpath or request.args.get('token', '')
    if not token_key and subpath:
        parts = subpath.strip('/').split('/')
        token_key = "/".join(parts)

    if not token_key:
        return 'Invalid or missing verification token.', 400

    token_doc = run_async(db.get_verify_token(token_key))
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    short_st = request.args.get('st', '')

    try:
        from templates.template_manager import get_random_verification_template
        selected_template = get_random_verification_template()
    except Exception:
        selected_template = 'verify.html'

    try:
        return render_template(selected_template, token=token_key, short_st=short_st)
    except Exception:
        return render_template('verify.html', token=token_key, short_st=short_st)

@app.route('/go_shortener')
def go_shortener():
    token_key = request.args.get('token', '')
    if not token_key:
        return 'Missing verification token.', 400

    token_doc = run_async(db.get_verify_token(token_key))
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    short_st = request.args.get('st', '') or token_key

    # Return HTML page displaying "Redirecting, please wait..." with animated dots
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Redirecting...</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Poppins', sans-serif; background: radial-gradient(circle at top, #1f1c2c, #090a0f); color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }}
        .card {{ background: rgba(26, 26, 38, 0.9); backdrop-filter: blur(12px); max-width: 480px; width: 100%; padding: 40px 30px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 40px rgba(0,0,0,0.6); text-align: center; }}
        .spinner {{ width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1); border-top-color: #e50914; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 25px auto; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        h2 {{ font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 10px; }}
        p {{ color: #b3b3b3; font-size: 14px; line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="spinner"></div>
        <h2>Redirecting, please wait<span id="dots">.</span></h2>
        <p>Generating your shortlink... Please do not close or refresh this page.</p>
    </div>
    <script>
        const dotsElement = document.getElementById('dots');
        let dotCount = 1;
        setInterval(() => {{
            dotCount++;
            dotsElement.textContent = '.'.repeat(dotCount);
        }}, 400);

        fetch('/api/get_shortener_url?token={token_key}&st={short_st}')
            .then(res => res.json())
            .then(data => {{
                if (data && data.url) {{
                    window.location.href = data.url;
                }} else {{
                    window.location.href = '/api/verify?st={short_st}&token={token_key}';
                }}
            }})
            .catch(() => {{
                window.location.href = '/api/verify?st={short_st}&token={token_key}';
            }});
    </script>
</body>
</html>"""

@app.route('/api/get_shortener_url')
def get_shortener_url():
    try:
        token_key = request.args.get('token', '')
        short_st = request.args.get('st', '') or token_key

        base_url = run_async(db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")).rstrip("/")
        verify_backend_endpoint = f"{base_url}/api/verify?st={short_st}&token={token_key}"

        if not token_key:
            return jsonify({"url": verify_backend_endpoint})

        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return jsonify({"url": verify_backend_endpoint})

        shorteners = run_async(db.get_shorteners())
        active_shorteners = [s for s in shorteners if s.get('enabled', True) and s.get('domain') and s.get('api_key')]

        if active_shorteners:
            candidates = active_shorteners.copy()
            # Keep configured shortener priority stable; avoid random routing on each request.
            candidates.sort(key=lambda item: str(item.get("domain", "")).lower())

            encoded_dest = urllib.parse.quote(verify_backend_endpoint, safe='')

            def _fetch_shortener(active_shortener):
                domain = active_shortener.get('domain', '').strip().rstrip('/')
                api_key = active_shortener.get('api_key', '').strip()
                if not domain or not api_key:
                    return None

                if not domain.startswith("http://") and not domain.startswith("https://"):
                    domain = "https://" + domain

                endpoints = []
                if "?" in domain:
                    if "url=" in domain:
                        api_url = domain
                    elif "api=" in domain:
                        api_url = f"{domain}&url={encoded_dest}"
                    else:
                        api_url = f"{domain}&api={api_key}&url={encoded_dest}"
                    endpoints.append(api_url)
                elif "/st" in domain or "/api" in domain:
                    endpoints.append(f"{domain}?api={api_key}&url={encoded_dest}")
                else:
                    endpoints.append(f"{domain}/st?api={api_key}&url={encoded_dest}")
                    endpoints.append(f"{domain}/api?api={api_key}&url={encoded_dest}")
                    endpoints.append(f"{domain}?api={api_key}&url={encoded_dest}")

                for api_url in endpoints:
                    try:
                        res = requests.get(api_url, timeout=10.0)
                        data = None
                        try:
                            data = res.json()
                        except Exception:
                            try:
                                data = json.loads(res.text)
                            except Exception:
                                data = None

                        short_url = None
                        if isinstance(data, dict):
                            short_url = (
                                data.get("shortenedUrl") or
                                data.get("url") or
                                data.get("shortlink") or
                                data.get("result") or
                                data.get("link") or
                                data.get("short_url") or
                                (data.get("data", {}).get("url") if isinstance(data.get("data"), dict) else None) or
                                (data.get("data", {}).get("shortenedUrl") if isinstance(data.get("data"), dict) else None)
                            )
                        elif isinstance(res.text, str) and res.text.strip().startswith("http"):
                            short_url = res.text.strip()

                        if short_url and str(short_url).strip().startswith("http"):
                            return str(short_url).replace("\\/", "/").strip()
                    except Exception:
                        pass
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)) as executor:
                futures = [executor.submit(_fetch_shortener, s) for s in candidates]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result_url = future.result()
                        if result_url:
                            return jsonify({"url": result_url})
                    except Exception:
                        pass

        return jsonify({"url": verify_backend_endpoint})
    except Exception as err:
        print(f"Error in /api/get_shortener_url: {err}")
        token_key = request.args.get('token', '')
        short_st = request.args.get('st', '') or token_key
        base_url = run_async(db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")).rstrip("/")
        return jsonify({"url": f"{base_url}/api/verify?st={short_st}&token={token_key}"})

@app.route('/api/verify', methods=['GET', 'POST'])
def verify_backend():
    token_key = request.values.get('token', '') or request.values.get('st', '')
    short_st = request.values.get('st', token_key)

    user_agent = request.headers.get('User-Agent', '')

    # Identify user from token
    user_id = 0
    username = ""
    token_doc = run_async(db.get_verify_token(token_key)) if token_key else None
    if token_doc:
        user_id = token_doc.get('user_id', 0)
        username = token_doc.get('username', '')

    bot_config = run_async(db.get_config())
    bot_username = bot_config.get('BOT_USERNAME', '')
    bot_dest = f"https://telegram.me/{bot_username}?start=verify_{short_st}" if bot_username else "https://telegram.me/"

    # Check if explicit bot, scraper, or non-browser request
    if is_explicit_bot_or_scraper(user_agent) or not is_legitimate_browser(user_agent):
        if user_id > 0:
            run_async(db.add_ban_user(user_id))
            alert_text = (
                f"<b>🚨 BYPASS BOT DETECTED — ADMIN ALERT</b>\n\n"
                f"• <b>User ID:</b> <code>{user_id}</code>\n"
                f"• <b>Username:</b> @{username or 'None'}\n"
                f"• <b>User-Agent:</b> <code>{user_agent[:150]}</code>\n"
                f"• <b>Action Taken:</b> Access Blocked & User Banned"
            )
            try:
                if TG_BOT_TOKEN and OWNER_ID:
                    requests.post(
                        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                        json={"chat_id": OWNER_ID, "text": alert_text, "parse_mode": "HTML"},
                        timeout=3
                    )
            except Exception as notify_err:
                print(f"Error sending bypass alert: {notify_err}")

        return render_template('bypass_detected.html')

    # Chrome browser confirmed: complete verification
    if user_id > 0:
        expire_sec = run_async(db.get_config_val("VERIFY_EXPIRE_SECONDS", 86400))
        run_async(db.set_user_verified(user_id, duration_seconds=int(expire_sec)))
        if token_key:
            run_async(db.mark_verify_token_used(token_key))

    return render_template('verify_success.html', redirect_url=bot_dest)

def start_uptime_monitor():
    def _monitor_loop():
        time.sleep(5)
        cached_url = None
        last_fetch = 0
        while True:
            try:
                now = time.time()
                if not cached_url or (now - last_fetch) > 300:
                    cached_url = run_async(db.get_config_val("BASE_URL", "https://your-render-service.onrender.com")).rstrip("/")
                    last_fetch = now

                if cached_url:
                    requests.get(f"{cached_url}/", timeout=4)
            except Exception:
                pass
            time.sleep(1)

    Thread(target=_monitor_loop, daemon=True).start()

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    from config import API_HASH, APP_ID, TG_BOT_TOKEN
    start_uptime_monitor()
    Thread(target=run, daemon=True).start()
    while True:
        if not APP_ID or not API_HASH or not TG_BOT_TOKEN:
            print(
                "ERROR: Required Telegram API credentials are missing! "
                "Please set APP_ID, API_HASH, and TG_BOT_TOKEN environment variables."
            )
            time.sleep(60)
            continue
        try:
            Bot().run()
        except FloodWait as e:
            print(f"FloodWait: {e.x} seconds")
            time.sleep(e.x)
        except Exception as exc:
            if "API key is required" in str(exc) or "API_ID_INVALID" in str(exc):
                print(
                    f"FATAL: Invalid or missing API key credentials: {exc}. "
                    "Please check your APP_ID, API_HASH, and TG_BOT_TOKEN environment variables."
                )
                time.sleep(60)
            else:
                print(f"FATAL: Bot crashed at startup: {exc}")
                traceback.print_exc()
                time.sleep(10)
