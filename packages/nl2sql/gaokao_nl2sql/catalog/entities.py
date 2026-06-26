"""实体归一化：把语义帧补齐为当前数据范围可执行的查询条件。"""

from __future__ import annotations

from dataclasses import dataclass

from gaokao_nl2sql.catalog.scope import QueryScope
from gaokao_nl2sql.catalog.semantic import (
    CandidateProfile,
    QueryFilters,
    QueryOutput,
    SemanticFrame,
)

_PROVINCE_NAMES = {
    "四川",
    "四川省",
    "云南",
    "云南省",
    "重庆",
    "重庆市",
    "北京",
    "北京市",
    "上海",
    "上海市",
    "广东",
    "广东省",
    "广西",
    "广西壮族自治区",
    "湖南",
    "湖南省",
    "湖北",
    "湖北省",
    "河南",
    "河南省",
    "河北",
    "河北省",
    "山东",
    "山东省",
    "山西",
    "山西省",
    "陕西",
    "陕西省",
    "江苏",
    "江苏省",
    "浙江",
    "浙江省",
    "安徽",
    "安徽省",
    "福建",
    "福建省",
    "江西",
    "江西省",
    "辽宁",
    "辽宁省",
    "吉林",
    "吉林省",
    "黑龙江",
    "黑龙江省",
    "内蒙古",
    "宁夏",
    "青海",
    "青海省",
    "甘肃",
    "甘肃省",
    "新疆",
    "西藏",
    "海南",
    "海南省",
    "天津",
    "天津市",
}


@dataclass(frozen=True, slots=True)
class EntityResolver:
    """轻量实体归一化器。

    当前先做确定性标准化；后续可接学校/专业别名表，不改变 Pipeline 接口。
    """

    def resolve(self, frame: SemanticFrame, scope: QueryScope) -> SemanticFrame:
        filters = frame.filters
        subject_category = filters.subject_category
        if subject_category == "物理":
            subject_category = "物理类"
        elif subject_category == "历史":
            subject_category = "历史类"
        school_province = _clean_text(filters.school_province)
        city = _clean_text(filters.city)
        if school_province is None and city in _PROVINCE_NAMES:
            school_province = city.removesuffix("省").removesuffix("市")
            city = None

        return SemanticFrame(
            route=frame.route,
            task=frame.task,
            exam_province=frame.exam_province or scope.exam_province,
            year=frame.year or scope.plan_year,
            candidate=CandidateProfile(
                rank=frame.candidate.rank,
                score=frame.candidate.score,
                rank_adjustment=frame.candidate.rank_adjustment,
            ),
            filters=QueryFilters(
                school_name=_clean_text(filters.school_name),
                major_name=_clean_text(filters.major_name),
                subject_category=subject_category,
                school_province=school_province,
                city=city,
                ownership=filters.ownership,
                tuition_max=filters.tuition_max,
                special_program=_clean_text(filters.special_program),
                batch=_clean_text(filters.batch),
            ),
            output=QueryOutput(
                target=frame.output.target,
                group_by=frame.output.group_by,
                sort=frame.output.sort,
                limit=max(1, min(frame.output.limit, 200)),
            ),
            missing_required=frame.missing_required,
            confidence=frame.confidence,
        )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
