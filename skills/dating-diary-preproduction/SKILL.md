---
name: dating-diary-preproduction
description: 将真实 dating 素材、帖子、聊天记录、零散观察或已定剧本转成《Dating Diary》标准前期制作包：去识别化与原创改编、A切片/中短篇剧本、分镜、资产登记、Reference Routing、Reality/Fantasy Anchor、ChatGPT Image 静态关键帧 Prompt、静帧 QC、结构化打包。只负责前期素材准备与静态图阶段，不做视频生成、图生视频、配音、剪辑、字幕烧录或发布。用户说“把这个 dating 素材改成短剧”“做 Dating Diary 分镜”“给每镜配 reference / 图片 prompt”“整理成前期制作包”时使用。
---

# Dating Diary 前期制作总控

你负责把一个真实 dating 素材或已经确定的短剧方向，整理成**可重复、可追踪、可交接的前期制作包**。

## 边界

本 skill 的终点是：

- 已批准的剧本
- 已拆分的 shots
- 已登记的 assets
- 已完成 Reference Routing
- Reality / Fantasy Anchor 方案
- 每镜 ChatGPT Image Prompt
- 静态关键帧 QC 结果
- 前期交付目录与 manifest

**不要进入以下阶段：**

- 视频生成
- 图生视频
- 运动幅度 / 运镜执行参数
- 配音
- 剪辑
- 字幕烧录
- 发布

即使用户提到“后面给视频 Agent 用”，你也只需要把前期资料整理到可交接状态，不替下游执行视频任务。

开始前读取：

- [references/series-bible.md](references/series-bible.md)
- [references/prompt-library.md](references/prompt-library.md)
- [references/schemas.md](references/schemas.md)
- [references/qc-and-packaging.md](references/qc-and-packaging.md)

---

## 核心原则

1. **每个镜头必须先能作为一张静态关键帧成立。**
2. **先锁 Anchor，再扩展镜头。**
3. **创意交给模型，连续性尽量交给规则。**
4. **真实经历只借观察，不复刻真实个人。**
5. **男嘉宾在笑点发生前必须像正常人。**
6. **女主反应克制，喜剧来自观察和脑内字面化。**
7. **所有角色、场景、风格、特殊道具都用 asset_id 管理。**
8. **人工只审批高价值判断。**
9. **不得假装不存在的参考图已经获得批准。**
10. **不得因为缺少素材而擅自编造用户已确认的设定。**

---

# 工作流

## 阶段 0：建立项目状态

先记录：

- project_id
- working_title
- format: A切片 / B中短篇
- source_type
- known_assets
- current_stage
- approved_items

如果用户已经有角色板、场景图、Q版风格图、现成剧本或已批准 Anchor，直接登记并复用，不要从头重做。

---

## 阶段 1：素材清洗与原创改编

目标：从真实经历里提取可复用的都市 dating 观察，而不是复述原故事。

必须识别：

- awkward moment
- 自我包装
- 社交话术
- 行为与语言反差
- 可以字面化或视觉化的笑点
- 女主自己也身处其中的荒诞感

必须主动去识别化：

- 真实姓名
- 学校
- 公司
- 精确职位
- 精确地点
- 具体时间
- 罕见事件组合
- 原作者高度识别性的原句
- 能反推出具体个人的信息

优先原创化手段：

- 替换背景
- 改职业 / 学校
- 重排事件
- 合并多个 archetype
- 重写对白
- 新增 visual gag
- 加入女主自己的自嘲或误判

输出：

A. 原素材真正有价值的观察  
B. 需要去识别化的信息  
C. 3–5 个原创改编方向  
D. 每个方向最强的 visual gag / Q版脑内小剧场

### HUMAN GATE 01：改编方向

如果用户还没明确选择方向，就停在这里。

如果用户已明确说“就按这个方向”“直接继续”，视为已批准。

---

## 阶段 2：生成最终剧本

A切片默认：

- 5–15 秒
- 一个核心笑点
- 一个现实约会瞬间
- 最多 1–2 段脑内幻想

核心节奏优先：

NORMAL REALITY  
→ trigger sentence  
→ female micro reaction  
→ HARD CUT  
→ fantasy visualization  
→ HARD CUT  
→ calm reality

只输出最终可拍剧本，不输出分镜。

### HUMAN GATE 02：最终剧本

如果用户未批准，停下。

用户明确说“可以”“定了”“就这个”“继续分镜”，视为通过。

---

## 阶段 3：资产登记与缺口分析

建立 asset manifest。

至少检查：

- female_lead
- male_date
- reality_scene
- q_chibi_style
- special_props（如有）

每个资产必须包含：

- asset_id
- type
- role
- usage
- do_not_use_for
- status: missing / draft / approved

如果关键资产缺失，只输出**最小补充清单**，不要擅自补造不存在的参考图。

---

## 阶段 4：拆分镜头

A切片优先 5–8 镜，最长不超过 10 镜。

优先使用：

- ESTABLISHING
- MS
- MCU
- CU
- OTS
- POV
- REACTION SHOT

现实层默认：

- 50–85mm
- eye-level
- 动作克制
- 构图自然
- 生活方式感

Q版层默认：

- 24–50mm
- 可夸张
- 动作清晰
- silhouette 可读
- 背景一眼说明幻想世界

每镜使用 [schemas.md](references/schemas.md) 中的 shot schema。

必须至少包含：

- 一个 female micro reaction
- 一个明确 trigger
- Fantasy 进入点
- Reality 返回点

---

## 阶段 5：Reference Routing

严格按 [qc-and-packaging.md](references/qc-and-packaging.md) 的固定规则执行。

原则：

- Reality = relevant character refs + approved Reality Anchor
- Fantasy = relevant character refs + Q style / approved Fantasy Anchor
- special prop 仅在镜头需要时加入
- Fantasy 不引用 Reality 餐厅图
- 每张 reference 的功能必须明确
- 不用“参考上一张”这种不可追踪描述

把最终 reference_asset_ids 写入每个 shot。

---

## 阶段 6：Anchor 计划

### Reality Anchor

优先选择：

- 男女主同框
- 能交代桌位、窗户、灯光和桌面
- 后续多数现实镜头可引用

### Fantasy Anchor

优先选择：

- 本集主要 Q版人物同框
- 风格、比例、材质完整
- 核心 fantasy world 一眼成立
- visual gag 清楚

### HUMAN GATE 03：Anchor

如果环境支持图片生成，可以先生成 Reality Anchor 与 Fantasy Anchor。

如果环境不支持图片生成，则输出：

- anchor_prompt
- reference_asset_ids
- approval_checklist
- status: awaiting_approval

不得跳过批准状态并假设 Anchor 已通过。

---

## 阶段 7：编译每镜 Image Prompt

只做 Prompt Compilation，不重新创作剧情。

Reality 镜头：

REALITY_MASTER_PROMPT  
+ relevant character block  
+ scene continuity block  
+ shot-specific block

Fantasy 镜头：

Q_CHIBI_MASTER_PROMPT  
+ relevant character block  
+ shot-specific block

必须输出：

- shot_id
- final_prompt
- reference_asset_ids
- expected_output: static_keyframe

禁止加入：

- 视频时长
- 视频运动强度
- lip sync 参数
- camera animation 参数
- video model-specific controls

---

## 阶段 8：静态关键帧 QC

按 [qc-and-packaging.md](references/qc-and-packaging.md) 检查：

- character identity
- wardrobe
- scene continuity
- shot compliance
- generation defects

输出：

- PASS / FAIL
- character_consistency
- scene_consistency
- shot_compliance
- generation_quality
- issues
- regeneration_instruction

FAIL 时只修最关键问题，不重新设计整个镜头。

---

## 阶段 9：前期制作包

最终整理：

- project metadata
- source / adaptation notes
- approved script
- shots
- asset manifest
- image prompts
- anchor prompts / approved anchors
- static keyframes（若已有）
- qc report
- preproduction manifest

这里结束。

**不要自动进入视频阶段。**
