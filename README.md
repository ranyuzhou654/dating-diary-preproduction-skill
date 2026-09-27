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
        PRECHK{"前置条件<br/>manifest 存在 · 关键帧文件齐全<br/>comfy_run.py check 通过"}
        PRECHK -- "缺项" --> STOP(["停下，告诉用户缺什么"])
        PRECHK -- "通过（handoff_ready=false 时汇报写明）" --> P1[/"P1 build_segments.py<br/>分段 + 参考图路由<br/>→ 10_production/segments.json"/]
        P1 -- "接口少于所需参考图" --> P1R[/"build_segments.py --max-refs N"/]
        P1R --> P2
        P1 --> P2["P2 编写视频提示词<br/>10_production/prompts/G{n}.json"]
        P2 --> V[/"validate_video_prompts.py"/]
        V -- "ERROR" --> P2
        V -- "通过（WARNING 逐条确认）" --> P3[/"P3 comfy_run.py run<br/>每段默认 3 个 take<br/>完成即下载 → 11_renders/G{n}/"/]
        P3 -- "中途断开" --> P3W[/"comfy_run.py wait"/]
        P3W --> P3
        P3 -- "node_errors" --> INSPECT[/"comfy_run.py inspect<br/>重新核对节点"/]
        INSPECT --> P3
        P3 -- "执行报错（同段最多补交 2 次）" --> P3E["记录到 production_state.json<br/>汇报用户"]
        P3 -- "全部下载完成" --> P4A[/"P4 pick_takes.py<br/>现实段按人物相似度选 take<br/>Q版段取第一条 → selection.json"/]
        P4A --> P4B[/"assemble.py<br/>→ 12_rough_cut/rough_cut.mp4"/]
        P4B --> P5["P5 production_manifest.json<br/>+ 汇报：段数/时长 · 选中 take · 待处理问题 · 粗剪位置"]
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
        ├── comfy_run.py               # 上传、提交、断点续跑、下载
        ├── pick_takes.py              # 按人物一致性选 take
        └── assemble.py                # 粗剪 + production manifest
tests/
├── mock_comfy.py                 # 假 ComfyUI 服务器
├── fixture_workflow_api.json     # 模拟的 API 格式工作流
└── e2e_test.py                   # 整条视频链路的端到端测试
```

## 安装

依赖：Python 3.9+、ffmpeg。人脸相关的两个脚本另需 `pip install -r requirements-optional.txt`。

### Codex

在本仓库（或以它为子目录的工作区）里打开 Codex，`AGENTS.md` 会引导它读取两个 SKILL.md。

如果你的 Codex 版本支持全局 skills 目录，也可以复制过去：

```bash
cp -R skills/dating-diary-preproduction skills/dating-diary-production ~/.codex/skills/
```

### Claude Code

```bash
cp -R skills/dating-diary-preproduction skills/dating-diary-production ~/.claude/skills/
```

## 连接云端 ComfyUI

见 `skills/dating-diary-production/references/comfy-setup.md`。简要步骤：

1. 浏览器打开 `https://你的ComfyUI地址/system_stats`，确认能返回 JSON。
2. ComfyUI 菜单 **Workflow → Export (API)**，保存为 `workflows/minimax_h3_api.json`。
3. `cp skills/dating-diary-production/comfy.config.example.json comfy.json`，填 `base_url`（或设环境变量 `COMFY_URL`）。
4. `python3 skills/dating-diary-production/scripts/comfy_run.py inspect --config comfy.json --write`，核对节点编号。
5. `python3 skills/dating-diary-production/scripts/comfy_run.py check <集目录> --config comfy.json`。

ComfyUI 默认没有登录验证，不要把它裸露在公网上。

## 使用示例

- 「把这段素材改成 Dating Diary A 切片，女主 F01，男主 M03，场景 S01。」
- 「剧本定了，继续。」
- 「Anchor 可以，继续到粗剪。」
- 「继续 ep03。」（从状态文件恢复）
- 「G3 换第二个 take，重新拼粗剪。」

## 设计原则

- 借真实经历的观察，不复刻真实个人；原始素材不进 git。
- 男嘉宾在笑点发生前应看起来真实、正常、体面。
- 女主喜剧感来自微反应与脑内高速运转，而不是夸张嫌弃。
- Reality 与 Fantasy 使用不同视觉语言和 reference 系统；Q版视频段不接写实参考图。
- 每个镜头先作为**一张静态关键帧**成立。
- 所有 reference 都通过 asset_id 管理；人物身份特征只来自角色 `profile.json`。
- 连续性优先用规则和脚本控制，而不是每次让模型自由判断。
