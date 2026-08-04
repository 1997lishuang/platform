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
            if key and value:
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
