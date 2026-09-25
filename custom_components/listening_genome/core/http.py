"""
Outbound HTTP for the Listening Genome controller (§1.9, §3.8).

Every external call (Last.fm, ListenBrainz, and the MusicBrainz fallback path) goes through the
:class:`HttpClient` protocol so tests can inject a fixture-backed implementation and never touch
the network. :class:`AiohttpClient` is the real implementation, built on a shared ``aiohttp.ClientSession`` with
a per-host :class:`~.compat.Throttler`.

Ported from the fork by swapping ``mass.http_session`` for an injected ``aiohttp.ClientSession``,
which under Home Assistant comes from ``async_get_clientsession(hass)``. The :class:`HttpClient`
protocol is what every importer and enricher is written against, and it is the seam their tests
inject a fixture through.

One addition: an identifying ``User-Agent``. In the fork every request left through Music
Assistant's session and carried MA's identity. Home Assistant's shared session sends a generic
one, and MusicBrainz's API rules require ``Application/version ( contact )`` and throttle or
refuse clients that do not identify themselves. :func:`user_agent` builds that string and
:class:`AiohttpClient` sends it on every request it makes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from ..compat import Throttler, json_loads
from .constants import PROJECT_URL, USER_AGENT_PRODUCT

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiohttp import ClientSession


class HttpClient(Protocol):
    """Minimal async HTTP surface used by every Genome importer/enricher."""

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Issue a ``GET`` request and return the JSON-decoded body.

        :param url: The absolute URL to request.
        :param params: Optional query-string parameters.
        :param headers: Optional extra request headers.
        """
        ...

    async def post_json(
        self,
        url: str,
        *,
        json: Any,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Issue a ``POST`` request with a JSON body and return the JSON-decoded response.

        :param url: The absolute URL to request.
        :param json: The JSON-serializable request body.
        :param headers: Optional extra request headers.
        """
        ...


def user_agent(version: str) -> str:
    """
    Return the identifying ``User-Agent`` MusicBrainz asks for: ``Application/version ( url )``.

    :param version: The integration's version, as its ``manifest.json`` states it.
    """
    return f"{USER_AGENT_PRODUCT}/{version} ( {PROJECT_URL} )"


def describe_http_error(err: BaseException) -> str:
    """
    Describe a failed request in a few words fit for a log line, never including the URL.

    ``aiohttp.ClientResponseError`` carries ``status``; timeouts and connection failures are
    named by kind. The URL is left out on purpose (Last.fm puts its API key in the query).
    """
    status = getattr(err, "status", None)
    if isinstance(status, int):
        reason = getattr(err, "message", "") or ""
        return f"HTTP {status}{f' {reason}' if reason else ''}"
    if isinstance(err, TimeoutError):
        return "timed out"
    name = type(err).__name__
    if "Connect" in name or isinstance(err, OSError):
        return f"connection failed ({name})"
    return name


class AiohttpClient:
    """``HttpClient`` backed by a shared ``aiohttp.ClientSession`` with a per-host throttler."""

    def __init__(
        self,
        session: ClientSession,
        *,
        rate_limit: int,
        period: float,
        user_agent: str | None = None,
    ) -> None:
        """
        Initialize the client.

        :param session: The shared client session to issue requests on.
        :param rate_limit: Maximum number of requests allowed per ``period``.
        :param period: The throttling window, in seconds.
        :param user_agent: Sent as ``User-Agent`` on every request (see :func:`user_agent`).
            Per-request headers are merged over it, so a caller can still override it.
        """
        self.session = session
        self.user_agent = user_agent
        self._throttler = Throttler(rate_limit=rate_limit, period=period)

    def _headers(self, headers: Mapping[str, str] | None) -> dict[str, str] | None:
        """Return the request headers: the User-Agent, then anything the caller passed."""
        merged: dict[str, str] = {}
        if self.user_agent:
            merged["User-Agent"] = self.user_agent
        if headers:
            merged.update(headers)
        return merged or None

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Issue a throttled ``GET`` request and return the JSON-decoded body."""
        async with (
            self._throttler,
            self.session.get(url, params=params, headers=self._headers(headers)) as resp,
        ):
            resp.raise_for_status()
            return await resp.json(loads=json_loads)

    async def post_json(
        self,
        url: str,
        *,
        json: Any,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Issue a throttled ``POST`` request with a JSON body and return the decoded response."""
        async with (
            self._throttler,
            self.session.post(url, json=json, headers=self._headers(headers)) as resp,
        ):
            resp.raise_for_status()
            return await resp.json(loads=json_loads)


__all__ = ["AiohttpClient", "HttpClient", "describe_http_error", "user_agent"]
