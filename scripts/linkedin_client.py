#!/usr/bin/env python3
"""
LinkedIn client — OAuth 2.0 authentication, read own posts, create posts.

SETUP (one-time)
────────────────
1. Go to https://www.linkedin.com/developers/apps/new and create an app.
2. Under "Auth" tab → add Redirect URL:  http://localhost:8080/callback
3. Under "Products" tab → request:
     • "Sign In with LinkedIn using OpenID Connect"  (gives openid, profile, email)
     • "Share on LinkedIn"                           (gives w_member_social)
     • "Marketing Developer Platform" (optional)     (gives r_member_social for reading posts)
4. Copy your Client ID and Client Secret into .env:
     LINKEDIN_CLIENT_ID=your_client_id
     LINKEDIN_CLIENT_SECRET=your_client_secret

USAGE
─────
  python scripts/linkedin_client.py auth                    # OAuth login (opens browser)
  python scripts/linkedin_client.py me                      # Show your profile
  python scripts/linkedin_client.py posts                   # List your recent posts
  python scripts/linkedin_client.py posts --limit 20        # Fetch more posts
  python scripts/linkedin_client.py post "Your post text"   # Publish a post
  python scripts/linkedin_client.py token                   # Show stored token info

NOTE ON SCOPES
──────────────
"r_member_social" (reading your feed posts) requires LinkedIn's "Marketing Developer
Platform" product approval. Without it, `posts` will still work for posts you authored
but may return empty. Posting always works with "Share on LinkedIn" approved.
"""

import argparse
import http.server
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080/callback"
TOKEN_FILE = Path.home() / ".linkedin_token.json"

# Scopes — "r_member_social" may require Marketing Developer Platform approval
SCOPES = ["openid", "profile", "email", "w_member_social", "r_member_social"]

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
API_BASE = "https://api.linkedin.com"


# ── Token storage ──────────────────────────────────────────────────────────────
def save_token(token_data: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    print(f"  Token saved → {TOKEN_FILE}")


def load_token() -> dict | None:
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
        if data.get("expires_at", 0) < time.time():
            print("Stored token has expired — re-authenticating.")
            return None
        return data
    except (json.JSONDecodeError, KeyError):
        return None


# ── OAuth 2.0 flow ─────────────────────────────────────────────────────────────
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth callback code."""

    code: str | None = None
    error: str | None = None
    state_received: str | None = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _CallbackHandler.code = params["code"][0]
            _CallbackHandler.state_received = params.get("state", [""])[0]
            self._html("Authentication successful! You can close this tab.")
        elif "error" in params:
            desc = params.get("error_description", ["Unknown error"])[0]
            _CallbackHandler.error = urllib.parse.unquote_plus(desc)
            self._html(f"Authentication failed: {_CallbackHandler.error}")
        else:
            self._html("Unexpected callback — no code or error received.")

    def _html(self, message: str):
        body = (
            f"<html><body style='font-family:sans-serif;padding:2rem'>"
            f"<h2>{message}</h2></body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass  # suppress access log noise


def authenticate() -> dict:
    """Run the full OAuth 2.0 authorization-code flow and return token data."""
    _require_credentials()

    state = secrets.token_urlsafe(16)
    # Attempt r_member_social first; fall back without it if LinkedIn rejects
    scopes_to_try = [SCOPES, [s for s in SCOPES if s != "r_member_social"]]

    for scopes in scopes_to_try:
        _CallbackHandler.code = None
        _CallbackHandler.error = None

        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(scopes),
            "state": state,
        }
        auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

        server = http.server.HTTPServer(("localhost", 8080), _CallbackHandler)
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()

        print(f"\nOpening LinkedIn authentication in your browser…")
        print(f"  Scopes requested: {', '.join(scopes)}")
        print(f"  Callback:         {REDIRECT_URI}\n")
        webbrowser.open(auth_url)
        thread.join(timeout=120)

        if _CallbackHandler.error:
            if "r_member_social" in _CallbackHandler.error and scopes == SCOPES:
                print("  r_member_social scope rejected — retrying without it.")
                continue
            raise SystemExit(f"OAuth error: {_CallbackHandler.error}")

        if not _CallbackHandler.code:
            raise SystemExit("No auth code received within 120 seconds. Try again.")

        break  # got a code

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": _CallbackHandler.code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    _check_response(resp)
    token = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 5_184_000)
    save_token(token)
    return token


def get_token() -> dict:
    token = load_token()
    if token:
        return token
    print("No valid token found — starting authentication.")
    return authenticate()


# ── API helpers ────────────────────────────────────────────────────────────────
def _headers(token: dict) -> dict:
    return {
        "Authorization": f"Bearer {token['access_token']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }


def _check_response(resp: requests.Response) -> None:
    if not resp.ok:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise SystemExit(
            f"LinkedIn API error {resp.status_code}: "
            f"{json.dumps(detail, indent=2) if isinstance(detail, dict) else detail}"
        )


def api_get(path: str, params: dict | None = None, *, version: str = "v2") -> dict:
    token = get_token()
    url = f"{API_BASE}/{version}/{path}" if not path.startswith("http") else path
    resp = requests.get(url, headers=_headers(token), params=params or {}, timeout=30)
    _check_response(resp)
    return resp.json()


def api_post_json(path: str, body: dict, *, version: str = "v2") -> dict | None:
    token = get_token()
    url = f"{API_BASE}/{version}/{path}" if not path.startswith("http") else path
    h = {**_headers(token), "Content-Type": "application/json"}
    resp = requests.post(url, headers=h, json=body, timeout=30)
    _check_response(resp)
    return resp.json() if resp.content else None


# ── Commands ───────────────────────────────────────────────────────────────────
def cmd_auth():
    token = authenticate()
    granted = token.get("scope", "N/A")
    expires_days = token.get("expires_in", 0) // 86400
    print(f"\nAuthenticated successfully.")
    print(f"  Scopes granted: {granted}")
    print(f"  Token valid for: ~{expires_days} days")


def cmd_me():
    profile = api_get("userinfo")
    print(f"\nLinkedIn profile:")
    print(f"  Name:    {profile.get('name', 'N/A')}")
    print(f"  Email:   {profile.get('email', 'N/A')}")
    print(f"  Locale:  {profile.get('locale', 'N/A')}")
    print(f"  Sub:     {profile.get('sub', 'N/A')}")
    return profile


def cmd_posts(limit: int = 10):
    profile = api_get("userinfo")
    person_id = profile["sub"]
    author_urn = f"urn:li:person:{person_id}"

    print(f"\nFetching posts for {profile.get('name', person_id)}…")
    data = api_get(
        "posts",
        params={"author": author_urn, "q": "author", "count": limit},
        version="rest",
    )
    posts = data.get("elements", [])
    if not posts:
        print(
            "\nNo posts returned.\n"
            "This can happen if:\n"
            "  • You have no posts yet\n"
            "  • r_member_social scope was not granted (requires Marketing Developer Platform)\n"
            "  • Your LinkedIn Developer App is still in review\n"
        )
        return

    print(f"\n{len(posts)} post(s):\n")
    for i, post in enumerate(posts, 1):
        # Newer /rest/posts format
        text = post.get("commentary", "")
        # Older ugcPosts format fallback
        if not text:
            share = post.get("specificContent", {}).get(
                "com.linkedin.ugc.ShareContent", {}
            )
            text = share.get("shareCommentary", {}).get("text", "(no text)")

        created_ms = post.get("createdAt", post.get("created", {}).get("time", 0))
        created_str = ""
        if created_ms:
            import datetime
            created_str = datetime.datetime.fromtimestamp(
                created_ms / 1000, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")

        state = post.get("lifecycleState", "")
        print(f"  [{i}] {str(text)[:140]}")
        if created_str:
            print(f"       {created_str}  |  {state}")
        print()


def cmd_post(text: str):
    profile = api_get("userinfo")
    person_id = profile["sub"]
    author_urn = f"urn:li:person:{person_id}"

    body = {
        "author": author_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    result = api_post_json("posts", body, version="rest") or {}
    post_id = result.get("id", "")
    print(f"\nPost published successfully!")
    if post_id:
        print(f"  Post ID: {post_id}")
        print(f"  View at: https://www.linkedin.com/feed/update/{post_id}/")


def cmd_token():
    token = load_token()
    if not token:
        print("No stored token. Run: python scripts/linkedin_client.py auth")
        return
    import datetime
    expires = datetime.datetime.fromtimestamp(
        token["expires_at"], tz=datetime.timezone.utc
    )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    days_left = (expires - now).days
    print(f"\nStored token:")
    print(f"  Scopes:     {token.get('scope', 'N/A')}")
    print(f"  Expires:    {expires.strftime('%Y-%m-%d')}  ({days_left} days left)")
    print(f"  Token file: {TOKEN_FILE}")


# ── Guards ─────────────────────────────────────────────────────────────────────
def _require_credentials():
    missing = []
    if not CLIENT_ID:
        missing.append("LINKEDIN_CLIENT_ID")
    if not CLIENT_SECRET:
        missing.append("LINKEDIN_CLIENT_SECRET")
    if missing:
        raise SystemExit(
            f"Missing environment variable(s): {', '.join(missing)}\n\n"
            "Steps:\n"
            "  1. Create an app at https://www.linkedin.com/developers/apps/new\n"
            "  2. Add redirect URL: http://localhost:8080/callback\n"
            "  3. Request products: 'Sign In with LinkedIn' + 'Share on LinkedIn'\n"
            "  4. Add to .env:\n"
            "       LINKEDIN_CLIENT_ID=<your-client-id>\n"
            "       LINKEDIN_CLIENT_SECRET=<your-client-secret>\n"
        )


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn CLI — read and post to your LinkedIn account",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/linkedin_client.py auth\n"
            "  python scripts/linkedin_client.py me\n"
            "  python scripts/linkedin_client.py posts\n"
            "  python scripts/linkedin_client.py posts --limit 20\n"
            '  python scripts/linkedin_client.py post "Hello from PrismRAG!"\n'
            "  python scripts/linkedin_client.py token\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="Authenticate via LinkedIn OAuth (opens browser)")
    sub.add_parser("me", help="Show your LinkedIn profile info")

    posts_p = sub.add_parser("posts", help="List your recent LinkedIn posts")
    posts_p.add_argument("--limit", type=int, default=10, help="Max posts to fetch (default: 10)")

    post_p = sub.add_parser("post", help="Publish a new LinkedIn post")
    post_p.add_argument("text", help="Post text content (use quotes for multi-word text)")

    sub.add_parser("token", help="Show stored token status and expiry")

    args = parser.parse_args()

    dispatch = {
        "auth": cmd_auth,
        "me": cmd_me,
        "token": cmd_token,
    }
    if args.cmd in dispatch:
        dispatch[args.cmd]()
    elif args.cmd == "posts":
        cmd_posts(args.limit)
    elif args.cmd == "post":
        cmd_post(args.text)


if __name__ == "__main__":
    main()
