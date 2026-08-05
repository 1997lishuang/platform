from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.market_quote_provider import (
    CloseAIMarketQuoteProvider,
    LocalMarketQuoteProvider,
    MarketQuoteResult,
    MarketQuoteProviderConfig,
    OpenAICompatibleMarketQuoteProvider,
    MarketQuoteRequest,
    build_supplier_quote_prompt,
    build_market_quote_search_queries,
    create_market_quote_provider,
    extract_response_source_urls,
    extract_responses_content,
    format_provider_http_error,
    parse_market_quote_json,
)
from boq_pricing.infrastructure.market_quotes import MarketQuoteRepository
from boq_pricing.infrastructure.sqlalchemy_rules import SqlAlchemyPriceRuleRepository


def test_parse_market_quote_json_from_markdown_wrapped_response():
    parsed = parse_market_quote_json(
        """
        参考如下：
        {"price_min": 82, "price_max": 88, "recommended_price": 85, "tax_included": true,
         "confidence": 0.62, "source_urls": ["https://example.com"], "assumptions": {"region": "华南"}}
        """
    )

    assert parsed["recommended_price"] == 85
    assert parsed["source_urls"] == ["https://example.com"]


def test_closeai_provider_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("CLOSEAI_API_KEY", "test-key")
    monkeypatch.setenv("CLOSEAI_MODEL", "gpt-test")
    monkeypatch.setenv("CLOSEAI_BASE_URL", "https://api.openai-proxy.org/v1")

    provider = CloseAIMarketQuoteProvider()

    assert provider.provider_name == "closeai"
    assert provider.model == "gpt-test"
    assert provider.endpoint == "https://api.openai-proxy.org/v1/chat/completions"


def test_market_quote_provider_factory_selects_closeai(monkeypatch):
    monkeypatch.setenv("CLOSEAI_API_KEY", "test-key")

    provider = create_market_quote_provider("closeai")

    assert isinstance(provider, CloseAIMarketQuoteProvider)


def test_configured_provider_can_use_responses_api_with_web_search():
    provider = create_market_quote_provider(
        "doubao",
        config=MarketQuoteProviderConfig(
            provider="doubao",
            api_key="test-key",
            model="doubao-seed-evolving",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            timeout_seconds=180,
            endpoint_type="responses",
            enable_web_search=True,
            search_tool_type="web_search",
        ),
    )

    assert isinstance(provider, OpenAICompatibleMarketQuoteProvider)
    assert provider.endpoint == "https://ark.cn-beijing.volces.com/api/v3/responses"

    payload = provider.build_payload("system", "user", temperature=0.1)

    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["input"][0]["type"] == "message"
    assert payload["input"][0]["role"] == "user"
    assert "system" in payload["input"][0]["content"]


def test_extract_responses_content_from_output_text():
    content = extract_responses_content(
        '{"output_text":"{\\"quotes\\":[{\\"supplier\\":\\"A\\",\\"price\\":1}]}"}'
    )

    assert '"quotes"' in content


def test_extract_response_source_urls_from_nested_annotations():
    urls = extract_response_source_urls(
        """
        {
          "output": [
            {
              "type": "message",
              "content": [
                {
                  "type": "output_text",
                  "text": "{}",
                  "annotations": [
                    {"type": "url_citation", "url": "https://supplier.example/item"}
                  ]
                }
              ]
            }
          ]
        }
        """
    )

    assert urls == ["https://supplier.example/item"]


def test_format_doubao_web_search_not_open_error():
    message = format_provider_http_error(
        "doubao",
        404,
        (
            '{"error":{"code":"ToolNotOpen",'
            '"message":"Your account has not activated web search.",'
            '"type":"NotFound"},"request_id":"req-1"}'
        ),
        "Not Found",
    )

    assert "账号未开通联网搜索内容插件" in message
    assert "https://console.volcengine.com/common-buy/CC_content_plugin" in message
    assert "Request id: req-1" in message


def test_build_market_quote_search_queries_include_pc_style_terms():
    queries = build_market_quote_search_queries(
        MarketQuoteRequest(
            item_name="预制钢筋混凝土桩",
            unit="m",
            features={"桩型": "PHC-300-AB-70", "桩长度": "8-10m", "混凝土": "C80"},
            region="华南",
            price_month="2026-07",
            standard="GB13476-2023",
        )
    )

    joined = "\n".join(queries)
    assert "PHC-300-AB-70" in joined
    assert "8-10m" in joined
    assert "C80" in joined
    assert "造价通" in joined
    assert "招标公告" in joined


def test_supplier_quote_prompt_filters_generic_features_and_limits_queries():
    prompt = build_supplier_quote_prompt(
        MarketQuoteRequest(
            item_name="组串式逆变器",
            unit="台",
            features={
                "规格型号": "320kW",
                "其他技术要求": "满足相关技术规范及发包人要求",
                "备注": "详见设计图纸",
                "冗长说明": "这是一个" + "很长" * 80,
            },
            region="CN",
            price_month="2026-07",
            standard="GB13476-2023",
            work_content="安装、调试、并网、试运行、资料移交。" * 20,
        )
    )
    payload = parse_market_quote_json(prompt)

    assert payload["item"]["features"]["规格型号"] == "320kW"
    assert "其他技术要求" not in payload["item"]["features"]
    assert "满足相关技术规范及发包人要求" not in prompt
    assert len(payload["queries"]) <= 5
    assert len(payload["item"]["work_content"]) <= 121


def test_local_provider_uses_configurable_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5")

    provider = create_market_quote_provider("local")

    assert isinstance(provider, LocalMarketQuoteProvider)
    assert provider.model == "qwen2.5"
    assert provider.endpoint == "http://127.0.0.1:11434/v1/chat/completions"


def test_market_quote_repository_saves_pending_review_quote():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    row = MarketQuoteRepository(session_factory).save(
        MarketQuoteResult(
            provider="doubao",
            model="test-model",
            item_name="PHC桩",
            unit="m",
            features={"桩型": "PHC-300-AB-70"},
            region_code="AH-LA",
            price_min=Decimal("82"),
            price_max=Decimal("88"),
            recommended_price=Decimal("85"),
            tax_included=True,
            confidence=Decimal("0.6"),
            source_urls=["https://example.com"],
            assumptions={"note": "test"},
            raw_response="{}",
        ),
        username="estimator",
    )

    assert row.status == "pending_review"
    assert row.recommended_price == Decimal("85")


def test_market_quote_repository_reuses_only_adopted_quotes():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = MarketQuoteRepository(session_factory)

    row = repository.save(
        MarketQuoteResult(
            provider="doubao",
            model="test-model",
            item_name="PHC桩",
            unit="m",
            features={"桩型": "PHC-300-AB-70"},
            region_code="CN",
            price_min=Decimal("82"),
            price_max=Decimal("88"),
            recommended_price=Decimal("85"),
            tax_included=True,
            confidence=Decimal("0.6"),
            source_urls=["https://example.com"],
            assumptions={"note": "test", "supplier_quotes": []},
            raw_response="{}",
        ),
        username="estimator",
    )

    pending = repository.find_reusable("PHC桩", "m", {"桩型": "PHC-300-AB-70"}, "CN")
    adopted = repository.approve(row.quote_code, "reviewer", "ok")
    reusable = repository.find_reusable("PHC桩", "m", {"桩型": "PHC-300-AB-70"}, "CN")

    assert pending is None
    assert adopted.status == "adopted"
    assert reusable is not None
    assert reusable.quote_code == row.quote_code


def test_market_quote_approval_publishes_active_price_rule():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = MarketQuoteRepository(session_factory)

    row = repository.save(
        MarketQuoteResult(
            provider="doubao",
            model="test-model",
            item_name="预制钢筋混凝土桩",
            unit="m",
            features={"桩型": "PHC-300-AB-70", "桩长度": "8-10m"},
            region_code="CN",
            price_min=Decimal("82"),
            price_max=Decimal("88"),
            recommended_price=Decimal("85"),
            tax_included=True,
            confidence=Decimal("0.6"),
            source_urls=["https://example.com"],
            assumptions={"supplier_quotes": []},
            raw_response="{}",
        ),
        username="estimator",
    )

    repository.approve(row.quote_code, "reviewer", "ok")

    rules = SqlAlchemyPriceRuleRepository(session_factory).load(region_code="CN")
    assert len(rules) == 1
    assert rules[0].rule_id == f"MQ-{row.quote_code}"
    assert rules[0].item_name_contains == "预制钢筋混凝土桩"
    assert rules[0].unit_price == Decimal("85.0000")
    assert rules[0].feature_conditions["桩长度"] == "8-10m"
    assert rules[0].source == f"market_quote:{row.quote_code}"


def test_market_quote_repository_lists_paged_quotes():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = MarketQuoteRepository(session_factory)

    for index in range(3):
        repository.save(
            MarketQuoteResult(
                provider="doubao",
                model="test-model",
                item_name=f"材料{index}",
                unit="m",
                features={"规格": str(index)},
                region_code="CN",
                price_min=Decimal("1"),
                price_max=Decimal("2"),
                recommended_price=Decimal("1.5"),
                tax_included=True,
                confidence=Decimal("0.6"),
                source_urls=["https://example.com"],
                assumptions={"supplier_quotes": []},
                raw_response="{}",
            ),
            username="estimator",
        )

    rows, total = repository.list_page(status="pending_review", page=2, page_size=2)

    assert total == 3
    assert len(rows) == 1
    assert rows[0].item_name == "材料0"


def test_market_quote_repository_rejects_pending_quote():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = MarketQuoteRepository(session_factory)

    row = repository.save(
        MarketQuoteResult(
            provider="doubao",
            model="test-model",
            item_name="水尺",
            unit="m",
            features={"材质": "不锈钢"},
            region_code="CN",
            price_min=Decimal("10"),
            price_max=Decimal("12"),
            recommended_price=Decimal("11"),
            tax_included=True,
            confidence=Decimal("0.7"),
            source_urls=["https://example.com"],
            assumptions={"note": "test"},
            raw_response="{}",
        ),
        username="estimator",
    )

    rejected = repository.reject(row.quote_code, "reviewer", "source mismatch")

    assert rejected.status == "rejected"
    assert rejected.reviewed_by == "reviewer"
    assert rejected.review_comment == "source mismatch"
