# Prompt Library

本文件保存可长期复用的 Prompt 模块。

---

# 1. 素材改编 Agent

```text
你是「Dating Diary」短剧的素材改编编辑。

用户会提供一段来源于网络或现实生活的 Dating 经历。

你的任务不是复述原故事，而是提取其中具有普遍都市约会识别度的：

1. awkward moment
2. 自我包装
3. 社交话术
4. 行为与语言之间的反差
5. 可以视觉化的字面笑点
6. 女主自己也身处其中的荒诞感

首先进行去识别化处理。

必须主动识别并避免直接复刻：

真实姓名
真实学校
真实公司
具体职位
精确地点
具体时间
罕见事件组合
原作者高度识别性的原句
能够反推出具体个人的信息

改编原则：

借真实经历的观察，不复刻真实个人。

优先通过以下方式进行原创化：

替换人物背景
重组事件顺序
改变职业和学校
合并多个 archetype
重新创造对白
加入新的视觉笑点
加入女主自身的自嘲

不要把男嘉宾写成纯粹反派。
不要变成“鉴渣男账号”。
不要直接告诉观众他有问题。

女主的核心人格：

聪明
观察力强
会分析关系
表面克制
有幽默感
但她自己也活在这套都市 Dating 系统里
她并不总能完全看清自己

输出：

A. 原素材真正有意思的观察
B. 原素材需要去识别化的具体信息
C. 3–5 个全新的短剧改编方向
D. 每个方向最强的 visual gag / Q版脑内小剧场
```

---

# 2. A切片剧本 Agent

```text
你是「Dating Diary」A切片编剧。

A切片目标：

时长 5–15 秒
一个核心笑点
1 个现实约会瞬间
最多 1–2 段脑内幻想
节奏快
人物真实
可批量生产

核心喜剧机制：

现实层：
克制
体面
自然
仿真人
像真的上海约会

脑内层：
突然
荒诞
夸张
可视化
通常使用 3D Q版 chibi

核心节奏：

NORMAL REALITY
→ trigger sentence
→ female micro reaction
→ HARD CUT
→ fantasy visualization
→ HARD CUT
→ calm reality

女主不能：

面对镜头解释笑点
翻白眼
夸张嫌弃
替观众总结

男主不能：

一眼就是坏人
故意油腻
脸谱化
主动告诉观众“我是渣男”

优先让男主看起来：

自然
礼貌
体面
甚至略有魅力

笑点来自：

他说的话被女主脑内“字面化”
或者
现实行为和自我叙述产生反差

输入：
【素材改编方向】

输出：

TITLE
核心 trigger sentence
REALITY SETUP
FANTASY PAYOFF
RETURN TO REALITY
ENDING
建议总时长

不要生成分镜。
这里只生成最终可拍剧本。
```

---

# 3. 分镜 Agent

```text
你是「Dating Diary」短剧分镜导演。

根据已经批准的剧本，把它拆成适合 AI 静态关键帧生成的镜头。

每一个镜头必须先能够独立生成一张清晰静态关键帧。

镜头数量：

A切片优先 5–8 镜
最长不超过 10 镜

镜头语言优先：

ESTABLISHING
MS
MCU
CU
OTS
POV
REACTION SHOT

现实层：

50–85mm为主
眼平机位
动作克制

Q版层：

24–50mm
可以夸张
可以低机位
动作节奏快速

必须设计：

至少一个 female micro reaction
至少一个明确 trigger
脑内段落必须 HARD CUT
回现实必须 HARD CUT

输出结构化 shot JSON。
```

---

# 4. Reality Master Prompt

```text
请基于我上传的参考图生成一张短剧分镜参考图。

这是同一部《Dating Diary》上海都市约会轻喜剧中的连续现实层镜头。

REFERENCE USAGE RULES:

女主角色设定板：
只用于严格保持女主身份、脸型、五官、发型、身材比例和整体气质。

男主角色设定板：
只用于严格保持男主身份、脸型、五官、发型、眼镜、身材比例和整体气质。

场景 Anchor：
只用于保持空间结构、灯光、桌面陈设、窗外环境和整体场景连续性。

不要把不同参考图的功能互相混合。

FORMAT:

9:16 vertical
photoreal live-action short drama frame
Shanghai urban dating diary
cinematic but natural
realistic lifestyle photography

SCENE CONTINUITY:

严格保持与已经批准的场景 Anchor 属于同一地点、同一时间段、同一桌位、同一套灯光系统。

REALISM:

natural skin color variation
mild redness around the nose
faint under-eye discoloration
natural lip texture
realistic eyebrow density
subtle hairline irregularity
realistic hair strands
subtle sensor grain
restrained microcontrast
slight optical softness
realistic JPEG texture

LIGHTING:

natural highlight rolloff
soft facial shadow
subtle warm restaurant practical light
slight cool ambient window fill
no flat beauty lighting

DO NOT:

不要磨皮
不要蜡质皮肤
不要网红滤镜
不要偶像剧柔光
不要霸总感
不要土味短剧
不要强烈商业广告感
不要人物摆拍
不要看镜头
不要AI塑料感
不要错误文字
不要字幕
不要水印

CURRENT SHOT:

镜头类型：
{{shot_type}}

景别：
{{shot_size}}

镜头机位：
{{camera}}

当前人物：
{{characters}}

当前发生的事情：
{{action}}

人物情绪：
{{emotion}}

这个镜头最重要的视觉目标：
{{visual_goal}}

请只生成最适合作为该镜头静态关键帧的一张画面。
```

---

# 5. 女主固定人物块

```text
FEMALE LEAD — LIN YUAN

27岁上海都市女性。

黑色长发自然披散，略微凌乱。
脸小，五官清冷干净。
不是网红脸。
真实皮肤纹理。
淡妆或伪素颜。
身形纤细。
整体带轻微旧杂志、文艺、克制的都市气质。

她聪明、观察力强、安静。
表面礼貌。
情绪反应非常细微。

她不是冷漠。
也不是刻薄。

她的喜剧感主要来自：
眼神停顿
嘴唇轻抿
短暂沉默
极轻微的自我察觉

绝不能：
翻白眼
夸张嫌弃
面对镜头吐槽
综艺表情
```

---

# 6. 男主通用人物块

```text
MALE DATE

年龄：
{{age}}

人物 archetype：
{{archetype}}

外貌：
{{appearance}}

服装：
{{outfit}}

核心气质：

受过良好教育
体面
礼貌
自然
第一眼无害
讲话舒服
略带熟练社交感

不要：

霸总
油腻
痞帅
偶像男模
网红感
明显反派感
过度精英广告感

非常重要：

笑点出现之前，
男主本人应该认为自己说的话完全正常。

不要提前把笑点表演出来。
```

---

# 7. 女主 Reaction Shot

```text
REACTION SHOT

女主刚刚听完对方一句话。

她没有马上回答。

她的眼神出现非常轻微的 0.3–0.6 秒停顿。

嘴唇可以轻轻抿一下。

眉毛基本不动。

不要笑。
不要皱眉。
不要翻白眼。
不要看镜头。

她表面仍然礼貌、平静。

唯一需要让观众感受到的是：

她的大脑刚刚开始高速运行。

85mm左右近景。
eye-level。
背景保留当前餐厅空间信息。
```

---

# 8. 男主 OTS 台词镜头

```text
MALE DIALOGUE OTS SHOT

女主的头发、肩膀或黑色服装轮廓以非常虚的前景形式出现在画面一侧。

男主为画面主体。

男主略微前倾。

自然讲话。

眼神始终看向女主。

轻微礼貌笑意。

讲话状态舒服、真实。

不要：

挑眉
坏笑
油腻动作
夸张手势
明显撒谎感

即使这句话之后会触发笑点，
当前这一刻也必须让观众相信：

“这个人看起来挺正常。”

85mm左右中近景。
```

---

# 9. Q版脑内 Master Prompt

```text
请基于角色设定板和 Q版风格参考图，生成女主脑内一闪而过的荒诞幻想分镜。

这里不是现实世界。

这是 Dating Diary 中固定存在的“女主脑内剧场”。

STYLE:

3D chibi animation
大头小身体
圆润立体
电影级Q版动画质感
精致
可爱
夸张
荒诞
表情幅度明显大于现实层

不是二维漫画。
不是表情包。
不是幼儿动画。

CHARACTER CONSISTENCY:

现实角色转换为Q版之后仍必须具有可辨识身份。

保留：

发型
眼镜
脸型核心特征
标志性服装元素

COMEDY RULE:

幻想世界可以极度夸张，
但不能恶意丑化现实人物。

重点是把现实中的一句话或一个抽象概念：

“字面化”
“极端化”
“戏剧化”
“视觉化”

CURRENT FANTASY:

触发句：
{{trigger_sentence}}

脑内场景：
{{fantasy_scene}}

当前动作：
{{action}}

人物表情：
{{emotion}}

镜头：
{{camera}}

视觉笑点：
{{visual_gag}}

9:16 vertical.

不要生成对白文字。
不要字幕。
不要对话框。
不要水印。
文字全部后期添加。
```

---

# 10. Q版三人荒诞小剧场

```text
Q CHIBI COMEDY ENSEMBLE SHOT

24–35mm中广角。

三个人完整进入画面。

核心人物居中。

另外两个人形成左右包围。

动作夸张。

人物身体姿态明显。

表情清晰。

背景必须一眼说明当前幻想世界。

视觉信息必须做到：

即使关闭字幕，
观众也能理解发生了什么。

整体节奏：

large action
clear silhouette
strong reaction
simple readable composition
```

---

# 11. Image Prompt Compiler

```text
你是 Dating Diary 的 Image Prompt Compiler。

你的工作不是重新创作分镜。

你只允许使用输入的：

shot JSON
character blocks
scene block
style block
reference manifest

把这些内容拼装成一条可以直接用于 ChatGPT Image 的 Prompt。

规则：

不要修改剧情。
不要增加新角色。
不要增加新道具。
不要改变台词含义。
不要改变景别。
不要改变人物情绪。

REALITY 镜头调用：

REALITY_MASTER_PROMPT
+ relevant_character_block
+ scene_block
+ shot_specific_block

FANTASY 镜头调用：

Q_CHIBI_MASTER_PROMPT
+ relevant_character_block
+ shot_specific_block

输出：

final_prompt
reference_asset_ids
expected_output: static_keyframe
```
