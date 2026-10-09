# AniZoneFlix Telegram File Store Bot

<p align="center">
  <strong>A Telegram file-storage and link-delivery bot maintained by AniZoneFlix.</strong><br>
  <a href="https://t.me/anizoneflix">Updates & support: @anizoneflix</a>
</p>

## Features

- Store and retrieve Telegram media through deep links.
- Batch and advanced batch link generation (`/batch`, `/advbatch`, `/auto_batch`).
- MongoDB-backed user, configuration, and channel data.
- Multiple database channels and clone-bot management.
- Optional force-subscription, verification, URL shorteners, and premium access.
- Admin controls, reports, backups, and broadcasts.
- Telegram HTML message formatting with bold text, italics, and blockquotes where supported.
- Ordered batch output: requested message order is preserved, including descending ranges; configured shortener selection is deterministic.

## Requirements

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Telegram API ID and API hash from [my.telegram.org](https://my.telegram.org)
- A MongoDB database/connection URI
- A Telegram channel where the bot can access the stored messages; grant the bot the required permissions.

## Configuration

Set these environment variables in your deployment platform (or in a local `.env` file):

| Variable | Required | Description |
| --- | --- | --- |
| `APP_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `TG_BOT_TOKEN` | Yes | Bot token |
| `DATABASE_URL` | Yes | MongoDB connection URI |
| `CHANNEL_ID` | Yes | Primary database channel ID, usually `-100...` |
| `OWNER_ID` | Yes | Numeric Telegram user ID of the owner |
| `PORT` | No | Web server port; platform-provided `PORT` is respected |
| `DB_NAME` | No | MongoDB database name (default: `AniZoneFlix`) |
| `BAN_SUPPORT` | No | Support URL (default: `https://t.me/anizoneflix`) |
| `TG_BOT_WORKERS` | No | Telegram worker count (default: `200`) |
| `BASE_URL` | As needed | Public HTTPS URL used by verification/deep-link web routes; configure the database setting if your deployment manages it there |
| `START_PIC` | No | URL for the start image |
| `FORCE_PIC` | No | URL for the force-subscription image |
| `CUSTOM_CAPTION` | No | Custom media caption |

Do not commit real tokens, API hashes, or database credentials. Keep MongoDB network access restricted where possible.

## MongoDB persistence and troubleshooting

- Use a managed MongoDB deployment (such as MongoDB Atlas) or a MongoDB instance with persistent storage. A container's local filesystem is not a database backup.
- Set `DATABASE_URL` to the full MongoDB connection URI and `DB_NAME` to the same database name across every restart/deployment. The default database name is `AniZoneFlix`.
- In Atlas, create a database user, allow the deployment host in Network Access, and verify the URI includes the correct credentials and cluster. Never paste credentials into public logs or commit them to Git.
- Do not change `DB_NAME` between deploys unless you intentionally want to use a different database. An empty-looking bot after a deploy often means it connected to a different database or cluster, not that MongoDB deleted the records.
- Database calls from Flask are dispatched to the bot's running asyncio loop. The web server no longer creates and closes temporary event loops for MongoDB calls, avoiding Motor clients being reused across different loops.
- If the database is unavailable, configuration writes should report failure instead of claiming that settings were saved. Check startup logs for MongoDB connection errors and confirm the database user has read/write access.
- Back up the database before upgrading or changing cluster/database names. Do not restore a backup by deleting collections unless that replacement is intended.

## Base URL configuration

Set `BASE_URL` to the public HTTPS origin of the running web service, for example `https://your-service.onrender.com`, with no verification path appended. You can also update it using `/set_base_url https://your-service.onrender.com` as an authorized admin/owner. The bot verifies the value by reading it back from MongoDB before reporting success. All generated verification links use the stored value; if it is absent, the environment variable is used as the fallback. If a stale URL remains, update the database setting and check that the deployed service points to the expected `DATABASE_URL` and `DB_NAME`.

## Verification template

AniZoneFlix uses one shared `templates/verify.html` template for every user. It is responsive and avoids mandatory external font downloads and heavy blur effects to keep it usable on low-end phones as well as desktop devices. Other verification variants and development test files have been removed from this release.

## Run locally or on a VPS

```bash
git clone <your-repository-url>
cd <repository-directory>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Export the required variables in your shell or place them in a `.env` file supported by your deployment setup, then run:

```bash
python3 main.py
```

To run tests:

```bash
python3 -m unittest discover -s . -p 'test_*.py'
```

## Deploy with Docker

The repository includes a `Dockerfile`.

```bash
docker build -t anizoneflix-bot .
docker run --env-file .env -p 8001:8001 anizoneflix-bot
```

Set `PORT` to the port your hosting platform expects. Confirm that the Flask server binds to `0.0.0.0` and that the platform health check targets the configured port.

## Deploy on Render

1. Push this repository to a Git provider.
2. In Render, create a **Web Service** from the repository.
3. Choose Docker deployment (or the Python runtime if you configure the build/start commands yourself).
4. Add the required environment variables from the table above.
5. Attach a persistent MongoDB service/Atlas database and set `DATABASE_URL`.
6. Deploy and inspect the build and runtime logs. Resolve missing variables or dependency-build errors before sharing the service URL.
7. Set the public HTTPS URL in the bot's `BASE_URL` configuration wherever verification links are generated.
8. Test `/start`, a known file deep link, batch generation, and the verification flow.

Free hosting plans may sleep, restart, or have resource limits; no deployment guide can guarantee uninterrupted uptime on every provider or plan.

## Troubleshooting

- **Bot does not start:** check `TG_BOT_TOKEN`, `APP_ID`, `API_HASH`, and startup logs.
- **Database errors:** verify `DATABASE_URL`, database permissions, IP/network allow-list, and connectivity.
- **Files are missing:** confirm `CHANNEL_ID`, channel membership/permissions, and that the requested message IDs exist.
- **Verification links fail:** make sure `BASE_URL` is the public HTTPS address and that the web service is reachable.
- **FloodWait errors:** Telegram rate limits are enforced by Telegram. The bot waits as required; do not remove FloodWait handling.
- **Slow batch scans:** use reasonable message ranges and monitor hosting CPU, network, and Telegram API limits.

## Branding

- Brand: **AniZoneFlix**
- Channel: [https://t.me/anizoneflix](https://t.me/anizoneflix)
- Handle: **@anizoneflix**

Use this branding for project-facing messages and documentation. Keep technical filenames and third-party dependency names unchanged where renaming them would break compatibility.
