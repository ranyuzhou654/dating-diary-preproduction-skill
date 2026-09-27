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
2. 对应角色设定板与 profile.json（identity_anchors / must_not_have）
3. 场景 Anchor
4. 分镜要求
5. 前后镜头
6. face_check.py 的输出（写实镜头）

你只负责检查，不参与生成，也不看生成时的推理过程。

请检查以下项目。

CHARACTER IDENTITY

脸型是否一致
五官是否一致
逐条核对角色 profile 的 identity_anchors：每一条是否都在
逐条核对 must_not_have：是否出现了不该有的特征（例如不戴眼镜的角色戴了眼镜）
身材比例是否明显改变
face_check.py 的相似度结果（写实镜头）：低于阈值直接 FAIL

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

REAL-WORLD LIKENESS

画面中是否有人物长得像真实名人或公众人物（背景人群也要看）
是否出现真实公司、品牌、学校的 logo 或徽标（剧情明确需要的文字道具除外，且不得带官方徽标）
以上任一出现 → FAIL

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

严格恢复参考图中的黑色层次短发和略乱的刘海。

男主不戴眼镜（must_not_have: glasses）。

除此之外不要改变画面构图、场景、灯光和人物动作。
```

每次最多修 1–3 个最高优先级问题。

重跑上限与记录：

- 每个镜头最多 3 次尝试（含第一次），由 `scripts/keyframe_state.py` 强制执行。
- 每次尝试的文件、QC 结论、问题和修复指令都写入 `07_keyframes/keyframe_state.json`。
- 第 3 次仍 FAIL → 状态 `exception`，进入异常列表，继续处理下一镜，不阻塞流水线。
- 异常镜头在交付包中列为 unresolved，由用户之后处理（换参考图、改镜头描述或手动选图）。

face_check 阈值：

- 默认 0.45（InsightFace buffalo_l 的余弦相似度）。实测参考：同一男主的关键帧对其设定图约 0.55，同一女主约 0.61；而**另一集的男主**对这张图也有 0.39——AI 生成的相似风格男性之间相似度偏高，所以阈值不能低于 0.4。
- 第一集跑完后，用人工确认合格/不合格的关键帧各几张校准，写入 `00_meta/project.json` 的 `face_threshold`，之后运行时用 `--threshold` 传入。
- 相似度只能拦住“明显换了个人”，拦不住发型、眼镜这类细节，这些靠清单层。

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

01_source/            # original_source.* 被 .gitignore 排除；只有去识别化后的 adaptation_notes.md 会被跟踪
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
    keyframe_state.json
    shot_01_try1.png
    shot_01.png      # QC 通过后的定稿
    shot_02.png

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
- 剧本与 shots 已通过 check_dialogue_timing.py（每镜 duration_hint ≥ est_speech_seconds）
- 每镜都有静帧，且完成 QC
- 所有 FAIL 镜头要么重跑通过，要么以 exception 身份列入 manifest 的 `exceptions`
- 原始素材未进入 09_handoff 与任何 git 跟踪的文件

到此结束。

**不要继续调用或设计视频生成流程。** 视频阶段由 `dating-diary-production` skill 读取 manifest 接手。
