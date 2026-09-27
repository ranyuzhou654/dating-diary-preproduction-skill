# MiniMax H3 参考转视频提示词规范

一段（segment）对应一个 JSON 文件，整份 JSON 原样作为提示词文本发给 ComfyUI 的提示词节点。

## 结构

```json
{
  "subject_definitions": [
    "<Subject 1> is the young man in <Picture 5>, seen in the scene in <Picture 1> and <Picture 3>, <appearance_block_en>, no glasses, wearing <wardrobe_en>.",
    "<Subject 2> is the young woman in <Picture 4>, seen at the table in <Picture 2>, <appearance_block_en>, wearing <wardrobe_en>.",
    "<Subject 3> is the restaurant environment in <Picture 6>, <scene description from the anchor>."
  ],
  "summary": "[reference generation] <一句话：场景、竖屏 9:16、本段 N 秒、这段的喜剧机制>",
  "retention_analysis": [
    "<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - The man's identity is maintained with <identity_anchors> as defined in <Picture 5>."
  ],
  "detailed_description": "<总体风格>. Vertical 9:16 framing. No on-screen text or subtitles. [Shot 1] ... [Shot 2] At 00:01.300, cut to ... <d>[Chinese] 台词</d> ...",
  "overall_soundscape": "<环境声与动作声>",
  "non_diegetic_music": "N/A"
}
```

## 规则

1. **Subject**：每个出场人物一个 Subject，场景一个 Subject。人物的主参考图是角色设定图（现实段）或 Q版角色图（Q版段），关键帧作为“seen in”补充。
2. **外貌描述不临场发挥**：直接用 `character_blocks` 的 `appearance_block_en` 和 `wardrobe_en`。`must_not_have` 写成否定（"no glasses"、"clean-shaven, no stubble"）。
3. **Picture 编号**：与 `segments.json` 中该段 `pictures[].n` 一致；每张图至少被引用一次。工作流的参考图槽位比本段图片多时，多出的槽位会被填成白色空图，提示词里**不要**提到这些编号。
4. **[Shot k]**：按本段镜头顺序编号。第 1 镜不写时间戳，之后每镜写 `At 00:0x.xxx`，取自该镜的 `start`。相邻两镜是同一景别的连续表演时，可以合并成一个 [Shot]，但时间戳必须递增。
5. **每个 [Shot] 写清**：景别与机位、构图参照哪张图（matching <Picture n>）、人物动作、表情、说话方式、镜头运动。
6. **台词**：逐字照抄 `dialogue_lines`。中文 `<d>[Chinese] …</d>`，英文 `<d>[English] …</d>`，中英混说的一句按中文标。说话前写清是谁、怎么说（"says plainly"、"murmurs"）。
7. **没有负向提示词**：分镜和 series bible 里的“不要”全部改成正向句：
   - 不看镜头 → "She never looks at the camera."
   - 不翻白眼 → "no eye-roll"
   - 不定格炫耀 → "naturally, without any freeze or emphasis"
   - 不血腥 / 不丑化 → "cartoonish and adorable, never violent or mocking"
8. **固定句**：`detailed_description` 必须含 "Vertical 9:16 framing. No on-screen text or subtitles."；字幕全部后期加。
9. **音乐**：`non_diegetic_music` 固定 "N/A"，配乐后期统一铺。
10. **现实层风格句**（可按场景调整光线）：
    "Realistic urban TV-drama look with natural skin texture, shallow depth of field, warm interior practical light against cool ambient light from the window, and subtle film grain." 并写明人物左右站位，例如 "The man is always on the left side of the table and the woman on the right."
11. **Q版层风格句**：
    "Polished 3D chibi animation style with big heads and small bodies, glossy stylized materials, rich saturated color and snappy, exaggerated comedic timing."
    Q版群像（投资人、同学、路人）写成 "invented cartoon characters"，不得像真实人物；不写真实公司或品牌名。
12. **summary 的时长**写本段 Duration，不写整集时长。

## 示例（现实段，两镜）

```json
{
  "subject_definitions": [
    "<Subject 1> is the young man in <Picture 4>, seen in the scene in <Picture 1>, a tall, lean-athletic man in his mid-20s, about 183 cm, soft layered black hair with a messy fringe, dark eyes, clean-shaven, no glasses, wearing a fitted plain black crew-neck T-shirt, black trousers and black sneakers, plus a heather-gray university sweatshirt tied around the waist with STANFORD in dark-red block letters on the back.",
    "<Subject 2> is the young woman in <Picture 3>, seen at the table in <Picture 2>, 27, slim, long loose slightly messy black hair, a small face with clean, cool features and real skin texture, light makeup, wearing a black spaghetti-strap slip dress.",
    "<Subject 3> is the restaurant environment in <Picture 5>, an upscale high-rise restaurant in Shanghai at night with floor-to-ceiling windows over the Lujiazui skyline, dark marble tables and small brass table lamps."
  ],
  "summary": "[reference generation] A realistic, understated first-date moment in a Shanghai restaurant, vertical 9:16, 6 seconds: he arrives with a university sweatshirt tied around his waist that happens to face her perfectly, she teases him lightly, and he answers with unguarded sincerity.",
  "retention_analysis": [
    "<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - Maintained with his soft layered black hair, lean athletic build and the STANFORD sweatshirt as defined in <Picture 4>.",
    "<Subject 2> (appears in [Shot 2]): fully_preserved - Maintained with her long messy black hair and black slip dress as defined in <Picture 3>.",
    "<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - The skyline window, marble tables and brass lamps as defined in <Picture 5>."
  ],
  "detailed_description": "Realistic urban TV-drama look with natural skin texture, shallow depth of field, warm interior practical light against cool ambient light from the window, and subtle film grain. Vertical 9:16 framing. No on-screen text or subtitles. The man is always on the left side of the table and the woman on the right. [Shot 1] A medium shot from near the woman's seat, matching <Picture 1>. <Subject 1> (S1) walks up and turns to pull out his chair; the sweatshirt around his waist swings and its back faces the camera, STANFORD fully readable, naturally, without any emphasis. He never looks at the camera. [Shot 2] At 00:01.300, cut to a medium close-up of <Subject 2> (S2), matching <Picture 2>. Her eyes flick to his waist and back; a small amused smile, friendly rather than mocking, <d>[Chinese] 你这个外套……角度系得挺好的。</d> S1, off-screen, answers plainly, <d>[Chinese] 啊？随便系的。</d>",
  "overall_soundscape": "Low murmur of an upscale restaurant, soft clinking of glasses, the light scrape of a chair.",
  "non_diegetic_music": "N/A"
}
```
