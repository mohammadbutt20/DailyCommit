"""Discord OAuth helpers, with Discord's HTTP API mocked (httpx.MockTransport)."""

import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from dailycommit.api.auth import discord
from dailycommit.config import settings


@pytest.fixture(autouse=True)
def discord_app(monkeypatch):
    monkeypatch.setattr(settings, "discord_client_id", "client-123")
    monkeypatch.setattr(settings, "discord_client_secret", SecretStr("shh"))
    monkeypatch.setattr(settings, "public_url", "https://commit.example/")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "/groups"),
        ("", "/groups"),
        ("/join/DEMO2026", "/join/DEMO2026"),
        ("/g/3/today?tab=code", "/g/3/today?tab=code"),
        ("//evil.example", "/groups"),
        ("/\\evil.example", "/groups"),
        ("https://evil.example", "/groups"),
        ("javascript:alert(1)", "/groups"),
        ("/ok\r\nSet-Cookie: x=1", "/groups"),
    ],
)
def test_safe_next_only_allows_same_site_paths(value, expected):
    assert discord.safe_next(value) == expected


def test_authorize_url():
    url = urlparse(discord.authorize_url("st4te"))
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == discord.AUTHORIZE_URL
    assert q == {
        "response_type": "code",
        "client_id": "client-123",
        "scope": "identify",
        "state": "st4te",
        "redirect_uri": "https://commit.example/api/auth/discord/callback",
        "prompt": "none",
    }


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        (
            {"id": "80351110224678912", "avatar": "8342729096ea3675442027381ff50dfe"},
            "https://cdn.discordapp.com/avatars/80351110224678912/8342729096ea3675442027381ff50dfe.png?size=128",
        ),
        (
            {"id": "1", "avatar": "a_abc"},
            "https://cdn.discordapp.com/avatars/1/a_abc.gif?size=128",
        ),
        (  # new username system: (id >> 22) % 6
            {"id": "80351110224678912", "avatar": None, "discriminator": "0"},
            f"https://cdn.discordapp.com/embed/avatars/{(80351110224678912 >> 22) % 6}.png",
        ),
        (  # legacy discriminator: discriminator % 5
            {"id": "1", "avatar": None, "discriminator": "1337"},
            "https://cdn.discordapp.com/embed/avatars/2.png",
        ),
    ],
)
def test_avatar_url(user, expected):
    assert discord.avatar_url(user) == expected


def test_profile_prefers_global_name():
    p = discord.profile_from({"id": 42, "username": "ada_l", "global_name": "Ada", "avatar": None})
    assert (p.id, p.display_name) == ("42", "Ada")
    assert discord.profile_from({"id": "42", "username": "ada_l"}).display_name == "ada_l"


def test_profile_without_id_is_rejected():
    with pytest.raises(discord.DiscordError):
        discord.profile_from({"username": "x"})


async def _fetch(handler, code: str) -> discord.DiscordProfile:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await discord.fetch_profile(code, client)


def test_fetch_profile_exchanges_code_then_reads_me():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url == discord.TOKEN_URL:
            return httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer"})
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"id": "7", "username": "bo", "avatar": None})

    profile = asyncio.run(_fetch(handler, "the-code"))

    assert profile.id == "7" and profile.display_name == "bo"
    token_req = seen[0]
    body = parse_qs(token_req.content.decode())
    assert body == {
        "grant_type": ["authorization_code"],
        "code": ["the-code"],
        "redirect_uri": ["https://commit.example/api/auth/discord/callback"],
    }
    # Client credentials go in HTTP Basic auth, not the body.
    assert token_req.headers["Authorization"].startswith("Basic ")
    assert str(seen[1].url) == discord.ME_URL


@pytest.mark.parametrize(
    "responses",
    [
        {"token": httpx.Response(400, json={"error": "invalid_grant"})},
        {"token": httpx.Response(200, json={})},
        {
            "token": httpx.Response(200, json={"access_token": "tok"}),
            "me": httpx.Response(401, json={"message": "401: Unauthorized"}),
        },
    ],
)
def test_fetch_profile_failures_raise_discord_error(responses):
    def handler(request: httpx.Request) -> httpx.Response:
        return responses["token" if request.url == discord.TOKEN_URL else "me"]

    with pytest.raises(discord.DiscordError):
        asyncio.run(_fetch(handler, "bad"))


def test_enabled_only_with_both_credentials(monkeypatch):
    assert settings.discord_enabled
    monkeypatch.setattr(settings, "discord_client_secret", SecretStr(""))
    assert not settings.discord_enabled
