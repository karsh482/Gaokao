"""QueryClassifier：把自然语言问题归类到 15 类查询之一（或通用类）。

分类用于决定可用性闸门策略（趋势类、政策类直接短路；缺失指标短路或降级标注），
并抽取问题中引用到的缺失指标名。识别基于关键词/意图标志位，确定性、可单测。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryCategory(Enum):
    """15 类查询 + 通用结构化查询。"""

    SCHOOL = "school"
    MAJOR = "major"
    SCORE_RANK_FILTER = "score_rank_filter"
    COMPARE = "compare"
    TREND = "trend"
    STATS_RANK = "stats_rank"
    SCORE_RANK_CONVERT = "score_rank_convert"
    ENROLLMENT_PLAN = "enrollment_plan"
    SELECTION_REQ = "selection_req"
    SPECIAL_PROGRAM = "special_program"
    MULTI_FILTER = "multi_filter"
    REGION = "region"
    ADMISSION_PROBABILITY = "admission_probability"
    POLICY_EXPLAIN = "policy_explain"
    GENERIC = "generic"


@dataclass(frozen=True)
class ClassifiedQuery:
    """分类结果与抽取到的引用指标。"""

    category: QueryCategory
    requested_metrics: frozenset[str]
    requested_provinces: frozenset[str] = frozenset()
    requires_probability_model: bool = False


# 缺失指标关键词（用于检测请求是否引用了当前无数据的指标）。
_METRIC_KEYWORDS: tuple[str, ...] = (
    "录取均分",
    "平均分",
    "实际录取人数",
    "录取人数",
    "985",
    "211",
)

# 指标关键词归一到 DataScope.unavailable_metrics 中登记的指标名。
_METRIC_NORMALIZE: dict[str, str] = {
    "录取均分": "录取均分",
    "平均分": "录取均分",
    "实际录取人数": "实际录取人数",
    "录取人数": "实际录取人数",
    "985": "985",
    "211": "211",
}

# 各类别关键词。顺序即优先级：靠前的意图先于靠后的通用筛选判定。
_TREND_KEYWORDS = ("趋势", "涨幅", "跌幅", "逐年", "历年", "近几年", "近年", "变化趋势", "走势")
_POLICY_KEYWORDS = ("什么意思", "政策", "规则", "解释", "如何理解", "怎么算", "含义", "什么是")
_PROBABILITY_KEYWORDS = ("概率", "把握", "冲稳保", "能不能上", "录取可能", "几率", "希望大吗")
_CONVERT_KEYWORDS = ("一分一段", "排名对应", "分数对应", "换算", "对应位次", "对应分数")
_SELECTION_REQUIREMENT_KEYWORDS = (
    "选科要求",
    "科目要求",
    "需要选",
    "要选",
    "选哪些科目",
    "选什么科",
)
_SUBJECT_FILTER_KEYWORDS = ("物理类", "历史类", "选科", "选考", "首选", "再选")
_SPECIAL_KEYWORDS = ("专项", "国家专项", "地方专项", "高校专项", "民族班", "预科", "定向", "中外合作")
_REGION_KEYWORDS = (
    "所在地",
    "城市",
    "省份的大学",
    "哪个城市",
    "位于",
    "地处",
    "本省",
    "省内",
    "省外",
    "有哪些大学",
    "有哪些院校",
    "有哪些学校",
)
_ENROLLMENT_KEYWORDS = (
    "招生计划",
    "计划人数",
    "招多少",
    "招几人",
    "招几个人",
    "招几个",
    "招几名",
    "计划招生",
    "招生名额",
    "招生人数",
    "招收人数",
    "计划招聘人数",
    "招聘人数",
)
_PROGRAM_LIST_KEYWORDS = (
    "有哪些专业",
    "专业有哪些",
    "招收哪些专业",
    "招哪些专业",
    "开设哪些专业",
    "开设什么专业",
    "招什么专业",
)
_PLAN_CHANGE_KEYWORDS = (
    "是否有变化",
    "有没有变化",
    "有变化吗",
    "变化",
    "变了吗",
    "对比",
    "比较",
    "比去年",
    "比2025",
    "比 2025",
    "增加",
    "减少",
    "多招",
    "少招",
)
_STATS_KEYWORDS = ("排名", "排行", "统计", "最高", "最低", "平均", "数量最多", "前几", "排序")
_COMPARE_KEYWORDS = ("对比", "比较", "哪个更", "和", "与", "vs", "相比", "谁更")
_MAJOR_KEYWORDS = ("专业", "学科", "院系")
_SCHOOL_KEYWORDS = ("大学", "学院", "学校", "院校", "高校")
_SCORE_RANK_FILTER_KEYWORDS = ("能上", "能报", "可以上", "够得上", "多少分", "分能", "位次能")
_PROVINCE_KEYWORDS = (
    "贵州",
    "四川",
    "云南",
    "重庆",
    "北京",
    "上海",
    "广东",
    "广西",
    "湖南",
    "湖北",
    "河南",
    "河北",
    "山东",
    "山西",
    "陕西",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "辽宁",
    "吉林",
    "黑龙江",
    "内蒙古",
    "宁夏",
    "青海",
    "甘肃",
    "新疆",
    "西藏",
    "海南",
    "天津",
)
_EXACT_PROBABILITY_KEYWORDS = ("概率", "几率", "录取可能")
_SPECIFIC_SCHOOL_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,30}(?:大学|学院|学校))")


def _extract_metrics(question: str) -> frozenset[str]:
    """抽取问题中引用到的（可能缺失的）指标名。"""
    found: set[str] = set()
    for keyword in _METRIC_KEYWORDS:
        if keyword in question:
            found.add(_METRIC_NORMALIZE[keyword])
    return frozenset(found)


def _extract_provinces(question: str) -> frozenset[str]:
    """抽取问题中显式提到的考试/招生省份候选。"""
    found: set[str] = set()
    province_context = ("高考", "招生", "考生", "录取", "投档", "数据", "省份")
    subject_context = ("物理类", "历史类", "物理", "历史")
    for province in _PROVINCE_KEYWORDS:
        if province not in question:
            continue
        if f"{province}大学" in question or f"{province}学院" in question:
            continue
        has_province_suffix = f"{province}省" in question
        has_context = any(
            re.search(rf"{re.escape(province)}.{{0,6}}{keyword}", question)
            or re.search(rf"{keyword}.{{0,6}}{re.escape(province)}", question)
            for keyword in province_context
        )
        has_subject_context = any(
            re.search(rf"{re.escape(province)}.{{0,6}}{keyword}", question)
            for keyword in subject_context
        )
        if has_province_suffix or has_context or has_subject_context:
            found.add(province)
    return frozenset(found)


def _count_filter_dimensions(question: str) -> int:
    """粗略统计问题中出现的筛选维度数量，用于识别多条件组合筛选。"""
    dimensions = 0
    groups = (
        _SUBJECT_FILTER_KEYWORDS,
        _SPECIAL_KEYWORDS,
        _REGION_KEYWORDS,
        _SCORE_RANK_FILTER_KEYWORDS,
        ("学费", "公办", "民办", "类型"),
        _METRIC_KEYWORDS,
    )
    for group in groups:
        if any(kw in question for kw in group):
            dimensions += 1
    return dimensions


def _mentions_specific_school(question: str) -> bool:
    """判断问题中是否出现具体院校名，避免把“有哪些学校”误判成院校名。"""
    for match in _SPECIFIC_SCHOOL_PATTERN.finditer(question):
        school = match.group(1)
        if any(token in school for token in ("哪些", "什么", "哪所", "哪几所")):
            continue
        return True
    return False


def _looks_like_program_list_question(question: str) -> bool:
    """“某校有哪些/招哪些专业”应走招生专业目录，而不是 2025 投档专业检索。"""
    return _mentions_specific_school(question) and any(
        keyword in question for keyword in _PROGRAM_LIST_KEYWORDS
    )


def _looks_like_plan_change_question(question: str) -> bool:
    """招生计划人数变化类问题需要跨 2025/2026 两张表对比。"""
    if not _mentions_specific_school(question):
        return False
    has_plan_signal = any(keyword in question for keyword in _ENROLLMENT_KEYWORDS) or (
        "专业" in question and any(keyword in question for keyword in ("招", "招生"))
    )
    has_change_signal = any(keyword in question for keyword in _PLAN_CHANGE_KEYWORDS)
    return has_plan_signal and has_change_signal


@dataclass(frozen=True)
class QueryClassifier:
    """基于关键词/意图标志位的查询分类器。"""

    def classify(self, question: str) -> ClassifiedQuery:
        metrics = _extract_metrics(question)
        provinces = _extract_provinces(question)
        category = self._categorize(question, metrics)
        if category is QueryCategory.ENROLLMENT_PLAN:
            metrics = frozenset(
                metric for metric in metrics if metric != "实际录取人数"
            )
        requires_probability_model = (
            category is QueryCategory.ADMISSION_PROBABILITY
            and any(kw in question for kw in _EXACT_PROBABILITY_KEYWORDS)
        )
        return ClassifiedQuery(
            category=category,
            requested_metrics=metrics,
            requested_provinces=provinces,
            requires_probability_model=requires_probability_model,
        )

    def _categorize(
        self, question: str, metrics: frozenset[str]
    ) -> QueryCategory:
        text = question

        if _looks_like_plan_change_question(text):
            return QueryCategory.ENROLLMENT_PLAN
        if any(kw in text for kw in _TREND_KEYWORDS):
            return QueryCategory.TREND
        if any(kw in text for kw in _PROBABILITY_KEYWORDS):
            return QueryCategory.ADMISSION_PROBABILITY
        if any(kw in text for kw in _POLICY_KEYWORDS):
            return QueryCategory.POLICY_EXPLAIN
        if any(kw in text for kw in _CONVERT_KEYWORDS) or (
            "位次" in text and "对应" in text
        ):
            return QueryCategory.SCORE_RANK_CONVERT

        if any(kw in text for kw in _SELECTION_REQUIREMENT_KEYWORDS):
            return QueryCategory.SELECTION_REQ
        if _looks_like_program_list_question(text):
            return QueryCategory.ENROLLMENT_PLAN
        if any(kw in text for kw in _ENROLLMENT_KEYWORDS):
            return QueryCategory.ENROLLMENT_PLAN
        if any(kw in text for kw in _SPECIAL_KEYWORDS):
            return QueryCategory.SPECIAL_PROGRAM

        # 多条件组合筛选：出现两个及以上筛选维度。
        if _count_filter_dimensions(text) >= 2:
            return QueryCategory.MULTI_FILTER

        if any(kw in text for kw in _COMPARE_KEYWORDS):
            return QueryCategory.COMPARE

        # 统计/排名：缺失指标作为主要输出（录取均分排名、录取人数统计）走此类。
        if any(kw in text for kw in _STATS_KEYWORDS):
            return QueryCategory.STATS_RANK

        if any(kw in text for kw in _REGION_KEYWORDS):
            return QueryCategory.REGION
        if any(kw in text for kw in _SUBJECT_FILTER_KEYWORDS):
            return QueryCategory.SELECTION_REQ
        if any(kw in text for kw in _SCORE_RANK_FILTER_KEYWORDS):
            return QueryCategory.SCORE_RANK_FILTER
        if any(kw in text for kw in _MAJOR_KEYWORDS):
            return QueryCategory.MAJOR
        if any(kw in text for kw in _SCHOOL_KEYWORDS):
            return QueryCategory.SCHOOL

        return QueryCategory.GENERIC
