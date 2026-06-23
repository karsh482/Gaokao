"""CatalogPipeline：在既有 NL2SQL 外层增加范围解析、闸门与结果标注。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from gaokao_nl2sql.catalog.answering import SqlAnswerSynthesizer
from gaokao_nl2sql.catalog.annotator import AvailabilityInfo, ResultAnnotator
from gaokao_nl2sql.catalog.citation import Citation, CitationBuilder
from gaokao_nl2sql.catalog.classifier import (
    ClassifiedQuery,
    QueryCategory,
    QueryClassifier,
)
from gaokao_nl2sql.catalog.coverage import (
    CoverageWarning,
    DataCoverageRegistry,
)
from gaokao_nl2sql.catalog.data_scope import DataScope, DataScopeRegistry
from gaokao_nl2sql.catalog.entities import EntityResolver
from gaokao_nl2sql.catalog.gate import AvailabilityGate, UnavailableReason
from gaokao_nl2sql.catalog.intent import AdmissionIntent, IntentExtractor
from gaokao_nl2sql.catalog.planner import QueryPlanner
from gaokao_nl2sql.catalog.scope import ScopeResolver
from gaokao_nl2sql.catalog.semantic import SemanticFrame, SemanticFrameExtractor
from gaokao_nl2sql.catalog.sql_compiler import SqlCompiler
from gaokao_nl2sql.guard import validate_select_sql
from gaokao_nl2sql.pipeline import Nl2SqlPipeline


@dataclass(slots=True)
class CatalogResult:
    """Query Catalog 编排后的查询结果。"""

    question: str
    sql: str | None
    rows: list[dict[str, Any]]
    row_count: int
    summary: str
    answer: str | None
    exam_province: str
    plan_year: int
    subject_category: str | None
    availability: AvailabilityInfo
    notes: tuple[str, ...]
    citations: tuple[Citation, ...]
    coverage_warnings: tuple[CoverageWarning, ...]
    category: QueryCategory
    applied_filters: dict[str, Any]
    template_name: str | None = None


@dataclass(slots=True)
class CatalogPipeline:
    """确定性目录编排器，不修改既有 Nl2SqlPipeline 内部逻辑。"""

    nl2sql_pipeline: Nl2SqlPipeline
    scope_resolver: ScopeResolver | None = None
    classifier: QueryClassifier | None = None
    gate: AvailabilityGate | None = None
    data_scope: DataScope | None = None
    annotator: ResultAnnotator | None = None
    citation_builder: CitationBuilder | None = None
    planner: QueryPlanner | None = None
    intent_extractor: IntentExtractor | None = None
    semantic_extractor: SemanticFrameExtractor | None = None
    entity_resolver: EntityResolver | None = None
    sql_compiler: SqlCompiler | None = None
    answer_synthesizer: SqlAnswerSynthesizer | None = None
    coverage_registry: DataCoverageRegistry | None = None

    def __post_init__(self) -> None:
        self.scope_resolver = self.scope_resolver or ScopeResolver()
        self.classifier = self.classifier or QueryClassifier()
        self.gate = self.gate or AvailabilityGate()
        self.data_scope = self.data_scope or DataScopeRegistry().current()
        self.annotator = self.annotator or ResultAnnotator()
        self.citation_builder = self.citation_builder or CitationBuilder()
        self.planner = self.planner or QueryPlanner()
        self.entity_resolver = self.entity_resolver or EntityResolver()
        self.sql_compiler = self.sql_compiler or SqlCompiler()
        self.coverage_registry = self.coverage_registry or DataCoverageRegistry()

    def run(
        self,
        question: str,
        *,
        exam_province: str | None = None,
        plan_year: int | None = None,
    ) -> CatalogResult:
        """执行 Query Catalog 编排后的查询。"""
        assert self.scope_resolver is not None
        assert self.classifier is not None
        assert self.gate is not None
        assert self.data_scope is not None
        assert self.annotator is not None
        assert self.citation_builder is not None
        assert self.planner is not None
        assert self.coverage_registry is not None

        scope = self.scope_resolver.resolve(exam_province, plan_year)
        classified = self.classifier.classify(question)
        request_provinces = self._request_provinces(
            scope.exam_province,
            exam_province,
            classified.requested_provinces,
        )
        decision = self.gate.evaluate(
            scope,
            classified,
            self.data_scope,
            request_provinces=request_provinces,
        )
        intent = AdmissionIntent(intent="other")
        if (
            not decision.allowed
            and decision.reasons == (UnavailableReason.PROBABILITY_MODEL_PENDING,)
            and self.intent_extractor is not None
        ):
            intent = self.intent_extractor.extract(question)
            if intent.is_actionable:
                classified = _as_score_rank_reference(classified)
                decision = self.gate.evaluate(
                    scope,
                    classified,
                    self.data_scope,
                    request_provinces=request_provinces,
                )

        if not decision.allowed:
            annotation = self.annotator.unavailable(scope, decision)
            return CatalogResult(
                question=question,
                sql=None,
                rows=[],
                row_count=0,
                summary=decision.message,
                answer=None,
                exam_province=annotation.exam_province,
                plan_year=annotation.plan_year,
                subject_category=annotation.subject_category,
                availability=annotation.availability,
                notes=annotation.notes,
                citations=(),
                coverage_warnings=(),
                category=classified.category,
                applied_filters=dict(annotation.applied_filters),
                template_name=None,
            )

        frame = self._extract_semantic_frame(question, scope, classified)
        if frame is not None:
            classified = _category_for_frame(frame, classified)
            intent = _intent_from_frame(frame)
            plan = self.sql_compiler.compile(frame)
        else:
            plan = None

        if (
            plan is None
            and self.intent_extractor is not None
            and intent.intent == "other"
            and _should_extract_admission_intent(question, classified)
        ):
            intent = self.intent_extractor.extract(question)
        if plan is None:
            plan = self.planner.plan(
                question=question,
                scope=scope,
                query=classified,
                intent=intent,
            )
        if plan is not None:
            safe_sql = validate_select_sql(
                plan.sql,
                default_limit=self.nl2sql_pipeline.default_limit,
                max_limit=self.nl2sql_pipeline.max_limit,
            )
            rows = self.nl2sql_pipeline.executor.run(safe_sql)
            sql = safe_sql
            template_name = plan.template_name
        else:
            scoped_question = self._scoped_question(question, scope.exam_province, scope.plan_year)
            result = self.nl2sql_pipeline.run(scoped_question)
            rows = result.rows
            sql = result.sql
            template_name = None
        annotation = self.annotator.annotate(
            scope=scope,
            decision=decision,
            question=question,
            category=classified.category,
            rows=rows,
        )
        citations = self.citation_builder.build(
            category=classified.category,
            scope=scope,
            rows=rows,
        )
        coverage_warnings = self.coverage_registry.warnings_for(
            category=classified.category,
            question=question,
        )
        notes = annotation.notes + tuple(w.message for w in coverage_warnings)
        summary = _build_summary(
            template_name=template_name,
            question=question,
            rows=rows,
            notes=notes,
            intent=intent,
        )
        answer = self._synthesize_answer(
            question=question,
            sql=sql,
            rows=rows,
            summary=summary,
            notes=notes,
        )
        return CatalogResult(
            question=question,
            sql=sql,
            rows=rows,
            row_count=len(rows),
            summary=summary,
            answer=answer,
            exam_province=annotation.exam_province,
            plan_year=annotation.plan_year,
            subject_category=annotation.subject_category,
            availability=annotation.availability,
            notes=notes,
            citations=citations,
            coverage_warnings=coverage_warnings,
            category=classified.category,
            applied_filters=dict(annotation.applied_filters),
            template_name=template_name,
        )

    def _extract_semantic_frame(
        self,
        question: str,
        scope,
        classified: ClassifiedQuery,
    ) -> SemanticFrame | None:
        assert self.entity_resolver is not None
        if self.semantic_extractor is None:
            return None
        if not _should_extract_semantic_frame(question, classified):
            return None
        frame = self.semantic_extractor.extract(question)
        if frame.task == "generic" or frame.route != "sql":
            return None
        return self.entity_resolver.resolve(frame, scope)

    def _synthesize_answer(
        self,
        *,
        question: str,
        sql: str | None,
        rows: list[dict[str, Any]],
        summary: str,
        notes: tuple[str, ...],
    ) -> str | None:
        if self.answer_synthesizer is None or sql is None:
            return None
        return self.answer_synthesizer.synthesize(
            question=question,
            sql=sql,
            rows=rows,
            summary=summary,
            notes=notes,
        )

    @staticmethod
    def _request_provinces(
        scope_province: str,
        explicit_province: str | None,
        mentioned_provinces: frozenset[str],
    ) -> frozenset[str]:
        if explicit_province is not None:
            return frozenset({explicit_province}) | mentioned_provinces
        if mentioned_provinces:
            return mentioned_provinces
        return frozenset({scope_province})

    @staticmethod
    def _scoped_question(question: str, exam_province: str, plan_year: int) -> str:
        return (
            f"{question.strip()}\n\n"
            f"查询范围限定：exam_province='{exam_province}'，plan_year={plan_year}。"
        )


def _as_score_rank_reference(query: ClassifiedQuery) -> ClassifiedQuery:
    """把口语化概率问题降级为单年分数/位次参考评估。"""

    return ClassifiedQuery(
        category=QueryCategory.SCORE_RANK_FILTER,
        requested_metrics=query.requested_metrics,
        requested_provinces=query.requested_provinces,
        requires_probability_model=False,
    )


def _category_for_frame(frame: SemanticFrame, fallback: ClassifiedQuery) -> ClassifiedQuery:
    """把语义帧任务映射回 Query Catalog 的确定性类别。"""

    if frame.task in {"admission_search", "admission_feasibility"}:
        return ClassifiedQuery(
            category=QueryCategory.SCORE_RANK_FILTER,
            requested_metrics=fallback.requested_metrics,
            requested_provinces=fallback.requested_provinces,
            requires_probability_model=False,
        )
    return fallback


def _intent_from_frame(frame: SemanticFrame) -> AdmissionIntent:
    """复用既有摘要逻辑需要的最小录取意图对象。"""

    if frame.task not in {"admission_search", "admission_feasibility"}:
        return AdmissionIntent(intent="other")
    return AdmissionIntent(
        intent=frame.task,
        school_name=frame.filters.school_name,
        major_name=frame.filters.major_name,
        subject_category=frame.filters.subject_category,
        candidate_rank=frame.candidate.rank,
        candidate_score=frame.candidate.score,
    )


def _should_extract_semantic_frame(
    question: str,
    query: ClassifiedQuery,
) -> bool:
    """限制语义帧抽取范围，避免无关问题消耗 LLM。"""

    return _should_extract_admission_intent(question, query)


def _should_extract_admission_intent(
    question: str,
    query: ClassifiedQuery,
) -> bool:
    """限制 LLM 意图抽取触发范围，避免普通查询无谓调用模型。"""

    if _score_or_rank_hint(question) and _admission_target_hint(question):
        return True
    if query.category in {
        QueryCategory.SCHOOL,
        QueryCategory.MAJOR,
        QueryCategory.SCORE_RANK_FILTER,
        QueryCategory.ADMISSION_PROBABILITY,
        QueryCategory.MULTI_FILTER,
    }:
        return bool(_score_or_rank_hint(question))
    return False


def _score_or_rank_hint(question: str) -> bool:
    return bool(re.search(r"\d+\s*(?:分|名|位)", question) or "位次" in question)


def _admission_target_hint(question: str) -> bool:
    return any(
        token in question
        for token in ("大学", "学院", "学校", "院校", "高校", "专业", "法学", "医学", "工科")
    )


def _build_summary(
    *,
    template_name: str | None,
    question: str,
    rows: list[dict[str, Any]],
    notes: tuple[str, ...],
    intent: AdmissionIntent | None = None,
) -> str:
    """构造给前端直接展示的保守摘要。"""

    if not rows:
        return notes[-1] if notes else "当前范围内暂无数据。"

    if template_name in {
        "admission_feasibility_lookup",
        "admission_search_lookup",
        "semantic_admission_feasibility",
        "semantic_admission_search",
    }:
        first = rows[0]
        school = first.get("school_name") or "目标院校"
        major = first.get("major_name") or "相关专业"
        band = first.get("confidence_band") or "参考"
        note = first.get("confidence_note") or "基于历史数据的参考评估，非录取承诺。"
        has_major = _has_major_intent(question, intent)
        if template_name in {"admission_search_lookup", "semantic_admission_search"}:
            if first.get("candidate_rank") is not None:
                return (
                    f"当前条件下共返回 {len(rows)} 条可参考录取记录。"
                    f"排序按最低位次从高到低，第一条为 {school} {major}，"
                    f"2025 年最低位次 {first.get('min_rank')}。{note}"
                )
            if first.get("candidate_score") is not None:
                return (
                    f"当前条件下共返回 {len(rows)} 条可参考录取记录。"
                    f"排序按最低位次从高到低，第一条为 {school} {major}，"
                    f"2025 年最低分 {first.get('min_score')}。{note}"
                )
            return f"当前条件下共返回 {len(rows)} 条可参考录取记录。{note}"
        if first.get("candidate_rank") is not None and first.get("min_rank") is not None:
            basis = (
                f"依据：考生位次 {first.get('candidate_rank')}，"
                f"该记录 2025 年最低位次 {first.get('min_rank')}，"
                f"位次差 {first.get('rank_gap')}。{note}"
            )
            if not has_major:
                return (
                    f"参考结论：按 {school} 的院校记录看，当前位次附近最接近的是"
                    f"{major}，参考档位为“{band}”。{basis}"
                )
            return (
                f"参考结论：{school} {major} 为“{band}”。"
                f"{basis}"
            )
        if first.get("candidate_score") is not None and first.get("min_score") is not None:
            basis = (
                f"依据：考生分数 {first.get('candidate_score')}，"
                f"该记录 2025 年最低分 {first.get('min_score')}，"
                f"分差 {first.get('score_gap')}。{note}"
            )
            if not has_major:
                return (
                    f"参考结论：按 {school} 的院校记录看，当前分数附近最接近的是"
                    f"{major}，参考档位为“{band}”。{basis}"
                )
            return (
                f"参考结论：{school} {major} 为“{band}”。"
                f"{basis}"
            )
        if not has_major:
            return f"参考结论：按 {school} 的院校记录看，最接近的是{major}，参考档位为“{band}”。{note}"
        return f"参考结论：{school} {major} 为“{band}”。{note}"

    if template_name == "score_rank_filter":
        return f"当前条件下共返回 {len(rows)} 条可参考记录，按最低位次从高到低排序。"
    if template_name == "multi_filter_lookup":
        return f"当前组合条件下共返回 {len(rows)} 条可参考记录。"
    if template_name == "school_detail":
        return f"当前院校查询共返回 {len(rows)} 条专业/批次记录。"
    if template_name == "major_lookup":
        return f"当前专业查询共返回 {len(rows)} 条院校/专业记录。"
    return f"当前查询共返回 {len(rows)} 条记录。"


def _question_has_major_intent(question: str) -> bool:
    """判断用户是否指定了具体专业，避免院校整体查询被描述为单专业结论。"""

    major_keywords = ("计算机", "临床医学", "医学", "法学", "会计")
    return any(keyword in question for keyword in major_keywords)


def _has_major_intent(question: str, intent: AdmissionIntent | None) -> bool:
    if intent is not None and intent.is_actionable:
        return bool(intent.major_name)
    return _question_has_major_intent(question)
