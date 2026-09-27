# 云端 ComfyUI 连接设置

ComfyUI 自带 HTTP API，就是浏览器打开的那个地址，不需要另外安装。本 skill 用到的接口：

| 接口 | 用途 |
|---|---|
| `GET /system_stats` | 连通性与显卡信息 |
| `GET /object_info/<节点类型>` | 查节点声明了哪些输入（参考图接口数量） |
| `POST /upload/image` | 上传参考图 |
| `POST /prompt` | 提交一个任务 |
| `GET /history/<prompt_id>` | 任务是否完成、输出了哪些文件 |
| `GET /view?filename=…` | 下载输出 |
| `GET /queue` | 服务器队列 |

## 1. 确认能访问

浏览器打开 `https://你的ComfyUI地址/system_stats`，返回一段 JSON 即可。

租用 GPU 平台常见的三种访问方式：

- **平台的自定义服务 / 端口映射地址**：直接填进 `base_url`。
- **SSH 隧道**（在本机开 `localhost:8188`）：脚本也要在同一台机器、隧道开着的时候运行，`base_url` 填 `http://127.0.0.1:8188`。
- **ComfyUI 启动参数**：远程访问需要 `--listen`（或 `--listen 0.0.0.0`）。

**安全**：ComfyUI 默认没有登录验证，暴露到公网等于任何人都能用你的显卡、读写服务器文件。优先用 SSH 隧道或平台的私有链接；必须公网时，在前面放一个带口令的反向代理，然后在配置里写：

```json
"auth": {"header": "Authorization", "prefix": "Bearer ", "env": "COMFY_TOKEN"}
```

口令放环境变量 `COMFY_TOKEN`，**不要写进配置文件或提交到 git**。`base_url` 也可以用环境变量 `COMFY_URL` 覆盖。

## 2. 导出 API 格式工作流

ComfyUI 菜单 **Workflow → Export (API)**，保存为 `workflows/minimax_h3_api.json`（相对于配置文件的位置）。

注意：API 格式和普通保存的工作流不是一个格式。普通格式里有 `nodes`/`links` 数组，API 格式是 `{"136": {"class_type": ..., "inputs": {...}}, ...}`。

导出前在画布上确认：

- 分辨率（#145）已设为竖屏 480×864（或 544×960）；
- RTX 超分（#157）按需要开启或绕过；
- 所有参考图接口都连着“加载图像”节点（脚本会自动删掉并按每段需要重新接）。

## 3. 配置节点映射

```bash
cp comfy.config.example.json comfy.json
python3 scripts/comfy_run.py inspect --config comfy.json          # 列出所有节点，给出猜测的映射
python3 scripts/comfy_run.py inspect --config comfy.json --write  # 把猜测写进配置
python3 scripts/comfy_run.py check <project_dir> --config comfy.json
```

需要映射的节点（`nodes`）：

| 键 | 含义 | 当前工作流里的编号 |
|---|---|---|
| conditioning | MiniMax H3 参考转视频节点（有 ref_image_* 输入） | 136 |
| prompt | 提示词文本节点（CR Prompt Text） | 146 |
| duration | 时长（秒）节点 | 147 |
| noise | 随机噪波节点（种子） | 129 |
| save | 保存视频节点（有 filename_prefix） | 截图外，需 inspect 确认 |

输入名（`inputs`）默认是 `prompt` / `value` / `noise_seed` / `filename_prefix`。如果 `check` 或提交时报 `node_errors`，打开导出的 json 看这几个节点 `inputs` 里真实的键名，改进配置。

`check` 会读取参考转视频节点声明的 `ref_image_*` 接口数量，并和分段需要的最大参考图数比较。若节点只声明了固定数量，用 `build_segments.py --max-refs N` 限制。

## 4. 文件与存储

- 参考图上传到服务器的 `input/dating_diary/<集名>/`。
- 视频输出到服务器 `output/dating_diary/<集名>/G{n}/`，脚本在任务完成后立刻下载到本地 `11_renders/`。
- 租用实例释放后服务器文件可能丢失，本地 `11_renders/` 才是正本；大文件放对象存储，不进 git。
