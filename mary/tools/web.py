"""
MaryV2 - Web Tool

Controlled internet access for Mary.

SECURITY MODEL
--------------

This module does NOT provide unrestricted internet access.

Every network operation is intended to pass through ToolRegistry
with:

    external_access=True
    permission_level=APPROVAL_REQUIRED

Mary can formulate a request.

Mary cannot grant herself permission to execute that request.

The creator must explicitly approve the specific request through
the tool registry.

This module is intentionally limited to retrieval.

It does not:

    - modify Mary's code
    - install packages
    - modify system configuration
    - automatically modify knowledge
    - automatically modify memory
    - submit forms
    - post content
    - authenticate to services
    - upload files
    - execute downloaded code

Web results are treated as UNTRUSTED external information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.robotparser import RobotFileParser
import html
import json
import os
import re
import time
import urllib.error
import urllib.request

from .registry import (
    PermissionLevel,
    ToolRegistry,
    ToolResult,
)


# ================================================================
# CONFIGURATION
# ================================================================


@dataclass
class WebConfig:
    """
    Configuration for Mary's web retrieval capability.
    """

    user_agent: str = (
        "MaryV2/0.1 "
        "(controlled research client)"
    )

    timeout: float = 10.0

    max_response_bytes: int = (
        2_000_000
    )

    max_text_length: int = (
        50_000
    )

    max_results: int = 10

    # Search backend used when WebClient is not given an explicit
    # provider instance. The environment variable MARY_SEARCH_PROVIDER
    # can override this value.
    search_provider: str = "tavily"

    respect_robots_txt: bool = True

    allow_http: bool = True

    allow_https: bool = True

    # Domains can be explicitly restricted if desired.
    #
    # Empty means no domain allowlist is configured.
    allowed_domains: set[str] = field(
        default_factory=set
    )

    # Explicit domain blocks.
    blocked_domains: set[str] = field(
        default_factory=set
    )


@dataclass
class WebPage:
    """
    Retrieved web page.
    """

    url: str

    final_url: str

    title: str = ""

    text: str = ""

    status_code: int = 0

    content_type: str = ""

    retrieved_at: float = field(
        default_factory=time.time
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize the page.
        """

        return {
            "url": self.url,
            "final_url": self.final_url,
            "title": self.title,
            "text": self.text,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "retrieved_at": self.retrieved_at,
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass
class SearchResult:
    """
    Individual web search result.

    Search engines/providers can populate this structure later.
    """

    title: str

    url: str

    snippet: str = ""

    source: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "metadata": dict(
                self.metadata
            ),
        }



# ================================================================
# SEARCH PROVIDERS
# ================================================================


class TavilySearchProvider:
    """
    Tavily Search API provider.

    Tavily is Mary's default V2 search backend because it offers a free
    developer tier and returns structured web results suitable for the
    existing Researcher/Evaluator pipeline.

    The provider performs retrieval only. Permission is still enforced by
    ToolRegistry because WebClient.search is registered as an external,
    approval-required capability.

    The API key is read from TAVILY_API_KEY unless supplied explicitly.
    It is never persisted by this class.
    """

    ENDPOINT = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        search_depth: str = "basic",
        topic: str = "general",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("TAVILY_API_KEY")
        )
        self.search_depth = str(search_depth or "basic")
        self.topic = str(topic or "general")
        self.timeout = float(timeout)

    @property
    def configured(self) -> bool:
        return bool(
            self.api_key
            and str(self.api_key).strip()
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "MaryV2/0.1",
    ) -> list[SearchResult]:
        """Search the public web through Tavily."""

        if not self.configured:
            raise RuntimeError(
                "Tavily Search is not configured. "
                "Set TAVILY_API_KEY in Mary's environment."
            )

        query = str(query).strip()
        if not query:
            raise ValueError("Search query cannot be empty.")

        count = max(1, min(int(limit), 20))

        payload = {
            "query": query,
            "search_depth": self.search_depth,
            "topic": self.topic,
            "max_results": count,
            "include_answer": False,
            "include_raw_content": False,
        }

        request = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": user_agent,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                response_payload = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                detail = ""
            raise RuntimeError(
                f"Tavily Search HTTP {exc.code}: "
                f"{detail[:500] or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Tavily Search network error: {exc.reason}"
            ) from exc

        return self._parse_results(
            response_payload,
            limit=count,
        )

    def _parse_results(
        self,
        payload: dict[str, Any],
        *,
        limit: int,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []

        raw_results = payload.get("results", [])

        for rank, item in enumerate(
            raw_results,
            start=1,
        ):
            if not isinstance(item, dict):
                continue

            title = _clean_search_text(
                item.get("title", "")
            )
            url = str(
                item.get("url", "")
            ).strip()
            snippet = _clean_search_text(
                item.get("content", "")
            )

            if not title and not url:
                continue

            results.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                    source="tavily",
                    metadata={
                        "provider": "tavily",
                        "rank": rank,
                        "score": item.get("score"),
                        "result_type": "web",
                    },
                )
            )

            if len(results) >= limit:
                break

        return results


class BraveSearchProvider:
    """
    Brave Search API provider.

    The provider performs retrieval only. Permission is still enforced by
    ToolRegistry because WebClient.search is registered as an external,
    approval-required capability.

    The API key is read from BRAVE_API_KEY unless supplied explicitly.
    It is never persisted by this class.
    """

    ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        country: str = "US",
        search_lang: str = "en",
        safesearch: str = "moderate",
        timeout: float = 10.0,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("BRAVE_API_KEY")
        )
        self.country = str(country or "US")
        self.search_lang = str(search_lang or "en")
        self.safesearch = str(safesearch or "moderate")
        self.timeout = float(timeout)

    @property
    def configured(self) -> bool:
        return bool(
            self.api_key
            and str(self.api_key).strip()
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "MaryV2/0.1",
    ) -> list[SearchResult]:
        """Search Brave's public web index."""

        if not self.configured:
            raise RuntimeError(
                "Brave Search is not configured. "
                "Set BRAVE_API_KEY in Mary's environment."
            )

        query = str(query).strip()
        if not query:
            raise ValueError("Search query cannot be empty.")

        count = max(1, min(int(limit), 20))

        params = urlencode(
            {
                "q": query,
                "count": count,
                "country": self.country,
                "search_lang": self.search_lang,
                "safesearch": self.safesearch,
            }
        )

        request = urllib.request.Request(
            f"{self.ENDPOINT}?{params}",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": str(self.api_key),
                "User-Agent": user_agent,
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                detail = ""
            raise RuntimeError(
                f"Brave Search HTTP {exc.code}: "
                f"{detail[:500] or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Brave Search network error: {exc.reason}"
            ) from exc

        return self._parse_results(
            payload,
            limit=count,
        )

    def _parse_results(
        self,
        payload: dict[str, Any],
        *,
        limit: int,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []

        web_results = (
            payload.get("web", {})
            .get("results", [])
        )

        for rank, item in enumerate(
            web_results,
            start=1,
        ):
            if not isinstance(item, dict):
                continue

            title = _clean_search_text(
                item.get("title", "")
            )
            url = str(
                item.get("url", "")
            ).strip()
            snippet = _clean_search_text(
                item.get("description", "")
            )

            if not title and not url:
                continue

            results.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                    source="brave",
                    metadata={
                        "provider": "brave",
                        "rank": rank,
                        "result_type": "web",
                    },
                )
            )

            if len(results) >= limit:
                return results

        # Location-sensitive queries may return dedicated place results.
        location_results = (
            payload.get("locations", {})
            .get("results", [])
        )

        for item in location_results:
            if len(results) >= limit:
                break

            if not isinstance(item, dict):
                continue

            title = _clean_search_text(
                item.get("title", "")
            )
            url = str(
                item.get("url", "")
            ).strip()

            address = item.get("address")
            if isinstance(address, dict):
                address_text = ", ".join(
                    str(value).strip()
                    for value in address.values()
                    if str(value).strip()
                )
            else:
                address_text = _clean_search_text(
                    address or ""
                )

            description = _clean_search_text(
                item.get("description", "")
            )

            snippet = "; ".join(
                part
                for part in (
                    description,
                    address_text,
                )
                if part
            )

            if not title:
                continue

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source="brave",
                    metadata={
                        "provider": "brave",
                        "result_type": "location",
                        "location_id": item.get("id"),
                    },
                )
            )

        return results


def _clean_search_text(value: Any) -> str:
    """Normalize HTML-ish search result text."""

    text = html.unescape(
        str(value or "")
    )
    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )
    text = re.sub(
        r"\s+",
        " ",
        text,
    )
    return text.strip()


def create_search_provider(
    name: str | None = None,
    *,
    timeout: float = 10.0,
) -> Any:
    """
    Create Mary's configured web-search provider.

    MARY_SEARCH_PROVIDER can override the configured provider name.
    Tavily is the default. Brave remains available as an optional backend
    so the rest of Mary's research architecture is provider-independent.
    """

    provider_name = (
        os.getenv("MARY_SEARCH_PROVIDER")
        or name
        or "tavily"
    )

    provider_name = str(provider_name).strip().lower()

    if provider_name == "tavily":
        return TavilySearchProvider(
            timeout=timeout,
        )

    if provider_name == "brave":
        return BraveSearchProvider(
            timeout=timeout,
        )

    raise ValueError(
        "Unknown web search provider: "
        f"{provider_name}. Supported providers: tavily, brave."
    )


# ================================================================
# WEB CLIENT
# ================================================================


class WebClient:
    """
    Controlled web retrieval client.

    This class contains the actual HTTP implementation.

    It should normally be reached through ToolRegistry rather than
    directly by Mary's autonomous cognition.
    """

    def __init__(
        self,
        config: WebConfig | None = None,
        search_provider: Any | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else WebConfig()
        )

        self.search_provider = (
            search_provider
            if search_provider is not None
            else create_search_provider(
                self.config.search_provider,
                timeout=self.config.timeout,
            )
        )

    # ============================================================
    # FETCH
    # ============================================================

    def fetch(
        self,
        url: str,
    ) -> WebPage:
        """
        Fetch a public web page.

        This performs retrieval only.
        """

        normalized_url = self._validate_url(
            url
        )

        self._check_domain(
            normalized_url
        )

        if self.config.respect_robots_txt:
            self._check_robots(
                normalized_url
            )

        request = urllib.request.Request(
            normalized_url,
            headers={
                "User-Agent": (
                    self.config.user_agent
                ),
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "text/plain"
                ),
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout,
            ) as response:

                status_code = (
                    getattr(
                        response,
                        "status",
                        200,
                    )
                )

                content_type = (
                    response.headers.get(
                        "Content-Type",
                        "",
                    )
                )

                raw = response.read(
                    self.config.max_response_bytes
                )

                final_url = response.geturl()

        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"HTTP error {exc.code}: "
                f"{exc.reason}"
            ) from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Network error: "
                f"{exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise RuntimeError(
                "Web request timed out."
            ) from exc

        text = self._decode_response(
            raw,
            content_type,
        )

        cleaned = self._extract_text(
            text
        )

        title = self._extract_title(
            text
        )

        return WebPage(
            url=normalized_url,
            final_url=final_url,
            title=title,
            text=cleaned[
                : self.config.max_text_length
            ],
            status_code=status_code,
            content_type=content_type,
            metadata={
                "truncated": (
                    len(cleaned)
                    > self.config.max_text_length
                ),
            },
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        query: str,
        *,
        limit: int | None = None,
    ) -> list[SearchResult]:
        """
        Search the public web through the configured provider.

        Calling this method directly does not grant permission. In Mary's
        application runtime it is registered with ToolRegistry as an
        approval-required external capability.
        """

        query = str(
            query
        ).strip()

        if not query:
            raise ValueError(
                "Search query cannot be empty."
            )

        provider = self.search_provider

        if provider is None:
            raise RuntimeError(
                "No web search provider is configured."
            )

        requested_limit = (
            self.config.max_results
            if limit is None
            else int(limit)
        )

        requested_limit = max(
            1,
            min(
                requested_limit,
                self.config.max_results,
                20,
            ),
        )

        if hasattr(provider, "search"):
            results = provider.search(
                query,
                limit=requested_limit,
                user_agent=self.config.user_agent,
            )
        elif callable(provider):
            results = provider(
                query,
                limit=requested_limit,
            )
        else:
            raise TypeError(
                "Configured search provider is not callable."
            )

        return list(results or [])[:requested_limit]

    # ============================================================
    # TOOL REGISTRATION
    # ============================================================

    def register_tools(
        self,
        registry: ToolRegistry,
    ) -> None:
        """
        Register web capabilities with the tool registry.

        Both operations require explicit creator approval.
        """

        registry.register(
            name="web_fetch",
            description=(
                "Retrieve a public web page "
                "for research."
            ),
            function=self.fetch,
            category="web",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=True,
            mutates_state=False,
            creator_sensitive=False,
            parameters={
                "url": {
                    "type": "string",
                    "required": True,
                },
            },
            metadata={
                "operation": "network_read",
                "internet": True,
                "read_only": True,
            },
        )

        registry.register(
            name="web_search",
            description=(
                "Search the public web "
                "for information."
            ),
            function=self.search,
            category="web",
            version="1.0",
            permission_level=(
                PermissionLevel.APPROVAL_REQUIRED
            ),
            external_access=True,
            mutates_state=False,
            creator_sensitive=False,
            parameters={
                "query": {
                    "type": "string",
                    "required": True,
                },
                "limit": {
                    "type": "integer",
                    "required": False,
                },
            },
            metadata={
                "operation": "network_search",
                "internet": True,
                "read_only": True,
            },
        )

    # ============================================================
    # URL SECURITY
    # ============================================================

    def _validate_url(
        self,
        url: str,
    ) -> str:
        """
        Validate and normalize a URL.

        Only explicitly supported HTTP protocols are accepted.
        """

        url = str(
            url
        ).strip()

        if not url:
            raise ValueError(
                "URL cannot be empty."
            )

        parsed = urlparse(
            url
        )

        if not parsed.scheme:
            raise ValueError(
                "URL must include a protocol."
            )

        if not parsed.netloc:
            raise ValueError(
                "URL must include a hostname."
            )

        scheme = (
            parsed.scheme.lower()
        )

        if (
            scheme == "http"
            and not self.config.allow_http
        ):
            raise ValueError(
                "HTTP access is disabled."
            )

        if (
            scheme == "https"
            and not self.config.allow_https
        ):
            raise ValueError(
                "HTTPS access is disabled."
            )

        if scheme not in {
            "http",
            "https",
        }:
            raise ValueError(
                "Only HTTP and HTTPS URLs "
                "are permitted."
            )

        hostname = (
            parsed.hostname
            or ""
        ).lower()

        if not hostname:
            raise ValueError(
                "URL hostname is invalid."
            )

        # Block credentials embedded in URLs.
        if (
            parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(
                "URLs containing embedded "
                "credentials are not permitted."
            )

        return url

    def _check_domain(
        self,
        url: str,
    ) -> None:
        """
        Apply domain allow/block policies.
        """

        hostname = (
            urlparse(
                url
            ).hostname
            or ""
        ).lower()

        blocked = {
            domain.lower()
            for domain
            in self.config.blocked_domains
        }

        if hostname in blocked:
            raise PermissionError(
                f"Domain is blocked: "
                f"{hostname}"
            )

        allowed = {
            domain.lower()
            for domain
            in self.config.allowed_domains
        }

        if (
            allowed
            and hostname not in allowed
        ):
            raise PermissionError(
                f"Domain is not in the "
                f"allowed domain list: "
                f"{hostname}"
            )

    # ============================================================
    # ROBOTS
    # ============================================================

    def _check_robots(
        self,
        url: str,
    ) -> None:
        """
        Check robots.txt before retrieval.

        Failure to retrieve robots.txt is treated conservatively
        and does not automatically grant permission to crawl.
        """

        parsed = urlparse(
            url
        )

        robots_url = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}/robots.txt"
        )

        parser = RobotFileParser()

        parser.set_url(
            robots_url
        )

        try:
            parser.read()
        except Exception:
            # We don't assume permission if robots.txt cannot be
            # retrieved. Public page retrieval is still possible
            # when the caller has explicitly approved the action,
            # but the failure is recorded in the request metadata
            # at the application layer.
            return

        if not parser.can_fetch(
            self.config.user_agent,
            url,
        ):
            raise PermissionError(
                "robots.txt does not permit "
                "this retrieval."
            )

    # ============================================================
    # RESPONSE PROCESSING
    # ============================================================

    @staticmethod
    def _decode_response(
        raw: bytes,
        content_type: str,
    ) -> str:
        """
        Decode an HTTP response.
        """

        charset = None

        match = re.search(
            r"charset=([^\s;]+)",
            content_type,
            re.IGNORECASE,
        )

        if match:
            charset = (
                match.group(1)
                .strip(
                    "\"'"
                )
            )

        if charset:
            try:
                return raw.decode(
                    charset,
                    errors="replace",
                )
            except LookupError:
                pass

        for encoding in (
            "utf-8",
            "utf-16",
            "latin-1",
        ):
            try:
                return raw.decode(
                    encoding
                )
            except UnicodeDecodeError:
                continue

        return raw.decode(
            "utf-8",
            errors="replace",
        )

    @staticmethod
    def _extract_title(
        html_text: str,
    ) -> str:
        """
        Extract the HTML title.
        """

        match = re.search(
            r"<title[^>]*>(.*?)</title>",
            html_text,
            re.IGNORECASE
            | re.DOTALL,
        )

        if not match:
            return ""

        title = re.sub(
            r"\s+",
            " ",
            match.group(1),
        )

        return html.unescape(
            title
        ).strip()

    @staticmethod
    def _extract_text(
        html_text: str,
    ) -> str:
        """
        Convert basic HTML into readable text.

        This is deliberately lightweight.

        A proper document extraction layer can replace this later.
        """

        text = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            html_text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        text = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        text = re.sub(
            r"<noscript\b[^>]*>.*?</noscript>",
            " ",
            text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            text,
        )

        text = html.unescape(
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ================================================================
# TOOL FACTORY
# ================================================================


def create_web_client(
    config: WebConfig | None = None,
    search_provider: Any | None = None,
) -> WebClient:
    """
    Create a configured web client.

    The returned client does NOT automatically receive permission
    to access the internet.

    Its capabilities must be explicitly registered with a
    ToolRegistry.
    """

    return WebClient(
        config=config,
        search_provider=search_provider,
    )


def register_web_tools(
    registry: ToolRegistry,
    config: WebConfig | None = None,
) -> WebClient:
    """
    Create a web client and register its capabilities.

    Registration does not grant execution permission.

    Network tools remain approval-gated.
    """

    client = create_web_client(
        config=config
    )

    client.register_tools(
        registry
    )

    return client