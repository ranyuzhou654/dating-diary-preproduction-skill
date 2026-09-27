# QC, Reference Routing & Packaging

# 1. Reference Routing

尽量使用确定性规则，不要让模型每镜自由判断。

```text
IF layer = REALITY
AND characters = female
THEN
female_model_sheet
+ approved_reality_anchor

IF layer = REALITY
AND characters = male
THEN
male_model_sheet
+ approved_reality_anchor

IF layer = REALITY
AND characters = female + male
THEN
female_model_sheet
+ male_model_sheet
+ approved_reality_anchor

IF layer = FANTASY
AND characters = male
THEN
male_model_sheet
+ q_chibi_style_reference
+ approved_fantasy_anchor_if_available

IF layer = FANTASY
AND characters = female + male
THEN
female_model_sheet
+ male_model_sheet
+ q_chibi_style_reference
+ approved_fantasy_anchor_if_available

IF special_prop exists
THEN
add special_prop_reference

IF layer = FANTASY
THEN
DO NOT add reality_scene_reference
```

---

# 2. Anchor 策略

不要一上来生成整片所有静帧。

先处理：

1. Reality Anchor
2. Fantasy Anchor

Reality Anchor 应优先：

- 男女主同框
- 空间关系清楚
- 桌位明确
- 窗户 / 灯具 / 桌面陈设可辨认
- 能作为多数 Reality 镜头的空间基准

Fantasy Anchor 应优先：

- 定义本集 Q版世界
- 主要人物同时出现
- Q版比例稳定
- 材质和灯光清楚
- 核心 visual gag 可读

只有 Anchor 被批准后，才进入批量静帧阶段。

---

# 3. 推荐 Reference 使用方式

示例：

```text
SHOT 01 Reality
characters
+ original scene reference

SHOT 02 Reality
characters
+ approved Reality Anchor

SHOT 03 Reality
characters
+ approved Reality Anchor

SHOT 04 Fantasy
character
+ q style reference

SHOT 05 Fantasy
character
+ approved Fantasy Anchor

SHOT 06 Reality
character
+ approved Reality Anchor
```

---

# 4. 静帧 QC Agent

```text
你是 Dating Diary 的视觉连续性检查 Agent。

你会得到：

1. 当前生成镜头
2. 对应角色设定板
3. 场景 Anchor
4. 分镜要求
5. 前后镜头

请检查以下项目。

CHARACTER IDENTITY

脸型是否一致
五官是否一致
发型是否一致
眼镜是否存在
身材比例是否明显改变

WARDROBE

服装是否与本场景一致
颜色是否变化
关键饰品是否丢失

SCENE

是否仍然是同一家餐厅
桌椅是否合理连续
窗户位置是否突变
光线时间是否变化
桌面物品是否严重改变

SHOT COMPLIANCE

景别是否正确
机位是否正确
应该OTS时是否确实是OTS
人物是否看镜头
动作是否符合描述
人数是否正确

GENERATION DEFECT

手部异常
餐具异常
肢体融合
多余人物
奇怪文字
错误logo
脸部AI塑料感

输出：

PASS / FAIL

score:
character_consistency
scene_consistency
shot_compliance
generation_quality

如果 FAIL：

列出最多3个最重要的问题。

并输出：

regeneration_instruction

不要重新设计整个镜头。
只针对问题修改。
```

---

# 5. 自动重跑原则

FAIL 时不要整段重写 Prompt。

优先追加最小修复指令：

```text
REGENERATION PRIORITY:

严格恢复参考图中的细框圆形金属眼镜。

严格保持原本黑色蓬松短发。

除此之外不要改变画面构图、场景、灯光和人物动作。
```

每次最多修 1–3 个最高优先级问题。

---

# 6. 分镜表结构

统一字段：

| 镜头 | 时间提示 | 景别 / 机位 | 画面内容 | 主体动作 | 台词 / 字幕 | 声音提示 | 情绪功能 | Image Prompt | Reference |
|---|---|---|---|---|---|---|---|---|---|

注意：

- “时间提示”只用于叙事节奏
- “声音提示”只用于前期资料说明
- 不包含视频生成参数

---

# 7. 前期制作包

推荐目录：

```
Dating_A_001/

00_meta/
    project.json

01_source/
    original_source.txt
    adaptation_notes.md

02_script/
    script.md
    script.json

03_storyboard/
    storyboard.xlsx
    shots.json

04_assets/
    characters/
    scene/
    style/
    props/

05_prompts/
    image_prompts.json
    shot_01.txt
    shot_02.txt

06_anchors/
    reality_anchor.png
    fantasy_anchor.png

07_keyframes/
    shot_01.png
    shot_02.png
    shot_03.png

08_qc/
    qc_report.json

09_handoff/
    preproduction_manifest.json
```

---

# 8. Handoff Definition

当以下条件全部满足时，才标记：

```json
{
  "stage": "preproduction_complete",
  "handoff_ready": true
}
```

条件：

- 剧本 approved
- shots 完整
- assets 可追踪
- Reality Anchor approved
- Fantasy Anchor approved（如果本集存在 Fantasy）
- 每镜都有 image prompt
- 每镜都有 reference_asset_ids
- 已有静帧的镜头完成 QC
- 所有 FAIL 镜头要么重跑通过，要么明确列为 unresolved

到此结束。

**不要继续调用或设计视频生成流程。**
