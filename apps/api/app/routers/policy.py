"""政策 / 招生章程检索接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from gaokao_rag import PolicyRagError, PolicyRagPipeline

from app.dependencies import get_policy_rag_pipeline, require_api_key
from app.models import PolicyQueryRequest, PolicyQueryResponse

router = APIRouter(tags=["policy"])


@router.post(
    "/policy/query",
    response_model=PolicyQueryResponse,
    dependencies=[Depends(require_api_key)],
)
def policy_query(
    request: PolicyQueryRequest,
    pipeline: PolicyRagPipeline = Depends(get_policy_rag_pipeline),
) -> PolicyQueryResponse:
    try:
        result = pipeline.query(
            request.question,
            school=request.school,
            year=request.year,
            category=request.category,
            province=request.province,
            plan_year=request.plan_year,
            document_type=request.document_type,
            top_k=request.top_k,
        )
    except PolicyRagError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"政策检索失败: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PolicyQueryResponse(
        question=result.question,
        answer=result.answer,
        result_count=result.result_count,
        results=[
            {
                "id": item.id,
                "document_uid": item.document_uid,
                "global_chunk_id": item.global_chunk_id,
                "local_chunk_id": item.local_chunk_id,
                "title": item.title,
                "category": item.category,
                "content_type": item.content_type,
                "chunk_role": item.chunk_role,
                "snippet": item.snippet,
                "similarity": item.similarity,
                "source_url": item.source_url,
                "source": item.source,
                "school_name": item.school_name,
                "province": item.province,
                "document_year": item.document_year,
                "page_number": item.page_number,
                "page_side": item.page_side,
                "heading_path": list(item.heading_path),
                "table_title": item.table_title,
                "context_text": item.context_text if request.include_context else None,
                "context_chunk_ids": list(item.context_chunk_ids),
            }
            for item in result.results
        ],
        citations=[
            {
                "title": citation.title,
                "category": citation.category,
                "source_url": citation.source_url,
                "source": citation.source,
                "school_name": citation.school_name,
                "province": citation.province,
                "document_year": citation.document_year,
                "page_number": citation.page_number,
                "page_side": citation.page_side,
                "heading_path": list(citation.heading_path),
                "table_title": citation.table_title,
                "global_chunk_id": citation.global_chunk_id,
                "local_chunk_id": citation.local_chunk_id,
            }
            for citation in result.citations
        ],
        notes=list(result.notes),
    )
