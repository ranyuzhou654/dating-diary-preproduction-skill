# Dating Diary Preproduction Skill

一个用于《Dating Diary》短剧**前期素材准备**的 Claude Skill。

它把真实 dating 经历、帖子、聊天记录或零散观察，整理成一套可直接进入后续制作环节的标准化前期资料：

**素材清洗 → 原创改编 → 剧本 → 分镜 → 资产登记 → Reference Routing → Anchor 规划 → ChatGPT Image 静态关键帧 Prompt → 静帧 QC → 交付包**

> 本仓库明确 **不负责视频生成**。不包含图生视频、运镜执行、配音、剪辑、字幕烧录或发布。

## 核心工作流

1. 读取原始素材，提取真正有价值的 awkward moment、话术、自我包装和行为反差。
2. 主动去识别化，避免复刻真实个人。
3. 提供 3–5 个原创改编方向，由用户选择。
4. 生成 A 切片或中短篇最终剧本。
5. 用户确认剧本后，拆成适合静态关键帧生成的镜头。
6. 建立角色、场景、Q 版风格和特殊道具资产。
7. 按规则自动为每个镜头分配 reference。
8. 先规划 / 生成 Reality Anchor 与 Fantasy Anchor。
9. Anchor 批准后，编译每个镜头的 ChatGPT Image Prompt。
10. 对静帧做人物、服装、场景、构图和生成瑕疵 QC。
11. 输出标准化前期制作包，供下游视频系统继续使用。

## Human Gates

Skill 默认保留 3 个需要人工判断的节点：

- **Gate 01：改编方向**
- **Gate 02：最终剧本**
- **Gate 03：Reality / Fantasy Anchor**

其它机械工作尽量自动化。

## 仓库结构

```
skills/
└── dating-diary-preproduction/
    ├── SKILL.md
    └── references/
        ├── series-bible.md
        ├── prompt-library.md
        ├── schemas.md
        └── qc-and-packaging.md
```

## 安装

### Claude Code

全局安装：

```bash
git clone https://github.com/ranyuzhou654/dating-diary-preproduction-skill.git
cp -R dating-diary-preproduction-skill/skills/dating-diary-preproduction ~/.claude/skills/
```

或复制到某个项目：

```
<project>/.claude/skills/dating-diary-preproduction/
```

### Claude.ai / 其他支持 Skills 的环境

将 `skills/dating-diary-preproduction` 文件夹打包上传。

## 使用示例

- 「把这段小红书 dating 经历改成 Dating Diary A 切片。」
- 「这个剧本已经定了，帮我拆分镜并配置 reference。」
- 「根据现有女主、男主和餐厅参考图，给每镜生成 ChatGPT Image prompt。」
- 「检查这些静态分镜有没有人物和场景连续性问题。」
- 「把这一集整理成标准前期制作包。」

## 设计原则

- 借真实经历的观察，不复刻真实个人。
- 男嘉宾在笑点发生前应看起来真实、正常、体面。
- 女主喜剧感来自微反应与脑内高速运转，而不是夸张嫌弃。
- Reality 与 Fantasy 使用不同视觉语言和 reference 系统。
- 每个镜头先作为**一张静态关键帧**成立。
- 所有 reference 都通过 asset_id 管理。
- 连续性优先用规则控制，而不是每次让模型自由判断。
