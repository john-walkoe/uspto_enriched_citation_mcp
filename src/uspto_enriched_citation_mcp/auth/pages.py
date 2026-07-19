"""Server-rendered HTML for the OAuth sign-in flow (chooser + error pages).

Plain inline-styled HTML: no external assets, renders identically in every
browser the IdP redirect lands in. Do not change user-facing wording without
checking with John. Ported from edgar_mcp/auth/pages.py; branding only.
"""
from __future__ import annotations

import html

_SERVICE_NAME = "USPTO Citations MCP"

_BASE_CSS = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
         sans-serif; background: #f5f6f8; color: #1a1f2b; margin: 0; }
  .card { max-width: 420px; margin: 12vh auto 0; background: #fff;
          border: 1px solid #e2e5ea; border-radius: 10px; padding: 32px;
          box-shadow: 0 1px 4px rgba(20,30,50,.06); }
  h1 { font-size: 1.15rem; margin: 0 0 6px; }
  p  { font-size: .9rem; color: #4a5262; line-height: 1.45; }
  .btn { display: flex; align-items: center; justify-content: center;
         gap: 10px; width: 100%; box-sizing: border-box; margin-top: 12px;
         padding: 11px 16px; border: 1px solid #cfd4dc; border-radius: 8px;
         background: #fff; color: #1a1f2b; font-size: .95rem;
         text-decoration: none; }
  .btn:hover { background: #f0f2f5; }
  .foot { font-size: .75rem; color: #8a92a3; margin-top: 22px; }
"""

_MS_ICON = (
    '<svg width="18" height="18" viewBox="0 0 21 21">'
    '<rect x="1" y="1" width="9" height="9" fill="#f25022"/>'
    '<rect x="11" y="1" width="9" height="9" fill="#7fba00"/>'
    '<rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>'
    '<rect x="11" y="11" width="9" height="9" fill="#ffb900"/></svg>'
)

_GOOGLE_ICON = (
    '<svg width="18" height="18" viewBox="0 0 48 48">'
    '<path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4'
    " 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.2C12.4 13.4 17.7 9.5 24 9.5z"
    '"/><path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6'
    " 3-2.3 5.5-4.8 7.2l7.7 6C44.1 38 46.5 31.8 46.5 24.5z"
    '"/><path fill="#FBBC05" d="M10.5 28.6c-.5-1.5-.8-3-.8-4.6s.3-3.1.8-4.6l'
    '-7.9-6.2C.9 16.5 0 20.1 0 24s.9 7.5 2.6 10.8l7.9-6.2z"/>'
    '<path fill="#34A853" d="M24 48c6.3 0 11.6-2.1 15.5-5.7l-7.7-6c-2.1 1.4'
    '-4.8 2.3-7.8 2.3-6.3 0-11.6-3.9-13.5-9.4l-7.9 6.2C6.5 42.6 14.6 48 24 48z"/>'
    "</svg>"
)


def select_page(txn_id: str) -> str:
    """IdP chooser shown after an MCP client starts the authorization flow."""
    txn = html.escape(txn_id, quote=True)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width, initial-scale=1">
<title>Sign in - {_SERVICE_NAME}</title><style>{_BASE_CSS}</style></head>
<body><div class="card">
<h1>{_SERVICE_NAME}</h1>
<p>Sign in with the account you registered with to connect your MCP client.</p>
<a class="btn" href="/auth/start/microsoft?txn={txn}">{_MS_ICON}
Sign in with Microsoft</a>
<a class="btn" href="/auth/start/google?txn={txn}">{_GOOGLE_ICON}
Sign in with Google</a>
<p class="foot">Access is limited to registered users. Your login is used only
to verify your identity; no password is ever seen by this service.</p>
</div></body></html>"""


def error_page(title: str, message: str, register_url: str = "") -> str:
    """Terminal error page (unregistered user, failed upstream login, ...)."""
    extra = ""
    if register_url:
        extra = (
            f'<a class="btn" href="{html.escape(register_url, quote=True)}">'
            "Request access</a>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - {_SERVICE_NAME}</title>
<style>{_BASE_CSS}</style></head>
<body><div class="card">
<h1>{html.escape(title)}</h1>
<p>{html.escape(message)}</p>
{extra}
<p class="foot">You can close this window and retry from your MCP client.</p>
</div></body></html>"""
