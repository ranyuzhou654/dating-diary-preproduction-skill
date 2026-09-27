# Structured Schemas

## 1. Project State

```json
{
  "project_id": "dating_A_001",
  "working_title": "朋友非让我下的",
  "format": "A_slice",
  "source_type": "real_story",
  "current_stage": "storyboard",
  "approved_items": {
    "adaptation_direction": true,
    "script": true,
    "reality_anchor": false,
    "fantasy_anchor": false
  }
}
```

---

## 2. Asset Manifest

```json
{
  "asset_id": "female_lin_yuan_v01",
  "type": "character",
  "role": "female_lead",
  "usage": [
    "identity",
    "face",
    "hair",
    "body_proportion"
  ],
  "do_not_use_for": [
    "scene",
    "lighting"
  ],
  "status": "approved"
}
```

### 角色 profile.json

每个角色目录必须有 `profile.json`。身份特征只在这里定义，所有 prompt 和 QC 都从这里读取，不在模板里写死。

```json
{
  "asset_id": "male_date_002",
  "role": "male_date",
  "display_name": "沈越",
  "age": "mid-20s",
  "appearance_block_en": "a tall, lean-athletic man in his mid-20s, about 183 cm, soft layered black hair with a messy fringe, dark eyes, clean-shaven",
  "appearance_block_zh": "25岁左右，身高183cm，精瘦运动型，黑色层次短发，刘海略乱",
  "identity_anchors": [
    "soft layered black hair with a messy fringe",
    "lean athletic build, defined shoulders and arms"
  ],
  "must_not_have": [
    "glasses",
    "beard or stubble"
  ],
  "wardrobe": {
    "default": "fitted plain black crew-neck T-shirt, black trousers, black sneakers, black watch",
    "episode_overrides": {
      "ep02": "plus a heather-gray university sweatshirt tied around the waist, STANFORD in dark-red block letters on the back"
    }
  },
  "chibi_asset_id": "male_date_002_chibi",
  "voice_ref": "voice/male_date_002.wav"
}
```

- `identity_anchors`：必须出现、QC 逐条核对。
- `must_not_have`：必须不出现。例如不戴眼镜的角色要写 `glasses`，防止模型从别的角色或模板里带入。
- `appearance_block_en`：视频阶段直接复用这段英文描述，不让模型临场改写。

推荐目录：

```
assets/

characters/
    female_lin_yuan_v01/
        model_sheet.png
        closeup.png
        fullbody.png
        profile.json

    male_date_001/
        model_sheet.png
        closeup.png
        fullbody.png
        profile.json

scenes/
    shanghai_bistro_v01/
        anchor.png
        empty_scene.png
        scene.json

styles/
    q_chibi_v01/
        style_reference.png
        style.json

props/
    special_prop_v01/
        reference.png
        prop.json
```

---

## 3. Shot Schema

```json
{
  "shot_id": "03",
  "layer": "reality",
  "duration_hint": 3.8,
  "characters": [
    "male_date_001"
  ],
  "scene_id": "shanghai_bistro_v01",
  "shot_type": "medium_close_up",
  "camera": {
    "angle": "eye_level",
    "lens": "85mm"
  },
  "action": "男主略微前倾，自然讲话",
  "dialogue": "我其实平时不太用 dating app，是朋友非让我下的。",
  "dialogue_lines": [
    {"speaker": "male_date_001", "text": "我其实平时不太用 dating app，是朋友非让我下的。", "lang": "zh"}
  ],
  "est_speech_seconds": 3.6,
  "sound_hint": "餐厅低声交谈、杯具轻响",
  "emotion": [
    "natural",
    "polite",
    "slightly_socially_skilled"
  ],
  "visual_goal": "让观众觉得他挺正常",
  "transition": "cut",
  "reference_asset_ids": [
    "male_date_001",
    "reality_anchor_001"
  ],
  "image_prompt": "",
  "status": "pending"
}
```

注意：

- `duration_hint` 是叙事节奏参考，不是视频生成参数；但它**不得小于** `est_speech_seconds`（由 `scripts/check_dialogue_timing.py` 计算）。下游视频阶段会用它来分段。
- `dialogue_lines` 是结构化台词，下游视频阶段直接用于生成 `<d>` 对白标签；`dialogue` 保留为人读字段。
- 不写 camera movement 的执行强度。
- 不写 motion scale、lip-sync、seed、video model 参数。

---

## 4. Anchor Schema

```json
{
  "anchor_id": "reality_anchor_001",
  "type": "reality",
  "scene_id": "shanghai_bistro_v01",
  "characters": [
    "female_lin_yuan_v01",
    "male_date_001"
  ],
  "reference_asset_ids": [
    "female_lin_yuan_v01",
    "male_date_001",
    "shanghai_bistro_v01"
  ],
  "anchor_prompt": "",
  "status": "awaiting_approval"
}
```

---

## 5. QC Schema

```json
{
  "shot_id": "05",
  "qc": {
    "status": "FAIL",
    "character_consistency": 62,
    "scene_consistency": 94,
    "shot_compliance": 82,
    "generation_quality": 86,
    "face_similarity": {"male_date_002": 0.31},
    "attempt": 1,
    "issues": [
      "男主发型明显变短（identity_anchors: soft layered black hair）",
      "男主出现了眼镜（must_not_have: glasses）"
    ],
    "regeneration_instruction": "严格恢复参考图中的黑色层次短发和略乱的刘海；男主不戴眼镜。除此之外不要改变构图、场景、灯光和人物动作。"
  }
}
```

---

## 5.5 Keyframe State

`07_keyframes/keyframe_state.json`，由 `scripts/keyframe_state.py` 维护，**不要手动编辑**。

```json
{
  "project_id": "dating_A_001",
  "max_attempts": 3,
  "shots": {
    "04": {
      "status": "fail",
      "attempts": [
        {"n": 1, "file": "07_keyframes/shot_04_try1.png", "qc": "FAIL",
         "issues": ["男主出现了眼镜"], "instruction": "男主不戴眼镜……"}
      ]
    }
  }
}
```

status 取值：`pending` → `fail`（可重跑）→ `pass` / `exception`（达到上限）。

---

## 6. Preproduction Manifest

```json
{
  "project_id": "dating_A_001",
  "title": "朋友非让我下的",
  "aspect_ratio": "9:16",
  "stage": "preproduction_complete",
  "handoff_ready": true,
  "assets": {
    "characters": [],
    "scenes": [],
    "styles": [],
    "props": []
  },
  "anchors": {
    "reality": "06_anchors/reality_anchor.png",
    "fantasy": "06_anchors/fantasy_anchor.png"
  },
  "shots": [
    {
      "shot_id": "01",
      "keyframe": "07_keyframes/shot_01.png",
      "layer": "reality",
      "reference_asset_ids": [],
      "image_prompt_file": "05_prompts/shot_01.txt",
      "qc_status": "PASS",
      "characters": ["female_lin_yuan_v01", "male_date_002"],
      "scene_id": "shanghai_bistro_v01",
      "shot_type": "medium_two_shot",
      "action": "男主走近并转身拉椅子",
      "emotion": ["natural"],
      "visual_goal": "第一秒交代人物标签",
      "dialogue_lines": [],
      "duration_hint": 1.3,
      "est_speech_seconds": 0,
      "sound_hint": "餐厅环境音、椅子轻响"
    }
  ],
  "exceptions": []
}
```

`assets.characters` 中每项给出 `asset_id`、`model_sheet` 路径和 `profile` 路径；有 Q版角色图时再给 `chibi_sheet`。`assets.props` 每项给出 `asset_id` 和 `reference`。

这里不包含任何视频生成参数（分辨率、帧数、种子、模型设置）。上面的叙事字段是给下游分段和写视频提示词用的。
