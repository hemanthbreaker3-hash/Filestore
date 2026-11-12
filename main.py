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
import secrets
import hmac
import hashlib
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
from flask import Flask, g, jsonify, redirect, render_template, request, session
from hydrogram.parser.html import Parser
from hydrogram.raw import types as raw_types

MAIN_LOOP = None

def run_async(coro):
    """
    Executes async coroutine on main bot event loop if running, or isolated loop otherwise.
    """
    global MAIN_LOOP
    if not MAIN_LOOP or not MAIN_LOOP.is_running():
        if hasattr(coro, "close"):
            coro.close()
        raise RuntimeError("Bot event loop is not ready; retry the request shortly.")
    future = asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)
    return future.result(timeout=20)

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

# Make this monkey-patch idempotent. If main is imported/reloaded, never wrap
# our own patched function as the original (which creates recursive invoke calls).
if not hasattr(hydrogram.Client, "_filestore_original_invoke"):
    hydrogram.Client._filestore_original_invoke = hydrogram.Client.invoke
original_invoke = hydrogram.Client._filestore_original_invoke

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

app = Flask(__name__, template_folder="web/templates")
# Configure a stable, deployment-provided signing secret. Never use a public/default key.
app.secret_key = os.environ.get("SESSION_SECRET_KEY", "").strip()
if not app.secret_key:
    app.secret_key = secrets.token_urlsafe(48)
    app.logger.warning("SESSION_SECRET_KEY is unset; sessions will reset when this process restarts.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    # Secure cookies are required in production HTTPS. Set SESSION_COOKIE_SECURE=false
    # only for local HTTP development.
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"},
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    MAX_CONTENT_LENGTH=1024 * 1024,
)

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

def is_chrome_only(user_agent: str) -> bool:
    """Require actual Chrome for the interactive verification page.

    Edge/Opera may include Chromium tokens, so exclude them explicitly.
    User-Agent checks are a compatibility gate, not a security proof.
    """
    ua = (user_agent or "").lower()
    if not ua or any(x in ua for x in ("edg/", "edga/", "edgios/", "opr/", "opera", "samsungbrowser", "firefox", "fxios", "crios")):
        return False
    return "chrome/" in ua and "chromium/" not in ua and "headlesschrome" not in ua

def is_legitimate_browser(user_agent: str) -> bool:
    return is_supported_chrome_browser(user_agent)

def is_explicit_bot_or_scraper(user_agent: str) -> bool:
    # Verification is intentionally Chrome-only; this is a compatibility check,
    # not proof of identity because User-Agent headers can be spoofed.
    return not is_chrome_only(user_agent)

def _signed_session_marker(token_key: str, session_id: str) -> str:
    """Opaque HMAC marker binds a verification attempt to its browser session."""
    payload = f"{token_key}:{session_id}".encode("utf-8")
    return hmac.new(app.secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _bypass_response(reason: str, token_key: str = "", target: str = ""):
    # Target is displayed only as escaped text by Jinja; never redirect to it.
    sid = str(session.get("verification_session") or "")
    if not sid:
        sid = secrets.token_urlsafe(32)
        session["verification_session"] = sid
    marker = _signed_session_marker(target[:500], sid) if target else ""
    base = request.url_root.rstrip("/")
    detected_url = (base + "/bypass-detected?" + urllib.parse.urlencode({
        "target": target[:500], "hash": marker, "session": sid[:100]
    })) if marker else ""
    return render_template("bypass_detected.html", reason=reason,
                           detected_url=detected_url, target=target[:500]), 403


def _looks_like_bookmarklet_or_script() -> bool:
    """Reject obvious bookmarklet/script probes on verification endpoints."""
    ua = (request.headers.get("User-Agent") or "").lower()
    if "javascript:" in request.url.lower() or "data:text/html" in request.url.lower():
        return True
    if request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate" and "javascript:" in request.args.get("url", "").lower():
        return True
    return any(x in ua for x in ("headlesschrome", "phantomjs", "selenium", "playwright", "puppeteer"))


@app.get("/bypass-detected")
def bypass_detected():
    token_key = (request.args.get("target") or "")[:500]
    sid = (request.args.get("session") or "")[:100]
    supplied = (request.args.get("hash") or "")[:128]
    expected = _signed_session_marker(token_key, sid) if token_key and sid else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        return "Invalid security event URL.", 403
    return render_template("bypass_detected.html",
                           reason="A verification bypass attempt was detected. Access was not granted.",
                           detected_url="", target=token_key), 403


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

    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception as err:
        app.logger.exception("Verification frontend could not access the bot/database event loop")
        return ('Verification service is starting or temporarily unavailable. '
                'Please wait a few seconds and reopen this link.'), 503
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    user_agent = request.headers.get("User-Agent", "")
    if not is_chrome_only(user_agent):
        # Browsers cannot be forced to launch another app; provide a user-initiated
        # Chrome intent on Android and clear instructions elsewhere.
        current_url = request.url
        parsed = urllib.parse.urlsplit(current_url)
        android_intent = "intent://" + parsed.netloc + parsed.path
        if parsed.query:
            android_intent += "?" + parsed.query
        android_intent += "#Intent;scheme=" + (parsed.scheme or "https") + ";package=com.android.chrome;end"
        return render_template("chrome_required.html", current_url=current_url,
                               android_intent=android_intent), 200

    short_st = request.args.get('st', '')
    # Bind the flow to this browser session; the signed Flask cookie is HttpOnly.
    if session.get("verification_token") != token_key or not session.get("verification_session"):
        session.clear()
        session["verification_token"] = token_key
        session["verification_session"] = secrets.token_urlsafe(32)
        session.permanent = True

    # Initialize the flow only. Authorization is decided by the backend callback.
    session['verification_flow_started_at'] = int(time.time())
    session.permanent = True
    session.modified = True
    return render_template('verify.html', token=token_key, short_st=short_st)

@app.route('/go_shortener')
def go_shortener():
    token_key = request.args.get('token', '')
    if not token_key:
        return 'Missing verification token.', 400

    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception:
        app.logger.exception("Shortener redirect could not access the bot/database event loop")
        return ('Verification service is starting or temporarily unavailable. '
                'Please wait a few seconds and retry.'), 503
    if not token_doc:
        return 'Verification link expired or invalid.', 403

    short_st = request.args.get('st', '') or token_key
    tab_id = (request.args.get('tab_id') or '').strip()
    # Carry tab metadata to the shortlink; authorization is checked after callback.

    # Keep this status page intentionally static: no spinner, no animated dots,
    # and no repeated/continuous animation. The API pre-generates/caches the link.
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Redirecting</title><style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#090a0f;color:#fff;font:16px Arial,sans-serif}}main{{text-align:center;padding:28px;border-radius:16px;background:#191a24}}p{{color:#c4c4cc}}</style></head><body><main><h2>Redirecting, please wait</h2><p>Preparing your verification link.</p></main><script nonce="{g.csp_nonce}">fetch('/api/get_shortener_url?'+new URLSearchParams({{token:{json.dumps(token_key)},st:{json.dumps(short_st)},tab_id:{json.dumps(tab_id)}}})).then(r=>r.json()).then(d=>{{if(d&&d.url)location.replace(d.url);else{{document.querySelector('main p').textContent='Unable to generate a verification link. Please return to Telegram and try again.';}}}}).catch(()=>{{document.querySelector('main p').textContent='Verification service unavailable. Please return to Telegram and try again.';}})</script></body></html>"""

@app.route('/api/get_shortener_url')
def get_shortener_url():
    try:
        token_key = (request.args.get('token') or '').strip()
        short_st = (request.args.get('st') or token_key).strip()
        tab_id = (request.args.get('tab_id') or '').strip()
        if not token_key:
            return jsonify({'error': 'missing token'}), 400
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', tab_id):
            return jsonify({'error': 'invalid tab identifier'}), 400
        base_url = str(run_async(db.get_config_val('BASE_URL', 'https://your-render-service.onrender.com'))).rstrip('/')
        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return jsonify({'error': 'invalid or expired token'}), 403

        # Do not reuse cached shortlinks: each attempt must carry its own tab-bound callback.
        shorteners = run_async(db.get_shorteners()) or []
        active = [item for item in shorteners if item.get('enabled', True) and item.get('domain') and item.get('api_key')]
        # /verify N can pin a token to a configured shortener. Without a pin,
        # preserve the normal randomized provider selection.
        preferred_id = str(token_doc.get('preferred_shortener_id') or '')
        if preferred_id:
            active = [item for item in active if str(item.get('_id')) == preferred_id]
            if not active:
                return jsonify({'error': 'The selected shortener is no longer enabled or configured'}), 409
        else:
            random.shuffle(active)
        for shortener in active:
            domain = str(shortener.get('domain', '')).strip().rstrip('/')
            api_key = str(shortener.get('api_key', '')).strip()
            shortener_id = str(shortener.get('_id', ''))
            if not domain or not api_key:
                continue
            if not domain.startswith(('http://', 'https://')):
                domain = 'https://' + domain
            parsed_domain = urllib.parse.urlsplit(domain)
            if parsed_domain.scheme not in ('http', 'https') or not parsed_domain.hostname:
                continue

            destination = base_url + '/api/verify?' + urllib.parse.urlencode({
                'token': token_key, 'st': short_st, 'sid': shortener_id, 'tab_id': tab_id
            })
            parsed_api = urllib.parse.urlsplit(domain)
            path = (parsed_api.path or '').rstrip('/')
            query_items = urllib.parse.parse_qsl(parsed_api.query, keep_blank_values=True)

            # Anti-Bypass Shield + standard AdLinkFly / provider compatibility.
            # Prefer one primary endpoint per shortener (API usage once when possible).
            anti_bypass_params = {
                'api': api_key,
                'url': destination,
                'format': 'text',
                'unprotected': '1',
            }
            compatibility_params = {
                'token': api_key,
                'st': api_key,
                'url': destination,
                'direct': '1',
                'unprotected': '1',
            }
            standard_params = {
                'api': api_key,
                'url': destination,
            }

            endpoints = []
            if path.endswith('/api/get_shortener_url') or path.endswith('/get_shortener_url'):
                params = dict(query_items)
                params.update(compatibility_params)
                endpoints.append(urllib.parse.urlunsplit((
                    parsed_api.scheme, parsed_api.netloc, parsed_api.path,
                    urllib.parse.urlencode(params), parsed_api.fragment
                )))
            elif path.endswith('/api') or path.endswith('/st'):
                # Prefer clean params first (arolinks etc. break with format=text)
                params = dict(query_items)
                params.update(standard_params)
                endpoints.append(urllib.parse.urlunsplit((
                    parsed_api.scheme, parsed_api.netloc, parsed_api.path,
                    urllib.parse.urlencode(params), parsed_api.fragment
                )))
                params = dict(query_items)
                params.update(anti_bypass_params)
                endpoints.append(urllib.parse.urlunsplit((
                    parsed_api.scheme, parsed_api.netloc, parsed_api.path,
                    urllib.parse.urlencode(params), parsed_api.fragment
                )))
            else:
                # Root domain (arolinks.com etc.): prefer clean standard API first.
                # format=text breaks pure providers (arolinks returns empty body).
                for suffix in ('/api', '/st', ''):
                    params = dict(query_items)
                    params.update(standard_params)
                    endpoints.append(urllib.parse.urlunsplit((
                        parsed_api.scheme, parsed_api.netloc, path + suffix,
                        urllib.parse.urlencode(params), parsed_api.fragment
                    )))
                # Anti-Bypass compatible params as secondary
                for suffix in ('/api', '/st', ''):
                    params = dict(query_items)
                    params.update(anti_bypass_params)
                    endpoints.append(urllib.parse.urlunsplit((
                        parsed_api.scheme, parsed_api.netloc, path + suffix,
                        urllib.parse.urlencode(params), parsed_api.fragment
                    )))

            # Deduplicate while preserving order; try at most a few
            endpoints = list(dict.fromkeys(endpoints))[:4]

            for api_url in endpoints:
                try:
                    response = requests.get(api_url, timeout=10, allow_redirects=False)
                    raw_response = (response.text or '').strip()
                    try:
                        data = response.json()
                    except Exception:
                        data = None

                    short_url = None
                    if isinstance(data, dict):
                        def _find_short_url(payload, depth=0):
                            if depth > 3 or not isinstance(payload, dict):
                                return None
                            if payload.get('status') == 'error' or payload.get('success') is False:
                                return None
                            keys = (
                                'shortenedUrl', 'shortened_url', 'short_url', 'short',
                                'shortlink', 'shortLink', 'link', 'url', 'output', 'result',
                            )
                            for key in keys:
                                candidate = payload.get(key)
                                if isinstance(candidate, str) and candidate.strip().startswith(('http://', 'https://')):
                                    return candidate.strip()
                            for key in ('data', 'result', 'shortener', 'response'):
                                nested = payload.get(key)
                                found = _find_short_url(nested, depth + 1)
                                if found:
                                    return found
                            return None
                        short_url = _find_short_url(data)
                    if not short_url and raw_response.startswith(('http://', 'https://')):
                        short_url = raw_response.splitlines()[0].strip()
                    if not short_url:
                        continue
                    parsed_short = urllib.parse.urlsplit(str(short_url).strip().replace('\\/', '/'))
                    if parsed_short.scheme not in ('http', 'https') or not parsed_short.hostname:
                        continue
                    short_url = urllib.parse.urlunsplit(parsed_short)
                    run_async(db.update_verify_token(token_key, {
                        'cached_shortlink': short_url,
                        'selected_shortener_id': shortener_id,
                        'selected_shortlink_host': (parsed_short.hostname or '').lower()
                    }))
                    return jsonify({'url': short_url})
                except Exception as exc:
                    print(f'Shortener request failed for {parsed_domain.hostname}: {type(exc).__name__}')
        # If no shortener works, do not pretend a shortener verification succeeded.
        return jsonify({'error': 'No configured shortener could generate a link'}), 502
    except Exception as err:
        print(f'Error in /api/get_shortener_url: {type(err).__name__}: {err}')
        return jsonify({'error': 'verification service temporarily unavailable'}), 503

@app.route('/api/register-tab', methods=['POST'])
def register_verification_tab():
    """Record tab metadata for later backend comparison; this does not verify access."""
    payload = request.get_json(silent=True) or request.form
    token_key = str(payload.get('token') or '').strip()
    tab_id = str(payload.get('tab_id') or '').strip()
    if request.args:
        return jsonify({'ok': False, 'error': 'Unexpected query parameters'}), 400
    if not token_key or session.get('verification_token') != token_key or not session.get('verification_session'):
        return jsonify({'ok': False, 'error': 'Verification flow is not initialized'}), 403
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', tab_id):
        return jsonify({'ok': False, 'error': 'Invalid tab identifier'}), 400
    try:
        token_doc = run_async(db.get_verify_token(token_key))
    except Exception:
        return jsonify({'ok': False, 'error': 'Verification service unavailable'}), 503
    if not token_doc:
        return jsonify({'ok': False, 'error': 'Verification token expired'}), 403
    session['verification_tab_id'] = tab_id
    session['verification_tab_registered_at'] = int(time.time())
    session.permanent = True
    session.modified = True
    return jsonify({'ok': True})


@app.route('/shortener-complete')
def shortener_complete():
    """Shortener destination for pre-generated links when Base URL mode is enabled."""
    token_key = (request.args.get('token') or '').strip()
    sid = (request.args.get('sid') or '').strip()
    if set(request.args.keys()) != {'token', 'sid'} or not token_key or not sid:
        return 'Invalid verification callback.', 400
    try:
        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return 'This verification link has expired or is invalid. Please request a new link from Telegram.', 403
        selected_id = str(token_doc.get('selected_shortener_id') or '')
        if not selected_id or not hmac.compare_digest(selected_id, sid):
            return 'The shortener does not match this verification request.', 403
        configured = run_async(db.get_shorteners()) or []
        selected = next((item for item in configured if str(item.get('_id')) == selected_id and item.get('enabled', True)), None)
        if not selected:
            return 'This shortener is no longer enabled. Request a new verification link.', 403
        if bool(selected.get('referer_enabled', False)):
            referer = request.headers.get('Referer', '')
            referer_host = (urllib.parse.urlsplit(referer).hostname or '').lower().rstrip('.')
            expected_host = str(token_doc.get('selected_shortlink_host') or '').lower().rstrip('.')
            if referer_host and expected_host and not (referer_host == expected_host or referer_host.endswith('.' + expected_host)):
                return 'Shortener return could not be validated. Please reopen the generated shortlink.', 403
        if token_doc.get('web_verified'):
            return 'This verification link has already been completed. Return to Telegram to continue.', 409
        run_async(db.update_verify_token(token_key, {
            'web_verified': True,
            'backend_verification_passed': True,
            'shortener_callback_at': int(time.time()),
        }))
        bot_config = run_async(db.get_config()) or {}
        bot_username = str(bot_config.get('BOT_USERNAME') or '').lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', bot_username):
            return 'Bot username is not configured. Contact the administrator.', 503
        bot_dest = f'https://telegram.me/{bot_username}?start=verify_{token_key}'
        return render_template('verify_success.html', redirect_url=bot_dest, animation_url='https://files.catbox.moe/5scyd0.gif')
    except Exception as err:
        app.logger.exception('Shortener completion callback failed: %s', type(err).__name__)
        return 'Verification service is temporarily unavailable. Please try again later.', 503


@app.route('/api/verify', methods=['GET', 'POST'])
def verify_backend():
    """Validate shortener return, grant timed access, then send user back to Telegram."""
    token_key = (request.values.get('token') or '').strip()
    short_st = (request.values.get('st') or token_key).strip()
    sid = (request.values.get('sid') or '').strip()
    tab_id = (request.values.get('tab_id') or '').strip()
    allowed_verify_keys = {"token", "st", "sid", "tab_id"}
    unknown_keys = set(request.values.keys()) - allowed_verify_keys
    if unknown_keys:
        return _bypass_response("Unknown query parameters were rejected.", token_key, request.path)
    if not token_key:
        token_key = short_st
    if not token_key:
        return 'Invalid or missing verification token. Please reopen the link from Telegram.', 400
    user_agent = request.headers.get('User-Agent', '')
    try:
        token_doc = run_async(db.get_verify_token(token_key))
        if not token_doc:
            return 'This verification link has expired or is invalid. Please request a new link from Telegram.', 403
        if _looks_like_bookmarklet_or_script():
            return _bypass_response("Bookmarklet, headless browser, or script-like request detected.", token_key, request.path)
        # Both stages must be completed in the same signed browser session.
        browser_token = str(session.get("verification_token") or "")
        browser_sid = str(session.get("verification_session") or "")
        if browser_token != token_key or not browser_sid:
            return _bypass_response("Verification session is missing or does not match. Reopen the original link from Telegram.", token_key, request.path)
        flow_started = int(session.get('verification_flow_started_at') or 0)
        if flow_started <= 0 or int(time.time()) - flow_started > 600:
            return render_template('bypass_detected.html', reason='Verification flow expired. Session not started — reopen the original link.'), 403
        expected_tab_id = str(session.get('verification_tab_id') or '')
        if (not tab_id or not expected_tab_id or not hmac.compare_digest(tab_id, expected_tab_id)):
            return render_template('bypass_detected.html', reason='Browser tab does not match the started verification flow. Access blocked.'), 403
        user_id = int(token_doc.get('user_id') or 0)
        username = token_doc.get('username') or ''
        # Referer enforcement is optional per shortener. When disabled, do not
        # reject callbacks merely because browsers/providers omit Referer.
        selected_id = str(token_doc.get('selected_shortener_id') or sid)
        configured = run_async(db.get_shorteners()) or []
        selected = next((item for item in configured if selected_id and str(item.get('_id')) == selected_id), None)
        if selected and bool(selected.get('header_protection_enabled', False)):
            # Practical browser-header validation. Header checks are supplementary;
            # the signed token + browser session/tab binding remain the real controls.
            user_agent = (request.headers.get('User-Agent') or '').strip()
            accept = (request.headers.get('Accept') or '').strip()
            fetch_mode = (request.headers.get('Sec-Fetch-Mode') or '').strip().lower()
            fetch_dest = (request.headers.get('Sec-Fetch-Dest') or '').strip().lower()
            if not user_agent or not accept:
                return render_template('bypass_detected.html', reason='Required browser headers are missing. Open the verification link in your normal browser.'), 403
            if fetch_mode and fetch_mode not in ('navigate', 'cors', 'same-origin', 'no-cors'):
                return render_template('bypass_detected.html', reason='Unexpected browser request headers detected.'), 403
            if fetch_dest and fetch_dest not in ('document', 'empty', 'iframe'):
                return render_template('bypass_detected.html', reason='Unexpected browser navigation headers detected.'), 403
        if selected and bool(selected.get('referer_enabled', False)):
            # Compare against the actual generated short-link host, not the API
            # endpoint configured in the panel (these are often different domains).
            # Browsers/providers may omit Referer due to privacy policies, so a
            # missing value must not reject an otherwise valid signed session.
            referer = request.headers.get('Referer', '')
            referer_host = (urllib.parse.urlsplit(referer).hostname or '').lower().rstrip('.')
            expected_host = str(token_doc.get('selected_shortlink_host') or '').lower().rstrip('.')
            if not expected_host:
                configured_domain = str(selected.get('domain', '')).strip()
                if not configured_domain.startswith(('http://', 'https://')):
                    configured_domain = 'https://' + configured_domain
                expected_host = (urllib.parse.urlsplit(configured_domain).hostname or '').lower().rstrip('.')
            if referer_host and expected_host and not (
                    referer_host == expected_host or referer_host.endswith('.' + expected_host)):
                return render_template('bypass_detected.html', reason='Shortlink referer does not match the generated verification link. Please reopen the link from Telegram.'), 403
        if is_explicit_bot_or_scraper(user_agent):
            # Do not grant access in a different browser; start again from the
            # original Telegram link in Chrome so the session cookie is present.
            return render_template('bypass_detected.html', reason='Chrome is required. Open the original verification link in Google Chrome and start again; session not started.'), 403
        bot_config = run_async(db.get_config()) or {}
        bot_username = str(bot_config.get('BOT_USERNAME') or '').lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', bot_username):
            bot_username = ''
        bot_dest = f'https://telegram.me/{bot_username}?start=verify_{token_key}' if bot_username else 'https://telegram.me/'
        expire_sec = int(run_async(db.get_config_val('VERIFY_EXPIRE_SECONDS', 86400)) or 86400)
        if user_id <= 0:
            return render_template('bypass_detected.html', reason='User session could not be validated. Session not started.'), 403
        run_async(db.set_user_verified(user_id, duration_seconds=expire_sec))
        run_async(db.update_verify_token(token_key, {'web_verified': True, 'backend_verification_passed': True}))
        session['verification_completed_at'] = int(time.time())
        return render_template('verify_success.html', redirect_url=bot_dest, animation_url='https://files.catbox.moe/5scyd0.gif')
    except Exception as err:
        print(f'Verification backend failed for token {token_key[:8]}…: {type(err).__name__}: {err}')
        return ('Verification could not be completed because the service is temporarily unavailable. '
                'Please return to Telegram and request a new link if this continues.'), 503



@app.before_request
def set_request_security_nonce():
    # A fresh nonce permits only the inline scripts explicitly marked by templates.
    g.csp_nonce = secrets.token_urlsafe(18)


@app.context_processor
def inject_template_security_nonce():
    return {"csp_nonce": getattr(g, "csp_nonce", "")}


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{getattr(g, 'csp_nonce', '')}' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "img-src 'self' https: data:; font-src 'self' https: data:; "
        "connect-src 'self' https:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    response.headers.setdefault("Cache-Control", "no-store")
    return response


def start_uptime_monitor():
    def _monitor_loop():
        time.sleep(5)
        cached_url = None
        last_fetch = 0
        while True:
            try:
                now = time.time()
                if not cached_url or (now - last_fetch) > 10:
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
