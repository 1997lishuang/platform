from decimal import Decimal
import unittest

from boq_pricing.domain import BillItem, PriceRule, SourceRef
from boq_pricing.parsing import FeatureParser
from boq_pricing.pricing import PricingEngine


class PricingEngineTest(unittest.TestCase):
    def test_matches_rule_and_calculates_total(self):
        item = BillItem(
            sequence="1.1",
            item_code=None,
            item_name="预制钢筋混凝土桩",
            feature_text="1.桩型：PHC-300-AB-70\n2.混凝土种类与强度等级：C80",
            unit="m",
            quantity=Decimal("10.5"),
            original_unit_price=None,
            original_total_price=None,
            work_content=None,
            remark=None,
            source=SourceRef("sample.xlsx", "Sheet1", 5),
        )
        item.features = FeatureParser().parse(item.feature_text)
        engine = PricingEngine(
            [
                PriceRule(
                    rule_id="R1",
                    item_name_contains="预制钢筋混凝土桩",
                    unit="m",
                    feature_conditions={"桩型": "PHC-300-AB-70"},
                    unit_price=Decimal("82"),
                    source="test",
                    version="v1",
                )
            ]
        )

        quote = engine.quote(item)

        self.assertEqual(quote.rule_id, "R1")
        self.assertEqual(quote.unit_price, Decimal("82"))
        self.assertEqual(quote.total_price, Decimal("861.00"))

    def test_matches_rule_by_standard_item_name(self):
        item = BillItem(
            sequence="1.1",
            item_code=None,
            item_name="静压预制桩",
            feature_text="桩型：PHC-300-AB-70",
            unit="m",
            quantity=Decimal("2"),
            original_unit_price=None,
            original_total_price=None,
            work_content=None,
            remark=None,
            source=SourceRef("sample.xlsx", "Sheet1", 5),
            standard_item_name="PHC管桩",
        )
        item.features = FeatureParser().parse(item.feature_text)
        engine = PricingEngine(
            [
                PriceRule(
                    rule_id="R-PHC",
                    item_name_contains="PHC管桩",
                    unit="m",
                    feature_conditions={"桩型": "PHC-300-AB-70"},
                    unit_price=Decimal("88"),
                    source="test",
                    version="v1",
                )
            ]
        )

        quote = engine.quote(item)

        self.assertEqual(quote.rule_id, "R-PHC")
        self.assertEqual(quote.total_price, Decimal("176.00"))

    def test_matches_rule_when_item_name_order_differs(self):
        item = BillItem(
            sequence="1.1",
            item_code=None,
            item_name="设备GNSS",
            feature_text="",
            unit="套",
            quantity=Decimal("1"),
            original_unit_price=None,
            original_total_price=None,
            work_content=None,
            remark=None,
            source=SourceRef("sample.xlsx", "Sheet1", 5),
        )
        item.features = FeatureParser().parse(item.feature_text)
        engine = PricingEngine(
            [
                PriceRule(
                    rule_id="R-GNSS",
                    item_name_contains="GNSS设备",
                    unit="套",
                    feature_conditions={},
                    unit_price=Decimal("13950"),
                    source="test",
                    version="v1",
                )
            ]
        )

        quote = engine.quote(item)

        self.assertEqual(quote.rule_id, "R-GNSS")
        self.assertEqual(quote.total_price, Decimal("13950.00"))


if __name__ == "__main__":
    unittest.main()
