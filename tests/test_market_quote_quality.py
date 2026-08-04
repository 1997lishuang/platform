from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boq_pricing.infrastructure.db import Base
from boq_pricing.infrastructure.market_quote_excel import validate_supplier_quote_result
from boq_pricing.infrastructure.market_quote_provider import (
    MarketQuoteProviderError,
    MarketQuoteResult,
    SupplierMarketQuote,
    SupplierMarketQuoteResult,
)
from boq_pricing.infrastructure.market_quotes import MarketQuoteRepository


def supplier_result(quotes):
    return SupplierMarketQuoteResult(
        provider="test",
        model="model",
        item_name="GNSS设备",
        unit="套",
        features={},
        region_code="CN",
        recommended_price=None,
        confidence=Decimal("0.8"),
        quotes=quotes,
        source_urls=[],
        assumptions={"require_source_url": False},
        raw_response="{}",
    )


def market_result(price: str) -> MarketQuoteResult:
    return MarketQuoteResult(
        provider="test",
        model="model",
        item_name="GNSS设备",
        unit="套",
        features={},
        region_code="CN",
        price_min=Decimal(price),
        price_max=Decimal(price),
        recommended_price=Decimal(price),
        tax_included=True,
        confidence=Decimal("0.8"),
        source_urls=["https://example.com/product/gnss-1"],
        assumptions={"supplier_quotes": [{"price": price}]},
        raw_response="{}",
    )


def test_rejects_quote_when_evidence_has_name_but_no_price():
    result = supplier_result(
        [
            SupplierMarketQuote(
                supplier="供应商A",
                brand=None,
                price=Decimal("13950"),
                unit="套",
                source_url="https://example.com/product/gnss-1",
                source_title="GNSS设备",
                evidence="页面提到GNSS设备，但没有明确价格。",
                tax_included=True,
            )
        ]
    )

    with pytest.raises(MarketQuoteProviderError):
        validate_supplier_quote_result(result)


def test_pending_quote_keeps_first_valid_recommended_price():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    repository = MarketQuoteRepository(session_factory)

    first = repository.save(market_result("100"), username="admin")
    second = repository.save(market_result("160"), username="admin")

    assert first.quote_code == second.quote_code
    assert second.recommended_price == Decimal("100.0000")
    assert second.assumptions_json["latest_model_recommended_price"] == "160"
    assert second.assumptions_json["locked_recommended_price"] == "100.0000"
