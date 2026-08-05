from __future__ import annotations

import json
import os
import re
import socket
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from boq_pricing.parsing.features import informative_features


@dataclass(frozen=True)
class MarketQuoteRequest:
    item_name: str
    unit: str | None
    features: dict[str, str]
    region: str | None = None
    price_month: str | None = None
    standard: str | None = None
    item_code: str | None = None
    quantity: str | None = None
    work_content: str | None = None
    remark: str | None = None


@dataclass(frozen=True)
class MarketQuoteResult:
    provider: str
    model: str
    item_name: str
    unit: str | None
    features: dict[str, str]
    region_code: str | None
    price_min: Decimal | None
    price_max: Decimal | None
    recommended_price: Decimal | None
    tax_included: bool
    confidence: Decimal
    source_urls: list[str]
    assumptions: dict[str, Any]
    raw_response: str


@dataclass(frozen=True)
class SupplierMarketQuote:
    supplier: str
    brand: str | None
    price: Decimal | None
    unit: str | None
    source_url: str | None
    source_title: str | None
    evidence: str | None
    tax_included: bool


@dataclass(frozen=True)
class SupplierMarketQuoteResult:
    provider: str
    model: str
    item_name: str
    unit: str | None
    features: dict[str, str]
    region_code: str | None
    recommended_price: Decimal | None
    confidence: Decimal
    quotes: list[SupplierMarketQuote]
    source_urls: list[str]
    assumptions: dict[str, Any]
    raw_response: str


@dataclass(frozen=True)
class MarketQuoteProviderConfig:
    provider: str
    api_key: str | None
    model: str
    base_url: str
    timeout_seconds: int
    endpoint_type: str = "chat_completions"
    enable_web_search: bool = False
    search_tool_type: str | None = "web_search_preview"


class MarketQuoteProviderError(RuntimeError):
    pass


class OpenAICompatibleMarketQuoteProvider:
    """Market quote provider for OpenAI-compatible chat completions APIs."""

    def __init__(
        self,
        provider_name: str,
        api_key: str | None,
        model: str,
        base_url: str,
        timeout_seconds: int = 60,
        endpoint_type: str = "chat_completions",
        enable_web_search: bool = False,
        search_tool_type: str | None = "web_search_preview",
    ) -> None:
        self.provider_name = provider_name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.endpoint_type = endpoint_type
        self.enable_web_search = enable_web_search
        self.search_tool_type = search_tool_type or "web_search_preview"

    @property
    def endpoint(self) -> str:
        if self.endpoint_type == "responses":
            if self.base_url.endswith("/responses"):
                return self.base_url
            return f"{self.base_url}/responses"
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def build_payload(self, system_prompt: str, user_prompt: str, temperature: float) -> dict[str, Any]:
        if self.endpoint_type == "responses":
            payload: dict[str, Any] = {
                "model": self.model,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": f"{system_prompt}\n\n{user_prompt}",
                    },
                ],
                "temperature": temperature,
            }
            if self.enable_web_search:
                payload["tools"] = [{"type": self.search_tool_type}]
            return payload
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

    def post_json(self, payload: dict[str, Any]) -> str:
        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as opened:
                return opened.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MarketQuoteProviderError(
                format_provider_http_error(self.provider_name, exc.code, detail, str(exc.reason))
            ) from exc
        except (http.client.RemoteDisconnected, ConnectionError, TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
            raise MarketQuoteProviderError(format_provider_connection_error(self.provider_name, exc)) from exc

    def quote(self, request: MarketQuoteRequest) -> MarketQuoteResult:
        if not self.api_key:
            raise MarketQuoteProviderError(f"{self.provider_name} API key is required.")
        payload = self.build_payload(
            (
                "你是工程造价市场价检索助手。必须给出可审计的 JSON，"
                "不要把无来源的推测当作确定价格。"
            ),
            build_market_quote_prompt(request),
            temperature=0.2,
        )
        body = self.post_json(payload)
        token_usage = extract_token_usage(body)
        content = extract_model_content(body, self.endpoint_type)
        response_source_urls = extract_response_source_urls(body)
        parsed = parse_market_quote_json(content)
        parsed_source_urls = [str(item) for item in parsed.get("source_urls", []) if item]
        source_urls = unique_urls([*parsed_source_urls, *response_source_urls])
        return MarketQuoteResult(
            provider=self.provider_name,
            model=self.model,
            item_name=request.item_name,
            unit=request.unit,
            features=request.features,
            region_code=request.region,
            price_min=to_decimal_or_none(parsed.get("price_min")),
            price_max=to_decimal_or_none(parsed.get("price_max")),
            recommended_price=to_decimal_or_none(parsed.get("recommended_price")),
            tax_included=bool(parsed.get("tax_included", True)),
            confidence=to_decimal_or_none(parsed.get("confidence")) or Decimal("0"),
            source_urls=source_urls,
            assumptions={
                **dict(parsed.get("assumptions", {})),
                "token_usage": token_usage,
                "response_source_urls": source_urls,
                "source_policy": "联网询价结果必须保留可点击来源链接，供人工复核。",
            },
            raw_response=content,
        )

    def quote_suppliers(self, request: MarketQuoteRequest) -> SupplierMarketQuoteResult:
        if not self.api_key:
            raise MarketQuoteProviderError(f"{self.provider_name} API key is required.")
        payload = self.build_payload(
            (
                "你是企业工程造价采购询价助手。你的任务是为工程量清单材料或设备寻找"
                "可审计的市场参考价。必须严谨区分公开来源、询价假设和不确定性；"
                "不得编造来源链接；来源不足时要降低置信度并说明。"
            ),
            build_supplier_quote_prompt(request),
            temperature=0.0,
        )
        body = self.post_json(payload)
        token_usage = extract_token_usage(body)
        content = extract_model_content(body, self.endpoint_type)
        response_source_urls = extract_response_source_urls(body)
        parsed = parse_market_quote_json(content)
        quotes = [
            SupplierMarketQuote(
                supplier=str(item.get("supplier") or item.get("brand") or "未注明"),
                brand=str(item["brand"]) if item.get("brand") else None,
                price=to_decimal_or_none(item.get("price")),
                unit=str(item["unit"]) if item.get("unit") else request.unit,
                source_url=str(item["source_url"]) if item.get("source_url") else None,
                source_title=str(item["source_title"]) if item.get("source_title") else None,
                evidence=str(item["evidence"]) if item.get("evidence") else None,
                tax_included=bool(item.get("tax_included", True)),
            )
            for item in parsed.get("quotes", [])
            if isinstance(item, dict)
        ]
        parsed_source_urls = [str(item) for item in parsed.get("source_urls", []) if item]
        quote_source_urls = [quote.source_url for quote in quotes if quote.source_url]
        source_urls = unique_urls([*quote_source_urls, *parsed_source_urls, *response_source_urls])
        return SupplierMarketQuoteResult(
            provider=self.provider_name,
            model=self.model,
            item_name=request.item_name,
            unit=request.unit,
            features=request.features,
            region_code=request.region,
            recommended_price=to_decimal_or_none(parsed.get("recommended_price")),
            confidence=to_decimal_or_none(parsed.get("confidence")) or Decimal("0"),
            quotes=quotes,
            source_urls=source_urls,
            assumptions={
                **dict(parsed.get("assumptions", {})),
                "token_usage": token_usage,
                "search_queries": build_market_quote_search_queries(request),
                "response_source_urls": source_urls,
                "require_source_url": self.enable_web_search,
                "source_policy": "联网询价的有效报价必须包含可点击来源链接，人工复核以链接原文为准。",
            },
            raw_response=content,
        )


class DoubaoMarketQuoteProvider(OpenAICompatibleMarketQuoteProvider):
    """Doubao/Volcengine Ark through an OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            provider_name="doubao",
            api_key=api_key or os.getenv("DOUBAO_API_KEY") or os.getenv("ARK_API_KEY"),
            model=model or os.getenv("DOUBAO_MODEL") or os.getenv("ARK_MODEL", "doubao-seed-1-6"),
            base_url=base_url
            or os.getenv("DOUBAO_BASE_URL")
            or os.getenv("DOUBAO_CHAT_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3"),
        )


class CloseAIMarketQuoteProvider(OpenAICompatibleMarketQuoteProvider):
    """CloseAI OpenAI-compatible adapter.

    CloseAI expects the OpenAI-compatible base URL to include the /v1 suffix.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            provider_name="closeai",
            api_key=api_key or os.getenv("CLOSEAI_API_KEY"),
            model=model or os.getenv("CLOSEAI_MODEL", "gpt-4o-mini"),
            base_url=base_url or os.getenv("CLOSEAI_BASE_URL", "https://api.openai-proxy.org/v1"),
            timeout_seconds=int(os.getenv("CLOSEAI_TIMEOUT_SECONDS", "60")),
        )


class LocalMarketQuoteProvider(OpenAICompatibleMarketQuoteProvider):
    """Adapter for locally deployed OpenAI-compatible model servers."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(
            provider_name="local",
            api_key=api_key or os.getenv("LOCAL_LLM_API_KEY", "local"),
            model=model or os.getenv("LOCAL_LLM_MODEL", "local-model"),
            base_url=base_url or os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:8001/v1"),
            timeout_seconds=int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "120")),
        )


def create_market_quote_provider(
    provider: str | None = None,
    config: MarketQuoteProviderConfig | None = None,
):
    selected = (provider or os.getenv("MARKET_QUOTE_PROVIDER", "doubao")).lower()
    if config is not None:
        return OpenAICompatibleMarketQuoteProvider(
            provider_name=selected,
            api_key=config.api_key or default_provider_api_key(selected),
            model=config.model,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            endpoint_type=config.endpoint_type,
            enable_web_search=config.enable_web_search,
            search_tool_type=config.search_tool_type,
        )
    if selected == "doubao":
        return DoubaoMarketQuoteProvider()
    if selected == "closeai":
        return CloseAIMarketQuoteProvider()
    if selected in {"local", "local-llm", "local_llm"}:
        return LocalMarketQuoteProvider()
    raise MarketQuoteProviderError(f"Unsupported market quote provider: {selected}")


def default_provider_api_key(provider: str) -> str | None:
    if provider == "doubao":
        return os.getenv("DOUBAO_API_KEY") or os.getenv("ARK_API_KEY")
    if provider == "closeai":
        return os.getenv("CLOSEAI_API_KEY")
    if provider in {"local", "local-llm", "local_llm"}:
        return os.getenv("LOCAL_LLM_API_KEY", "local")
    return None


def build_market_quote_prompt(request: MarketQuoteRequest) -> str:
    return json.dumps(
        {
            "task": "检索并估算工程量清单综合单价市场参考区间",
            "requirements": [
                "优先使用公开市场价、信息价、采购价、招投标公告、中标公告、厂家或经销商报价页等可追溯来源",
                "不得把无来源推测当成确定价格",
                "如果来源不足，recommended_price 必须为 null 或降低 confidence，并在 assumptions 中说明",
                "必须输出严格 JSON，不要输出 markdown",
            ],
            "output_schema": {
                "price_min": "number or null",
                "price_max": "number or null",
                "recommended_price": "number or null",
                "tax_included": "boolean",
                "confidence": "0-1 number",
                "source_urls": ["url"],
                "assumptions": {"key": "value"},
            },
            "item_name": request.item_name,
            "unit": request.unit,
            "features": request.features,
            "region": request.region,
            "price_month": request.price_month,
            "standard": request.standard,
        },
        ensure_ascii=False,
    )


def build_supplier_quote_prompt(request: MarketQuoteRequest) -> str:
    search_queries = build_market_quote_search_queries(request)
    features = prepare_market_quote_features(request.features)
    return json.dumps(
        {
            "task": "工程清单在线询价，抽取可审计供应商报价。",
            "queries": search_queries,
            "rules": [
                "先搜索再回答；只采纳能看到产品/规格和价格的具体页面。",
                "有效报价必须有 supplier、price、unit、source_url、evidence；不得编造链接或价格。",
                "优先政府信息价、招采/中标公告、厂家或授权经销商报价页；排除首页、搜索页、登录后价格和无价页面。",
                "最多返回3条不同来源；至少1条真实有效报价；recommended_price为有效报价均值。",
                "核对名称、规格、材质、等级、单位、工作内容；不匹配需写入 discard_reasons。",
            ],
            "item": {
                "code": request.item_code,
                "name": request.item_name,
                "unit": request.unit,
                "quantity": request.quantity,
                "features": features,
                "work_content": compact_prompt_text(request.work_content, 120),
                "remark": request.remark,
                "region": request.region,
                "price_month": request.price_month,
                "standard": request.standard,
            },
            "output_schema": {
                "quotes": [
                    {
                        "supplier": "供应商或平台名称",
                        "brand": "品牌名称或 null",
                        "price": "number or null",
                        "unit": "计价单位",
                        "source_url": "来源链接或 null",
                        "source_title": "来源标题或 null",
                        "evidence": "包含价格数字和规格匹配关系的简短证据说明",
                        "tax_included": "boolean",
                    }
                ],
                "recommended_price": "有效报价平均值，number or null",
                "confidence": "0-1 number",
                "source_urls": ["url"],
                "assumptions": {"search_queries": ["query"], "discard_reasons": ["原因"], "price_basis": "含税/运费/安装/地区月份"},
            },
        },
        ensure_ascii=False,
    )


def build_market_quote_search_queries(request: MarketQuoteRequest) -> list[str]:
    feature_values = [str(value) for value in prepare_market_quote_features(request.features).values() if value]
    feature_text = " ".join(feature_values)
    core = " ".join(part for part in [request.item_name, feature_text] if part).strip()
    region = request.region or "全国"
    year_month = request.price_month or "最新"
    standard = request.standard or ""
    queries = [
        f"{core} {region} {year_month} 采购价 含税",
        f"{core} {region} 信息价 工程造价",
        f"{core} 造价通 招标公告 采购 清单",
        f"{core} 厂家 报价 产品详情",
    ]
    if standard:
        queries.append(f"{core} {standard} 采购价")
    return [query for query in queries if query.strip()]


def prepare_market_quote_features(features: dict[str, str] | None, max_items: int = 8) -> dict[str, str]:
    informative = informative_features(features)
    compacted: dict[str, str] = {}
    for key, value in informative.items():
        compacted[compact_prompt_text(key, 24)] = compact_prompt_text(value, 80)
        if len(compacted) >= max_items:
            break
    return compacted


def compact_prompt_text(value: str | None, max_chars: int) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ;；、")
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)].rstrip() + "…"


def extract_chat_content(body: str) -> str:
    payload = json.loads(body)
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise MarketQuoteProviderError("Unexpected chat completion response.") from exc


def extract_model_content(body: str, endpoint_type: str) -> str:
    if endpoint_type == "responses":
        return extract_responses_content(body)
    return extract_chat_content(body)


def extract_token_usage(body: str) -> dict[str, int]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    prompt_tokens = to_int_or_zero(usage.get("prompt_tokens") or usage.get("input_tokens"))
    completion_tokens = to_int_or_zero(usage.get("completion_tokens") or usage.get("output_tokens"))
    total_tokens = to_int_or_zero(usage.get("total_tokens"))
    if total_tokens <= 0 and (prompt_tokens > 0 or completion_tokens > 0):
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def to_int_or_zero(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def format_provider_http_error(provider_name: str, status_code: int, detail: str, reason: str) -> str:
    """Translate model-provider HTTP errors into operator-friendly messages."""
    provider_label = {
        "doubao": "豆包/火山方舟",
        "closeai": "CloseAI",
        "local": "本地模型",
    }.get(provider_name, provider_name)
    error_code = ""
    message = ""
    request_id = ""
    try:
        payload = json.loads(detail) if detail else {}
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            error_code = str(error.get("code") or "")
            message = str(error.get("message") or "")
        request_id = str(payload.get("request_id") or payload.get("requestId") or "")
    except json.JSONDecodeError:
        message = detail

    combined = f"{error_code} {message}".lower()
    if error_code == "ToolNotOpen" or "not activated web search" in combined:
        action = (
            f"{provider_label}账号未开通联网搜索内容插件，当前无法返回可点击来源证据。"
            "请在火山控制台开通 Web Search/联网内容插件："
            "https://console.volcengine.com/common-buy/CC_content_plugin 。"
            "开通后重试；若暂时不需要联网搜索，可在平台配置关闭“联网搜索增强”，"
            "但关闭后结果不会满足“最新联网来源证据”的入库要求。"
        )
        if request_id:
            return f"HTTP Error {status_code}: {action} Request id: {request_id}"
        return f"HTTP Error {status_code}: {action}"

    clean_detail = detail or reason
    return f"HTTP Error {status_code}: {clean_detail}"


def format_provider_connection_error(provider_name: str, exc: BaseException) -> str:
    provider_label = {
        "doubao": "豆包/火山方舟",
        "closeai": "CloseAI",
        "local": "本地模型",
    }.get(provider_name, provider_name)
    detail = str(exc) or exc.__class__.__name__
    if isinstance(exc, http.client.RemoteDisconnected) or "remote end closed" in detail.lower():
        return (
            f"{provider_label}模型接口连接被远端关闭，未返回有效响应。"
            "通常是 Base URL/接口类型配置不匹配、模型服务临时不可用、网络代理中断，"
            "或联网搜索工具调用被服务端拒绝。请检查平台配置中的 Base URL、模型名称、"
            f"Endpoint 类型、联网搜索开关和 API Key 后重试。原始错误：{detail}"
        )
    return f"{provider_label}模型接口连接失败：{detail}"


def extract_responses_content(body: str) -> str:
    payload = json.loads(body)
    if payload.get("output_text"):
        return str(payload["output_text"])
    text_parts: list[str] = []
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text") or content.get("content")
            if text:
                text_parts.append(str(text))
    if text_parts:
        return "\n".join(text_parts)
    raise MarketQuoteProviderError("Unexpected responses API response.")


def extract_response_source_urls(body: str) -> list[str]:
    payload = json.loads(body)
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            url = value.get("url")
            if isinstance(url, str) and is_http_url(url):
                urls.append(url)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return unique_urls(urls)


def unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if not is_http_url(url) or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def is_http_url(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def parse_market_quote_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise MarketQuoteProviderError("Model response did not contain JSON.")
        return json.loads(match.group(0))


def to_decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))

