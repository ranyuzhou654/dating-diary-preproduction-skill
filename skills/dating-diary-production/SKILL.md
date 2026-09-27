---
name: dating-diary-production
description: 《Dating Diary》视频生产阶段：读取 dating-diary-preproduction 交付的 preproduction_manifest.json，自动分段、按规则为每段配参考图、编写 MiniMax H3 参考转视频 JSON 提示词并校验，提交到云端 ComfyUI 批量生成多个 take、下载、按人物一致性自动选 take、拼出粗剪。用户说“开始生成视频”“把这一集交给 ComfyUI”“跑视频”“继续生成 <集名>”“拼粗剪”时使用。不负责剧本、分镜和关键帧（那是前期 skill 的工作），也不做最终配乐、字幕和配音（只给出后期说明）。
---

# Dating Diary 视频生产

你负责把一套**已经完成的前期制作包**变成可以进剪辑的视频素材和一条粗剪。

## 运行环境

- 默认在 **Codex** 中运行。你负责写视频提示词、判断和汇报；所有确定性工作都交给 `scripts/` 里的脚本（只用 Python 标准库和 ffmpeg；自动选 take 时可选装 InsightFace）。
- ComfyUI 跑在用户租用的云端 GPU 上。默认是 AutoDL 上的 **zealman 镜像**：脚本通过它控制面板的工作流 API 提交（`backend: zealman`，工作流是面板上保存的 U01 卡片）；也支持裸 ComfyUI（`backend: comfyui`）。连接配置见 [references/comfy-setup.md](references/comfy-setup.md)。
- 面板地址放环境变量 `COMFY_URL`。面板没有登录验证，地址不要写进任何会提交的文件。
- 所有进度写在项目目录里：`10_production/segments.json`、`10_production/production_state.json`、`10_production/selection.json`。**每次开始先看这些文件**，从没完成的地方继续。

## 前置条件

开始前检查，缺一项就停下并告诉用户缺什么：

1. `09_handoff/preproduction_manifest.json` 存在，且 `handoff_ready: true`（为 false 时可以继续，但要在汇报里写明）。
2. manifest 里每个镜头都有 `keyframe`，引用的图片文件都存在。
3. ComfyUI 配置文件存在（默认 `comfy.json`，从 `comfy.config.example.json` 复制），`python3 scripts/comfy_run.py check <project_dir> --config comfy.json` 通过。zealman 后端的 `check` 会确认面板在线、实例不是无卡模式、ComfyUI 已启动（没启动会按 U 系列插件档自动启动）、卡片存在、参考图槽位够用。报“无卡模式”或卡片不存在时停下，告诉用户去 AutoDL 控制台有卡开机或在面板导入 U01 卡片。

本阶段**没有人工 Gate**。前期的三个 Gate（改编方向、最终剧本、Anchor）已经通过，这里只在出错时停下。

---

## 阶段 P1：分段

```bash
python3 scripts/build_segments.py <project_dir>
```

规则由脚本执行，不要手动改分段：

- 现实层和 Q版层切换处必须断开；
- 每段可用画面不超过 10 秒；
- 每镜时长 = max(duration_hint, 台词最短时长)；
- 提交给 ComfyUI 的 Duration = 可用时长 + 0.5 秒，至少 3 秒；
- 参考图路由：
  - 现实段：本段关键帧 → 出场角色设定图 → Reality Anchor → 道具
  - Q版段：本段关键帧 → Fantasy Anchor → Q版角色图 / Q版风格图 → 道具
  - **Q版段绝不接写实设定图和 Reality Anchor**，否则画风会被拉向写实。

每段最多 9 张参考图（节点的 `ref_image_0…8`）。`build_segments.py` 默认按 9 张截断；提交时脚本按每段的张数自动使用只接这么多槽位的卡片副本，不用空白图占位（见 comfy-setup.md 第 3 节）。如果 `check` 报告某段超出上限，用它给出的 `--max-refs N` 重跑分段（脚本按优先级从末尾丢弃），然后按新的 `pictures` 重写提示词。

脚本输出里的 warnings（缺文件、缺关键帧、单镜超长）要在汇报里原样列出。

## 阶段 P2：编写视频提示词

对 `segments.json` 里的每一段，写 `10_production/prompts/G{n}.json`。格式和写法严格按 [references/video-prompt.md](references/video-prompt.md)。要点：

- 只用 segments.json 里给出的内容：镜头动作、景别、情绪、台词、声音提示、`character_blocks`。不新增剧情、角色或道具。
- `<Picture n>` 编号必须和该段 `pictures` 列表一一对应。
- 人物外貌直接用 `character_blocks[*].appearance_block_en` 和 `wardrobe_en`，并把 `must_not_have` 写成否定句（例如 "no glasses"）。
- 台词逐字照抄 `dialogue_lines`，中文用 `<d>[Chinese] …</d>`，英文用 `<d>[English] …</d>`。
- 时间戳按每镜的 `start` 写 `At 00:0x.xxx`。
- 不写负向提示词（工作流没有负向输入）：分镜里的“避免”一律改写成正向句。

写完运行：

```bash
python3 scripts/validate_video_prompts.py <project_dir>
```

有 ERROR 必须修到通过。WARNING 逐条看一遍，确认是有意为之再继续。

## 阶段 P3：提交生成

```bash
python3 scripts/comfy_run.py run <project_dir> --config comfy.json
```

- 默认每段 3 个 take（不同种子），可用 `--takes` 调整；
- zealman 后端**一次只跑一个 take**：清显存 → 提交 → 等完成 → 下载 → 下一个（面板上连续排队会显存溢出）。一段 10 秒的视频要跑几分钟，整集要等较长时间，这是正常的；
- 只重跑某几段：`--only G2,G5`；已经完成的 take 会自动跳过，`--force` 才会追加；
- 中途断开后：再跑一次同样的 `run` 即可（先把上次留下的任务等完、下载，再补缺的 take）；只想等不想提交新任务时用 `wait`；
- 每个任务完成立刻下载到 `11_renders/G{n}/`。`prompt_id` 在 ComfyUI 重启后就失效，服务器上的文件也会随实例释放丢失。

出现 ERROR 时：

- 提交被拒（`node_errors`、`unknown input`）：通常是节点编号或输入名不对，按 comfy-setup.md 重新 `inspect`，不要猜；
- 执行报错（显存不足等）：记录在 production_state.json，汇报给用户；
- `lost`：服务器已经没有这个任务的记录（ComfyUI 重启过），下次 `run` 会自动补交；
- 同一段失败超过 2 次，脚本就不再自动补交（`max_resubmits`）。先查原因，确认修好后才用 `--retry-failed`。

## 阶段 P4：选 take 与粗剪

```bash
python3 scripts/pick_takes.py <project_dir>
python3 scripts/assemble.py <project_dir>
```

- `pick_takes.py` 对现实段按人物相似度打分选最优 take，Q版段取第一条；比所需时长短的 take 排在最后。它**只检查身份和长度，不判断表演**。
- 用户想换某段的 take：改 `selection.json` 里的 `file`（或 `in` / `out`），设 `"locked": true`，再跑 `assemble.py`。
- 粗剪输出到 `12_rough_cut/rough_cut.mp4`，全部硬切，用于检查节奏。

## 阶段 P5：交付与汇报

写 `10_production/production_manifest.json`：每段的 Duration、参考图、提示词文件、全部 take 及其种子、选中的 take、粗剪路径、未解决问题。

给用户的汇报只包括：

- 分了几段、成片多长；
- 每段选中的 take（附分数），以及没有合格 take 的段；
- 需要用户处理的问题（前期遗留的 exception、缺失素材、生成失败）；
- 粗剪位置；
- 用的是 AutoDL 时，提醒用户视频已全部下载到本地，可以去控制台关机停止计费（本 skill 不替用户关机）。

最终配乐、字幕、统一配音不在本 skill 自动执行，按 [references/post-production.md](references/post-production.md) 提示用户。
