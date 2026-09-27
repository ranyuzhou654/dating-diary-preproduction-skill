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
  "duration_hint": 1.2,
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

- `duration_hint` 只是叙事节奏参考，不是视频生成参数。
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
    "issues": [
      "男主眼镜消失",
      "发型明显变短"
    ],
    "regeneration_instruction": "严格恢复参考图中的细框圆形金属眼镜，并恢复原本黑色蓬松短发。除此之外不要改变构图、场景、灯光和人物动作。"
  }
}
```

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
      "qc_status": "PASS"
    }
  ]
}
```

这里不包含任何视频生成字段。
