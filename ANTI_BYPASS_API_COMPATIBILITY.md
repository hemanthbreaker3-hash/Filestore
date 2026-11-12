# Anti-Bypass Shield API setup in Filestore

1. Deploy the Anti-Bypass Shield service and configure a real provider shortener in its dashboard.
2. Copy the dedicated API key generated for that configured shortener. Do not use the account master key or the provider's private API key.
3. In Filestore, open `/panel` → Shorteners → Add Shortener (or use `/addshortener`).
4. Enter the Anti-Bypass deployment base URL and the dedicated API key. Example:
   - URL: `https://your-antibypass-domain.example`
   - API key: the dedicated `mzf_live_...` key shown for that shortener
5. Keep that shortener enabled in Filestore.

Filestore supports the Anti-Bypass routes `/api`, `/st`, and
`/api/get_shortener_url`. It sends the exact per-request verification
destination using the route's expected parameter names, and reads either a
plain-text URL or the JSON `shortenedUrl` response.

For `/api` and `/st`, the request includes `api`, `url`, `format=text`, and
`unprotected=1`. For `/api/get_shortener_url`, it includes `token`, `st`,
`url`, `direct=1`, and `unprotected=1`.

The `unprotected=1` option skips only the Anti-Bypass platform's own extra
verification layer. It does not bypass Filestore verification: the API key
still must be assigned to a configured provider shortener, and Filestore's
unique `verify_TOKEN` is still validated after the generated shortlink
redirects to its destination.

If multiple Filestore shorteners are enabled, Filestore randomly selects one
unless an explicit shortener is selected. If an API request fails or does not
return a valid HTTP(S) short URL, Filestore tries the next enabled shortener
and fails closed if none succeeds.
