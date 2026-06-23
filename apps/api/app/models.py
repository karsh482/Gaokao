"""请求 / 响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="自然语言问题")
    exam_province: str | None = Field(default=None, description="考试/招生省份")
    plan_year: int | None = Field(default=None, description="招生年份")


class AvailabilityInfo(BaseModel):
    available: bool
    reasons: list[str] = Field(default_factory=list)
    message: str = ""
    ignored_metric_conditions: list[str] = Field(default_factory=list)


class CitationInfo(BaseModel):
    source: str
    label: str
    fields: list[str] = Field(default_factory=list)
    exam_province: str
    plan_year: int
    note: str = ""


class CoverageWarningInfo(BaseModel):
    field: str
    label: str
    coverage_ratio: float
    message: str


class QueryResponse(BaseModel):
    question: str
    sql: str | None
    row_count: int
    summary: str = ""
    answer: str | None = None
    rows: list[dict[str, Any]]
    exam_province: str
    plan_year: int
    subject_category: str | None = None
    availability: AvailabilityInfo
    notes: list[str] = Field(default_factory=list)
    citations: list[CitationInfo] = Field(default_factory=list)
    coverage_warnings: list[CoverageWarningInfo] = Field(default_factory=list)
    template_name: str | None = None


class PolicyQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="政策/章程检索问题")
    school: str | None = Field(default=None, description="学校名称")
    year: int | None = Field(default=None, description="文档年份")
    category: str | None = Field(default=None, description="RAG 文档类别")
    province: str | None = Field(default=None, description="政策适用省份")
    plan_year: int | None = Field(default=None, description="兼容旧字段：政策年份")
    document_type: str | None = Field(default=None, description="兼容旧字段：政策文档类型")
    top_k: int | None = Field(default=None, ge=1, le=20, description="返回候选数量")
    include_context: bool = Field(default=False, description="是否返回完整扩展上下文")


class PolicyResultInfo(BaseModel):
    id: int
    document_uid: str
    global_chunk_id: str
    local_chunk_id: str
    title: str
    category: str
    content_type: str
    chunk_role: str
    snippet: str
    similarity: float
    source_url: str | None = None
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    table_title: str | None = None
    context_text: str | None = None
    context_chunk_ids: list[str] = Field(default_factory=list)


class PolicyCitationInfo(BaseModel):
    title: str
    category: str
    source_url: str | None = None
    source: str | None = None
    school_name: str | None = None
    province: str | None = None
    document_year: int | None = None
    page_number: int | None = None
    page_side: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    table_title: str | None = None
    global_chunk_id: str | None = None
    local_chunk_id: str | None = None


class PolicyQueryResponse(BaseModel):
    question: str
    answer: str | None = None
    result_count: int
    results: list[PolicyResultInfo] = Field(default_factory=list)
    citations: list[PolicyCitationInfo] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    database: str
