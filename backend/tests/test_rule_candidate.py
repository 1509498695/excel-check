"""AI 规则候选识别算法回归。"""

from __future__ import annotations

from backend.app.ai.rule_candidate import build_rule_candidates, critique_rule_candidate
from backend.app.ai.schemas import AiRuleWorkflowHints


def test_rule_candidate_fixed_template_recognizes_dual_compare() -> None:
    """固定模板里的两条筛选规则应收窄为跨组变量校验。"""
    description = """数据源：https://samosvn/data/project/samo/GameDatas/datas_qa88/battlepass.xls
sheet分页：level_reward
变量选择：INT_Level,INT_Index,INT_FreeRewardSubType,INT_FreeRewardValue

筛选规则1：INT_Index=1012

筛选规则2：INT_Index=1010

校验规则：以 INT_Level 为 key，判断 INT_FreeRewardSubType,INT_FreeRewardValue 字段相等"""

    candidates = build_rule_candidates(description)
    result = critique_rule_candidate(description)

    assert len(candidates) == 1
    assert result.verdict == "ready"
    assert result.rule_type == "dual_composite_compare"
    assert result.confidence >= 0.75
    assert result.workflow_hints.rule_type_hint == "dual_composite_compare"
    assert result.workflow_hints.left_filter_field == "INT_Index"
    assert result.workflow_hints.right_filter_value == "1010"
    assert result.workflow_hints.key_column == "INT_Level"


def test_rule_candidate_short_template_dual_slots_override_weak_fixed_hint() -> None:
    """完整双组槽位应覆盖前端或早期抽取带来的 fixed_value_compare 弱误判。"""
    description = """筛选：
- INT_Index = 1012,1010

Key值选择：INT_Level

判定：INT_FreeRewardSubType,INT_FreeRewardValue,INT_FreeRewardSubType1,INT_FreeRewardValue1,INT_FreeRewardSubType2,INT_FreeRewardValue2 在 INT_Index=1012 和 INT_Index=1010 两组中必须相等"""

    result = critique_rule_candidate(
        description,
        workflow_hints=AiRuleWorkflowHints(
            rule_type_hint="fixed_value_compare",
            filter_field="INT_Index",
            filter_value="1012,1010",
            key_column="INT_Level",
            compare_fields=[
                "INT_FreeRewardSubType",
                "INT_FreeRewardValue",
                "INT_FreeRewardSubType1",
                "INT_FreeRewardValue1",
                "INT_FreeRewardSubType2",
                "INT_FreeRewardValue2",
            ],
        ),
    )

    assert result.verdict == "ready"
    assert result.rule_type == "dual_composite_compare"
    assert result.workflow_hints.rule_type_hint == "dual_composite_compare"
    assert result.workflow_hints.left_filter_field == "INT_Index"
    assert result.workflow_hints.left_filter_value == "1012"
    assert result.workflow_hints.right_filter_value == "1010"
    assert result.workflow_hints.key_column == "INT_Level"


def test_rule_candidate_fixed_template_recognizes_key_filter_field_compare() -> None:
    """筛选规则里的唯一字段应作为 Key，校验规则 A=B 应收窄为字段对字段组合分支。"""
    description = """数据源：https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls
sheet分页：Strategic_slg2
变量选择：INT_ID,INT_Faction,INT_Group

筛选规则1：INT_ID唯一

筛选规则2：INT_Faction=0

校验规则：INT_Group=INT_ID"""

    candidates = build_rule_candidates(description)
    result = critique_rule_candidate(description)

    assert len(candidates) == 1
    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.filter_value == "0"
    assert result.workflow_hints.assertion_field == "INT_Group"
    assert result.workflow_hints.assertion_value_source == "field"
    assert result.workflow_hints.assertion_expected_field == "INT_ID"


def test_rule_candidate_dsl_recognizes_multi_filter_key_precondition() -> None:
    """DSL 多筛选里 FIELD 唯一只作为 Key 前置条件。"""
    description = """composite_condition_check
筛选：
- INT_ID 唯一
- INT_Faction = 0
Key：INT_ID
断言：INT_Group 等于字段 INT_ID"""

    result = critique_rule_candidate(description)

    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.assertion_expected_field == "INT_ID"


def test_rule_candidate_short_template_recognizes_key_and_duplicate_required() -> None:
    """短模板里的 Key值选择 / 判定 应归一成 Key 和断言。"""
    result = critique_rule_candidate(
        "筛选：INT_ID唯一，INT_Faction!=0，Key值选择：INT_ID，判定：INT_Group必须重复"
    )

    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.filter_operator == "ne"
    assert result.workflow_hints.filter_value == "0"
    assert result.workflow_hints.assertion_field == "INT_Group"
    assert result.workflow_hints.assertion_operator == "duplicate_required"


def test_rule_candidate_free_text_recognizes_user_strategic_slg2_case() -> None:
    """用户单句样例也应识别为组合分支字段对字段比较。"""
    result = critique_rule_candidate(
        "校验https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls配置表的Strategic_slg2分页，"
        "INT_ID唯一，INT_Faction=0，INT_Group=INT_ID"
    )

    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.assertion_field == "INT_Group"
    assert result.workflow_hints.assertion_expected_field == "INT_ID"


def test_rule_candidate_v3_template_recognizes_key_filter_field_compare() -> None:
    """v3 类型化槽位应直接收窄为组合分支字段对字段比较。"""
    description = """数据源：https://samosvn/data/project/samo/GameDatas/datas_qa88/quests.xls
sheet分页：Strategic_slg2
变量选择：INT_ID,INT_Faction,INT_Group

规则类型：composite_condition_check

目标字段：INT_Group
筛选条件：INT_Faction=0
Key字段：INT_ID
引用对象：无
比较字段：无

校验规则：INT_Group=INT_ID
规则参数：无"""

    candidates = build_rule_candidates(description)
    result = critique_rule_candidate(description)

    assert len(candidates) == 1
    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.assertion_field == "INT_Group"
    assert result.workflow_hints.assertion_expected_field == "INT_ID"


def test_rule_candidate_natural_template_recognizes_key_filter_field_compare() -> None:
    """自然句模板应收窄为组合分支字段对字段比较。"""
    description = """我想检查INT_Group。

只检查满足 INT_Faction=0 的数据。

如果需要按同一条配置对齐，用INT_ID作为 Key；不需要就写“无”。

规则是：INT_Group 必须等于字段 INT_ID。

补充说明：无"""

    candidates = build_rule_candidates(description)
    result = critique_rule_candidate(description)

    assert len(candidates) == 1
    assert result.verdict == "ready"
    assert result.rule_type == "composite_condition_check"
    assert result.workflow_hints.key_column == "INT_ID"
    assert result.workflow_hints.filter_field == "INT_Faction"
    assert result.workflow_hints.assertion_field == "INT_Group"
    assert result.workflow_hints.assertion_expected_field == "INT_ID"


def test_rule_candidate_conflicting_final_assertions_need_input() -> None:
    """一条规则同时要求枚举和非空时应提示拆分，避免误添加。"""
    result = critique_rule_candidate(
        "数据源：demo.xls\nsheet分页：Item\n变量选择：Status\n\n校验规则：Status 只能是 A,B 且不能为空"
    )

    assert result.verdict == "needs_input"
    assert result.should_stop is True
    assert result.rule_type is not None
    assert "多个最终断言" in result.missing[0].message


def test_rule_candidate_unsupported_aggregation_rejected() -> None:
    """聚合类需求不能被硬套到现有规则类型。"""
    result = critique_rule_candidate(
        "数据源：demo.xls\nsheet分页：Server\n变量选择：Score\n\n校验规则：按服务器分组计算平均战力必须大于 5000"
    )

    assert result.verdict == "rejected"
    assert result.should_stop is True
    assert "超出现有规则库能力" in result.reasoning_summary
    assert "平均值" in (result.rejection_reason or "")


def test_rule_candidate_uses_existing_workflow_hints_to_score_not_null() -> None:
    """已选择变量模式下，即使文本很短，也能借助 workflow_hints 收窄规则类型。"""
    result = critique_rule_candidate(
        "不能为空",
        workflow_hints=AiRuleWorkflowHints(target_field="ID"),
    )

    assert result.verdict == "ready"
    assert result.rule_type == "not_null"
    assert result.workflow_hints.target_field == "ID"
