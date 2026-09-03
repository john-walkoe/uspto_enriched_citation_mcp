# SSO Setup — Google + Microsoft sign-in for the USPTO Citations MCP

`CITATIONS_AUTH_MODE=oauth` turns this server's HTTP transport into an OAuth 2.1
authorization server + protected resource: MCP clients (Claude.ai, Claude
Desktop custom connectors, ChatGPT) discover the server, self-register (DCR),
and send the user's browser through a "Sign in with Microsoft / Google"
chooser. Who may connect is decided by YOUR user list, not the IdP: the
verified email must match an active row in the local `mcp_users` table.

`CITATIONS_AUTH_MODE=none` (the default) and STDIO transport are completely
unaffected — you can adopt this file's setup or ignore it entirely.

## How it works

- FastMCP's `OAuthProvider` supplies the standard OAuth machinery (metadata,
  `/authorize`, `/token`, `/register`, `/revoke`, PKCE). This repo's
  `src/uspto_enriched_citation_mcp/auth/provider.py` adds the dual-IdP bridge: `/auth/select`
  (chooser page), `/auth/start/{idp}`, `/auth/callback/{idp}` with full
  id_token verification (JWKS signature, issuer, audience, nonce, expiry;
  Google additionally requires `email_verified`).
- Authorization = the SQLite database at `CITATIONS_AUTH_DB_PATH` (default
  `data/mcp_auth.db`): `mcp_users` rows plus the OAuth server state that must
  survive restarts (registered clients, single-use auth codes, rotating
  refresh tokens — codes/tokens stored as SHA-256 hashes only).
- role `user` → scope `citations:user` (the full read surface). role `admin` →
  additionally `citations:admin`, which unhides the `citations_manage_users` tool
  (user management with an MCP App panel). Nothing else is admin-gated.
- Access tokens: 1 h HS256 JWTs minted by this server. Refresh tokens: 30 d
  IDLE timeout — rotation issues a fresh token on every use and re-checks the
  user row, so deactivating a user locks them out within an hour.
- Headless/machine clients skip the browser flow entirely by presenting the
  static `CITATIONS_AUTH_INTERNAL_TOKEN` as `Authorization: Bearer …` (grants
  both scopes).

## 1. Register the IdP applications (one-time, in a browser)

**Microsoft Entra ID** (https://entra.microsoft.com → App registrations →
New registration):
1. Name it (users see this on the consent screen).
2. Supported account types: pick per your audience — "Any Entra ID tenant +
   personal Microsoft accounts" pairs with `CITATIONS_AUTH_MS_TENANT=common`;
   work/school-only pairs with `organizations`; a single tenant GUID locks to
   that tenant.
3. Redirect URI (platform **Web**):
   `https://<your-host>/auth/callback/microsoft`
4. Copy the Application (client) ID → `CITATIONS_AUTH_MS_CLIENT_ID`.
5. Certificates & secrets → New client secret → copy the **Value** →
   `CITATIONS_AUTH_MS_CLIENT_SECRET`. Calendar the expiry date.
6. Token configuration → Add optional claim → ID token → `email` (without it,
   the code falls back to `preferred_username` when address-shaped).

**Google** (https://console.cloud.google.com → APIs & Services):
1. OAuth consent screen: External; add scopes `openid`, `email`, `profile`;
   **publish** it (in Testing mode only allowlisted test users can sign in).
2. Credentials → Create credentials → OAuth client ID → Web application;
   Authorized redirect URI: `https://<your-host>/auth/callback/google`.
3. Copy Client ID / secret → `CITATIONS_AUTH_GOOGLE_CLIENT_ID` / `_SECRET`.

Only one IdP is required — leave the other's client ID empty and the chooser
is skipped.

## 2. Environment

Add to your (gitignored) `.env` — see `.env.example` for the full block:

```bash
CITATIONS_AUTH_MODE=oauth
CITATIONS_AUTH_BASE_URL=https://<your-host>      # public https origin
CITATIONS_AUTH_JWT_SECRET=$(openssl rand -hex 32)
CITATIONS_AUTH_GOOGLE_CLIENT_ID=…
CITATIONS_AUTH_GOOGLE_CLIENT_SECRET=…
CITATIONS_AUTH_MS_CLIENT_ID=…
CITATIONS_AUTH_MS_CLIENT_SECRET=…
CITATIONS_AUTH_MS_TENANT=common
CITATIONS_AUTH_INTERNAL_TOKEN=$(openssl rand -hex 32)
```

Never commit secrets; the repo's `.gitignore` covers `.env` and `data/`.

## 3. Enable the admin tool (OAuth deployments)

Set `CITATIONS_ENABLE_USER_MANAGEMENT=true` in your environment. This gate is required for OAuth deployments: without it, the `citations_manage_users` admin tool is not registered and will not appear in `tools/list`, even for admin identities. Startup fails with a RuntimeError if OAuth is enabled but the gate fails to attach.

## 4. Seed the first admin (bootstrap)

The `citations_manage_users` MCP tool is admin-gated, so the first admin must be
seeded from the CLI:

```bash
uv run python scripts/manage_mcp_users.py add you@example.com --role admin --name "You"
uv run python scripts/manage_mcp_users.py list
# In Docker: docker exec <container> uv run python scripts/manage_mcp_users.py …
```

After that, manage users conversationally: ask the connected assistant to
"list registered users" / "add jane@firm.com" — the `citations_manage_users` tool
validates and re-renders the user table panel.

## 5. Reverse proxy notes

- The OAuth routes must be publicly reachable WITHOUT any shared secret:
  `/.well-known/*`, `/register`, `/authorize`, `/token`, `/revoke`, `/auth/*`,
  plus `/mcp` and `/health`.
- If you use a path allowlist, remember nginx's `$request_uri` includes the
  query string — end alternatives with `(/|\?|$)`, not `(/|$)`, or every real
  `/authorize?...` request 403s.
- Do NOT inject an x-api-key (or any credential) header on `/mcp` at the
  proxy — in oauth mode that would carry anonymous visitors past sign-in.
- SSE needs `proxy_buffering off` and long read timeouts.

## 6. Sharing one user list across servers (optional)

`CITATIONS_AUTH_DB_PATH` may point at a SQLite file shared by several MCP
servers **on the same host** (the store enables WAL + busy_timeout). One
`mcp_users` row then grants access to every server mounting that file. Do not
share the file across hosts or network filesystems.

(This server is typically deployed with its OWN user file, while PFW/PTAB/FPD
share one, so its access list can be managed independently of theirs.)

## 7. Verify

```bash
curl -s https://<your-host>/.well-known/oauth-authorization-server | jq .issuer
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<your-host>/mcp \
  -H 'content-type: application/json' -d '{}'          # → 401 (the point)
curl -s -o /dev/null -w '%{http_code}\n' \
  "https://<your-host>/authorize?response_type=code&client_id=x&redirect_uri=https%3A%2F%2Fexample.com&code_challenge=cccccccccccccccccccccccccccccccccccccccccch&code_challenge_method=S256"
#   → 400/302, NOT 403 (allowlist admits query strings)
```

Then add `https://<your-host>/mcp` as a custom connector in Claude.ai — it
should walk the chooser and connect. An admin identity sees
`citations_manage_users` in the tool list; a role `user` identity does not.
