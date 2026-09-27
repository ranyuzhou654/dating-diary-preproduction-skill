---
name: dating-diary-preproduction
description: 将真实 dating 素材、帖子、聊天记录、零散观察或已定剧本转成《Dating Diary》标准前期制作包：去识别化与原创改编、A切片/中短篇剧本、台词时长校验、分镜、资产登记、Reference Routing、Reality/Fantasy Anchor、image2 静态关键帧生成（状态文件 + 自动 QC + 有上限的重跑）、结构化打包。只负责前期素材准备与静态图阶段，不做视频生成、图生视频、配音、剪辑、字幕烧录或发布（视频阶段见 dating-diary-production）。用户说“把这个 dating 素材改成短剧”“做 Dating Diary 分镜”“给每镜配 reference / 图片 prompt”“生成关键帧”“整理成前期制作包”时使用。
---

# Dating Diary 前期制作总控

你负责把一个真实 dating 素材或已经确定的短剧方向，整理成**可重复、可追踪、可交接的前期制作包**。

## 运行环境

- 默认在 **Codex** 中运行。图片生成使用 Codex 内置的 **image2**，不调用外部图片 API。
- 本 skill 自带脚本，放在 `scripts/`，用 `python3` 运行。凡是脚本能做的判断（台词时长、关键帧状态、人脸相似度），一律以脚本结果为准，不靠模型自评。
- 所有进度写入项目目录下的状态文件。Codex 会话可能中断或被压缩上下文：**每次开始工作先读 `00_meta/project.json` 和 `07_keyframes/keyframe_state.json`，从未完成的地方继续。** 用户说“继续 <project_id>”即表示从状态文件恢复。

## 边界

本 skill 的终点是：

- 已批准的剧本（已通过台词时长校验）
- 已拆分的 shots
- 已登记的 assets
- 已完成 Reference Routing
- 已批准的 Reality / Fantasy Anchor
- 每镜 image2 Prompt
- 每镜静态关键帧及 QC 结果
- 前期交付目录与 manifest

**不要进入以下阶段：**

- 视频生成
- 图生视频
- 运动幅度 / 运镜执行参数
- 配音
- 剪辑
- 字幕烧录
- 发布

交付包完成后，视频阶段由 `dating-diary-production` skill 读取 `09_handoff/preproduction_manifest.json` 接手。你只需要把前期资料整理到可交接状态。

开始前读取：

- [references/series-bible.md](references/series-bible.md)
- [references/prompt-library.md](references/prompt-library.md)
- [references/schemas.md](references/schemas.md)
- [references/qc-and-packaging.md](references/qc-and-packaging.md)

---

## 核心原则

1. **每个镜头必须先能作为一张静态关键帧成立。**
2. **先锁 Anchor，再扩展镜头。**
3. **创意交给模型，连续性尽量交给规则和脚本。**
4. **真实经历只借观察，不复刻真实个人。**
5. **男嘉宾在笑点发生前必须像正常人。**
6. **女主反应克制，喜剧来自观察和脑内字面化。**
7. **所有角色、场景、风格、特殊道具都用 asset_id 管理。**
8. **人物身份特征只来自角色 profile.json 的 `identity_anchors`，模板里不写死任何具体特征（例如眼镜）。**
9. **人工只审批高价值判断。**
10. **不得假装不存在的参考图已经获得批准。**
11. **不得因为缺少素材而擅自编造用户已确认的设定。**
12. **原始素材只存为 `01_source/original_source.*`（被 .gitignore 排除）；后续阶段只使用去识别化后的 `01_source/adaptation_notes.md`。**

---

# 工作流

## 阶段 0：建立项目状态

创建项目目录（结构见 [qc-and-packaging.md](references/qc-and-packaging.md) 第 7 节），写入 `00_meta/project.json`：

- project_id
- working_title
- format: A切片 / B中短篇
- source_type
- input_asset_ids：用户指定的女主 / 男主 / 场景 ID
- known_assets
- current_stage
- approved_items

用户输入通常是：一段已筛选的真实素材 + 改编要求 + 女主角色 ID + 男主角色 ID + 场景 ID。按 ID 从 `assets/` 读取 profile.json 与参考图并登记；已有角色板、场景图、Q版风格图、现成剧本或已批准 Anchor，直接复用，不要从头重做。

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

输出（写入 `01_source/adaptation_notes.md`，只含去识别化后的内容）：

A. 原素材真正有价值的观察  
B. 需要去识别化的信息（只列类别，不抄原文）  
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

只输出最终可拍剧本，不输出分镜。同时写入 `02_script/script.md` 与 `02_script/script.json`（每句对白含 speaker 与 text）。

### 台词时长校验（提交 Gate 02 之前必须做）

运行：

```bash
python3 scripts/check_dialogue_timing.py 02_script/script.json
```

规则：中文按约 4.5 字/秒，英文按约 2.5 词/秒，另加换人说话的停顿。脚本给出每句的最短可说时长和全片最短时长。如果剧本声称的总时长短于脚本估算：

- 在提交给用户时**明确写出**“按台词实际需要约 X 秒”；
- 同时给出一版精简台词供选择。

不得把装不下台词的时长写进剧本。

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

角色资产还必须有 `profile.json`，其中包含 `identity_anchors`（必须出现的特征）和 `must_not_have`（必须不出现的特征，例如“不戴眼镜”）。格式见 [schemas.md](references/schemas.md)。

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

每镜的 `duration_hint` 不得小于该镜台词的 `est_speech_seconds`。拆完后再运行一次：

```bash
python3 scripts/check_dialogue_timing.py 03_storyboard/shots.json
```

有 FAIL 就调整 duration_hint，不要改台词（台词已在 Gate 02 批准）。

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

## 阶段 6：Anchor

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

用 image2 生成两张 Anchor（本集没有 Fantasy 就只生成 Reality），保存为 `06_anchors/reality_anchor.png`、`06_anchors/fantasy_anchor.png`，并对 Anchor 跑一次阶段 8 的 QC。然后把 Anchor 连同 QC 结果交给用户。

### HUMAN GATE 03：Anchor

状态写为 `awaiting_approval`，停下。

不得跳过批准状态并假设 Anchor 已通过。用户要求修改时，按修改意见重生成并再次提交。

---

## 阶段 7：编译每镜 Image Prompt

只做 Prompt Compilation，不重新创作剧情。

Reality 镜头：

REALITY_MASTER_PROMPT  
+ relevant character block（含该角色 identity_anchors 与 must_not_have）  
+ scene continuity block  
+ shot-specific block

Fantasy 镜头：

Q_CHIBI_MASTER_PROMPT  
+ relevant character block（含 identity_anchors 与 must_not_have）  
+ shot-specific block

必须输出（写入 `05_prompts/image_prompts.json` 与 `05_prompts/shot_XX.txt`）：

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

## 阶段 7.5：批量生成关键帧（Anchor 批准后自动进行）

先初始化状态文件：

```bash
python3 scripts/keyframe_state.py init <project_dir>
```

然后循环，**一次只处理一张**：

1. `python3 scripts/keyframe_state.py next <project_dir>` 取下一个待处理镜头及其尝试次数；返回 `DONE` 时结束循环。
2. 用 image2 生成：prompt 取 `05_prompts/shot_XX.txt`（若是重跑，末尾追加上次的 regeneration_instruction），参考图按该镜 reference_asset_ids 附上。
3. 保存为 `07_keyframes/shot_XX_tryN.png`（N 为尝试序号，从 1 开始）。
4. 执行阶段 8 的 QC。
5. `python3 scripts/keyframe_state.py record <project_dir> --shot XX --file <path> --status PASS|FAIL --issues "..." --instruction "..."` 写回结果。

脚本负责执行上限：同一镜头第 3 次仍 FAIL，会自动标记为 `exception` 并跳到下一镜。**不要**在脚本之外自行多跑。全部处理完后，`python3 scripts/keyframe_state.py status <project_dir>` 输出汇总，异常镜头列给用户（这不是新的 Gate，用户可以之后再处理）。

PASS 的镜头由脚本把最终文件复制为 `07_keyframes/shot_XX.png`。

---

## 阶段 8：静态关键帧 QC

两层检查，都要做：

**1. 客观层（脚本）**：写实人物镜头运行

```bash
python3 scripts/face_check.py --image <keyframe> --ref <character_model_sheet> [--ref ...]
```

任一应出现的角色相似度低于阈值 → 直接判 FAIL，不讨论。Q版镜头跳过这一层（人脸模型不适用于 chibi）。

**2. 清单层**：按 [qc-and-packaging.md](references/qc-and-packaging.md) 第 4 节逐项检查：

- character identity（逐条核对 identity_anchors 与 must_not_have）
- wardrobe
- scene continuity
- shot compliance
- generation defects
- 真实人物与商标（画面中不得出现像真实名人的脸、真实公司或品牌 logo）

清单层尽量由**独立的检查步骤**完成：若环境支持子任务，交给一个只做 QC、不参与生成的子任务；否则至少在生成结束后单独开一轮，只看图和标准，不看生成时的思路。

输出：

- PASS / FAIL
- character_consistency
- scene_consistency
- shot_compliance
- generation_quality
- issues
- regeneration_instruction

FAIL 时只修最关键问题（最多 3 个），不重新设计整个镜头。

---

## 阶段 9：前期制作包

最终整理：

- project metadata
- source / adaptation notes（仅去识别化内容）
- approved script
- shots（含 dialogue、speaker、duration_hint、est_speech_seconds、sound_hint）
- asset manifest
- image prompts
- approved anchors
- static keyframes
- qc report（含 exception 列表）
- `09_handoff/preproduction_manifest.json`

字段见 [schemas.md](references/schemas.md) 第 6 节。handoff 条件见 [qc-and-packaging.md](references/qc-and-packaging.md) 第 8 节。

这里结束。

**不要自动进入视频阶段。** 用户需要生成视频时，使用 `dating-diary-production` skill。
