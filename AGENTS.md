# AGENTS.md — Dating Diary 生产流水线

本仓库给 Codex 用。两个 skill 接力完成一集《Dating Diary》：

| 阶段 | Skill | 起点 → 终点 |
|---|---|---|
| 前期 | `skills/dating-diary-preproduction/SKILL.md` | 已筛选的素材 + 改编要求 + 角色/场景 ID → `09_handoff/preproduction_manifest.json` |
| 视频 | `skills/dating-diary-production/SKILL.md` | manifest → 云端 ComfyUI 生成 → `12_rough_cut/rough_cut.mp4` |

处理任何一集之前，先完整读对应阶段的 SKILL.md 和它列出的 references。

## 人工 Gate（只有这些，不许跳过，也不许新增）

1. 改编方向（前期阶段 1 之后）
2. 最终剧本（前期阶段 2 之后）
3. Reality / Fantasy Anchor（前期阶段 6 之后）

到了 Gate 就把需要用户判断的内容整理好，停下等待。用户明确批准后才继续。Gate 3 批准之后，直到粗剪完成，中间不再停下，除非出错。

## 通用规则

- **先读状态，再干活**：每次开始（包括用户说“继续 <集名>”）先读项目目录下的 `00_meta/project.json`、`07_keyframes/keyframe_state.json`、`10_production/*.json`，从未完成处继续。
- **脚本优先**：台词时长、关键帧重跑次数、人脸相似度、分段、参考图路由、提示词校验、ComfyUI 提交都由 `scripts/` 执行。脚本给出的结论不要用自己的判断推翻。
- **生图用 image2**（Codex 内置），一次只生成一张，按 SKILL.md 规定的路径和文件名保存。
- **生成和检查分开**：关键帧 QC 尽量交给单独的子任务或单独的一轮，只看图和标准。
- **身份特征只来自角色 `profile.json`**（`identity_anchors` / `must_not_have`），不要从模板、其他角色或旧剧集里带入特征。
- **原始素材不进 git**：只写到 `01_source/original_source.*`（已被 .gitignore 排除），后续只用去识别化后的 `adaptation_notes.md`。
- **不提交密钥**：ComfyUI 地址和口令放环境变量 `COMFY_URL` / `COMFY_TOKEN`，`comfy.json` 已被忽略。
- **大文件不进 git**：渲染结果、粗剪、关键帧的重试图都被 .gitignore 排除，放对象存储。

## 目录约定

每集一个目录（建议放在 `episodes/<集名>/`），结构见
`skills/dating-diary-preproduction/references/qc-and-packaging.md` 第 7 节，视频阶段再加：

```
10_production/   segments.json  prompts/G*.json  production_state.json  selection.json  production_manifest.json
11_renders/      G1/ G2/ …        （每段所有 take）
12_rough_cut/    rough_cut.mp4
```

## 测试

改动任何脚本后运行：

```bash
python3 tests/e2e_test.py
```

它会起一个假的 ComfyUI 服务器，把分段、校验、提交、断点续跑、下载、选 take、粗剪整条链路跑一遍。
