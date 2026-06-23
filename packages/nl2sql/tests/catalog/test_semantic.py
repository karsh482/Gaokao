"""语义帧抽取与归一化测试。"""

from __future__ import annotations

from gaokao_nl2sql.catalog.semantic import SemanticFrameExtractor, frame_from_mapping


class FakeSemanticModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.reply


def test_frame_from_mapping_parses_open_admission_search() -> None:
    frame = frame_from_mapping(
        {
            "route": "sql",
            "task": "admission_search",
            "exam_province": "贵州",
            "year": 2025,
            "candidate": {"rank": "9,500", "score": None},
            "filters": {"subject_category": "物理", "school_name": None},
            "output": {"target": "schools", "limit": 500},
            "missing_required": [],
            "confidence": "0.93",
        }
    )

    assert frame.route == "sql"
    assert frame.task == "admission_search"
    assert frame.exam_province == "贵州"
    assert frame.year == 2025
    assert frame.candidate.rank == 9500
    assert frame.filters.subject_category == "物理类"
    assert frame.output.target == "schools"
    assert frame.output.limit == 200
    assert frame.confidence == 0.93


def test_semantic_frame_extractor_accepts_json_fence() -> None:
    model = FakeSemanticModel(
        """```json
        {
          "route": "sql",
          "task": "admission_feasibility",
          "candidate": {"rank": 10000},
          "filters": {"school_name": "贵州大学", "subject_category": "物理类"},
          "output": {"target": "majors", "limit": 5},
          "missing_required": [],
          "confidence": 0.9
        }
        ```"""
    )

    frame = SemanticFrameExtractor(model=model).extract("贵州物理类 位次10000 能不能上贵州大学")

    assert frame.task == "admission_feasibility"
    assert frame.candidate.rank == 10000
    assert frame.filters.school_name == "贵州大学"
    assert frame.output.limit == 5
    assert model.calls == 1


def test_semantic_frame_extractor_falls_back_to_generic_on_bad_json() -> None:
    frame = SemanticFrameExtractor(model=FakeSemanticModel("not-json")).extract("随便问问")

    assert frame.task == "generic"
    assert frame.route == "sql"
