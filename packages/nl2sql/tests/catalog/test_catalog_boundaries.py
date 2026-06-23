"""Query Catalog 边界单元测试：渲染字段、空结果和筛选标注。"""

from __future__ import annotations

from typing import Any

import pytest

from gaokao_nl2sql.catalog.intent import IntentExtractor
from gaokao_nl2sql.catalog.pipeline import CatalogPipeline
from gaokao_nl2sql.catalog.semantic import frame_from_mapping
from gaokao_nl2sql.generator import SqlGenerator
from gaokao_nl2sql.pipeline import Nl2SqlPipeline


class FakeModel:
    def __init__(self, sql: str) -> None:
        self.sql = sql
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        return self.sql


class FakeExecutor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed_sql: str | None = None

    def run(self, sql: str) -> list[dict[str, Any]]:
        self.executed_sql = sql
        return self.rows


class FakeSemanticExtractor:
    def __init__(self, frame) -> None:
        self.frame = frame
        self.calls = 0

    def extract(self, question: str):
        self.calls += 1
        return self.frame


class FakeAnswerSynthesizer:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def synthesize(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        summary: str,
        notes: tuple[str, ...],
    ) -> str:
        self.calls.append(
            {
                "question": question,
                "sql": sql,
                "rows": rows,
                "summary": summary,
                "notes": notes,
            }
        )
        return self.answer


def _pipeline(sql: str, rows: list[dict[str, Any]]):
    model = FakeModel(sql)
    executor = FakeExecutor(rows)
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        )
    )
    return pipeline, model, executor


def test_school_query_preserves_required_result_fields() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "计算机类",
            "min_score": 600,
            "min_rank": 10000,
            "enrollment_plan_count": 20,
            "selection_requirements": "物理",
            "admission_program": "国家专项",
            "city": "贵阳",
            "ownership": "公办",
            "is_double_first_class": True,
        }
    ]
    pipeline, model, executor = _pipeline(
        "SELECT school_name, major_name, min_score, min_rank "
        "FROM staging.admission_records ORDER BY min_rank ASC",
        rows,
    )

    result = pipeline.run("物理类 查询贵州大学投档线、位次、专业列表和基本信息")

    assert result.row_count == 1
    returned = result.rows[0]
    for field in (
        "school_name",
        "major_name",
        "min_score",
        "min_rank",
        "enrollment_plan_count",
        "selection_requirements",
        "admission_program",
        "city",
        "ownership",
        "is_double_first_class",
    ):
        assert field in returned
    assert result.subject_category == "物理类"
    assert result.exam_province == "贵州"
    assert result.plan_year == 2025
    assert result.citations
    assert result.citations[0].source == "staging.admission_records"
    assert "min_rank" in result.citations[0].fields
    assert result.template_name == "school_detail"
    assert model.calls == 0
    assert executor.executed_sql is not None
    assert "limit 200" in executor.executed_sql.lower()


@pytest.mark.parametrize(
    "question, expected_note",
    [
        ("查询不存在大学的投档线", "该院校在指定省份与年份下暂无数据"),
        ("查询不存在专业", "暂无该专业数据"),
        ("国家专项有哪些", "暂无该专项招生数据"),
        ("成都有哪些大学", "该地域暂无匹配院校"),
        ("物理类 公办 学费低于 5000 的学校", "无符合全部条件的结果"),
    ],
)
def test_empty_result_notes_by_category(question: str, expected_note: str) -> None:
    pipeline, _, _ = _pipeline(
        "SELECT school_name FROM staging.admission_records",
        [],
    )

    result = pipeline.run(question)

    assert result.row_count == 0
    assert any(expected_note in note for note in result.notes)
    assert result.citations


def test_multi_filter_missing_metric_is_marked_and_query_continues() -> None:
    rows = [{"school_name": "贵州大学", "min_rank": 10000}]
    pipeline, model, executor = _pipeline(
        "SELECT school_name, min_rank FROM staging.admission_records "
        "WHERE ownership = '公办' ORDER BY min_rank ASC",
        rows,
    )

    result = pipeline.run("物理类 公办 按录取均分筛选学校")

    assert result.availability.available is True
    assert result.row_count == 1
    assert result.availability.ignored_metric_conditions == ("录取均分",)
    assert result.citations
    assert any("录取均分" in note and "已被忽略" in note for note in result.notes)
    assert model.calls == 1
    assert executor.executed_sql is not None


def test_admission_search_keeps_rank_first_sorting_and_scope_notes() -> None:
    pipeline, _, executor = _pipeline(
        "SELECT school_name, min_score, min_rank "
        "FROM staging.admission_records "
        "WHERE min_rank <= 10000 ORDER BY min_rank ASC",
        [{"school_name": "贵州大学", "min_score": 600, "min_rank": 10000}],
    )

    result = pipeline.run("物理类 位次 10000 能上哪些学校")

    assert result.row_count == 1
    assert result.template_name == "admission_search_lookup"
    assert executor.executed_sql is not None
    assert "ar.min_rank >= 10000" in executor.executed_sql
    assert "order by abs(ar.min_rank - 10000)" in executor.executed_sql.lower()
    assert result.applied_filters["exam_province"] == "贵州"
    assert result.applied_filters["plan_year"] == 2025
    assert result.applied_filters["subject_category"] == "物理类"


def test_admission_feasibility_returns_confidence_summary() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "计算机类",
            "min_score": 570,
            "min_rank": 12000,
            "candidate_rank": 10000,
            "rank_gap": 2000,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    pipeline, model, executor = _pipeline(
        "SELECT school_name FROM staging.admission_records",
        rows,
    )

    result = pipeline.run("贵州物理类 位次 10000 能不能上贵州大学")

    assert result.row_count == 1
    assert result.template_name == "admission_feasibility_lookup"
    assert result.summary.startswith("参考结论：按 贵州大学 的院校记录看")
    assert "当前位次附近最接近的是计算机类" in result.summary
    assert "参考档位为“稳”" in result.summary
    assert "非概率模型结果" in result.summary
    assert result.rows[0]["confidence_band"] == "稳"
    assert model.calls == 0
    assert executor.executed_sql is not None
    assert "candidate_rank" in executor.executed_sql
    assert "rank_gap" in executor.executed_sql


def test_admission_feasibility_major_query_keeps_major_summary() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "法学",
            "min_score": 588,
            "min_rank": 9927,
            "candidate_rank": 10000,
            "rank_gap": -73,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    pipeline, _, _ = _pipeline(
        "SELECT school_name FROM staging.admission_records",
        rows,
    )

    result = pipeline.run("贵州物理类 位次 10000 能不能上贵州大学法学专业")

    assert result.summary.startswith("参考结论：贵州大学 法学 为“稳”")
    assert "院校记录看" not in result.summary


def test_llm_intent_handles_natural_feasibility_question() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "计算机类",
            "min_score": 590,
            "min_rank": 9600,
            "candidate_rank": 9500,
            "rank_gap": 100,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    model = FakeModel(
        '{"intent":"admission_feasibility","school_name":"贵州大学",'
        '"major_name":null,"subject_category":"物理类",'
        '"candidate_rank":9500,"candidate_score":null}'
    )
    executor = FakeExecutor(rows)
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        ),
        intent_extractor=IntentExtractor(model=model),
    )

    result = pipeline.run("贵州物理类 9500名，能上贵州大学的哪些专业？")

    assert result.template_name == "admission_feasibility_lookup"
    assert result.row_count == 1
    assert executor.executed_sql is not None
    assert "9500 AS candidate_rank" in executor.executed_sql
    assert "ar.school_name ILIKE '%' || '贵州大学' || '%'" in executor.executed_sql
    assert "ar.major_name ILIKE" not in executor.executed_sql
    assert model.calls == 1


def test_open_admission_search_returns_school_candidates() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "计算机类",
            "min_score": 590,
            "min_rank": 9600,
            "candidate_rank": 9500,
            "rank_gap": 100,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    pipeline, model, executor = _pipeline(
        "SELECT school_name FROM staging.admission_records",
        rows,
    )

    result = pipeline.run("贵州物理类 9500名，能上哪些大学？")

    assert result.template_name == "admission_search_lookup"
    assert result.row_count == 1
    assert result.summary.startswith("当前条件下共返回 1 条可参考录取记录")
    assert "第一条为 贵州大学 计算机类" in result.summary
    assert executor.executed_sql is not None
    assert "ar.min_rank >= 9500" in executor.executed_sql
    assert "ar.school_name ILIKE" not in executor.executed_sql
    assert model.calls == 0


def test_llm_intent_major_controls_feasibility_summary() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "软件工程",
            "min_score": 590,
            "min_rank": 9600,
            "candidate_rank": 9500,
            "rank_gap": 100,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    model = FakeModel(
        '{"intent":"admission_feasibility","school_name":"贵州大学",'
        '"major_name":"软件工程","subject_category":"物理类",'
        '"candidate_rank":9500,"candidate_score":null}'
    )
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=FakeExecutor(rows),
        ),
        intent_extractor=IntentExtractor(model=model),
    )

    result = pipeline.run("贵州物理 9500 名，贵州大学软件工程稳不稳？")

    assert result.summary.startswith("参考结论：贵州大学 软件工程 为“稳”")
    assert "院校记录看" not in result.summary


def test_llm_intent_downgrades_probability_wording_to_reference() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "软件工程",
            "min_score": 590,
            "min_rank": 9600,
            "candidate_rank": 9500,
            "rank_gap": 100,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    model = FakeModel(
        '{"intent":"admission_feasibility","school_name":"贵州大学",'
        '"major_name":"软件工程","subject_category":"物理类",'
        '"candidate_rank":9500,"candidate_score":null}'
    )
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=FakeExecutor(rows),
        ),
        intent_extractor=IntentExtractor(model=model),
    )

    result = pipeline.run("贵州物理类 9500 名，贵州大学软件工程录取概率大吗？")

    assert result.availability.available is True
    assert result.category.name == "SCORE_RANK_FILTER"
    assert result.template_name == "admission_feasibility_lookup"
    assert "非概率模型结果" in result.summary


def test_selection_requirement_marks_field_coverage_gap() -> None:
    pipeline, _, _ = _pipeline(
        "SELECT school_name, major_name, selection_requirements "
        "FROM staging.admission_records "
        "WHERE selection_requirements IS NOT NULL",
        [],
    )

    result = pipeline.run("计算机专业选科要求是什么")

    assert result.template_name == "selection_requirement_lookup"
    assert result.coverage_warnings
    assert result.coverage_warnings[0].field == "selection_requirements"
    assert any("选科要求字段暂无数据" in note for note in result.notes)


def test_multi_filter_template_does_not_call_llm_and_cites_sources() -> None:
    rows = [
        {
            "school_name": "测试大学",
            "major_name": "计算机科学与技术",
            "subject_category": "物理类",
            "min_score": 520,
            "min_rank": 30000,
            "tuition": 7000,
            "city": "贵阳",
            "ownership": "公办",
        }
    ]
    pipeline, model, executor = _pipeline("SELECT 1", rows)

    result = pipeline.run("物理类 位次 30000 公办 学费 8000 以下的计算机专业有哪些学校")

    assert result.template_name == "multi_filter_lookup"
    assert result.row_count == 1
    assert model.calls == 0
    assert executor.executed_sql is not None
    sql = executor.executed_sql.lower()
    assert "ar.min_rank <= 30000" in sql
    assert "s.ownership = '公办'" in executor.executed_sql
    assert "ar.tuition <= 8000" in sql
    assert tuple(c.source for c in result.citations) == (
        "staging.admission_records",
        "school",
    )


def test_semantic_frame_handles_open_admission_search_and_answer() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "计算机类",
            "min_score": 590,
            "min_rank": 9600,
            "candidate_rank": 9500,
            "rank_gap": 100,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    model = FakeModel("SELECT should_not_be_used")
    executor = FakeExecutor(rows)
    semantic_extractor = FakeSemanticExtractor(
        frame_from_mapping(
            {
                "route": "sql",
                "task": "admission_search",
                "exam_province": "贵州",
                "year": 2025,
                "candidate": {"rank": 9500},
                "filters": {"subject_category": "物理类"},
                "output": {"target": "schools", "limit": 10},
            }
        )
    )
    answer_synthesizer = FakeAnswerSynthesizer("可以重点看贵州大学计算机类。")
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=model),
            executor=executor,
        ),
        semantic_extractor=semantic_extractor,
        answer_synthesizer=answer_synthesizer,
    )

    result = pipeline.run("贵州物理 9500 名，有哪些学校比较稳？")

    assert result.template_name == "semantic_admission_search"
    assert result.answer == "可以重点看贵州大学计算机类。"
    assert result.row_count == 1
    assert result.category.name == "SCORE_RANK_FILTER"
    assert executor.executed_sql is not None
    assert "ar.min_rank >= 9500" in executor.executed_sql
    assert "LIMIT 10" in executor.executed_sql
    assert model.calls == 0
    assert semantic_extractor.calls == 1
    assert len(answer_synthesizer.calls) == 1


def test_semantic_frame_controls_feasibility_school_and_major_filters() -> None:
    rows = [
        {
            "school_name": "贵州大学",
            "major_name": "法学",
            "min_score": 588,
            "min_rank": 9927,
            "candidate_rank": 10000,
            "rank_gap": -73,
            "confidence_band": "稳",
            "confidence_note": "基于单年位次的参考评估，非概率模型结果",
        }
    ]
    executor = FakeExecutor(rows)
    pipeline = CatalogPipeline(
        nl2sql_pipeline=Nl2SqlPipeline(
            generator=SqlGenerator(model=FakeModel("SELECT should_not_be_used")),
            executor=executor,
        ),
        semantic_extractor=FakeSemanticExtractor(
            frame_from_mapping(
                {
                    "route": "sql",
                    "task": "admission_feasibility",
                    "candidate": {"rank": 10000},
                    "filters": {
                        "school_name": "贵州大学",
                        "major_name": "法学",
                        "subject_category": "物理类",
                    },
                    "output": {"target": "records"},
                }
            )
        ),
    )

    result = pipeline.run("贵州物理 10000 名，贵大的法学够吗？")

    assert result.template_name == "semantic_admission_feasibility"
    assert result.summary.startswith("参考结论：贵州大学 法学 为“稳”")
    assert executor.executed_sql is not None
    assert "ar.school_name ILIKE '%' || '贵州大学' || '%'" in executor.executed_sql
    assert "ar.major_name ILIKE '%' || '法学' || '%'" in executor.executed_sql
