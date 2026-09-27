# Dating Diary Skills

《Dating Diary》短剧的生产流水线，由两个 skill 接力，在 **Codex** 中运行：

| Skill | 负责 |
|---|---|
| `dating-diary-preproduction` | 素材清洗 → 原创改编 → 剧本（含台词时长校验）→ 分镜 → 资产登记 → Reference Routing → Anchor → image2 批量关键帧（状态文件 + 自动 QC + 有上限的重跑）→ 前期交付包 |
| `dating-diary-production` | 读取交付包 → 自动分段与参考图路由 → MiniMax H3 视频提示词（带校验）→ 云端 ComfyUI 批量生成多个 take → 下载 → 自动选 take → 粗剪 |

前期 skill 本身不碰视频；视频阶段由 production skill 读取 `preproduction_manifest.json` 接手。

## 人工 Gate

整条流水线只有 3 个人工判断点：

- **Gate 01：改编方向**
- **Gate 02：最终剧本**
- **Gate 03：Reality / Fantasy Anchor**

Anchor 批准后，关键帧、QC、重跑、分段、视频生成、选 take、粗剪全部自动进行。自动重跑 3 次仍不合格的关键帧会进入异常列表，不阻塞流水线，之后由人处理。

## 完整流程图

菱形为判断，六边形为人工 Gate，平行四边形为 `scripts/` 里的脚本，矩形为模型执行的步骤。

```mermaid
flowchart TD
    IN(["输入：已筛选素材 + 改编要求<br/>女主 / 男主 / 场景 ID"]) --> RESUME{"已有状态文件？<br/>project.json / keyframe_state.json<br/>10_production/*.json"}
    RESUME -- "有：继续 &lt;集名&gt;" --> JUMP["从未完成的阶段继续"]
    RESUME -- "没有" --> S0

    subgraph PRE["dating-diary-preproduction（前期）"]
        direction TB
        S0["阶段 0 建立项目<br/>00_meta/project.json<br/>按 ID 读取 assets/ 的 profile.json 与参考图"]
        S0 --> S1["阶段 1 素材清洗与原创改编<br/>原始素材 → 01_source/original_source.*（不进 git）<br/>去识别化 → adaptation_notes.md<br/>3–5 个改编方向 + visual gag"]
        S1 --> G1{{"HUMAN GATE 01<br/>改编方向"}}
        G1 -- "未选定：停下等待" --> S1
        G1 -- "批准" --> S2["阶段 2 最终剧本<br/>02_script/script.md + script.json"]
        S2 --> T1[/"check_dialogue_timing.py<br/>script.json"/]
        T1 -- "时长不够" --> T1F["写明实际所需秒数<br/>附一版精简台词"]
        T1F --> G2
        T1 -- "OK" --> G2{{"HUMAN GATE 02<br/>最终剧本"}}
        G2 -- "修改" --> S2
        G2 -- "批准" --> S3["阶段 3 资产登记与缺口分析<br/>female_lead / male_date / reality_scene<br/>q_chibi_style / special_props"]
        S3 --> MISS{"关键资产缺失？"}
        MISS -- "是" --> MISSOUT["只输出最小补充清单<br/>不擅自补造参考图"]
        MISS -- "否" --> S4["阶段 4 拆分镜头<br/>03_storyboard/shots.json（5–8 镜，≤10）"]
        S4 --> T2[/"check_dialogue_timing.py<br/>shots.json"/]
        T2 -- "FAIL：只调 duration_hint" --> S4
        T2 -- "PASS" --> S5["阶段 5 Reference Routing<br/>每镜写入 reference_asset_ids<br/>Fantasy 不接 Reality 餐厅图"]
        S5 --> S6["阶段 6 image2 生成 Anchor<br/>06_anchors/reality_anchor.png<br/>fantasy_anchor.png（如有）<br/>+ 阶段 8 QC"]
        S6 --> G3{{"HUMAN GATE 03<br/>Reality / Fantasy Anchor<br/>状态 awaiting_approval"}}
        G3 -- "修改意见：重生成" --> S6
        G3 -- "批准（之后自动跑到粗剪）" --> S7["阶段 7 编译每镜 Image Prompt<br/>MASTER + 角色块 + 场景块 + 镜头块<br/>05_prompts/image_prompts.json / shot_XX.txt"]

        S7 --> KINIT[/"keyframe_state.py init"/]
        KINIT --> KNEXT[/"keyframe_state.py next"/]
        KNEXT -- "DONE" --> KSTAT[/"keyframe_state.py status<br/>汇总 + exception 列表"/]
        KNEXT -- "下一镜 + 尝试次数 N" --> KGEN["image2 一次生成一张<br/>重跑时追加 regeneration_instruction<br/>07_keyframes/shot_XX_tryN.png"]
        KGEN --> QCTYPE{"写实人物镜头？"}
        QCTYPE -- "是" --> FACE[/"face_check.py<br/>对比角色设定图"/]
        QCTYPE -- "Q版：跳过人脸" --> QCLIST
        FACE -- "低于阈值" --> QFAIL["FAIL"]
        FACE -- "通过" --> QCLIST["阶段 8 清单层 QC（独立子任务）<br/>identity_anchors / must_not_have<br/>服装 · 场景 · 镜头 · 瑕疵 · 真人与商标"]
        QCLIST -- "PASS" --> QPASS["PASS"]
        QCLIST -- "FAIL（最多修 3 个问题）" --> QFAIL
        QPASS --> KREC[/"keyframe_state.py record<br/>PASS → 复制为 shot_XX.png<br/>第 3 次 FAIL → exception"/]
        QFAIL --> KREC
        KREC --> KNEXT

        KSTAT --> S9["阶段 9 前期交付包<br/>09_handoff/preproduction_manifest.json"]
    end

    S9 --> PRECHK

    subgraph PROD["dating-diary-production（视频）"]
        direction TB
        PRECHK{"前置条件<br/>manifest 存在 · 关键帧文件齐全<br/>comfy_run.py check 通过<br/>（面板在线 · 有卡 · ComfyUI 已启动 · 卡片存在 · 槽位够用）"}
        PRECHK -- "缺项" --> STOP(["停下，告诉用户缺什么"])
        PRECHK -- "通过（handoff_ready=false 时汇报写明）" --> P1[/"P1 build_segments.py<br/>分段 + 参考图路由<br/>→ 10_production/segments.json"/]
        P1 -- "参考图多于槽位（U01 为 4）" --> P1R[/"build_segments.py --max-refs N"/]
        P1R --> P2
        P1 --> P2["P2 编写视频提示词<br/>10_production/prompts/G{n}.json"]
        P2 --> V[/"validate_video_prompts.py"/]
        V -- "ERROR" --> P2
        V -- "通过（WARNING 逐条确认）" --> P3[/"P3 comfy_run.py run<br/>每段默认 3 个 take，逐个进行：<br/>清显存 → 提交 → 等完成 → 下载到 11_renders/G{n}/"/]
        P3 -- "中途断开：再跑 run" --> P3
        P3 -- "lost：ComfyUI 重启过" --> P3L["记为 error<br/>下次 run 自动补交"]
        P3L --> P3
        P3 -- "node_errors" --> INSPECT[/"comfy_run.py inspect<br/>重新核对节点"/]
        INSPECT --> P3
        P3 -- "执行报错" --> P3E["记录到 production_state.json<br/>同段失败超过 2 次停止补交<br/>汇报用户"]
        P3 -- "全部下载完成" --> P4A[/"P4 pick_takes.py<br/>现实段按人物相似度选 take<br/>Q版段取第一条 → selection.json"/]
        P4A --> P4B[/"assemble.py<br/>→ 12_rough_cut/rough_cut.mp4"/]
        P4B --> P5["P5 production_manifest.json<br/>+ 汇报：段数/时长 · 选中 take · 待处理问题 · 粗剪位置<br/>提醒到 AutoDL 关机停止计费"]
        P5 --> SWAP{"用户要换某段 take？"}
        SWAP -- "改 selection.json<br/>locked: true" --> P4B
        SWAP -- "否" --> DONE(["粗剪完成<br/>配乐 / 字幕 / 配音见 post-production.md"])
    end
```

## 仓库结构

```
AGENTS.md                         # Codex 的总规则（Gate、状态文件、脚本优先……）
skills/
├── dating-diary-preproduction/
│   ├── SKILL.md
│   ├── references/               # series-bible / prompt-library / schemas / qc-and-packaging
│   └── scripts/
│       ├── check_dialogue_timing.py   # 台词最短时长，剧本和分镜都要过
│       ├── keyframe_state.py          # 关键帧进度、重跑上限（3 次）、异常列表
│       └── face_check.py              # 关键帧 vs 角色设定图的人脸相似度（写实镜头）
└── dating-diary-production/
    ├── SKILL.md
    ├── comfy.config.example.json
    ├── references/               # video-prompt / comfy-setup / post-production
    └── scripts/
        ├── build_segments.py          # 分段 + 参考图路由
        ├── validate_video_prompts.py  # 提示词与分段逐项核对
        ├── comfy_run.py               # zealman 面板 / 裸 ComfyUI：上传、逐个提交、断点续跑、下载
        ├── pick_takes.py              # 按人物一致性选 take
        └── assemble.py                # 粗剪 + production manifest
tests/
├── mock_comfy.py                 # 假 ComfyUI + 假 zealman 面板
├── fixture_workflow_api.json     # U01 MiniMax H3 参考转视频工作流（API 格式）
└── e2e_test.py                   # 整条视频链路的端到端测试
```

## 使用教程

下面按一集从零到粗剪的顺序写。你要做的事只有三类：**一次性准备**、**在 3 个 Gate 上做判断**、**验收粗剪**。其余步骤由 Codex 按两个 SKILL.md 调用脚本完成。

### 第 0 步：一次性准备

#### 0.1 本机环境

| 需要 | 用途 | 检查 |
|---|---|---|
| Python 3.9+ | 所有脚本 | `python3 --version` |
| ffmpeg / ffprobe | 粗剪、测试 | `ffmpeg -version` |
| （可选）InsightFace 等 | 写实关键帧的人脸比对、按人脸自动选 take | `pip install -r requirements-optional.txt` |

不装可选依赖也能跑完全程，只是会少两样：关键帧 QC 只做清单层检查，没有人脸相似度打分；选 take 时每段直接取第一条。

装好后跑一次自测，确认脚本在你的机器上能用：

```bash
python3 tests/e2e_test.py      # 最后一行是 ALL OK 即可
```

#### 0.2 在 Codex 里打开仓库

```bash
git clone <本仓库地址> dating-diary && cd dating-diary
codex        # 或用 Codex 桌面端打开这个目录
```

Codex 会自动读 `AGENTS.md`，再由它引导去读两个 SKILL.md，不需要额外安装。如果你的 Codex 版本支持全局 skills 目录，也可以把两个 skill 复制过去：

```bash
cp -R skills/dating-diary-preproduction skills/dating-diary-production ~/.codex/skills/
```

需要注意两点：

- **允许联网。** 视频阶段要访问云端面板。Codex 的沙箱默认可能不允许联网，需要在 Codex 设置里打开，或者在它请求时批准。
- **建议用本地 Codex 跑视频阶段。** 视频会下载到 Codex 所在机器的项目目录，而 `11_renders/`、`12_rough_cut/` 不进 git。如果用 Codex 云端任务，文件留在云端容器里，需要另外取回。

Claude Code 也能用：`cp -R skills/dating-diary-preproduction skills/dating-diary-production ~/.claude/skills/`。

#### 0.3 准备角色 / 场景库

Codex 开一集时按 ID 读取已有资产。建议在工作区建一个 `assets/` 目录：

```
assets/
├── characters/
│   ├── F01/              # 女主
│   │   ├── model_sheet.png   # 角色设定图（多角度），人脸比对和视频参考都用它
│   │   ├── closeup.png
│   │   ├── fullbody.png
│   │   └── profile.json
│   └── M03/ …            # 男嘉宾
├── scenes/S01/     anchor.png  empty_scene.png  scene.json
├── styles/q_chibi_v01/   style_reference.png  style.json
└── props/<道具ID>/   reference.png  prop.json
```

`profile.json` 是人物身份的**唯一来源**（完整格式见 `skills/dating-diary-preproduction/references/schemas.md`），关键字段：

| 字段 | 作用 |
|---|---|
| `appearance_block_en` | 一段英文外貌描述，关键帧和视频提示词都原样复用 |
| `identity_anchors` | 必须出现的特征，QC 逐条核对 |
| `must_not_have` | 必须不出现的特征，例如 `glasses`。不写的话，模型可能从别的角色带进来 |
| `wardrobe.default` / `episode_overrides` | 默认服装和某一集的专属服装 |
| `chibi_asset_id` | Q版形象（本集有幻想段时用） |

缺的资产不用提前补齐。Codex 在阶段 3 会列出一份**最小补充清单**，但不会替你编造参考图。

#### 0.4 连接 AutoDL 上的 ComfyUI（zealman 镜像）

1. AutoDL 控制台用**有卡模式**开机，浏览器打开面板地址（形如 `https://xxx.seetacloud.com:8443`）。
2. 在面板「API 生成」页导入 U01「MiniMax H3 参考转视频」工作流并保存，记下**卡片名**。
3. 在仓库根目录建配置（`comfy.json` 已被 .gitignore 排除）：

   ```bash
   cp skills/dating-diary-production/comfy.config.example.json comfy.json
   # 编辑 comfy.json：把 "workflow_id" 改成第 2 步的卡片名
   export COMFY_URL="https://你的实例.seetacloud.com:8443"   # 写进 ~/.zshrc 或 ~/.bashrc，不要写进仓库
   ```

4. 检查连接：

   ```bash
   python3 skills/dating-diary-production/scripts/comfy_run.py check --config comfy.json
   ```

   这一步会依次检查：面板在线 → 有 GPU（不是无卡模式）→ ComfyUI 已启动（没启动会自动按 U 系列插件档启动）→ 卡片存在 → 节点映射 → 参考图槽位数（U01 是 4 个）。报错时看末尾的「常见问题」。

面板**没有登录验证**，拿到地址的人就能用你的 GPU，所以地址不要提交到 git，也不要公开。更多细节（接口、槽位、任务丢失、裸 ComfyUI）见 `skills/dating-diary-production/references/comfy-setup.md`。

---

### 第 1 步：开一集

在 Codex 里一次说清四样东西：素材、改编要求、角色 ID、场景 ID。例如：

> 新建一集 ep05，放在 episodes/ep05。把下面这段素材改成 Dating Diary A 切片，女主 F01，男主 M03，场景 S01。要求：笑点落在男嘉宾过度准备的自我介绍上，保留一段 Q版脑内小剧场。
>
> （粘贴素材：帖子、聊天记录、你自己的观察都可以）

Codex 会：

- 建 `episodes/ep05/` 和 `00_meta/project.json`；
- 把原始素材存成 `01_source/original_source.*`（**不进 git**），后面只用去识别化后的 `adaptation_notes.md`；
- 按 ID 读取并登记角色和场景资产。

### 第 2 步：Gate 01 — 选改编方向

Codex 给出 3–5 个原创改编方向，每个都附最强的 visual gag / Q版脑内小剧场，然后**停下等你**。

你要看的：笑点是否来自观察而非丑化男嘉宾；有没有残留能认出真人的信息（姓名、学校、公司、精确地点和时间）。

回复示例：「用方向 2，把职业改成建筑师，其他不变。」或「方向 3，继续。」

### 第 3 步：Gate 02 — 定剧本

Codex 写出 `02_script/script.md` / `script.json`，并用脚本做**台词时长校验**：中文约 4.5 字/秒，另加换人停顿。如果台词在声称的时长里说不完，它会写明「按台词实际需要约 X 秒」，并附一版精简台词。

你要看的：节奏是否是「正常现实 → 触发句 → 女主微反应 → 硬切幻想 → 硬切回现实」，台词是否自然，总时长能否接受。

回复示例：「用精简版台词，定了。」

### 第 4 步：自动执行（无需操作）— 资产、分镜、参考图路由

- **阶段 3**：检查资产。缺关键资产时只列最小补充清单，你补上后说「资产补好了，继续」。
- **阶段 4**：拆 5–8 个镜头，并再做一次时长校验（只调镜头时长，不改已批准的台词）。
- **阶段 5**：按固定规则给每个镜头配参考图，Q版镜头不接写实餐厅图。

### 第 5 步：Gate 03 — 批准 Anchor（最后一个人工 Gate）

Codex 用 image2 生成 `06_anchors/reality_anchor.png`（有幻想段时再生成 `fantasy_anchor.png`），附上 QC 结果，然后停下。

你要看的：

- 人物是否符合 `profile.json`（逐条核对 `identity_anchors` 和 `must_not_have`）；
- 场景、光线、桌位是否是后续大多数镜头想要的样子；
- Q版比例和材质是否成立，笑点是否一眼能看懂；
- 画面里没有像真实名人的脸，也没有真实品牌 logo。

不满意就直接说修改意见，例如「男生头发再短一点，窗外换成夜景」，它会重生成再提交。

> **批准之前先确认 AutoDL 已经开机，并且 `check` 能通过。** 批准后 Codex 会一路跑到粗剪，中间不再停下，除非出错。

回复示例：「Anchor 可以，继续到粗剪。」

### 第 6 步：自动执行（无需操作）— 关键帧与前期交付包

- 编译每个镜头的图片提示词，再用 image2 **一次一张**生成关键帧；
- 每张都过 QC：写实镜头先跑 `face_check.py` 人脸比对，再做一轮独立的清单检查；
- 不合格就带着修改指令重跑，**同一镜头最多 3 次**。第 3 次仍不合格就记为 exception，跳到下一镜，不阻塞流程；
- 最后打包成 `09_handoff/preproduction_manifest.json`。

### 第 7 步：自动执行（无需操作）— 视频生成与下载

Codex 切换到视频 skill，依次执行：

1. `build_segments.py`：自动分段（现实段和 Q版段分开，每段 ≤ 10 秒），并给每段配参考图。U01 每段最多 4 张参考图，超出时 `check` 会提示用 `--max-refs 4` 重新分段；
2. 按 `references/video-prompt.md` 写每段的 MiniMax H3 JSON 提示词，再用 `validate_video_prompts.py` 校验；
3. `comfy_run.py run`：每段默认 3 个 take，**一个接一个**进行：清显存 → 提交 → 等完成 → **立刻下载到 `11_renders/G{n}/`**；
4. `pick_takes.py` 选出每段最好的 take，`assemble.py` 拼出 `12_rough_cut/rough_cut.mp4`。

生成 10 秒左右的一段要几分钟，一整集要等比较久，这是正常的。想看进度，可以另开一个终端：

```bash
python3 skills/dating-diary-production/scripts/comfy_run.py status episodes/ep05
ls episodes/ep05/11_renders/*/
```

如果不想让 Codex 一直开着等，也可以自己在后台跑生成，跑完再回 Codex 说「继续 ep05」，让它选 take、拼粗剪：

```bash
nohup python3 skills/dating-diary-production/scripts/comfy_run.py run episodes/ep05 --config comfy.json \
  > episodes/ep05/render.log 2>&1 &
```

### 第 8 步：验收粗剪、换 take

Codex 的汇报会包含：分了几段、成片多长、每段选中的 take（有分数时附分数）、需要你处理的问题（前期 exception、生成失败）、粗剪位置。

`pick_takes.py` **只检查人物一致性和长度，不判断表演**，所以请看一遍 `12_rough_cut/rough_cut.mp4`。

想换 take，直接说：「G3 换第二个 take，重新拼粗剪。」也可以手动改 `10_production/selection.json`：

```jsonc
"G3": {
  "file": "11_renders/G3/G3_s123456_00001_.mp4",  // 换成 candidates 里的另一个文件
  "in": 0.0, "out": 5.2,                           // 可选：调整截取的起止秒数
  "locked": true                                   // 锁定后，重跑 pick_takes 也不会覆盖
}
```

改完运行 `python3 skills/dating-diary-production/scripts/assemble.py episodes/ep05`。

某段所有 take 都不满意：「G2 再跑 2 个 take。」`--takes` 是每段的总数，所以已有 3 个时对应 `comfy_run.py run … --only G2 --takes 5`。

### 第 9 步：收尾

- **到 AutoDL 控制台关机**：视频已经全部下载到本地，开着机会一直计费。关机会保留数据，释放实例才会删除数据。Codex 不会替你关机。
- 配乐、字幕、统一配音在剪辑软件里做，见 `skills/dating-diary-production/references/post-production.md`。
- `11_renders/`、`12_rough_cut/` 不进 git，需要长期保存的请放到对象存储或网盘。

---

### 中断与恢复

所有进度都写在集目录的状态文件里（`00_meta/project.json`、`07_keyframes/keyframe_state.json`、`10_production/*.json`）。无论是 Codex 会话断了、上下文被压缩、电脑休眠还是 ComfyUI 重启，都只需要说：

> 继续 ep05

- 前期阶段：从最后一个未完成的阶段或镜头继续，已经通过的 Gate 不会再问。
- 视频阶段：已经提交的任务在服务器上会继续跑完。再次 `run` 时，脚本先把它们等完、下载下来，再补上缺的 take。
- ComfyUI 重启过：服务器已经查不到的任务会被标记为 `lost`，自动补交。
- 同一段失败超过 2 次就不再自动补交，Codex 会停下来汇报原因。

### 常用说法

| 你说 | Codex 做 |
|---|---|
| 「把这段素材改成 Dating Diary A 切片，女主 F01，男主 M03，场景 S01。」 | 开新集，走到 Gate 01 |
| 「方向 2，继续。」 | 通过 Gate 01，写剧本 |
| 「剧本定了，继续。」 | 通过 Gate 02，走到 Gate 03 |
| 「Anchor 可以，继续到粗剪。」 | 通过 Gate 03，一路跑到粗剪 |
| 「继续 ep05。」 | 读状态文件，从断点继续 |
| 「G3 换第二个 take，重新拼粗剪。」 | 改 selection.json 并重新 assemble |
| 「G2 再跑 2 个 take。」 | 只给 G2 追加 take |
| 「只重新拼粗剪。」 | 只跑 assemble.py |

### 手动命令速查

以下命令都在仓库根目录执行，`EP=episodes/ep05`。

| 命令 | 作用 |
|---|---|
| `python3 skills/dating-diary-preproduction/scripts/check_dialogue_timing.py $EP/02_script/script.json` | 台词时长校验（剧本或 shots.json） |
| `python3 skills/dating-diary-preproduction/scripts/keyframe_state.py status $EP` | 关键帧进度和 exception 列表 |
| `python3 skills/dating-diary-production/scripts/comfy_run.py check $EP --config comfy.json` | 检查面板、GPU、卡片、槽位 |
| `python3 skills/dating-diary-production/scripts/comfy_run.py inspect --config comfy.json` | 列出卡片节点和参考图槽位 |
| `python3 skills/dating-diary-production/scripts/build_segments.py $EP [--max-refs 4]` | 分段并配参考图 |
| `python3 skills/dating-diary-production/scripts/validate_video_prompts.py $EP` | 校验视频提示词 |
| `python3 skills/dating-diary-production/scripts/comfy_run.py run $EP --config comfy.json [--only G2] [--takes N]` | 生成并下载 |
| `python3 skills/dating-diary-production/scripts/comfy_run.py wait $EP --config comfy.json` | 只等待、下载已提交的任务 |
| `python3 skills/dating-diary-production/scripts/comfy_run.py status $EP` | 每段 take 状态 |
| `python3 skills/dating-diary-production/scripts/pick_takes.py $EP` | 选 take |
| `python3 skills/dating-diary-production/scripts/assemble.py $EP [--fit pad]` | 拼粗剪 |

### 常见问题

| 现象 | 原因与处理 |
|---|---|
| `check` 报 `no-GPU mode (无卡模式)` | AutoDL 以无卡模式开的机，回控制台按有卡模式重新开机 |
| `check` 报卡片 `is not saved on the panel` | `workflow_id` 和面板上的卡片名不一致。报错里会列出已保存的卡片，照着改 `comfy.json` |
| `cannot reach …` | 地址不对、实例没开机，或 Codex 沙箱没有联网权限 |
| `FAIL: a segment needs 5 references but the workflow has 4 slots` | 运行 `build_segments.py <集目录> --max-refs 4`，再让 Codex 重写受影响段的提示词。也可以在工作流里多接几个“加载图像”，再重新保存卡片 |
| 提交时报 `unknown input` 或 `node_errors` | 卡片的节点编号变了：删掉 `comfy.json` 里的 `nodes`，运行 `inspect --write` 重新识别 |
| 执行报错（显存不足等） | 已记录在 `production_state.json`，下次 `run` 会补交；同一段失败超过 2 次就停止，查明原因后用 `--retry-failed` |
| 某个任务一直 `queued` 最后变成 `lost` | ComfyUI 中途重启过，旧任务查不到了。再跑一次 `run` 就会补交 |
| 选 take 时显示 `InsightFace not installed` | 没装可选依赖，每段取第一条。可以装上 `requirements-optional.txt` 后重跑 `pick_takes.py`，或者手动改 selection.json |
| 粗剪上下有黑边或被裁得太多 | `assemble.py` 默认裁切铺满，`--fit pad` 改成加黑边 |


## 设计原则

- 借真实经历的观察，不复刻真实个人；原始素材不进 git。
- 男嘉宾在笑点发生前应看起来真实、正常、体面。
- 女主喜剧感来自微反应与脑内高速运转，而不是夸张嫌弃。
- Reality 与 Fantasy 使用不同视觉语言和 reference 系统；Q版视频段不接写实参考图。
- 每个镜头先作为**一张静态关键帧**成立。
- 所有 reference 都通过 asset_id 管理；人物身份特征只来自角色 `profile.json`。
- 连续性优先用规则和脚本控制，而不是每次让模型自由判断。
