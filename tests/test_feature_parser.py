import unittest

from boq_pricing.parsing import FeatureParser


class FeatureParserTest(unittest.TestCase):
    def test_extracts_numbered_key_values(self):
        features = FeatureParser().parse(
            "1.桩型： PHC-300-B-70\n2.桩长度：10-12m\n4.混凝土种类与强度等级：C80"
        )

        self.assertEqual(features.values["桩型"], "PHC-300-B-70")
        self.assertEqual(features.values["桩长度"], "10-12m")
        self.assertEqual(features.values["混凝土种类与强度等级"], "C80")
        self.assertEqual(features.values["桩径"], "300mm")
        self.assertEqual(features.values["桩型等级"], "B")
        self.assertEqual(features.values["壁厚"], "70mm")

    def test_enriches_pile_length_from_free_text(self):
        features = FeatureParser().parse("PHC-300-AB-70，混凝土C80，桩长度为8-10m，静压施工")

        self.assertEqual(features.values["桩型"], "PHC-300-AB-70")
        self.assertEqual(features.values["桩长度"], "8-10m")
        self.assertEqual(features.values["混凝土种类与强度等级"], "C80")
        self.assertEqual(features.values["桩径"], "300mm")
        self.assertEqual(features.values["桩型等级"], "AB")
        self.assertEqual(features.values["壁厚"], "70mm")

    def test_enriches_single_section_length_from_free_text(self):
        features = FeatureParser().parse("型号PHC-300-AB-70，C80预应力管桩，单节8～10米")

        self.assertEqual(features.values["单节长度"], "8-10m")
        self.assertEqual(features.values["桩型"], "PHC-300-AB-70")

    def test_extracts_technical_standard_from_free_text(self):
        features = FeatureParser().parse(
            "材质:镀锌钢管;\n规格:DN80×t3.25;\n技术规格应满足《低压流体输送用焊接钢管》GB/T3091-2015。"
        )

        self.assertEqual(features.values["材质"], "镀锌钢管")
        self.assertEqual(features.values["规格"], "DN80×t3.25")
        self.assertEqual(features.values["技术标准名称"], "低压流体输送用焊接钢管")
        self.assertEqual(features.values["技术标准编号"], "GB/T3091-2015")

    def test_ignores_generic_requirement_features(self):
        features = FeatureParser().parse(
            "规格:DN80\n其他技术要求:满足相关技术规范及发包人要求\n备注:详见设计图纸"
        )

        self.assertEqual(features.values["规格"], "DN80")
        self.assertNotIn("其他技术要求", features.values)
        self.assertNotIn("备注", features.values)


if __name__ == "__main__":
    unittest.main()
