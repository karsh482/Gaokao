"""自然语言查询接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from gaokao_nl2sql import (
    CatalogPipeline,
    SqlExecutionError,
    SqlGenerationError,
    UnsafeSqlError,
)

from app.dependencies import (
    get_pipeline_for_request,
    get_query_rewrite_model_for_request,
    require_api_key,
)
from app.models import QueryRequest, QueryResponse
from app.query_rewrite import (
    RewriteModel,
    rewrite_follow_up_question,
    rewrite_structured_query_fallback,
)

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_api_key)],
)
def query(
    request: QueryRequest,
    pipeline: CatalogPipeline = Depends(get_pipeline_for_request),
    rewrite_model: RewriteModel | None = Depends(get_query_rewrite_model_for_request),
) -> QueryResponse:
    model = rewrite_model if hasattr(rewrite_model, "complete") else None
    effective_question = rewrite_follow_up_question(
        question=request.question,
        history=request.history,
        exam_province=request.exam_province,
        plan_year=request.plan_year,
        model=model,
    ).question
    result = _run_pipeline(
        pipeline,
        effective_question,
        exam_province=request.exam_province,
        plan_year=request.plan_year,
    )
    if _should_retry_with_query_rewrite(result):
        fallback = rewrite_structured_query_fallback(
            question=effective_question,
            exam_province=request.exam_province,
            plan_year=request.plan_year,
            model=model,
        )
        if fallback.rewritten:
            retry_result = _run_pipeline(
                pipeline,
                fallback.question,
                exam_province=request.exam_province,
                plan_year=request.plan_year,
            )
            if _should_use_rewrite_result(retry_result):
                result = retry_result

    return _to_response(result)


def _run_pipeline(
    pipeline: CatalogPipeline,
    question: str,
    *,
    exam_province: str | None,
    plan_year: int | None,
):
    try:
        return pipeline.run(question, exam_province=exam_province, plan_year=plan_year)
    except SqlGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SQL 生成失败: {exc}",
        ) from exc
    except UnsafeSqlError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"生成的查询未通过安全校验: {exc}",
        ) from exc
    except SqlExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询执行失败: {exc}",
        ) from exc


def _should_retry_with_query_rewrite(result) -> bool:
    return (
        result.availability.available
        and result.row_count == 0
        and result.template_name is None
    )


def _should_use_rewrite_result(result) -> bool:
    return result.availability.available and (
        result.row_count > 0 or result.template_name is not None
    )


def _to_response(result) -> QueryResponse:
    return QueryResponse(
        question=result.question,
        sql=result.sql,
        row_count=result.row_count,
        summary=result.summary,
        answer=result.answer,
        rows=result.rows,
        exam_province=result.exam_province,
        plan_year=result.plan_year,
        subject_category=result.subject_category,
        availability={
            "available": result.availability.available,
            "reasons": list(result.availability.reasons),
            "message": result.availability.message,
            "ignored_metric_conditions": list(
                result.availability.ignored_metric_conditions
            ),
        },
        notes=list(result.notes),
        citations=[
            {
                "source": citation.source,
                "label": citation.label,
                "fields": list(citation.fields),
                "exam_province": citation.exam_province,
                "plan_year": citation.plan_year,
                "note": citation.note,
            }
            for citation in result.citations
        ],
        coverage_warnings=[
            {
                "field": warning.field,
                "label": warning.label,
                "coverage_ratio": warning.coverage_ratio,
                "message": warning.message,
            }
            for warning in result.coverage_warnings
        ],
        template_name=result.template_name,
    )
