# 云端 ComfyUI 连接设置

`comfy_run.py` 支持两种后端，在配置文件里用 `backend` 选：

| backend | 适用 | 提交方式 |
|---|---|---|
| `zealman`（默认） | AutoDL 上租的 **zealman 镜像**，浏览器打开的是它的控制面板（`https://xxx.seetacloud.com:8443`） | 面板的工作流 API：面板上保存的工作流卡片 + 每次只传要改的参数 |
| `comfyui` | 裸 ComfyUI（自己装的，或能直接访问 6006/8188 端口） | ComfyUI 原生 `/prompt`，用本地导出的 API 格式工作流 |

---

## A. zealman 面板（AutoDL）

### 用到的接口

| 接口 | 用途 |
|---|---|
| `GET /api/health`、`GET /api/gpu/info` | 面板在不在；是不是**无卡模式**（无卡模式能开机但跑不了生成） |
| `GET /api/comfy/status`、`POST /api/comfy/start` | ComfyUI 没启动就用 `pluginSeries: ["U"]` 启动并等它就绪 |
| `GET /api/comfy/plugin-availability` | 当前插件档位能不能跑 U 系列 |
| `GET /api/gpu/profile` | 显卡架构。U01 的文本编码器是 NVFP4 权重，只有 Blackwell（RTX 50 系）有原生算子 |
| `GET /api/workflow/list`、`GET /api/workflow/config/{id}` | 找到工作流卡片、读出它的节点（节点编号和参考图槽位都从这里来） |
| `POST /api/comfy/upload/file` | 上传参考图，返回的 `name` 填进 LoadImage |
| `POST /api/comfy/proxy/free` | 每个任务开跑前清显存 |
| `POST /api/workflow/generate` | 提交：`workflow_id` + `input_values`（键是 `节点ID:字段名`） |
| `GET /api/workflow/result?prompt_id=` | 轮询；`pending=false` 后给出 `/output/...` 地址 |
| `GET /api/comfy/queue-status` | 队列是否空闲（用来判断任务丢失） |
| `GET /output/...` | 下载成片 |

### 1. 准备面板

1. AutoDL 控制台**有卡模式**开机，打开面板地址，确认页面能进。
2. 面板「API 生成」页导入 MiniMax H3 参考转视频工作流（U01）并保存。卡片名就是配置里的 `workflow_id`。
3. 不需要在本地导出工作流：脚本会用 `/api/workflow/config/{id}` 读取卡片里的节点。

### 2. 配置

```bash
cp skills/dating-diary-production/comfy.config.example.json comfy.json
export COMFY_URL="https://你的实例.seetacloud.com:8443"      # 不写进文件
python3 skills/dating-diary-production/scripts/comfy_run.py inspect --config comfy.json   # 列出卡片节点和参考图槽位
python3 skills/dating-diary-production/scripts/comfy_run.py check <集目录> --config comfy.json
```

`check` 会依次确认：面板存活 → 有 GPU → ComfyUI 已启动（没启动就按 `plugin_series` 启动，`"auto_start": false` 时要加 `--start`）→ 卡片存在 → 节点映射 → 参考图槽位数 → 本集最多需要几张参考图。

U01 的节点（示例配置里已经填好）：

| 键 | 节点 | 字段 |
|---|---|---|
| conditioning | #136 MiniMax H3 参考转视频 | 参考图槽位 `ref_images.ref_image_0…3` |
| prompt | #146 CR Prompt Text | `prompt` |
| duration | #147 Float (Duration) | `value`（秒） |
| noise | #129 随机噪波 | `noise_seed` |
| save | #92 保存视频 | `filename_prefix` |
| 参考图 | #137 / #139 / #141 / #161 LoadImage | `image` |

卡片换了版本、节点编号变了：删掉配置里的 `nodes` 再跑 `inspect --write`，或者手动改。

### 3. 参考图槽位只有 4 个

面板 API 只能改参数，不能给工作流加节点，所以**每段最多 4 张参考图**（U01 有 4 个 LoadImage）：

- `check` 发现某段超过 4 张会 FAIL，`run` 会拒绝提交。处理方法：`build_segments.py <集目录> --max-refs 4` 重新分段（按优先级从末尾丢：道具 → 锚点 → 设定图，关键帧最优先保留），然后重写受影响段的提示词。
- 某段不足 4 张时，脚本把多出的槽位填成一张白色小图（面板自己也这么做），**提示词里不要提这些空槽位**。卡片里原来的示例图（`Untitled(4).jpg` 等）永远不会被用上。
- 想要更多槽位：在 ComfyUI 里给参考转视频节点多接几个“加载图像”（`ref_image_4`、`ref_image_5`…），重新保存卡片。脚本会自动识别新的槽位数。

### 4. 为什么一次只跑一个任务

面板文档说明：`generate` 不会自己清显存，连续提交 U 系列会“第一次成功、再跑 OOM”；ComfyUI 的“清显存”标记也只在下一个任务前生效一次。所以 `"serial": true`（zealman 默认）时 `run` 的流程是：

清显存 → 提交一个 take → 等它完成 → 立刻下载 → 下一个

`submit` 仍然可以一次排入全部任务，但不推荐在这个面板上用。

### 5. 任务丢失

`prompt_id` 只存在 ComfyUI 内存里：ComfyUI 重启（重新开机、崩溃、手动重启）后就查不到了，查询会一直返回 `pending=true`，和“还在跑”无法区分。脚本的判断：连续 3 次轮询都是 pending **而且面板队列空闲**，就把它记为 `lost`（状态 `error`），下次 `run` 自动补交。成片在完成的那一刻就下载到 `11_renders/`，不依赖服务器上的文件。

### 6. 时长和分辨率

- 工作流的帧数公式（#131）是 `max(5, round(秒×24))` 向上取到 `17k+5` 帧，所以成片会比 Duration 多 0–16 帧（最多约 0.67 秒）。分段已经留了 0.5 秒余量，剪辑按 `use_seconds` 截取，不受影响。
- 生成分辨率 544×960（#145），RTX 超分 ×2（#157）后输出 1088×1920。`assemble.py` 默认按 1080×1920 裁切铺满（`--fit crop`）。

### 7. 安全与计费

- 面板**没有登录验证**。拿到地址的人可以提交任务、删除输出、启停 ComfyUI。地址放环境变量 `COMFY_URL`，不要写进 git，也不要发到公开的地方。
- AutoDL 开机即计费。视频全部下载到本地后，提醒用户在 AutoDL 控制台关机（关机保留数据，释放才会删除）。
- 多台镜像机并发（`/api/concurrent/*`）需要 AutoDL Token，本 skill 暂不使用。

---

## B. 裸 ComfyUI

用到的接口：`/system_stats`、`/object_info/<节点类型>`、`/upload/image`、`/prompt`、`/history/<id>`、`/view`、`/queue`、`/free`。

1. 浏览器打开 `http://地址/system_stats` 能返回 JSON。远程访问需要 ComfyUI 启动参数 `--listen`；优先用 SSH 隧道（`base_url` 填 `http://127.0.0.1:8188`）。
2. ComfyUI 菜单 **Workflow → Export (API)**，保存为 `workflows/minimax_h3_api.json`（相对于配置文件）。API 格式是 `{"136": {"class_type": ..., "inputs": {...}}}`，不是带 `nodes`/`links` 的普通格式。
3. 配置里设 `"backend": "comfyui"`，其余节点映射同上；`workflow_id`、`plugin_series`、`auto_start` 不用。
4. 这个后端会把参考图节点整组删掉、按每段需要重新接，所以没有 4 张的上限；`"serial"` 默认为 false（一次排入全部任务），显存吃紧时改成 true。

需要口令时（放在带认证的反向代理后面）：

```json
"auth": {"header": "Authorization", "prefix": "Bearer ", "env": "COMFY_TOKEN"}
```

口令放环境变量 `COMFY_TOKEN`，**不要写进配置文件或提交到 git**。两种后端都支持这个设置。

## 文件与存储

- 参考图上传到服务器 input 目录（zealman：文件名前缀 `dating_diary__<集名>__`；裸 ComfyUI：子目录 `dating_diary/<集名>/`）。
- 视频输出到服务器 `output/dating_diary/<集名>/G{n}/`，完成后立即下载到本地 `11_renders/`。
- 租用实例释放后服务器文件会丢失，本地 `11_renders/` 才是正本；大文件放对象存储，不进 git。
