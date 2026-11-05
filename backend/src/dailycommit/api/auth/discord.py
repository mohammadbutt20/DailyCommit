"""Log in with Discord (OAuth2 authorization-code flow, `identify` scope only).

/auth/discord/login     sets a short-lived state cookie (CSRF) and redirects to Discord
/auth/discord/callback  checks the state, exchanges the code, reads the Discord profile,
                        upserts the user + `discord` identity and starts a normal session

Discord's access token is used once to read the profile and then dropped; we store only the
Discord user id, display name and avatar URL. Registered only when DISCORD_CLIENT_ID and
DISCORD_CLIENT_SECRET are set (see api/main.py).
"""

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from dailycommit.api.auth.sessions import start_session, user_for_identity
from dailycommit.api.deps import DB
from dailycommit.config import settings

router = APIRouter(prefix="/auth/discord", tags=["auth"])

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"
CDN = "https://cdn.discordapp.com"

STATE_COOKIE = "dc_oauth_state"
NEXT_COOKIE = "dc_oauth_next"
STATE_TTL_S = 600
HTTP_TIMEOUT_S = 10.0


class DiscordError(Exception):
    """Discord said no, or answered with something we can't use. Never the user's secrets."""


@dataclass(frozen=True)
class DiscordProfile:
    id: str
    display_name: str
    avatar_url: str


def redirect_uri() -> str:
    return f"{settings.public_url.rstrip('/')}/api/auth/discord/callback"


def safe_next(value: str | None) -> str:
    """Only same-site paths: '/groups' yes; '//evil.com', 'https://evil.com', '/\\evil' no."""
    if not value or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/groups"
    if any(c in value for c in "\r\n\t"):
        return "/groups"
    return value


def authorize_url(state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.discord_client_id,
            "scope": "identify",
            "state": state,
            "redirect_uri": redirect_uri(),
            "prompt": "none",  # returning users skip the authorize screen; new users still see it
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def avatar_url(user: dict) -> str:
    uid, avatar = str(user["id"]), user.get("avatar")
    if avatar:
        ext = "gif" if str(avatar).startswith("a_") else "png"
        return f"{CDN}/avatars/{uid}/{avatar}.{ext}?size=128"
    # Default avatars: new-style usernames use (id >> 22) % 6, legacy discriminators % 5.
    discriminator = str(user.get("discriminator") or "0")
    index = (int(uid) >> 22) % 6 if discriminator == "0" else int(discriminator) % 5
    return f"{CDN}/embed/avatars/{index}.png"


def profile_from(user: dict) -> DiscordProfile:
    if "id" not in user:
        raise DiscordError("Discord profile has no id")
    name = user.get("global_name") or user.get("username") or "Discord user"
    return DiscordProfile(
        id=str(user["id"]), display_name=str(name)[:64], avatar_url=avatar_url(user)
    )


async def fetch_profile(code: str, client: httpx.AsyncClient) -> DiscordProfile:
    """Exchange the authorization code and read the user's profile."""
    token = await client.post(
        TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()},
        auth=(settings.discord_client_id, settings.discord_client_secret.get_secret_value()),
        headers={"Accept": "application/json"},
    )
    if token.status_code != 200:
        raise DiscordError(f"token exchange failed with HTTP {token.status_code}")
    access = token.json().get("access_token")
    if not access:
        raise DiscordError("token response had no access_token")
    me = await client.get(ME_URL, headers={"Authorization": f"Bearer {access}"})
    if me.status_code != 200:
        raise DiscordError(f"profile request failed with HTTP {me.status_code}")
    return profile_from(me.json())


def _set_flow_cookie(response: RedirectResponse, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=STATE_TTL_S,
        httponly=True,
        samesite="lax",  # sent on Discord's top-level redirect back to us
        secure=settings.cookie_secure,
        path="/api/auth/discord",
    )


def _clear_flow_cookies(response: RedirectResponse) -> None:
    for name in (STATE_COOKIE, NEXT_COOKIE):
        response.delete_cookie(name, path="/api/auth/discord")


def _login_error(reason: str) -> RedirectResponse:
    response = RedirectResponse(f"/login?error={reason}", status_code=303)
    _clear_flow_cookies(response)
    return response


@router.get("/login", include_in_schema=False)
async def discord_login(next: str | None = None) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(authorize_url(state), status_code=303)
    _set_flow_cookie(response, STATE_COOKIE, state)
    _set_flow_cookie(response, NEXT_COOKIE, safe_next(next))
    return response


@router.get("/callback", include_in_schema=False)
async def discord_callback(
    request: Request,
    db: DB,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:  # e.g. access_denied: the user clicked Cancel on Discord's screen
        return _login_error("discord_denied")
    expected = request.cookies.get(STATE_COOKIE)
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        return _login_error("discord_state")

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            profile = await fetch_profile(code, client)
    except (DiscordError, httpx.HTTPError, ValueError):
        return _login_error("discord_failed")

    user = await user_for_identity(db, "discord", profile.id, profile.display_name)
    # Keep name and picture in sync with Discord on every login.
    user.display_name = profile.display_name
    user.avatar_url = profile.avatar_url

    response = RedirectResponse(safe_next(request.cookies.get(NEXT_COOKIE)), status_code=303)
    _clear_flow_cookies(response)
    await start_session(db, response, user)
    await db.commit()
    return response
