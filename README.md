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

## Supported environment variables

The repository deployment configuration supports **only** these nine variables. Add them to your hosting provider's environment settings or to a local `.env` file. Do not commit real credentials.

| Variable | Purpose |
|---|---|
| `API_HASH` | Telegram API hash |
| `APP_ID` | Telegram API ID |
| `CHANNEL_ID` | Telegram database channel ID |
| `DATABASE_URL` | MongoDB connection URI |
| `DB_NAME` | MongoDB database name (default: `Filestore`) |
| `OWNER` | Telegram owner username, without `@` |
| `OWNER_ID` | Numeric Telegram owner user ID |
| `PORT` | Web server port (default: `8080`) |
| `TG_BOT_TOKEN` | Telegram bot token |

Example shell exports (replace every placeholder with your own value):

```bash
export API_HASH='your_api_hash'
export APP_ID='your_app_id'
export CHANNEL_ID='-100xxxxxxxxxx'
export DATABASE_URL='mongodb+srv://username:password@cluster.mongodb.net/'
export DB_NAME='Filestore'
export OWNER='your_telegram_username'
export OWNER_ID='your_numeric_user_id'
export PORT='8080'
export TG_BOT_TOKEN='your_bot_token'
```

The VPS deployment script reads and saves only these nine variables.

## One-click VPS deploy (CDML-X style)

```bash
mkdir -p /bot1
cd /bot1

# Place project here (extract zip or clone)
# Example: unzip Filestore-updated.zip && mv Filestore-done Filestore
cd /bot1/Filestore

# Instance suffix (optional multi-bot on same VPS)
export CMD_SUFFIX="1"

# Start-screen buttons
export START_REPO_URL='https://t.me/YourChannel'
export START_REPO_BUTTON='Repository'
export START_UPDATE_URL='https://t.me/YourUpdates'
export START_UPDATE_BUTTON='Updates'
export START_DEV_URL='https://t.me/YourUsername'
export START_DEV_BUTTON='Developer'

# Real credentials (required)
export TG_BOT_TOKEN='YOUR_BOT_TOKEN'
export APP_ID='YOUR_APP_ID'
export API_HASH='YOUR_API_HASH'
export DATABASE_URL='mongodb+srv://user:pass@cluster/'
export CHANNEL_ID='-100xxxxxxxxxx'
export OWNER_ID='YOUR_TELEGRAM_ID'
export SESSION_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

chmod +x one-click-deploy.sh deploy.vps start.sh upgrade-system-tools.sh
./one-click-deploy.sh

# Service name becomes: filestore1_bot  (from CMD_SUFFIX=1)
# Restart later:  sudo systemctl restart filestore1_bot
```

On Termux, skip systemd and use `./start.sh` or `nohup ./start.sh &`.

Custom file-delivery button stays available via `/panel` → **Custom Button** or `/set_button`.

## Deploy on Render

1. Create a Render **Web Service** from this repository.
2. Use the repository's Dockerfile, or set the build command to `pip install -r requirements.txt` and the start command to `python main.py`.
3. Add the required environment variables above.
4. Deploy and wait for the bot and web service to start.
5. Open the service URL and confirm the home page responds.
6. In the bot's admin/panel commands, set the public `BASE_URL` to the Render service URL. Use the exact HTTPS origin, without a trailing path.
7. Configure shortener API domains and keys in the bot panel, then test a fresh verification link end-to-end.

The bot and Flask app share a process in the default deployment. Use one process/worker unless the application is refactored to share its event loop and database lifecycle across workers.

## Deploy on any VPS (Ubuntu / Debian / CentOS / etc.)

Works on most VPS providers (Hetzner, Contabo, DigitalOcean, AWS Lightsail, Oracle Free Tier, Vultr, etc.).

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y   # Debian/Ubuntu
# or: sudo yum update -y                # CentOS/RHEL

# 2. Install Python 3.10+ and tools
sudo apt install -y python3 python3-pip python3-venv git screen

# 3. Clone and enter project
git clone <your-repo-url> Filestore && cd Filestore

# 4. Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create .env (never commit this)
cat > .env << 'EOF'
TG_BOT_TOKEN=123456:ABC...
APP_ID=12345
API_HASH=your_api_hash
DATABASE_URL=mongodb+srv://user:pass@cluster/...
CHANNEL_ID=-100xxxxxxxxxx
OWNER_ID=123456789
SESSION_SECRET_KEY=generate_with_secrets_token_urlsafe
PORT=8080
EOF

# 6. Run (foreground test)
python main.py

# 7. Production with screen or systemd
screen -S filestore
python main.py
# Ctrl+A then D to detach
```

**Optional public Base URL on VPS:** use Cloudflare Tunnel, ngrok, or a reverse proxy (Caddy/Nginx) so the verification pages are reachable.  
If you do **not** want a public website, open `/panel` → **Verification Settings** → **Base URL: DISABLE**. The bot then uses direct Telegram verification links after any shortlink step (pure-bot mode, ideal for private VPS).

## Deploy on Termux (Android)

```bash
# Update packages
pkg update && pkg upgrade -y
pkg install -y python git

# Clone
git clone <your-repo-url> Filestore && cd Filestore

# Install deps (may take time)
pip install --upgrade pip
pip install -r requirements.txt

# Create .env with the same variables as above
nano .env

# Run
python main.py
```

Tips for Termux:
- Keep the phone awake or use `termux-wake-lock`.
- For background: `nohup python main.py > bot.log 2>&1 &`
- Public Base URL is usually unavailable on mobile data. Disable Base URL in `/panel` so verification works via Telegram deep links only.
- MongoDB Atlas free tier works fine over mobile data.

## Docker (any host)

```bash
docker build -t filestore .
docker run -d --name filestore \
  -e TG_BOT_TOKEN=... \
  -e APP_ID=... \
  -e API_HASH=... \
  -e DATABASE_URL=... \
  -e CHANNEL_ID=... \
  -e OWNER_ID=... \
  -e SESSION_SECRET_KEY=... \
  -p 8080:8080 \
  filestore
```

## Optional Vercel frontend

The `vercel/` directory provides a small landing page and path-preserving proxy. Configure these Vercel environment variables:

- `RENDER_BACKEND_URL`: the HTTPS URL of the Render backend.
- `TELEGRAM_BOT_USERNAME`: bot username without the leading `@`.
- `SITE_NAME`: optional website title.

If the Vercel domain is used for user-facing links, ensure the backend's `BASE_URL` and the generated callback URLs consistently use the intended public domain. Do not mix Render and Vercel origins in the same flow unless the proxy forwards cookies and callback paths correctly.

## Verification flow

**Web mode (Base URL enabled in /panel):**
1. The bot selects an enabled shortener from `/panel` (randomly when multiple are active) and calls its API using the saved API key.
2. The bot sends the actual short URL returned by that API. The shortener destination is this backend's `/shortener-complete` callback with the user's unique verification token and selected shortener ID.
3. After the shortener completes, it redirects to the backend callback. The backend checks the token, expiry, selected/enabled shortener, and Referer when that provider's Referer protection is enabled.
4. The backend marks the token's web verification complete and redirects to `telegram.me/BOT_USERNAME?start=verify_TOKEN`.
5. The bot validates the same token and user before granting access.

**Direct Telegram mode (Base URL disabled in /panel):**
1. The bot still selects an enabled shortener and generates the short URL through its saved API key.
2. The shortener destination is `telegram.me/BOT_USERNAME?start=verify_TOKEN`.
3. After completing the shortener, the user returns to Telegram. The bot validates the token and grants access without requiring a public website.

If verification itself is disabled, the bot skips this flow and delivers content directly. If no active shortener can generate a URL while verification is enabled, the bot fails closed and does not grant access.

Toggle Base URL under `/panel` → Verification Settings. The frontend is for presentation; backend code remains the authorization authority.

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


## Anti-Bypass API integration

See [ANTI_BYPASS_API_COMPATIBILITY.md](ANTI_BYPASS_API_COMPATIBILITY.md) for configuring the Anti-Bypass Shield dedicated shortener API in `/panel`.
