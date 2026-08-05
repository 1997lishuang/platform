from __future__ import annotations

import re
from collections.abc import Iterable

from boq_pricing.domain import FeatureSet


KEY_VALUE_RE = re.compile(
    r"^\s*(?:\d+|[一二三四五六七八九十]+)?[\.、]?\s*"
    r"(?P<key>[^:：；;\n]+?)\s*[:：]\s*(?P<value>.+?)\s*$"
)
PILE_MODEL_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<model>PHC[-\s]*(?P<diameter>\d{2,4})[-\s]*(?P<grade>AB|A|B|C)?[-\s]*(?P<thickness>\d{2,3}))(?![A-Za-z0-9])",
    re.I,
)
CONCRETE_STRENGTH_RE = re.compile(r"(?<![A-Za-z0-9])C\d{2,3}(?![A-Za-z0-9])", re.I)
PILE_LENGTH_RE = re.compile(
    r"(?:桩长|桩长度|桩身长度|有效桩长|长度)\s*(?:为|[:：])?\s*"
    r"(?P<value>\d+(?:\.\d+)?\s*(?:-|~|～|至|到)\s*\d+(?:\.\d+)?\s*(?:m|米)|"
    r"\d+(?:\.\d+)?\s*(?:m|米)(?:以上|以下|以内|左右)?)",
    re.I,
)
SINGLE_SECTION_LENGTH_RE = re.compile(
    r"(?:单节桩长|单节桩长度|单节长度|单节)\s*(?:为|[:：])?\s*"
    r"(?P<value>\d+(?:\.\d+)?\s*(?:-|~|～|至|到)\s*\d+(?:\.\d+)?\s*(?:m|米)|"
    r"\d+(?:\.\d+)?\s*(?:m|米)(?:以上|以下|以内|左右)?)",
    re.I,
)
STANDARD_NAME_RE = re.compile(r"《(?P<name>[^》]+)》")
STANDARD_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<code>(?:GB/T|GB|JGJ|JTG|DL/T|NB/T|CECS|CJ/T|YB/T|SY/T|HG/T)\s*[\dA-Za-z./-]+(?:-\d{4})?)(?![A-Za-z0-9])",
    re.I,
)
SPECIFIC_VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:PHC|DN|GB/T|GB|JGJ|JTG|DL/T|NB/T|CECS|CJ/T|YB/T|SY/T|HG/T|C\d{2,3})|"
    r"\d+(?:\.\d+)?\s*(?:mm|cm|m|米|kV|V|W|Wp|kW|MW|MPa|m2|m3|㎡|m²|m³|%)",
    re.I,
)
GENERIC_FEATURE_KEYS = {
    "其他技术要求",
    "其他要求",
    "技术要求",
    "质量要求",
    "施工要求",
    "验收要求",
    "备注",
    "说明",
}
GENERIC_VALUE_RE = re.compile(
    r"(满足|符合|执行|遵守|按照|按).{0,8}(相关|现行|国家|行业|地方|发包人|业主|设计|图纸|招标文件|技术)?"
    r".{0,8}(规范|标准|要求|规定)|"
    r"(满足|符合).{0,8}(发包人|业主|设计|图纸|招标文件).{0,8}要求|"
    r"详见.{0,8}(图纸|设计|招标文件)|"
    r"按.{0,8}(图纸|设计|规范|标准|发包人|业主).{0,8}(执行|要求|施工)",
    re.I,
)


class FeatureParser:
    """Parse project feature text into normalized key-value indicators."""

    def parse(self, raw_text: str | None) -> FeatureSet:
        text = normalize_text(raw_text or "")
        values: dict[str, str] = {}

        for line in split_feature_lines(text):
            match = KEY_VALUE_RE.match(line)
            if not match:
                continue
            key = normalize_key(match.group("key"))
            value = normalize_value(match.group("value"))
            if is_informative_feature(key, value):
                values[key] = value

        enrich_domain_features(text, values)
        return FeatureSet(raw_text=text, values=values)


def split_feature_lines(text: str) -> Iterable[str]:
    for part in re.split(r"[\r\n]+", text):
        stripped = part.strip()
        if stripped:
            yield stripped


def normalize_text(text: str) -> str:
    return str(text).replace("\u3000", " ").replace("；", "\n").strip()


def normalize_key(key: str) -> str:
    return re.sub(r"\s+", "", key).strip(" .、：:")


def normalize_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .、：:;；")


def informative_features(values: dict[str, str] | None) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in dict(values or {}).items()
        if is_informative_feature(str(key), str(value))
    }


def informative_feature_text(text: str | None) -> str:
    chunks: list[str] = []
    for line in split_feature_lines(normalize_text(text or "")):
        match = KEY_VALUE_RE.match(line)
        if match and not is_informative_feature(match.group("key"), match.group("value")):
            continue
        if is_generic_feature_value(line):
            continue
        chunks.append(line)
    return "\n".join(chunks)


def is_informative_feature(key: str | None, value: str | None) -> bool:
    key_norm = normalize_key(str(key or ""))
    value_norm = normalize_value(str(value or ""))
    if not key_norm or not value_norm:
        return False
    if is_generic_feature_value(value_norm):
        return False
    if key_norm in GENERIC_FEATURE_KEYS and not has_specific_feature_signal(value_norm):
        return False
    return True


def is_generic_feature_value(value: str | None) -> bool:
    normalized = compact_for_match(value)
    if not normalized:
        return True
    return bool(GENERIC_VALUE_RE.search(normalized) and not has_specific_feature_signal(normalized))


def has_specific_feature_signal(value: str | None) -> bool:
    return bool(SPECIFIC_VALUE_RE.search(compact_for_match(value)))


def compact_for_match(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def enrich_domain_features(text: str, values: dict[str, str]) -> None:
    """Supplement key indicators from free-form construction feature text."""

    model_match = PILE_MODEL_RE.search(text)
    if model_match:
        model = re.sub(r"\s+", "", model_match.group("model")).upper()
        values.setdefault("桩型", model)
        values.setdefault("桩径", f"{model_match.group('diameter')}mm")
        if model_match.group("grade"):
            values.setdefault("桩型等级", model_match.group("grade").upper())
        values.setdefault("壁厚", f"{model_match.group('thickness')}mm")

    single_section_match = SINGLE_SECTION_LENGTH_RE.search(text)
    if single_section_match:
        values.setdefault("单节长度", normalize_length(single_section_match.group("value")))

    pile_length_match = PILE_LENGTH_RE.search(text)
    if pile_length_match:
        values.setdefault("桩长度", normalize_length(pile_length_match.group("value")))

    if not any(key in values for key in ("混凝土种类与强度等级", "混凝土强度等级")):
        strength_match = CONCRETE_STRENGTH_RE.search(text)
        if strength_match:
            values["混凝土种类与强度等级"] = strength_match.group(0).upper()

    standard_names = unique_matches(match.group("name") for match in STANDARD_NAME_RE.finditer(text))
    if standard_names:
        values.setdefault("技术标准名称", "；".join(standard_names))

    standard_codes = unique_matches(normalize_standard_code(match.group("code")) for match in STANDARD_CODE_RE.finditer(text))
    if standard_codes:
        values.setdefault("技术标准编号", "；".join(standard_codes))


def unique_matches(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_standard_code(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def normalize_length(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).replace("米", "m")
    return normalized.replace("~", "-").replace("～", "-").replace("至", "-").replace("到", "-")
