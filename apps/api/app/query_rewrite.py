"""将前端传入的追问历史改写为独立完整问题。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import ChatMessage


class RewriteModel(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """返回改写结果。"""


@dataclass(slots=True)
class QueryRewriteResult:
    question: str
    rewritten: bool


def rewrite_follow_up_question(
    *,
    question: str,
    history: list[ChatMessage],
    exam_province: str | None,
    plan_year: int | None,
    model: RewriteModel | None,
    max_history_messages: int = 6,
) -> QueryRewriteResult:
    """基于最近对话把追问改写成适合单轮查询链路的完整问题。"""

    if not history:
        return QueryRewriteResult(question=question, rewritten=False)
    if model is None:
        return QueryRewriteResult(question=question, rewritten=False)

    trimmed_history = _trim_history(history, max_messages=max_history_messages)
    if not trimmed_history:
        return QueryRewriteResult(question=question, rewritten=False)

    try:
        rewritten = model.complete(
            _SYSTEM_PROMPT,
            _build_user_prompt(
                question=question,
                history=trimmed_history,
                exam_province=exam_province,
                plan_year=plan_year,
            ),
        ).strip()
    except Exception:
        return QueryRewriteResult(question=question, rewritten=False)

    cleaned = _clean_rewrite(rewritten)
    if not cleaned or cleaned == question:
        return QueryRewriteResult(question=question, rewritten=False)
    return QueryRewriteResult(question=cleaned, rewritten=True)


def rewrite_structured_query_fallback(
    *,
    question: str,
    exam_province: str | None,
    plan_year: int | None,
    model: RewriteModel | None,
) -> QueryRewriteResult:
    """首轮结构化解析失败时，将问题规范成更容易命中模板的单句查询。"""

    if model is None:
        return QueryRewriteResult(question=question, rewritten=False)
    try:
        rewritten = model.complete(
            _STRUCTURED_FALLBACK_SYSTEM_PROMPT,
            _build_structured_fallback_prompt(
                question=question,
                exam_province=exam_province,
                plan_year=plan_year,
            ),
        ).strip()
    except Exception:
        return QueryRewriteResult(question=question, rewritten=False)

    cleaned = _clean_rewrite(rewritten)
    if not cleaned or cleaned == question:
        return QueryRewriteResult(question=question, rewritten=False)
    return QueryRewriteResult(question=cleaned, rewritten=True)


def _trim_history(history: list[ChatMessage], *, max_messages: int) -> list[ChatMessage]:
    messages = [item for item in history if item.content.strip() and item.role in {"user", "assistant"}]
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


def _build_user_prompt(
    *,
    question: str,
    history: list[ChatMessage],
    exam_province: str | None,
    plan_year: int | None,
) -> str:
    scope_parts: list[str] = []
    if exam_province:
        scope_parts.append(f"考试省份={exam_province}")
    if plan_year is not None:
        scope_parts.append(f"招生年份={plan_year}")
    scope_text = "；".join(scope_parts) if scope_parts else "未指定固定范围"
    history_lines = [f"{_role_name(item.role)}：{item.content.strip()}" for item in history]
    history_text = "\n".join(history_lines)
    return (
        f"查询范围：{scope_text}\n\n"
        "最近对话：\n"
        f"{history_text}\n\n"
        f"当前追问：{question.strip()}\n\n"
        "请把“当前追问”改写成一个可以独立理解的完整问题。"
        "如果当前追问使用“这个分数”“这个位次”等指代，要从最近对话补全具体分数或位次。"
        "如果用户提到“排名/位次比去年高/低/提升/下降 N 名”，必须保留这个相对位次变化。"
        "如果用户问“四川的学校/四川省内院校/填报四川的学校”，四川表示院校所在地，不是考试省份。"
    )


def _build_structured_fallback_prompt(
    *,
    question: str,
    exam_province: str | None,
    plan_year: int | None,
) -> str:
    scope_parts: list[str] = []
    if exam_province:
        scope_parts.append(f"考试省份={exam_province}")
    if plan_year is not None:
        scope_parts.append(f"默认招生年份={plan_year}")
    scope_text = "；".join(scope_parts) if scope_parts else "未指定默认范围"
    return (
        f"查询范围：{scope_text}\n\n"
        f"原始问题：{question.strip()}\n\n"
        "请把原始问题改写成一个更容易被结构化查询系统识别的单句问题。"
        "保留学校、专业、科类、专项计划、批次、分数、位次、院校所在地等条件。"
        "用户说“今年/本年/明年/去年”时保留这个时间表达，不要用默认招生年份覆盖。"
        "用户说“某某系”时改写为“某某专业”或“某某相关专业”。"
        "不要新增用户没有提供的学校、专业、科类或分数位次。"
    )


def _clean_rewrite(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    prefixes = ("改写后：", "完整问题：", "独立问题：", "重写后：")
    for prefix in prefixes:
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _role_name(role: str) -> str:
    if role == "user":
        return "用户"
    if role == "assistant":
        return "助手"
    return role


_SYSTEM_PROMPT = """你是高考志愿咨询问题改写助手。
任务是把用户当前追问改写成一个脱离上下文也能独立理解的完整问题，用于后续结构化查询。
要求：
1. 保留用户原意，不扩展未提到的新条件；
2. 能从历史确定的条件要补全到问题里，例如分数、位次、学校、专业、科类、省份、年份；
3. 如果历史不足以补全，就尽量保持原问，不要编造；
4. 区分考试省份和院校所在地：“四川的学校/四川省内院校/填报四川的学校”中的四川是院校所在地；
5. 保留“排名/位次比去年高/低/提升/下降 N 名”等相对位次变化，不要改写丢失；
6. 只输出改写后的单句问题，不要解释。"""


_STRUCTURED_FALLBACK_SYSTEM_PROMPT = """你是高考志愿结构化查询改写助手。
任务是在结构化解析失败时，把用户问题改写成更标准、可查询的单句问题。
要求：
1. 只改写表达，不改变用户原意；
2. 不补充未知条件，不编造学校、专业、年份、科类、分数或位次；
3. 保留“今年/本年/明年/去年”等相对年份表达；
4. 把“某某系”规范成“某某专业”或“某某相关专业”；
5. 只输出改写后的单句问题，不要解释。"""
