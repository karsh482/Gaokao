"""LLM 结构化意图抽取：把自然语言归一成可控字段，不直接生成 SQL。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from gaokao_nl2sql.errors import SqlGenerationError
from gaokao_nl2sql.llm import ChatModel


AdmissionIntentType = Literal["admission_search", "admission_feasibility", "other"]

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class AdmissionIntent:
    """面向录取数据查询的结构化条件。"""

    intent: AdmissionIntentType
    school_name: str | None = None
    major_name: str | None = None
    subject_category: str | None = None
    candidate_rank: int | None = None
    candidate_score: int | None = None

    @property
    def is_actionable(self) -> bool:
        """是否足以进入确定性 SQL 计划。"""

        if self.intent not in {"admission_search", "admission_feasibility"}:
            return False
        return self.candidate_rank is not None or self.candidate_score is not None

    @property
    def has_target_school(self) -> bool:
        """是否指定了目标院校。"""

        return bool(self.school_name)


@dataclass(slots=True)
class IntentExtractor:
    """使用 LLM 抽取结构化意图；失败时返回 other，不影响原回退链路。"""

    model: ChatModel

    def extract(self, question: str) -> AdmissionIntent:
        if not question.strip():
            return AdmissionIntent(intent="other")

        try:
            reply = self.model.complete(_SYSTEM_PROMPT, _user_prompt(question))
            data = _extract_json_object(reply)
            return _coerce_intent(data)
        except (SqlGenerationError, ValueError, TypeError, json.JSONDecodeError):
            return AdmissionIntent(intent="other")


def _user_prompt(question: str) -> str:
    return (
        f"用户问题：{question.strip()}\n\n"
        "请只输出 JSON，不要解释。"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("empty intent response")
    fenced = _JSON_FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    parsed = json.loads(candidate.strip())
    if not isinstance(parsed, dict):
        raise ValueError("intent response must be object")
    return parsed


def _coerce_intent(data: dict[str, Any]) -> AdmissionIntent:
    intent = data.get("intent")
    if intent not in {"admission_search", "admission_feasibility"}:
        return AdmissionIntent(intent="other")

    return AdmissionIntent(
        intent="admission_feasibility",
        school_name=_optional_text(data.get("school_name")),
        major_name=_optional_text(data.get("major_name")),
        subject_category=_coerce_subject(data.get("subject_category")),
        candidate_rank=_optional_int(data.get("candidate_rank")),
        candidate_score=_optional_int(data.get("candidate_score")),
    )


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.lower() in {"null", "none", "unknown"}:
        return None
    return normalized


def _coerce_subject(value: Any) -> str | None:
    normalized = _optional_text(value)
    if normalized in {"物理类", "历史类"}:
        return normalized
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        normalized = value.replace(",", "").replace("，", "").strip()
        if normalized.isdigit():
            return int(normalized)
    return None


_SYSTEM_PROMPT = """你是高考志愿查询系统的意图抽取器。

目标：把用户问题抽取成结构化 JSON，禁止生成 SQL。

只识别“录取数据查询/能上哪些学校/能不能上某校/够不够某校某专业”类问题。
其他问题输出 {"intent":"other"}。

字段说明：
- intent: "admission_search"、"admission_feasibility" 或 "other"
- school_name: 目标院校名称，例如 "贵州大学"；没有则 null
- major_name: 用户明确指定的专业或专业类，例如 "法学"、"计算机类"；仅问学校整体时为 null
- subject_category: "物理类"、"历史类" 或 null
- candidate_rank: 用户给出的位次整数；没有则 null
- candidate_score: 用户给出的分数整数；没有则 null

抽取规则：
- “贵州物理类 9500名，能上哪些大学”应识别为 admission_search，school_name 为 null，candidate_rank 为 9500。
- “贵州物理类 位次10000 能不能上贵州大学”应识别为 admission_feasibility，school_name 为“贵州大学”，major_name 为 null。
- “贵州物理类 9500名，能上贵州大学的哪些专业”应识别为 admission_feasibility，school_name 为“贵州大学”，candidate_rank 为 9500。
- “580分够贵州大学法学吗”应识别 school_name 为“贵州大学”，major_name 为“法学”，candidate_score 为 580。
- 不确定字段用 null，不要猜测。
- 只输出一个 JSON 对象，不要 Markdown，不要解释。"""
