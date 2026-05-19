# 智能添加规则模块第四轮重构需求文档

## 背景与当前现状

智能添加规则模块已完成凭据、上下文、草稿仓储、字段解析、workflow hints、dry-run、compiler registry 和部分前端 composable 拆分。当前功能保持稳定，但复杂度仍集中在后端服务编排、线索抽取和前端大面板状态中。

本轮继续按“不改接口、不改解析语义、不新增规则类型”的原则做结构拆分：

- `agent_service.py` 仍承担服务编排、规则类型推断、组合 helper 和最终规则 materialize。
- `hint_extractor.py` 仍集中承载 source、filter、assertion、dual compare、sequence、fixed value 等多类抽取函数。
- `WorkbenchAiRulePanel.vue` 仍承担输入、模板、历史、生成和 UI 组装。
- 前端已具备 `GroupedSmartRuleWorkflowHintsState`，但历史 UI 仍需要平铺 hints 兼容。

## 本次目标

- 将最终 `RuleIntent -> FixedRuleDefinition` materializer 从 `agent_service.py` 拆出。
- 将规则类型推断和 compiler helper 从 service 私有函数中迁出。
- 建立 `extractors` 子模块，先迁出纯抽取函数，保持 `extract_workflow_hints_from_text()` 入口不变。
- 落地前端 workflow hints 分组状态的兼容层，保持后端 payload 仍由唯一 serializer 生成。
- 继续拆分前端智能规则面板的 history、template、draft 辅助逻辑。

## 明确不做

- 不改变 `/api/v1/ai/*` 入参出参。
- 不改变 `RuleDraftResponse / RuleIntent / MissingItem / RuleDraftPayload` 字段。
- 不新增规则类型，不改 `/fixed-rules` 协议，不做数据库迁移。
- 不删除旧自然句、旧 v3、旧三段模板兼容。
- 不重写 UI DOM 和交互布局。

## 受影响模块

- 后端 AI service：`backend/app/ai/agent_service.py`
- 后端新增边界：`materializers/`、`extractors/`、`rule_type_inference.py`、`compilers/helpers.py`
- 后端测试：`backend/tests/ai/*`、`backend/tests/snapshots/ai/*`
- 前端智能规则 UI：`WorkbenchAiRulePanel.vue`、`components/workbench/ai/composables/*`
- 前端状态工具：`frontend/src/utils/aiRuleInputDraft.ts`
- 文档：`CHANGELOG.md`、`docs/ARCHITECTURE.md`、`docs/MODULES.md`、`frontend/README.md`

## 接口、状态与数据结构影响

- 对外 API 无变化。
- 后端 `agent_service.py` 改为调用 materializer registry 和 rule type inference。
- 前端 session draft 新增 `workflowHintGroups` 分组状态，同时保留 `workflowHints` 平铺兼容层。
- `serializeHintsToWorkflowHints()` 同时支持平铺和分组 hints，继续作为唯一后端 payload 入口。

## 验收标准

- 现有智能添加规则流程保持稳定：输入、优化、AI 校验、预校验、确认添加、历史回填均可用。
- 高风险快照行为稳定：短模板 ready、dual compare ready、needs_input、rejected 聚合场景不退化。
- `agent_service.py` 不再维护最终 `FixedRuleDefinition` 大段 materializer。
- `hint_extractor.py` 至少将 source、fixed value、sequence 等纯函数迁入 `extractors`。
- 前端 hints 分组状态可创建、重置、序列化，旧平铺状态仍兼容。

## 联调与回归方式

后端：

```powershell
python -m pytest backend/tests/snapshots/ai backend/tests/ai -q
python -m pytest backend/tests/test_ai_api.py backend/tests/test_rule_candidate.py backend/tests/snapshots/ai -q
python -m pytest backend/tests -q
```

前端：

```powershell
cd frontend
npm run lint
npm run test:unit -- ai
npm run build
```

本地联调：

```powershell
python backend/run.py
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

检查：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:5173`
