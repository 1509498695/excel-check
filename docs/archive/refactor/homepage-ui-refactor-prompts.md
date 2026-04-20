# 首页 UI 重构 Prompt 包

用于在 Agent 模式下执行首页顶部指标卡片与引导操作区块的视觉重构。  
目标是解决大屏幕下的过度拉伸、左右断层、排版松散问题，同时严格保持现有业务逻辑、数据绑定、按钮事件与路由行为不变。

## 使用顺序
1. 先执行 Prompt 1，完成预读、视觉方向确认与改动边界收口。
2. 再执行 Prompt 2，实施 DOM 与 CSS 重构。
3. 最后执行 Prompt 3，完成构建、大屏验收与结果复核。

## 已锁定的实现范围
- 只允许修改 `frontend/src/views/MainBoard.vue`
- 只允许修改 `frontend/src/style.css`

不允许修改：
- `frontend/src/App.vue`
- `frontend/src/router/index.ts`
- 任意 store / api / types 文件
- 任意业务逻辑、事件函数、计算属性、数据源结构

## 当前问题摘要
- `frontend/src/style.css` 中 `.main-board` 被桌面覆盖规则扩成全宽，失去了聚焦宽度。
- `.workbench-toolbar-shell` 使用 `justify-content: space-between`，在 1920px 下把左右内容推到边缘。
- `.overview-grid` 与 `.workbench-step-guide-nav` 使用 `repeat(..., 1fr)`，宽屏下被等比拉伸。
- `.workbench-step-guide-detail` 的双栏比例把左侧标题文案与右侧说明/CTA 拉得过远。

关键现状片段：

```420:540:frontend/src/views/MainBoard.vue
      <div class="workbench-toolbar-tray">
        <div class="topbar-meta workbench-toolbar-meta">
          ...
        </div>

        <div class="overview-actions workbench-toolbar-actions">
          ...
        </div>
      </div>
    </header>

    <div class="workbench-desktop-layout">
      <section class="workbench-stage-content">
        <section class="overview-strip workbench-overview-strip">
          <div class="overview-grid">
            <article
              v-for="item in overviewItems"
              :key="item.label"
              class="overview-item"
              :class="`is-${item.tone}`"
            >
              <div class="overview-icon-box" :class="`is-${item.tone}`">
                <component :is="item.icon" class="overview-icon" />
              </div>
              <div>
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </article>
          </div>
        </section>

        <section class="workflow-guide workbench-step-guide-shell" :class="`is-${activeGuideDetail.tone}`">
          <div class="workbench-step-guide-nav">...</div>

          <div class="workbench-step-guide-detail">
            <div class="workbench-step-guide-copy">
              <span class="guide-badge">{{ activeGuideDetail.badge }}</span>
              <strong>{{ activeGuideDetail.title }}</strong>
              <p>{{ activeGuideDetail.description }}</p>
            </div>

            <div class="workbench-step-guide-meta">...</div>

            <div class="guide-actions workbench-step-guide-actions">
              <el-button
                :type="activeGuideDetail.action === 'execute' ? 'primary' : 'default'"
                @click="handleGuideAction"
              >
                {{ activeGuideDetail.actionLabel }}
              </el-button>
            </div>
          </div>
        </section>
```

```3612:3745:frontend/src/style.css
.main-board {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

.workbench-toolbar-shell {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 26px;
}

.workbench-step-guide-nav {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
  margin: 0;
}

.workbench-step-guide-detail {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.95fr);
  ...
}
```

---

## Prompt 1：预读与实现约束

```text
你是一名资深前端工程师兼高级 UI 交互设计师。请在当前 Excel Check 项目中执行首页 UI 收口预研。

# 任务目标
对首页中的两个模块进行视觉与排版重构准备：
1. 顶部指标卡片组
2. 引导操作区块（含“先接入数据源”标题、说明、灰色提示区、CTA 按钮）

核心目标：解决 1920px 大屏下内容被拉太宽、左右断层明显、排版松散的问题，做出更接近 Apple Design 和现代高端 SaaS 的聚拢感与精致感。

# 必读文件
- frontend/src/views/MainBoard.vue
- frontend/src/style.css
- frontend/src/App.vue

# 视觉方向要求（先写再改）
在开始改代码前，先输出 3 项短规格：
1. visual thesis：一句话说明这次首页顶部区域的氛围、材质、节奏
2. content plan：按「顶部指标卡片 / 引导操作区块」分别说明每块的主要信息层级
3. interaction thesis：列出 2-3 个轻量交互建议，要求克制，不得花哨

# 强制范围
只允许修改：
- frontend/src/views/MainBoard.vue
- frontend/src/style.css

禁止修改：
- App.vue
- router
- store / api / types
- 任意业务函数与数据逻辑

# 功能保留红线
以下内容必须保持完全不变：
- overviewItems 的 v-for 渲染
- {{ item.value }}、{{ item.label }}、{{ activeGuideDetail.title }}、{{ activeGuideDetail.description }}
- @click=\"handleGuideAction\"
- @click=\"handleGuideStepClick(item.step)\"
- 所有 el-button、el-tag 的业务行为

# 本轮重构原则
1. 顶部指标卡片必须保持 4 列
2. 引导操作区块必须改成视觉聚拢的 60/40 双栏，而不是使用宽泛的 justify-between
3. 仅重构 DOM 包裹层级与 class，不得改动业务字段
4. 所有新增注释必须简短，解释网格/布局为何这样收口宽屏

# 预研输出要求
在开始改代码前，请先总结：
1. 当前哪些 CSS 属性直接导致页面发散
2. 本轮你准备改哪些 DOM 包裹层与 class
3. 你将如何保证 1920px 下依然紧凑

确认以上内容后，再进入代码修改。
```

---

## Prompt 2：DOM + CSS 实施改造

```text
你现在开始实施首页 UI 重构。必须严格保持现有业务逻辑不变，只重构 DOM 结构和 CSS 类。

# 只允许修改
- frontend/src/views/MainBoard.vue
- frontend/src/style.css

# 业务红线
禁止修改以下任何行为：
- overviewItems 的数据来源与遍历逻辑
- activeGuideDetail / activeGuideStep 的任何计算逻辑
- handleGuideAction()
- handleGuideStepClick()
- runExecution()
- 任意 store 字段与组件 props
- 任意按钮文案绑定、路由跳转、事件触发

# 设计目标
参考 Apple Design 与现代高端 SaaS，做出更紧凑、更有层次、更聚焦的顶部区域。

## 模块 1：指标卡片组
- 保持 4 列网格，不允许改成 2 列或 3 列
- 优化每张卡内部排版：
  - 上层：图标 + 标题
  - 下层：放大后的核心数字
- 数字要显著更大，建议达到 text-3xl 级别的视觉感受
- 卡片视觉：
  - 纯白或极轻毛玻璃
  - 极淡边框
  - 柔和阴影
  - hover 时轻微抬升或阴影增强，但要克制
- 不要让所有内容都挤在卡片左上角，需要建立呼吸感和层级

## 模块 2：引导操作区块
- 严禁再用宽泛的 justify-between 把左右内容拉开
- 改为明确的双栏结构：
  - 左侧约 60%：badge、主标题、描述
  - 右侧约 40%：灰色提示框、标签、CTA 按钮
- “先接入数据源”必须成为视觉重心
- 灰色提示文案要降噪：更小字号、更浅颜色
- CTA 按钮要稳定对齐到右下区域，不能漂浮在空白里
- 模块整体要在 1920px 下依然聚拢，不得出现中间大断层

# 推荐实现策略
1. 在 MainBoard.vue 中：
   - 为 overview section 增加更明确的内部结构包裹层
   - 为每个指标卡增加 header / value 区域
   - 为 workflow detail 增加左右两栏包裹层
   - 在关键网格/布局变更处添加简短注释
2. 在 style.css 中：
   - 收紧 `.main-board` 或顶部内容区域的聚焦宽度
   - 调整 `.workbench-toolbar-shell` 的宽屏排布，避免 space-between 式发散
   - 重写 `.overview-grid`、`.overview-item` 相关内部层级样式
   - 重写 `.workbench-step-guide-detail` 的双栏比例与对齐方式
   - 优化 `.workbench-step-guide-meta` 与 `.workbench-step-guide-actions` 的对齐关系

# 关键实现要求
- 代码中必须保留原始模板绑定表达式
- 只允许添加包裹 div、重排顺序、追加 class、替换 class
- 可以新增少量语义化 class 名，但不要大面积改名已有系统
- 关键布局处必须有简短注释，例如：
  - “使用内层网格限制宽屏扩张，聚拢视觉焦点”
  - “保持 4 列不变，只重排卡片内部层级”
  - “右侧操作面板收口为固定信息区，避免 CTA 漂浮”

# 视觉收口要求
- 顶部区域在 1920px 下不能散
- 卡片组与引导区块之间要形成统一节奏
- 不允许引入夸张渐变、大面积重阴影、过多颜色
- 保持克制、专业、SaaS 化

# 完成后必须执行
1. npm run build
2. 自查 MainBoard.vue 中所有事件与数据绑定是否保持不变
3. 总结你具体改了哪些 DOM 结构、哪些 CSS 属性被移除或替换
```

---

## Prompt 3：1920px 宽屏验收与回归检查

```text
你现在执行首页 UI 重构后的回归验收。不要继续扩大改动范围，只围绕顶部指标卡片组与引导操作区块做校验和必要微调。

# 验收范围
- frontend/src/views/MainBoard.vue
- frontend/src/style.css

# 必做验证
1. 构建验证
   - 运行：npm run build
   - 必须通过

2. 功能一致性验证
   - overviewItems 仍正常渲染 4 张指标卡
   - 指标值仍直接来自原始绑定，例如 `{{ item.value }}`
   - guide 区按钮仍通过 `handleGuideAction` 触发
   - 步骤导航按钮仍通过 `handleGuideStepClick(item.step)` 触发
   - activeGuideDetail 的标题、描述、标签仍原样显示

3. 1920px 视觉验收
   - 页面在 1920px 分辨率下不能出现“左右贴边、中间断层巨大”的问题
   - 指标卡组仍为 4 列，但整体视觉聚拢
   - 单张卡片内部必须有明显层级：上方标题/图标，下方核心数字
   - “先接入数据源”标题必须明显强于灰色提示文案
   - 右侧提示面板与 CTA 必须形成一个紧凑的信息区
   - CTA 按钮位置稳定，不漂在大空白中

4. 样式检查
   - 如仍存在 `justify-content: space-between` 导致宽屏断层的地方，继续收口
   - 如引导区块左右栏间距仍过大，继续压缩
   - 如卡片内容仍显得挤在左上角，继续优化内部分布
   - hover 效果必须柔和，不得夸张

# 最终输出要求
完成后请总结：
1. 原代码中最影响“排版松散”的 CSS 属性有哪些
2. 你最终如何调整了：
   - 容器宽度
   - 指标卡内部层级
   - 引导区块双栏结构
   - CTA 对齐方式
3. `npm run build` 的结果
4. 1920px 下的视觉验收结论

# 红线复核
- 没有改任何 store / api / router / types
- 没有改任何事件函数逻辑
- 没有改任何数据绑定字段
- 只改了 MainBoard.vue 与 style.css
```

---

## 建议使用方式
- 如果要让 Agent 一次性执行到底，先发 Prompt 1，确认理解后继续发 Prompt 2，最后发 Prompt 3。
- 如果你希望更稳妥，可以把 Prompt 2 拆成两轮：
  1. 先只改 `MainBoard.vue`
  2. 再只改 `style.css`

## 结果检查清单
- `frontend/src/views/MainBoard.vue` 中原有 `v-for`、`{{ item.value }}`、`@click` 保持不变
- `frontend/src/style.css` 中宽屏布局不再依赖发散式 `space-between`
- 4 列指标卡保留，但内部层级更清晰
- 引导操作区块改为 60/40 聚焦布局
- 1920px 下页面不再显得空旷松散
