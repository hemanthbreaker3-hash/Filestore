"""Vercel serverless proxy for Render-hosted verification endpoints."""
import json, os
from urllib.parse import parse_qsl, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, request, Response
from config import setting

app = Flask(__name__)
BACKEND = (os.getenv("RENDER_BACKEND_URL") or setting("RENDER_BACKEND_URL")).rstrip("/")

@app.route("/", defaults={"unused": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@app.route("/<path:unused>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def proxy(unused=""):
    if not BACKEND:
        return Response("Vercel is deployed, but RENDER_BACKEND_URL is missing. Add your Render Web Service URL in Vercel → Settings → Environment Variables.", 503, mimetype="text/plain")
    raw_path = request.args.get("path", unused)
    path = "/" + "/".join(p for p in raw_path.split("/") if p and p not in (".", ".."))
    query = [(k, v) for k, v in parse_qsl(request.query_string.decode("utf-8", "replace"), keep_blank_values=True) if k != "path"]
    target = BACKEND + path + (("?" + urlencode(query, doseq=True)) if query else "")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length", "connection", "accept-encoding"}}
    headers["X-Forwarded-Host"] = request.headers.get("host", "")
    headers["X-Forwarded-Proto"] = "https"
    body = request.get_data() if request.method not in ("GET", "HEAD") else None
    try:
        with urlopen(Request(target, data=body, headers=headers, method=request.method), timeout=25) as r:
            data, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/octet-stream")
            extra = {k: v for k, v in r.headers.items() if k.lower() in {"cache-control", "set-cookie", "location"}}
    except HTTPError as e:
        data, status, ctype, extra = e.read(), e.code, e.headers.get("Content-Type", "text/plain"), {}
    except (URLError, TimeoutError, OSError) as e:
        return Response("Render backend unavailable: " + str(e), 502, mimetype="text/plain")
    if "json" in ctype.lower():
        try:
            payload = json.loads(data.decode("utf-8"))
            host = (os.getenv("BASE_URL") or os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL") or "").strip()
            if host and not host.startswith("http"): host = "https://" + host
            if host:
                def rewrite(x):
                    if isinstance(x, dict): return {k: rewrite(v) for k, v in x.items()}
                    if isinstance(x, list): return [rewrite(v) for v in x]
                    if isinstance(x, str) and x.startswith(BACKEND + "/"): return host.rstrip("/") + x[len(BACKEND):]
                    return x
                data = json.dumps(rewrite(payload)).encode("utf-8")
        except (ValueError, UnicodeDecodeError): pass
    out = Response(data, status=status, content_type=ctype)
    for k, v in extra.items(): out.headers[k] = v
    out.headers["Cache-Control"] = "no-store"
    return out
