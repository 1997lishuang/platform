from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from boq_pricing.config import PROJECT_ROOT


DATA_DIR = PROJECT_ROOT / "data" / "bid_strategy"
RULES_JSON = DATA_DIR / "rules.json"
RULE_FILES_DIR = PROJECT_ROOT / "rules" / "bid_strategy"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".pdf", ".docx", ".doc", ".txt", ".md", ".json"}
OLLAMA_MODEL = os.environ.get("BID_AGENT_OLLAMA_MODEL", "qwen2.5:1.5b")
MINERU_EXE = os.environ.get("BID_AGENT_MINERU_EXE", "")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("BID_AGENT_OLLAMA_TIMEOUT_SECONDS", "20"))
MINERU_TIMEOUT_SECONDS = int(os.environ.get("BID_AGENT_MINERU_TIMEOUT_SECONDS", "45"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RULE_FILES_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def slug(value: str) -> str:
    raw = re.sub(r"\W+", "-", value, flags=re.UNICODE).strip("-").lower()
    return raw or f"rule-{int(time.time())}"


def list_rules() -> list[dict[str, Any]]:
    ensure_dirs()
    return read_json(RULES_JSON, [])


def list_rule_files() -> list[dict[str, Any]]:
    ensure_dirs()
    seen: set[Path] = set()
    files: list[dict[str, Any]] = []
    for folder in [RULE_FILES_DIR, PROJECT_ROOT]:
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            relative = path.relative_to(PROJECT_ROOT)
            files.append({
                "name": path.name,
                "path": str(relative),
                "extension": path.suffix.lower(),
                "size": path.stat().st_size,
            })
    return sorted(files, key=lambda item: item["name"])


def save_rule_file(filename: str, content: bytes) -> dict[str, Any]:
    ensure_dirs()
    safe_name = Path(filename).name
    if Path(safe_name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("不支持的文件类型。")
    target = RULE_FILES_DIR / safe_name
    target.write_bytes(content)
    relative = target.relative_to(PROJECT_ROOT)
    return {"name": target.name, "path": str(relative), "extension": target.suffix.lower(), "size": target.stat().st_size}


def find_mineru_executable() -> str:
    candidates: list[Path] = []
    if MINERU_EXE:
        candidates.append(Path(MINERU_EXE))
    for name in ["mineru", "magic-pdf"]:
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend([
        Path(r"D:\soft\Aanconda\envs\taidibei\Scripts\mineru.exe"),
        Path(r"D:\soft\Aanconda\envs\taidibei\Scripts\magic-pdf.exe"),
        Path(r"D:\soft\Aanconda\Scripts\mineru.exe"),
        Path(r"D:\soft\Aanconda\Scripts\magic-pdf.exe"),
    ])
    for path in candidates:
        if path and path.exists():
            return str(path)
    return ""


def extract_txt(path: Path) -> str:
    for encoding in ["utf-8", "utf-8-sig", "gb18030", "gbk"]:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def extract_docx(path: Path) -> str:
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    chunks: list[str] = []
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        for paragraph in root.findall(".//w:p", namespaces):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespaces)).strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def extract_pdf(path: Path) -> str:
    try:
        import fitz

        doc = fitz.open(path)
        return "\n".join(page.get_text("text") for page in doc)
    except Exception:
        pass
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        pass
    return ""


def run_mineru(path: Path) -> str:
    mineru_exe = find_mineru_executable()
    candidates = [
        [mineru_exe, "-p", str(path), "-o", str(DATA_DIR / "mineru"), "-b", "pipeline", "-m", "auto", "-l", "ch"] if mineru_exe else [],
        [mineru_exe, "-p", str(path), "-o", str(DATA_DIR / "mineru")] if mineru_exe else [],
    ]
    for command in candidates:
        if not command:
            continue
        try:
            completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=MINERU_TIMEOUT_SECONDS)
            combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
            markdowns = sorted((DATA_DIR / "mineru").rglob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
            if markdowns:
                return markdowns[0].read_text(encoding="utf-8", errors="ignore")
            if completed.returncode == 0 and combined.strip():
                return combined
        except Exception:
            continue
    return ""


def run_rapidocr(path: Path) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()
        result, _ = ocr(str(path))
        if not result:
            return ""
        return "\n".join(str(item[1]) for item in result if len(item) >= 2 and item[1])
    except Exception:
        return ""


def flatten_json_text(value: Any) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            parts.append(str(key))
            parts.append(flatten_json_text(item))
    elif isinstance(value, list):
        for item in value:
            parts.append(flatten_json_text(item))
    elif value is not None:
        parts.append(str(value))
    return "\n".join(part for part in parts if part)


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "yes", "是"):
        return True
    if value in (0, "0", "false", "False", "no", "否"):
        return False
    return default


def normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    rule = dict(rule or {})
    benchmark = dict(rule.get("benchmark") or {})
    correction = dict(benchmark.get("correction") or {})
    score = dict(rule.get("score") or {})

    rule["id"] = str(rule.get("id") or slug(rule.get("name") or "rule"))
    rule["name"] = str(rule.get("name") or rule["id"])
    rule["source"] = str(rule.get("source") or "")
    rule["status"] = rule.get("status") or "draft"
    rule["maxScore"] = to_float(rule.get("maxScore"), 100)

    valid_trim_modes = {
        "none", "drop_high", "drop_low", "drop_high_low", "over5_drop_high_low", "rule4_count",
        "rule13_count", "rule14_count", "rule15_count", "rule16_count", "rule18_count",
        "rule19_control", "rule20_count", "rule22_count", "rule2_correction",
    }
    benchmark["type"] = benchmark.get("type") or "mean"
    benchmark["factor"] = to_float(benchmark.get("factor"), 1)
    if "floatRate" in benchmark:
        benchmark["floatRate"] = to_float(benchmark.get("floatRate"), 0)
    if isinstance(benchmark.get("floatRateScenarios"), list):
        benchmark["floatRateScenarios"] = [value for value in (to_float(item) for item in benchmark["floatRateScenarios"]) if value is not None]
    benchmark["trimMode"] = benchmark.get("trimMode") if benchmark.get("trimMode") in valid_trim_modes else "none"

    lower = to_float(correction.get("lowerFactor"))
    upper = to_float(correction.get("upperFactor"))
    mode = correction.get("mode")
    if mode not in {"none", "clip", "remove_outside"}:
        mode = "clip" if lower is not None and upper is not None else "remove_outside" if upper is not None else "none"
    enabled = to_bool(correction.get("enabled"), mode != "none")
    correction = {
        "enabled": enabled,
        "mode": mode if enabled else "none",
        "lowerFactor": lower,
        "upperFactor": upper,
        "rounds": int(to_float(correction.get("rounds"), 1 if enabled else 0) or 0),
        "trimMode": correction.get("trimMode") if correction.get("trimMode") in valid_trim_modes else "none",
        "skipCounts": correction.get("skipCounts") if isinstance(correction.get("skipCounts"), list) else [],
    }
    benchmark["correction"] = correction
    rule["benchmark"] = benchmark

    valid_score_types = {"asymmetric", "band", "distance", "target_price", "rule15_band", "rule16_tier", "rule17_table", "rule19_score", "rule20_score", "rule21_score", "rule22_score"}
    score["type"] = score.get("type") if score.get("type") in valid_score_types else "asymmetric"
    score["targetFactor"] = to_float(score.get("targetFactor"), 1)
    score["fullLowPct"] = to_float(score.get("fullLowPct"), 0)
    score["fullHighPct"] = to_float(score.get("fullHighPct"), 0)
    score["highPenaltyPerPct"] = to_float(score.get("highPenaltyPerPct"), 0)
    score["lowPenaltyPerPct"] = to_float(score.get("lowPenaltyPerPct"), 0)
    score["belowTargetScore"] = to_float(score.get("belowTargetScore"))
    score["minScore"] = to_float(score.get("minScore"), 0)
    if "baseScore" in score:
        score["baseScore"] = to_float(score.get("baseScore"), rule["maxScore"])
    if "rationalityScore" in score:
        score["rationalityScore"] = to_float(score.get("rationalityScore"), 0)
    rule["score"] = score

    warnings: list[str] = []
    if (rule["maxScore"] or 0) <= 0:
        rule["maxScore"] = 100
        warnings.append("满分字段无效，已按 100 处理。")
    if score["type"] == "band" and (score["fullLowPct"] or 0) > (score["fullHighPct"] or 0):
        score["fullLowPct"], score["fullHighPct"] = score["fullHighPct"], score["fullLowPct"]
        warnings.append("满分偏差区间上下限已自动调换。")
    if correction["enabled"] and correction["lowerFactor"] is None and correction["upperFactor"] is None:
        correction["enabled"] = False
        correction["mode"] = "none"
        warnings.append("异常报价修正缺少阈值，已关闭修正。")

    existing_notes = str(rule.get("notes") or "")
    rule["notes"] = ((existing_notes + " ") if existing_notes and warnings else existing_notes) + "；".join(warnings)
    return rule


def rule_from_structured_json(name: str, source: str, text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except Exception:
        return None
    flat = re.sub(r"\s+", "", flatten_json_text(data))
    looks_like_rule2 = "0.95" in flat and "15%" in flat and "-5" in flat and "0.4" in flat and "0.6" in flat
    looks_like_rule4 = "0.85" in flat and "1.25" in flat and "0.6" in flat and "0.7" in flat
    if not (looks_like_rule2 or looks_like_rule4 or "评标基准价" in flat or "价格得分" in flat):
        return None
    factor = 0.95 if ("*0.95" in flat or "×0.95" in flat or "0.95" in flat) else 1
    trim_mode = "over5_drop_high_low" if looks_like_rule2 or ("超过5" in flat and "最高" in flat and "最低" in flat) else "none"
    correction = {"enabled": False, "mode": "none", "lowerFactor": None, "upperFactor": None, "rounds": 0, "trimMode": "none", "skipCounts": []}
    if looks_like_rule2 or ("15%" in flat and ("剔除" in flat or "修正" in flat)):
        correction = {"enabled": True, "mode": "remove_outside", "lowerFactor": None, "upperFactor": 1.15, "rounds": 1, "trimMode": "rule2_correction", "skipCounts": [2] if looks_like_rule2 or "仅有2家" in flat or "投标人仅有2家" in flat else []}
    max_score = 40 if looks_like_rule2 or "得分40" in flat or "得分:40" in flat or "得分\":40" in flat or ("40" in flat and "-5<" in flat) else 100
    score = {"type": "band", "targetFactor": 1, "fullLowPct": -5 if "-5" in flat else 0, "fullHighPct": 0, "highPenaltyPerPct": 0.6 if "0.6" in flat else 0, "lowPenaltyPerPct": 0.4 if "0.4" in flat else 0, "belowTargetScore": None, "minScore": 0}
    if "0.85" in flat:
        max_score = 100
        score = {"type": "target_price", "targetFactor": 0.85, "fullLowPct": 0, "fullHighPct": 0, "highPenaltyPerPct": 0.7 if "0.7" in flat else 0, "lowPenaltyPerPct": 0, "belowTargetScore": 0 if "不得分" in flat else None, "minScore": 60 if "最低为60" in flat or "最低60" in flat else 0}
    return normalize_rule({"id": slug(Path(source).stem), "name": name, "source": source, "status": "draft", "maxScore": max_score, "benchmark": {"type": "mean", "factor": factor, "trimMode": trim_mode, "correction": correction}, "score": score, "notes": "由结构化 JSON 直接转换，请重点复核修正分支、边界符号和扣分公式。"})


def default_rule_from_text(name: str, source: str, text: str) -> dict[str, Any]:
    structured = rule_from_structured_json(name, source, text)
    if structured:
        return structured
    normalized = re.sub(r"\s+", "", text)
    max_score = 100
    if "40分" in normalized:
        max_score = 40
    else:
        matches = [float(item) for item in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*分", text)]
        plausible = [item for item in matches if item >= 10]
        if plausible:
            max_score = max(plausible)
    factor = 0.9 if "90%" in normalized or "0.9" in normalized else 0.95 if "95%" in normalized or "0.95" in normalized else 1
    trim_mode = "rule4_count" if "6-7" in normalized and "8" in normalized else "over5_drop_high_low" if "去掉" in normalized and "最高" in normalized and "最低" in normalized else "none"
    correction = {"enabled": False, "mode": "none", "lowerFactor": None, "upperFactor": None, "rounds": 0}
    if "1.25" in normalized or "0.6" in normalized:
        correction = {"enabled": True, "mode": "clip", "lowerFactor": 0.6 if "0.6" in normalized else None, "upperFactor": 1.25 if "1.25" in normalized else None, "rounds": 2}
    elif "15%" in normalized:
        correction = {"enabled": True, "mode": "remove_outside", "lowerFactor": None, "upperFactor": 1.15, "rounds": 1}
    score = {"type": "asymmetric", "targetFactor": 1, "fullLowPct": 0, "fullHighPct": 0, "highPenaltyPerPct": 0.5, "lowPenaltyPerPct": 0.25, "belowTargetScore": None, "minScore": 0}
    if "0.85" in normalized:
        score.update({"type": "target_price", "targetFactor": 0.85, "highPenaltyPerPct": 0.7, "lowPenaltyPerPct": 0, "belowTargetScore": 0 if ("不得分" in normalized or "得0" in normalized) else None, "minScore": 60})
    elif "-5%" in normalized or "≤-5" in normalized:
        score.update({"type": "band", "fullLowPct": -5, "fullHighPct": 0, "highPenaltyPerPct": 0.6, "lowPenaltyPerPct": 0.4})
    elif "最近" in normalized or "绝对值" in normalized:
        score.update({"type": "distance", "highPenaltyPerPct": 1, "lowPenaltyPerPct": 1})
    return normalize_rule({"id": slug(Path(source).stem), "name": name, "source": source, "status": "draft", "maxScore": max_score, "benchmark": {"type": "mean", "factor": factor, "trimMode": trim_mode, "correction": correction}, "score": score, "notes": "由系统自动生成的草稿，请确认边界条件、扣分系数和基准价修正方式。"})


def extract_text(path: Path, allow_heavy: bool = False) -> tuple[str, str]:
    extension = path.suffix.lower()
    if extension in {".txt", ".md", ".json"}:
        return extract_txt(path), extension.lstrip(".")
    if extension == ".docx":
        return extract_docx(path), "docx"
    if extension == ".pdf":
        text = extract_pdf(path)
        if text.strip():
            return text, "pdf-text"
        if not allow_heavy:
            return "", "quick-skip-ocr"
        text = run_mineru(path)
        return text, "mineru" if text.strip() else "unavailable"
    if extension in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        if not allow_heavy:
            return "", "quick-skip-ocr"
        text = run_rapidocr(path)
        if text.strip():
            return text, "rapidocr"
        text = run_mineru(path)
        return text, "mineru" if text.strip() else "unavailable"
    return "", "unsupported"


def rule_confidence(text: str, rule: dict[str, Any]) -> int:
    normalized = re.sub(r"\s+", "", text or "")
    rule = normalize_rule(rule)
    scoring = rule.get("score") or {}
    correction = (rule.get("benchmark") or {}).get("correction") or {}
    score = 0
    if rule.get("maxScore", 0) > 0:
        score += 1
    if (rule.get("benchmark") or {}).get("factor", 0) > 0:
        score += 1
    if scoring.get("type") in {"asymmetric", "band", "distance", "target_price"}:
        score += 1
    if "0.85" in normalized:
        score += 4 if scoring.get("type") == "target_price" and abs(scoring.get("targetFactor", 0) - 0.85) < 0.001 else -6
    if "1.25" in normalized or "0.6" in normalized:
        score += 3 if correction.get("enabled") and correction.get("mode") == "clip" else -4
    if "15%" in normalized:
        score += 3 if correction.get("enabled") and correction.get("mode") == "remove_outside" else -3
    if "-5%" in normalized or "≤-5" in normalized or "<=-5" in normalized:
        score += 3 if scoring.get("type") == "band" and scoring.get("fullLowPct") == -5 else -3
    if "40分" in normalized:
        score += 2 if abs(rule.get("maxScore", 0) - 40) < 0.001 else -2
    if "0.7" in normalized:
        score += 2 if abs(scoring.get("highPenaltyPerPct", 0) - 0.7) < 0.001 else -2
    return score


def call_ollama_for_rule(name: str, source: str, text: str) -> tuple[dict[str, Any] | None, str]:
    prompt = f"""你是招投标价格评分规则解析器。请只输出 JSON，不要解释。
把下面规则文本解析成统一结构，字段包含 id/name/source/status/maxScore/benchmark/score/notes。
benchmark.trimMode 可用 none、over5_drop_high_low、rule4_count、rule13_count、rule14_count、rule15_count、rule16_count、rule18_count、rule19_control、rule20_count、rule22_count。
score.type 可用 asymmetric、band、distance、target_price、rule15_band、rule16_tier、rule17_table、rule19_score、rule20_score、rule21_score、rule22_score。

来源：{source}
文本：
{text[:6000]}
"""
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
            raw = data.get("response", "")
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return None, "Ollama 返回内容不是 JSON。"
            parsed = json.loads(match.group(0))
            parsed["source"] = source
            parsed["status"] = "draft"
            parsed["id"] = parsed.get("id") or slug(name)
            return normalize_rule(parsed), ""
    except urllib.error.URLError as error:
        return None, f"Ollama 未连接或不可用：{error}"
    except Exception as error:
        return None, f"Ollama 解析失败：{error}"


def resolve_rule_file(relative_path: str) -> Path:
    path = (PROJECT_ROOT / relative_path).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError("文件路径不在项目目录内。")
    if not path.exists() or not path.is_file():
        raise ValueError("规则文件不存在。")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("不支持的文件类型。")
    return path


def parse_rule_file(relative_path: str, allow_heavy: bool = False) -> dict[str, Any]:
    ensure_dirs()
    path = resolve_rule_file(relative_path)
    text, extractor = extract_text(path, allow_heavy=allow_heavy)
    source = str(path.relative_to(PROJECT_ROOT))
    name = f"{path.stem}：自动解析草稿"
    heuristic_rule = default_rule_from_text(name, source, text)
    rule = None
    model_message = ""
    if text.strip():
        rule, model_message = call_ollama_for_rule(name, source, text)
    if rule is None:
        rule = heuristic_rule
        if extractor == "quick-skip-ocr":
            model_message = "已使用快速模式生成规则草稿，未执行耗时 OCR。请手工复核草稿，或点击深度 OCR 解析识别图片文字。"
    elif rule_confidence(text, heuristic_rule) > rule_confidence(text, rule):
        model_message = (model_message + " " if model_message else "") + "模型结果与原文强特征不一致，已采用本地规则解析草稿。"
        rule = heuristic_rule
    return {"file": source, "extractor": extractor, "text": text, "rule": rule, "modelMessage": model_message}


def upsert_rule(rule: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    rules = list_rules()
    normalized = normalize_rule(rule)
    normalized["status"] = "confirmed"
    existing_ids = {item.get("id") for item in rules}
    if normalized["id"] in existing_ids:
        rules = [normalized if item.get("id") == normalized["id"] else item for item in rules]
    else:
        rules.append(normalized)
    write_json(RULES_JSON, rules)
    return normalized


def health() -> dict[str, Any]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            ollama_available = response.status == 200
    except Exception:
        ollama_available = False
    return {
        "ok": True,
        "ollamaModel": OLLAMA_MODEL,
        "mineruAvailable": bool(find_mineru_executable()),
        "mineruPath": find_mineru_executable(),
        "rapidocrAvailable": importlib.util.find_spec("rapidocr_onnxruntime") is not None,
        "ollamaAvailable": ollama_available,
    }
