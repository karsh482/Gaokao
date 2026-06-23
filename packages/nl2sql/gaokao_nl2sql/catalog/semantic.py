"""通用语义帧：把自然语言查询归一成稳定中间表示。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from gaokao_nl2sql.errors import SqlGenerationError
from gaokao_nl2sql.llm import ChatModel


Route = Literal["sql", "rag", "hybrid", "unsupported"]
Task = Literal[
    "admission_search",
    "admission_feasibility",
    "school_detail",
    "major_lookup",
    "region_lookup",
    "selection_requirement",
    "special_program",
    "generic",
]
OutputTarget = Literal["schools", "majors", "records", "answer"]

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    """考生输入条件。"""

    rank: int | None = None
    score: int | None = None


@dataclass(frozen=True, slots=True)
class QueryFilters:
    """结构化筛选条件。"""

    school_name: str | None = None
    major_name: str | None = None
    subject_category: str | None = None
    city: str | None = None
    ownership: str | None = None
    tuition_max: int | None = None
    special_program: str | None = None
    batch: str | None = None


@dataclass(frozen=True, slots=True)
class QueryOutput:
    """用户期望的输出形态。"""

    target: OutputTarget = "records"
    group_by: str | None = None
    sort: str = "rank_gap"
    limit: int = 20


@dataclass(frozen=True, slots=True)
class SemanticFrame:
    """Query Catalog 的稳定中间语义层。"""

    route: Route = "sql"
    task: Task = "generic"
    exam_province: str | None = None
    year: int | None = None
    candidate: CandidateProfile = field(default_factory=CandidateProfile)
    filters: QueryFilters = field(default_factory=QueryFilters)
    output: QueryOutput = field(default_factory=QueryOutput)
    missing_required: tuple[str, ...] = ()
    confidence: float = 0.0

    @property
    def has_candidate_metric(self) -> bool:
        return self.candidate.rank is not None or self.candidate.score is not None


@dataclass(slots=True)
class SemanticFrameExtractor:
    """LLM 语义帧抽取器；失败时返回 generic，交给旧链路兜底。"""

    model: ChatModel

    def extract(self, question: str) -> SemanticFrame:
        if not question.strip():
            return SemanticFrame()
        try:
            reply = self.model.complete(_SYSTEM_PROMPT, _user_prompt(question))
            data = _extract_json_object(reply)
            return frame_from_mapping(data)
        except (SqlGenerationError, ValueError, TypeError, json.JSONDecodeError):
            return SemanticFrame()


def frame_from_mapping(data: dict[str, Any]) -> SemanticFrame:
    """从 LLM JSON 或测试字典构造语义帧，并做白名单归一。"""

    filters = data.get("filters") if isinstance(data.get("filters"), dict) else {}
    candidate = data.get("candidate") if isinstance(data.get("candidate"), dict) else {}
    output = data.get("output") if isinstance(data.get("output"), dict) else {}

    return SemanticFrame(
        route=_coerce_choice(data.get("route"), {"sql", "rag", "hybrid", "unsupported"}, "sql"),
        task=_coerce_choice(
            data.get("task"),
            {
                "admission_search",
                "admission_feasibility",
                "school_detail",
                "major_lookup",
                "region_lookup",
                "selection_requirement",
                "special_program",
                "generic",
            },
            "generic",
        ),
        exam_province=_optional_text(data.get("exam_province")),
        year=_optional_int(data.get("year")),
        candidate=CandidateProfile(
            rank=_optional_int(candidate.get("rank")),
            score=_optional_int(candidate.get("score")),
        ),
        filters=QueryFilters(
            school_name=_optional_text(filters.get("school_name")),
            major_name=_optional_text(filters.get("major_name")),
            subject_category=_coerce_subject(filters.get("subject_category")),
            city=_optional_text(filters.get("city")),
            ownership=_coerce_ownership(filters.get("ownership")),
            tuition_max=_optional_int(filters.get("tuition_max")),
            special_program=_optional_text(filters.get("special_program")),
            batch=_optional_text(filters.get("batch")),
        ),
        output=QueryOutput(
            target=_coerce_choice(
                output.get("target"),
                {"schools", "majors", "records", "answer"},
                "records",
            ),
            group_by=_optional_text(output.get("group_by")),
            sort=_optional_text(output.get("sort")) or "rank_gap",
            limit=_bounded_limit(output.get("limit")),
        ),
        missing_required=tuple(
            str(item)
            for item in data.get("missing_required", ())
            if isinstance(item, str) and item.strip()
        ),
        confidence=_optional_float(data.get("confidence")) or 0.0,
    )


def _user_prompt(question: str) -> str:
    return f"用户问题：{question.strip()}\n\n请只输出 JSON，不要解释。"


def _extract_json_object(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("empty semantic frame response")
    fenced = _JSON_FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    parsed = json.loads(candidate.strip())
    if not isinstance(parsed, dict):
        raise ValueError("semantic frame response must be object")
    return parsed


def _coerce_choice(value: Any, allowed: set[str], default: str):
    if isinstance(value, str) and value in allowed:
        return value
    return default


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
    if normalized == "物理":
        return "物理类"
    if normalized == "历史":
        return "历史类"
    return None


def _coerce_ownership(value: Any) -> str | None:
    normalized = _optional_text(value)
    if normalized in {"公办", "民办"}:
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


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _bounded_limit(value: Any) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return 20
    return max(1, min(parsed, 200))


_SYSTEM_PROMPT = """你是高考志愿系统的语义解析器。

目标：把用户问题解析为稳定 JSON 语义帧，禁止生成 SQL。

只输出一个 JSON 对象，字段如下：
{
  "route": "sql|rag|hybrid|unsupported",
  "task": "admission_search|admission_feasibility|school_detail|major_lookup|region_lookup|selection_requirement|special_program|generic",
  "exam_province": "贵州|null",
  "year": 2025,
  "candidate": {"rank": 9500, "score": null},
  "filters": {
    "school_name": "贵州大学|null",
    "major_name": "计算机类|null",
    "subject_category": "物理类|历史类|null",
    "city": "贵阳|null",
    "ownership": "公办|民办|null",
    "tuition_max": 8000,
    "special_program": "国家专项|null",
    "batch": "本科批|null"
  },
  "output": {"target": "schools|majors|records|answer", "group_by": "school|null", "sort": "rank_gap", "limit": 20},
  "missing_required": [],
  "confidence": 0.0
}

规则：
- 查询“能上哪些大学/学校/院校/专业”属于 admission_search；没有目标学校时 school_name 为 null。
- 查询“能不能上某校/够不够某校某专业/稳不稳”属于 admission_feasibility。
- 查询院校投档线、专业列表、基本信息属于 school_detail。
- 查询某专业有哪些学校属于 major_lookup。
- 问政策、章程、规则解释优先 route=rag。
- 不确定字段填 null，不要猜测。
- 分数或位次缺失但任务需要时，把字段名放入 missing_required。
- 只输出 JSON，不要 Markdown，不要解释。"""
