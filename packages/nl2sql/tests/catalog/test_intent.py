"""结构化意图抽取测试。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.intent import IntentExtractor


class FakeIntentModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.reply


def test_intent_extractor_parses_admission_search_json() -> None:
    model = FakeIntentModel(
        '{"intent":"admission_search","school_name":"贵州大学",'
        '"major_name":null,"subject_category":"物理类",'
        '"candidate_rank":9500,"candidate_score":null}'
    )

    intent = IntentExtractor(model=model).extract("贵州物理类 9500名，能上贵州大学的哪些专业？")

    assert intent.is_actionable is True
    assert intent.school_name == "贵州大学"
    assert intent.major_name is None
    assert intent.subject_category == "物理类"
    assert intent.candidate_rank == 9500
    assert model.calls == 1


def test_intent_extractor_supports_school_open_admission_search() -> None:
    model = FakeIntentModel(
        '{"intent":"admission_search","school_name":null,'
        '"major_name":null,"subject_category":"物理类",'
        '"candidate_rank":9500,"candidate_score":null}'
    )

    intent = IntentExtractor(model=model).extract("贵州物理类 9500名，能上哪些大学？")

    assert intent.is_actionable is True
    assert intent.school_name is None
    assert intent.subject_category == "物理类"
    assert intent.candidate_rank == 9500


def test_intent_extractor_ignores_invalid_response() -> None:
    intent = IntentExtractor(model=FakeIntentModel("not-json")).extract("随便问问")

    assert intent.intent == "other"
    assert intent.is_actionable is False
