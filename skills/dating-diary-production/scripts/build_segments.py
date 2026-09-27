#!/usr/bin/env python3
"""Group the storyboard's shots into video-generation segments and route references.

Reads  09_handoff/preproduction_manifest.json   (from dating-diary-preproduction)
Writes 10_production/segments.json

Rules (deterministic, no model judgement):
  * a new segment starts whenever the layer changes (reality <-> fantasy);
  * a segment never exceeds --max-seconds of usable footage (default 10);
  * a shot lasts max(duration_hint, est_speech_seconds);
  * Duration sent to ComfyUI = usable seconds + --pad (default 0.5), at least --min-seconds (3);
  * reality segment references: its keyframes → character model sheets → reality anchor → props;
  * fantasy segment references: its keyframes → fantasy anchor → chibi sheets / Q style → props.
    Photoreal model sheets and the reality anchor are never attached to a fantasy segment.

  python3 build_segments.py <project_dir> [--max-seconds 10] [--pad 0.5] [--min-seconds 3] [--max-refs 9]

--max-refs caps the references per segment (default 9, what the MiniMax H3 node takes: ref_image_0…8);
the lowest-priority ones (props, then anchors, then sheets; keyframes last) are dropped first.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speech import lines_seconds  # noqa: E402

MANIFEST = "09_handoff/preproduction_manifest.json"
OUT = "10_production/segments.json"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def shot_seconds(sh):
    need = sh.get("est_speech_seconds")
    if need is None:
        need = lines_seconds(sh.get("dialogue_lines") or [])
    return round(max(float(sh.get("duration_hint") or 0), float(need or 0), 0.5), 2)


def index_assets(man, proj):
    """asset_id -> dict(path=..., kind=..., profile=...)"""
    idx = {}
    assets = man.get("assets", {})
    for c in assets.get("characters", []):
        prof = {}
        if c.get("profile") and os.path.exists(os.path.join(proj, c["profile"])):
            prof = load(os.path.join(proj, c["profile"]))
        idx[c["asset_id"]] = {"kind": "character", "path": c.get("model_sheet"), "profile": prof,
                              "chibi": c.get("chibi_sheet") or prof.get("chibi_sheet")}
    for kind in ("props", "styles", "scenes"):
        for x in assets.get(kind, []):
            idx[x["asset_id"]] = {"kind": kind[:-1], "path": x.get("reference") or x.get("path")}
    return idx


def character_block(aid, a, episode):
    p = a.get("profile") or {}
    wardrobe = p.get("wardrobe") or {}
    outfit = (wardrobe.get("episode_overrides") or {}).get(episode)
    base = wardrobe.get("default")
    return {
        "asset_id": aid,
        "display_name": p.get("display_name"),
        "role": p.get("role"),
        "appearance_block_en": p.get("appearance_block_en"),
        "identity_anchors": p.get("identity_anchors", []),
        "must_not_have": p.get("must_not_have", []),
        "wardrobe_en": ", ".join(x for x in (base, outfit) if x),
    }


def build(proj, max_s, pad, min_s, max_refs):
    man = load(os.path.join(proj, MANIFEST))
    if not man.get("handoff_ready"):
        print("WARNING: manifest is not marked handoff_ready; continuing anyway")
    idx = index_assets(man, proj)
    anchors = man.get("anchors", {})
    episode = man.get("episode") or man.get("project_id")
    warnings_global = []

    segs, cur = [], None
    for sh in man["shots"]:
        dur = shot_seconds(sh)
        layer = sh.get("layer", "reality")
        if cur is None or cur["layer"] != layer or cur["use_seconds"] + dur > max_s + 1e-6:
            cur = {"layer": layer, "shots": [], "use_seconds": 0.0}
            segs.append(cur)
        cur["shots"].append({
            "shot_id": sh["shot_id"],
            "start": round(cur["use_seconds"], 2),
            "seconds": dur,
            "keyframe": sh.get("keyframe"),
            "shot_type": sh.get("shot_type"),
            "camera": sh.get("camera"),
            "action": sh.get("action"),
            "emotion": sh.get("emotion"),
            "visual_goal": sh.get("visual_goal"),
            "dialogue_lines": sh.get("dialogue_lines") or [],
            "sound_hint": sh.get("sound_hint"),
            "characters": sh.get("characters") or [],
            "props": [r for r in (sh.get("reference_asset_ids") or []) if idx.get(r, {}).get("kind") == "prop"],
        })
        cur["use_seconds"] = round(cur["use_seconds"] + dur, 2)
        if dur > max_s:
            warnings_global.append(f"shot {sh['shot_id']} alone needs {dur}s (> {max_s}s); it gets its own over-long segment")

    out_segs, char_blocks = [], {}
    for i, s in enumerate(segs, 1):
        gid = f"G{i}"
        warn = []
        chars = []
        for sh in s["shots"]:
            for c in sh["characters"]:
                if c not in chars:
                    chars.append(c)
        pics = []

        def add(path, role, aid=None):
            if not path:
                return
            if any(p["path"] == path for p in pics):
                return
            if not os.path.exists(os.path.join(proj, path)):
                warn.append(f"missing file: {path}")
            pics.append({"n": len(pics) + 1, "path": path, "role": role, "asset_id": aid})

        for sh in s["shots"]:
            if sh["keyframe"]:
                add(sh["keyframe"], f"keyframe shot {sh['shot_id']}")
            else:
                warn.append(f"shot {sh['shot_id']} has no keyframe")
        if s["layer"] == "reality":
            for c in chars:
                a = idx.get(c)
                if not a:
                    warn.append(f"character {c} not in asset manifest")
                    continue
                add(a["path"], f"model sheet {c}", c)
            add(anchors.get("reality"), "reality anchor")
        else:
            add(anchors.get("fantasy"), "fantasy anchor")
            for c in chars:
                a = idx.get(c) or {}
                if a.get("chibi"):
                    add(a["chibi"], f"chibi sheet {c}", c)
            for aid, a in idx.items():
                if a["kind"] == "style":
                    add(a["path"], f"q style {aid}", aid)
        for sh in s["shots"]:
            for pr in sh["props"]:
                add(idx[pr]["path"], f"prop {pr}", pr)

        if max_refs and len(pics) > max_refs:
            dropped = pics[max_refs:]
            pics = pics[:max_refs]
            warn.append("dropped refs over --max-refs: " + ", ".join(p["role"] for p in dropped))

        for c in chars:
            if c in idx and c not in char_blocks:
                char_blocks[c] = character_block(c, idx[c], episode)

        use = s["use_seconds"]
        out_segs.append({
            "id": gid,
            "layer": s["layer"],
            "shot_ids": [sh["shot_id"] for sh in s["shots"]],
            "shots": s["shots"],
            "characters": chars,
            "use_seconds": use,
            "duration": round(max(use + pad, min_s), 1),
            "pictures": pics,
            "prompt_file": f"10_production/prompts/{gid}.json",
            "render_dir": f"11_renders/{gid}",
            "warnings": warn,
        })

    result = {
        "project_id": man.get("project_id"),
        "episode": episode,
        "aspect_ratio": man.get("aspect_ratio", "9:16"),
        "settings": {"max_seconds": max_s, "pad": pad, "min_seconds": min_s, "max_refs": max_refs},
        "total_use_seconds": round(sum(s["use_seconds"] for s in out_segs), 1),
        "character_blocks": char_blocks,
        "exceptions_from_preproduction": man.get("exceptions", []),
        "warnings": warnings_global,
        "segments": out_segs,
    }
    os.makedirs(os.path.join(proj, "10_production/prompts"), exist_ok=True)
    with open(os.path.join(proj, OUT), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    for s in out_segs:
        print(f"{s['id']:<4}{s['layer']:<9}shots {','.join(s['shot_ids']):<14} use {s['use_seconds']:>5.1f}s  "
              f"Duration {s['duration']:>4}s  refs {len(s['pictures'])}")
        for w in s["warnings"]:
            print(f"      ! {w}")
    for w in warnings_global:
        print(f"! {w}")
    print(f"\ntotal usable footage ≈ {result['total_use_seconds']}s → {OUT}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--max-seconds", type=float, default=10.0)
    ap.add_argument("--pad", type=float, default=0.5)
    ap.add_argument("--min-seconds", type=float, default=3.0)
    ap.add_argument("--max-refs", type=int, default=9, help="0 = no limit")
    a = ap.parse_args()
    build(a.project, a.max_seconds, a.pad, a.min_seconds, a.max_refs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
