from __future__ import annotations

from app.models import ChatMessage
from app.query_rewrite import (
    QueryRewriteResult,
    rewrite_follow_up_question,
    rewrite_structured_query_fallback,
)


class FakeRewriteModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0
        self.last_user_prompt = ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_user_prompt = user_prompt
        return self.reply


def test_rewrite_follow_up_question_no_history_passthrough() -> None:
    model = FakeRewriteModel("重写后：贵州大学法学专业能不能上？")

    result = rewrite_follow_up_question(
        question="法学呢？",
        history=[],
        exam_province="贵州",
        plan_year=2025,
        model=model,
    )

    assert result == QueryRewriteResult(question="法学呢？", rewritten=False)
    assert model.calls == 0


def test_rewrite_follow_up_question_uses_recent_history() -> None:
    model = FakeRewriteModel("改写后：贵州物理类考生报考贵州大学法学专业是否可行？")
    history = [
        ChatMessage(role="user", content="贵州物理类 位次10000 能不能上贵州大学？"),
        ChatMessage(role="assistant", content="可以作为参考。"),
        ChatMessage(role="user", content="那法学呢？"),
    ]

    result = rewrite_follow_up_question(
        question="那法学呢？",
        history=history,
        exam_province="贵州",
        plan_year=2025,
        model=model,
    )

    assert result.rewritten is True
    assert result.question == "贵州物理类考生报考贵州大学法学专业是否可行？"
    assert model.calls == 1
    assert "最近对话" in model.last_user_prompt
    assert "贵州物理类 位次10000 能不能上贵州大学？" in model.last_user_prompt
    assert "那法学呢？" in model.last_user_prompt


def test_rewrite_prompt_preserves_score_reference_and_school_location() -> None:
    model = FakeRewriteModel("完整问题：贵州物理类580分可以填报四川省内哪些学校？")
    history = [
        ChatMessage(role="user", content="贵州物理类 580分能报哪些学校？"),
        ChatMessage(role="assistant", content="可以参考若干院校。"),
    ]

    result = rewrite_follow_up_question(
        question="这个分数可以填报四川的哪些学校？",
        history=history,
        exam_province="贵州",
        plan_year=2025,
        model=model,
    )

    assert result.rewritten is True
    assert result.question == "贵州物理类580分可以填报四川省内哪些学校？"
    assert "这个分数" in model.last_user_prompt
    assert "补全具体分数或位次" in model.last_user_prompt
    assert "四川表示院校所在地" in model.last_user_prompt


def test_rewrite_prompt_preserves_relative_rank_change() -> None:
    model = FakeRewriteModel("完整问题：贵州物理类580分，排名比去年高1000名，可以冲哪些学校？")

    result = rewrite_follow_up_question(
        question="排名比去年高1000名，可以冲哪些学校？",
        history=[ChatMessage(role="user", content="贵州物理类 580分能报哪些学校？")],
        exam_province="贵州",
        plan_year=2025,
        model=model,
    )

    assert result.rewritten is True
    assert "相对位次变化" in model.last_user_prompt
    assert "排名比去年高1000名" in model.last_user_prompt


def test_rewrite_follow_up_question_falls_back_on_failure() -> None:
    class BrokenModel:
        def complete(self, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("boom")

    result = rewrite_follow_up_question(
        question="那法学呢？",
        history=[ChatMessage(role="user", content="贵州物理类 位次10000 能不能上贵州大学？")],
        exam_province="贵州",
        plan_year=2025,
        model=BrokenModel(),
    )

    assert result.question == "那法学呢？"
    assert result.rewritten is False


def test_structured_query_fallback_rewrites_without_history() -> None:
    model = FakeRewriteModel("完整问题：今年贵州大学数学专业一共招几人？")

    result = rewrite_structured_query_fallback(
        question="帮我看今年贵州大学数学系招几个",
        exam_province="贵州",
        plan_year=2025,
        model=model,
    )

    assert result == QueryRewriteResult(
        question="今年贵州大学数学专业一共招几人？",
        rewritten=True,
    )
    assert model.calls == 1
    assert "原始问题" in model.last_user_prompt
    assert "某某系" in model.last_user_prompt
    assert "不要用默认招生年份覆盖" in model.last_user_prompt
