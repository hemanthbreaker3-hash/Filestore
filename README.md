# AniZoneFlix FileStore

Telegram-powered file sharing bot with a Flask verification website, configurable shorteners, and an optional Vercel-to-Render website proxy.

## Features

- Telegram bot for file links, batch links, access management, force-subscription, and admin tools.
- Flask verification pages stored in `web/templates/`.
- Shortlink callback verification performed by the backend.
- Session, flow-expiry, and browser-tab binding checks before access is granted.
- Optional Referer enforcement per configured shortener. When disabled for a shortener, the Referer check is skipped; the remaining backend checks still apply.
- Security response headers and a Content Security Policy nonce for the verification page's inline scripts.
- Optional Vercel frontend/proxy under `vercel/`.

## Project layout

```text
.
├── main.py                 # Flask verification app and bot process entry point
├── bot.py                  # Telegram bot client
├── config.py               # Environment configuration
├── database/
│   └── database.py         # MongoDB access layer
├── plugins/                # Telegram bot command handlers
├── web/
│   └── templates/          # HTML templates for verification states
├── universal_bypass.js     # Frontend utility used by the project
├── requirements.txt
├── Dockerfile
├── Procfile
└── vercel/                 # Optional Vercel frontend/proxy
```

## Required environment variables

Set these in your hosting provider's environment settings. Never commit real credentials or `.env` files.

| Variable | Required | Description |
|---|---:|---|
| `TG_BOT_TOKEN` | Yes | Telegram bot token from BotFather |
| `APP_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `DATABASE_URL` | Yes | MongoDB connection URI |
| `CHANNEL_ID` | Recommended | Telegram channel ID used to store/retrieve files |
| `OWNER_ID` | Recommended | Numeric Telegram owner ID |
| `SESSION_SECRET_KEY` | Yes for stable production sessions | Long random secret used to sign Flask sessions; keep stable across deploys and instances |
| `PORT` | No | Web server port; defaults to `8080` |
| `DB_NAME` | No | MongoDB database name; defaults to `Filestore` |
| `SESSION_COOKIE_SECURE` | No | Defaults to `true`; set to `false` only for local HTTP development |
| `LOG_LEVEL` | No | Python logging level, e.g. `INFO` or `DEBUG` |

Generate a session secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the resulting value as `SESSION_SECRET_KEY` in the host dashboard. Do not paste the secret into source code or commit it. If the secret changes, existing browser sessions will be invalidated.

Other optional bot settings are read from environment variables in `config.py`, including `TG_BOT_WORKERS`, `FSUB_LINK_EXPIRY`, `START_PIC`, `FORCE_PIC`, `PROTECT_CONTENT`, and custom message values.

## Deploy on Render

1. Create a Render **Web Service** from this repository.
2. Use the repository's Dockerfile, or set the build command to `pip install -r requirements.txt` and the start command to `python main.py`.
3. Add the required environment variables above.
4. Deploy and wait for the bot and web service to start.
5. Open the service URL and confirm the home page responds.
6. In the bot's admin/panel commands, set the public `BASE_URL` to the Render service URL. Use the exact HTTPS origin, without a trailing path.
7. Configure shortener API domains and keys in the bot panel, then test a fresh verification link end-to-end.

The bot and Flask app share a process in the default deployment. Use one process/worker unless the application is refactored to share its event loop and database lifecycle across workers.

## Optional Vercel frontend

The `vercel/` directory provides a small landing page and path-preserving proxy. Configure these Vercel environment variables:

- `RENDER_BACKEND_URL`: the HTTPS URL of the Render backend.
- `TELEGRAM_BOT_USERNAME`: bot username without the leading `@`.
- `SITE_NAME`: optional website title.

If the Vercel domain is used for user-facing links, ensure the backend's `BASE_URL` and the generated callback URLs consistently use the intended public domain. Do not mix Render and Vercel origins in the same flow unless the proxy forwards cookies and callback paths correctly.

## Verification flow

1. User opens the frontend verification page.
2. The page navigates to the configured shortlink.
3. The shortener returns the browser to the backend callback.
4. The backend validates the token, session, expiry, browser-tab binding, and (only if enabled for that shortener) the Referer.
5. The backend grants access and redirects to the Telegram bot only if all required checks pass. Any failed check denies access.

The frontend is for presentation and navigation; backend code is the authorization authority. A browser tab identifier and Referer are supplementary signals, not cryptographic proof of a human or a specific physical tab. Do not treat them as substitutes for server-side sessions, short-lived tokens, expiry, rate limiting, and one-time token consumption.

## Local development

Use Python 3.10 or newer. Install dependencies in a virtual environment:

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set the required environment variables, then run:

```bash
python main.py
```

For local HTTP only, set `SESSION_COOKIE_SECURE=false`; restore it to `true` in HTTPS production. MongoDB and valid Telegram credentials are needed to exercise the full app. The browser verification flow cannot be fully tested by Python syntax checks alone.

## Troubleshooting

- **Sessions restart unexpectedly:** set a persistent `SESSION_SECRET_KEY`; do not generate a new value at every start.
- **Browser does not keep the session locally:** local HTTP development needs `SESSION_COOKIE_SECURE=false`. Production should use HTTPS and leave it enabled.
- **Verification says the session was not started:** reopen the original link in the same browser tab and complete the shortlink without switching browsers. Confirm the public callback URL points to this backend.
- **No shortener can generate a link:** check the configured shortener domain/API key and inspect application logs. The backend intentionally refuses to grant access when no shortener succeeds.
- **Database unavailable:** verify `DATABASE_URL`, database network access, and provider allowlists.
- **Bot starts but cannot retrieve files:** verify `CHANNEL_ID` and that the bot is an administrator in the storage channel.
- **Imports fail during deployment:** use the supported Python version and install all packages from `requirements.txt`; check the first missing/incompatible package in build logs.

## Security notes

- Keep `SESSION_SECRET_KEY`, Telegram credentials, and MongoDB credentials private.
- Keep the service on HTTPS in production.
- Review logs before enabling verbose logging in a public deployment; do not log tokens or session cookies.
- A successful syntax check is not equivalent to a full production security audit. Test the actual browser → shortener → callback → Telegram flow after each deployment.


## External Verify Bot API mode

Administrators can first set the public API Base URL in the Verify Bot `/panel` → **Set API Base URL** button. Then run `/verifyapi` in FileStore and enter that same base URL, optionally followed by the matching client API key and Verify Bot username separated by `|`. The Verify Bot exposes `GET /api/info` to show the configured API base URL and endpoint paths:

`https://your-verification-api.onrender.com | YOUR_CLIENT_API_KEY`

Without a key, send just the URL. The configured service must implement `POST /api/request` (returning `start_link`), `GET /api/{user_id}` (returning `verified`), and `GET /api/request-status/{user_id}?bot_username=...` (returning the request-scoped verified status). The bot uses the configured API to create a verification link and checks status before showing a verification button. Use `/panel` → **Verification** → **Switch Verification Mode** to choose external Verify Bot API mode or the existing normal shortener flow. Existing locally verified access is still respected by the original local flow.

### Fixing `CHANNEL_INVALID`

`CHANNEL_INVALID` means Telegram cannot resolve the configured source/database channel ID for the requested file. Confirm `CHANNEL_ID` is the numeric channel ID (usually starts with `-100`), that the bot is a member/admin of that channel, and that the file deep link was generated for the same database channel. The bot now skips invalid/inaccessible secondary channel IDs and displays a clearer message if no valid source channel remains; it cannot recover deleted files or correct a wrong channel ID automatically.
