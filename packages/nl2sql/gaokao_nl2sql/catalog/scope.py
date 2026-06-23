"""ScopeResolver：把可选的 exam_province / plan_year 解析为本次实际采用的范围。

缺省时回落到默认范围（贵州 / 2025），并通过 used_default_* 标注是否使用了默认值，
供 ResultAnnotator 在响应中如实呈现所采用的口径。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryScope:
    """一次查询实际采用的范围口径。"""

    exam_province: str
    plan_year: int
    used_default_province: bool
    used_default_year: bool


@dataclass(frozen=True)
class ScopeResolver:
    """范围解析器：未提供参数时回落到默认范围并标注。"""

    default_province: str = "贵州"
    default_year: int = 2025

    def resolve(
        self,
        exam_province: str | None,
        plan_year: int | None,
    ) -> QueryScope:
        """解析实际采用的考试省份与招生年份。

        未提供（None）时回落默认值并置 used_default_*=True；
        已提供时原样采用并置 used_default_*=False。
        """
        used_default_province = exam_province is None
        used_default_year = plan_year is None
        return QueryScope(
            exam_province=self.default_province
            if used_default_province
            else exam_province,
            plan_year=self.default_year if used_default_year else plan_year,
            used_default_province=used_default_province,
            used_default_year=used_default_year,
        )
