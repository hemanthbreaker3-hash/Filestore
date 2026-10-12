# Vercel website + Render bot (same repository)

This directory contains the **website deployment only**. Keep the Telegram bot and its database/event loop on Render. The Vercel site serves a polished landing page and proxies verification/API routes to Render, so verification remains backed by the running bot.

## Deploy on Vercel

1. Push this repository to GitHub/GitLab.
2. In Vercel, **Add New → Project** and import the same repository.
3. In **Root Directory**, choose `vercel` and save. Keep the Root Directory set to `vercel` for this configuration.
4. Add Environment Variable `RENDER_BACKEND_URL` = your Render web-service origin, e.g. `https://your-service.onrender.com` (no trailing slash).
5. Optional: set `BASE_URL` to your stable Vercel production domain, e.g. `https://your-project.vercel.app`. Leave it unset to use Vercel's `VERCEL_PROJECT_PRODUCTION_URL`/`VERCEL_URL` when rewriting proxied API responses.
6. The included `pyproject.toml` explicitly points Vercel to the Flask entrypoint `api.proxy:app`, fixing the “No Flask entrypoint found” build error.
7. Deploy. The homepage is static; `/v/...`, `/verify`, `/link/...`, `/go_shortener`, and `/api/...` are proxied to Render.

## Vercel environment / config.py

Environment variables take precedence. For local-only testing you may fill `vercel/.env` or `vercel/config.py`; `.env` is gitignored and should never contain credentials in a public commit. On Vercel, use Project Settings → Environment Variables. Required: `RENDER_BACKEND_URL`. Optional: `BASE_URL`, `SITE_NAME`.

## Configure Render bot base URL

1. Keep the bot service deployed from the repository root (not the `vercel` directory).
2. In Render → your bot Web Service → Environment, set `BASE_URL` to the Vercel production URL, for example `https://your-project.vercel.app`.
3. If a `BASE_URL` is already stored in MongoDB, it takes precedence over the environment fallback. Update it through the bot's authorized `/set_base_url https://your-project.vercel.app` command, or clear/change the stored setting, then restart/redeploy Render.
4. Check `https://your-project.vercel.app/` and test a real `/v/<token>` verification link.

Vercel assigns a deployment URL automatically, but a separate Render process cannot discover a new Vercel domain by itself. Use the stable Vercel production domain in Render's `BASE_URL`/bot setting once. This avoids links pointing at the Render hostname while using Vercel as the public website.

## Render environment variables

Configure the bot's existing required values in Render: `TG_BOT_TOKEN`, `APP_ID`, `API_HASH`, `DATABASE_URL`, `CHANNEL_ID`, and `OWNER_ID`. Keep `DB_NAME` the same as your current production database. Set `BASE_URL=https://your-project.vercel.app` for verification links. Do not copy bot credentials into Vercel; Vercel only needs `RENDER_BACKEND_URL` and optionally `BASE_URL`.

## Notes

- The Vercel and Render deployments can use the same repository with different Root Directories/start commands.
- Do not deploy the Telegram bot process on Vercel: serverless functions are not a persistent bot worker and do not share Render's in-memory asyncio loop.
- This setup cannot guarantee “100% deploy success” across provider/account/runtime changes. Always inspect the Vercel build log and Render runtime log after deployment.
