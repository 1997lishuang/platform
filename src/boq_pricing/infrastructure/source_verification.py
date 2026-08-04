from __future__ import annotations

import re
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceVerification:
    url: str
    reachable: bool
    status_code: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    reason: str | None = None
    specific_page: bool = True
    text_excerpt: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def verify_source_url(url: str, timeout_seconds: int = 6) -> SourceVerification:
    if not is_http_url(url):
        return SourceVerification(url=url, reachable=False, reason="不是 http/https 链接", specific_page=False)
    if not is_specific_source_url(url):
        return SourceVerification(url=url, reachable=False, reason="来源链接不是具体报价/公告/商品页面", specific_page=False)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    head_result = _request(url, "HEAD", headers, timeout_seconds)
    if head_result.reachable:
        get_result = _request(url, "GET", {**headers, "Range": "bytes=0-65535"}, timeout_seconds)
        return get_result if get_result.reachable else head_result
    return _request(url, "GET", {**headers, "Range": "bytes=0-65535"}, timeout_seconds)


def _request(url: str, method: str, headers: dict[str, str], timeout_seconds: int) -> SourceVerification:
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200) or 200)
            content_type = response.headers.get("Content-Type")
            text_excerpt = None
            if method == "GET":
                text_excerpt = extract_text_excerpt(response.read(65536), content_type)
            final_url = response.geturl()
            return SourceVerification(
                url=url,
                reachable=200 <= status < 400 and is_specific_source_url(final_url),
                status_code=status,
                final_url=final_url,
                content_type=content_type,
                reason=None if 200 <= status < 400 else f"HTTP {status}",
                specific_page=is_specific_source_url(final_url),
                text_excerpt=text_excerpt,
            )
    except urllib.error.HTTPError as exc:
        return SourceVerification(
            url=url,
            reachable=200 <= exc.code < 400 and is_specific_source_url(exc.geturl()),
            status_code=exc.code,
            final_url=exc.geturl(),
            content_type=exc.headers.get("Content-Type") if exc.headers else None,
            reason=f"HTTP {exc.code}",
            specific_page=is_specific_source_url(exc.geturl()),
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return SourceVerification(url=url, reachable=False, reason=str(exc))


def is_http_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def is_specific_source_url(value: str | None) -> bool:
    if not is_http_url(value):
        return False
    parsed = urlparse(value)
    path = (parsed.path or "").strip("/")
    if not path:
        return False
    lowered = path.lower()
    segments = [segment for segment in lowered.split("/") if segment]
    generic_segments = {
        "search",
        "s",
        "list",
        "lists",
        "category",
        "categories",
        "product",
        "products",
        "news",
        "article",
        "zt",
    }
    if len(segments) == 1 and segments[0] in generic_segments:
        return False
    if any(flag in lowered for flag in ("search", "keyword", "query=")):
        return False
    return True


def extract_text_excerpt(raw: bytes, content_type: str | None) -> str | None:
    if content_type and not any(kind in content_type.lower() for kind in ("text", "html", "json", "xml")):
        return None
    text = raw.decode("utf-8", errors="ignore")
    if not text:
        text = raw.decode("gb18030", errors="ignore")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1200] if text else None
