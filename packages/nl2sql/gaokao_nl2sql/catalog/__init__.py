"""Query Catalog：确定性纯逻辑组件。

在既有三段式 NL2SQL 链路外包裹范围解析、可用性闸门与结果标注，
保证诚实的数据可用性反馈（不虚构超范围数据）。核心组件保持确定性，
可选注入 LLM 意图抽取器增强自然语言鲁棒性。
"""

from __future__ import annotations

from gaokao_nl2sql.catalog.annotator import (
    AvailabilityInfo,
    ResultAnnotation,
    ResultAnnotator,
)
from gaokao_nl2sql.catalog.citation import Citation, CitationBuilder
from gaokao_nl2sql.catalog.classifier import ClassifiedQuery, QueryCategory, QueryClassifier
from gaokao_nl2sql.catalog.coverage import CoverageWarning, DataCoverageRegistry
from gaokao_nl2sql.catalog.answering import (
    OpenAICompatibleSqlAnswerSynthesizer,
    SqlAnswerSynthesizer,
)
from gaokao_nl2sql.catalog.converter import (
    ConversionResult,
    ScoreRankConverter,
    ScoreSegment,
)
from gaokao_nl2sql.catalog.data_scope import DataScope, DataScopeRegistry
from gaokao_nl2sql.catalog.entities import EntityResolver
from gaokao_nl2sql.catalog.gate import AvailabilityGate, GateDecision, UnavailableReason
from gaokao_nl2sql.catalog.intent import AdmissionIntent, IntentExtractor
from gaokao_nl2sql.catalog.pipeline import CatalogPipeline, CatalogResult
from gaokao_nl2sql.catalog.planner import QueryPlan, QueryPlanner
from gaokao_nl2sql.catalog.probability import (
    AdmissionConfidence,
    ConfidenceBand,
    ConfidenceReference,
)
from gaokao_nl2sql.catalog.scope import QueryScope, ScopeResolver
from gaokao_nl2sql.catalog.semantic import (
    CandidateProfile,
    QueryFilters,
    QueryOutput,
    SemanticFrame,
    SemanticFrameExtractor,
)
from gaokao_nl2sql.catalog.sql_compiler import SqlCompiler

__all__ = [
    "AdmissionConfidence",
    "AdmissionIntent",
    "AvailabilityGate",
    "AvailabilityInfo",
    "CatalogPipeline",
    "CatalogResult",
    "CandidateProfile",
    "Citation",
    "CitationBuilder",
    "ClassifiedQuery",
    "ConfidenceBand",
    "ConfidenceReference",
    "ConversionResult",
    "CoverageWarning",
    "DataScope",
    "DataCoverageRegistry",
    "DataScopeRegistry",
    "EntityResolver",
    "GateDecision",
    "IntentExtractor",
    "OpenAICompatibleSqlAnswerSynthesizer",
    "QueryCategory",
    "QueryFilters",
    "QueryOutput",
    "QueryPlan",
    "QueryPlanner",
    "QueryClassifier",
    "QueryScope",
    "ResultAnnotation",
    "ResultAnnotator",
    "ScopeResolver",
    "ScoreRankConverter",
    "ScoreSegment",
    "SemanticFrame",
    "SemanticFrameExtractor",
    "SqlAnswerSynthesizer",
    "SqlCompiler",
    "UnavailableReason",
]
