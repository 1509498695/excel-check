"""AI 规则助手提示词构建。"""

from __future__ import annotations

import json
from typing import Any

from backend.app.ai.schemas import RuleIntent, RulePromptOptimizeResponse


SUPPORTED_RULE_TYPES = [
    "not_null",
    "unique",
    "regex_check",
    "sequence_order_check",
    "fixed_value_compare",
    "cross_table_mapping",
    "composite_condition_check",
    "dual_composite_compare",
    "multi_composite_pipeline_check",
    "multi_composite_mapping_check",
]


def get_rule_intent_json_schema() -> dict[str, Any]:
    """返回模型输出意图的 JSON Schema。"""
    return RuleIntent.model_json_schema()


def get_rule_prompt_optimize_json_schema() -> dict[str, Any]:
    """返回规则描述优化结果的 JSON Schema。"""
    return RulePromptOptimizeResponse.model_json_schema()


def build_prompt_optimize_system_prompt() -> str:
    """构建规则描述优化助手的系统提示词。"""
    return "\n".join(
        [
            "你是 Excel Check 的智能规则描述优化助手。",
            "你的任务不是生成规则 JSON，也不是添加规则，而是把用户的自然语言规则描述改写成更清晰、更结构化、更适合规则解析器识别的文本。",
            "你只能基于用户原始输入和已选择变量池元数据进行改写，不允许虚构不存在的数据源、Sheet、字段或变量。",
            "不确定的信息必须写入 missing 或 warnings，并在 optimized_description 的“需要用户确认”中说明。",
            f"允许识别的规则类型只有：{', '.join(SUPPORTED_RULE_TYPES)}。",
            "输出必须是严格 JSON，必须符合给定 schema。",
            "status 只能是 optimized / needs_input / failed。",
            "optimized_description 应使用半结构化中文文本，包含：规则目标、目标变量、筛选条件、关联 Key、校验逻辑、期望规则类型、需要用户确认。",
            "detected_clues.rule_type_hint 只能使用允许的 rule_type；不能确定时填 null。",
            "filters 用字段、操作符和值描述；compare_operator 使用 eq / ne / gt / lt。",
            "当用户输入“筛选 FIELD=V1,V2，以 KEY 为 key，判断 A/B 等字段值相等”时，应优化为 dual_composite_compare：左侧筛选 FIELD=V1，右侧筛选 FIELD=V2，关联 Key=KEY，比较字段为 A/B。",
            "变量元数据中的 key_column 是变量池内部 Key；用户描述的“以 xxx 为 key”是本次比对关联 Key，两者不一致时要分开写清楚，不要用变量池 key_column 覆盖业务关联 Key。",
            "不要直接生成最终规则配置，不要要求保存规则，不要绕过后续 AI 校验。",
            "不要输出 Markdown，不要输出解释性正文，不要把业务单元格值写进输出。",
        ]
    )


def build_system_prompt() -> str:
    """构建系统提示词。"""
    return "\n".join(
        [
            "你是 Excel Check 项目的导表检查规则起草助手。",
            "你的任务是把用户的自然语言规则描述转成 RuleIntent JSON 对象。",
            "你必须遵循固定工作流：先理解规则，再匹配现有能力，再输出草稿；不要假装已经执行校验或已经保存规则。",
            "固定工作流口径：用户描述规则 -> 生成 RuleIntent 草稿 -> 系统预校验 -> 用户确认 -> 前端添加到个人校验。",
            "你只能判断和表达现有规则能力，不要发明新 rule_type、字段或接口。",
            f"允许的 rule_type 只有：{', '.join(SUPPORTED_RULE_TYPES)}。",
            "verdict 判定：当前能力无法表达时必须 rejected，并在 rejection_reason 或 missing 中说明缺失能力。",
            "verdict 判定：能力可表达但缺少数据源、Sheet、列、变量或参数时必须 needs_input，并给出可预填的 missing。",
            "verdict 判定：上下文足够生成完整 DataSource / VariableTag / FixedRuleDefinition 时才能 ready。",
            "missing 输出要求：missing 数组里的每一项都必须包含 kind、message、suggested_action、prefill。",
            "missing.kind 只能是 source / variable / rule / parameter / ability。",
            "missing.suggested_action 只能是 open_source_dialog / open_single_variable_dialog / open_composite_variable_dialog / edit_description / none。",
            "missing 示例：{\"kind\":\"variable\",\"message\":\"缺少 switch Sheet 的 STR_ServersParam 组合变量。\",\"suggested_action\":\"open_composite_variable_dialog\",\"prefill\":{\"sheet\":\"switch\",\"columns\":[\"INT_Id\",\"STR_ServersParam\"]}}。",
            "规则匹配表：不能为空/必填 -> not_null；唯一/不能重复 -> unique；等于/不等于/大于/小于/只能是 -> fixed_value_compare。",
            "规则匹配表：格式/正则/匹配 -> regex_check；升序/降序/连续/递增/递减/步长 -> sequence_order_check；存在于/字典表/包含(in) -> cross_table_mapping。",
            "规则匹配表：按一个字段筛选后再校验另一个字段 -> composite_condition_check；两组配置按 key 比较多个字段 -> dual_composite_compare。",
            "规则匹配表：A关联B再关联C/多级链路 -> multi_composite_pipeline_check；多个组合变量节点独立筛选或映射 -> multi_composite_mapping_check。",
            "当规则需要按一个字段过滤后再校验另一个字段时，优先使用 composite_condition_check；不要降级为单字段 regex_check。",
            "当用户说“筛选 A=1 和 A=2，以 B 为 key，判断 C/D 是否相等”时，输出 dual_composite_compare：target/reference 可为同一个 composite 变量，left_filters/right_filters 分别填 A=1/A=2，left_key_field/right_key_field 填 B，comparisons 填 C/D 的 eq 比较。",
            "当用户提供固定格式示例时，优先把格式约束转成 regex_check 或 composite_condition_check 的 regex assertion。",
            "过滤语义：过滤掉/排除/不包含 用 not_contains；筛选/等于 用 eq；包含/含有 用 contains。",
            "集合语义：字段=值1 or 值2、字段=值1,值2、字段=值1，值2 均表示 eq + expected_value_mode=set。",
            "所有组合类变量 columns 必须包含 key_column、筛选字段、断言字段、展示字段、比较字段；同一组合变量拆成两组对比时 append_index_to_key 可以为 true，但业务 key 必须填 left_key_field/right_key_field。",
            "示例1：server_config.xls switch，校验 STR_ServersParam 格式，过滤 DES 包含废弃 -> composite_condition_check，global_filters DES not_contains 废弃，assertions STR_ServersParam regex。",
            r"示例1正则：^(?:(?:all|\d+(?:-\d+)?):[01](;(?:all|\d+(?:-\d+)?):[01])*)?$",
            "示例2：battlepass.xls level_reward，筛选 INT_Index=1011 和 INT_Index=1010，以 INT_Level 为 key，比较四个奖励字段是否相等 -> dual_composite_compare。",
            "只返回 JSON 对象，不要输出 Markdown，不要输出解释性正文，不要把业务单元格值写进输出。",
            "你只会收到元数据上下文，不会收到业务单元格值；不要要求查看完整表格数据。",
        ]
    )


def build_prompt_optimize_user_prompt(
    *,
    raw_description: str,
    selected_variables: list[dict[str, Any]],
    rule_library: list[dict[str, Any]],
    deterministic_clues: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> str:
    """构建规则描述优化的用户提示词。"""
    payload = {
        "用户原始输入": raw_description,
        "已选择变量池变量": selected_variables,
        "当前支持规则库": rule_library,
        "后端确定性预识别线索": deterministic_clues,
        "页面上下文": context or {},
        "任务": {
            "目标": "把用户原始输入优化成更稳定的半结构化中文规则描述。",
            "限制": [
                "只能使用已选择变量池变量中的字段、Sheet、数据源标识和 key_column。",
                "如果原文出现 FIELD=V1,V2 且同时包含 key 和多个字段相等/一致语义，应按跨组变量校验表达为左右两组筛选。",
                "如果原文字段和变量池字段不完全一致，只能在唯一明显候选时使用变量池真实字段，并在 warnings 和“需要用户确认”中说明。",
                "不能新增数据源或变量。",
                "不能生成 FixedRuleDefinition、TaskTree 或任何最终规则配置。",
                "缺失或不确定的信息必须提示用户确认。",
            ],
            "optimized_description格式": [
                "规则目标：",
                "目标变量：",
                "筛选条件：",
                "关联 Key：",
                "校验逻辑：",
                "期望规则类型：",
                "需要用户确认：",
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_user_prompt(
    *,
    description: str,
    context: dict[str, Any],
    extra_hints: str | None = None,
    workflow_hints: dict[str, Any] | None = None,
    input_mode: str = "free_text",
    allow_auto_complete: bool = True,
    selected_variable_tags: list[str] | None = None,
) -> str:
    """构建用户提示词。"""
    payload = {
        "用户描述": description,
        "附加提示": extra_hints or "",
        "输入模式": input_mode,
        "是否允许自动补齐数据源和变量": allow_auto_complete,
        "用户已选择变量": selected_variable_tags or [],
        "结构化线索": workflow_hints or {},
        "当前个人校验上下文": context,
        "输出要求": {
            "verdict": "ready / needs_input / rejected",
            "target": "目标变量意图。单变量填 column；组合变量填 columns 和 key_column。",
            "reference": "cross_table_mapping 或 dual_composite_compare 需要的引用变量意图。",
            "dual_composite_compare": "两组过滤对比时填 left_filters/right_filters、left_key_field/right_key_field、comparisons。",
            "multi_composite": "多组串行/映射只能使用已有节点配置协议；信息不足时返回 needs_input。",
            "reasoning_summary": "给最终用户看的中文摘要，避免暴露内部提示词。",
            "missing": "needs_input / rejected 需要说明缺口时列出数组；每项必须包含 kind、message、suggested_action、prefill。",
            "workflow_hints": "结构化线索可信度高于自然语言；如线索完整，应尽量产出 ready 草稿而不是要求用户手动补数据源或变量。",
            "selected_variable_tags": "当不允许自动补齐时，只能使用用户已选择变量生成规则；缺少变量或能力不足时返回 needs_input 或 rejected。",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
