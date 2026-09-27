#!/usr/bin/env python3
"""End-to-end test of the production scripts against the mock ComfyUI server.

Builds a throwaway episode with placeholder images, then runs:
build_segments → (templated prompts) → validate_video_prompts → comfy_run run
→ pick_takes → assemble, and checks the outputs. Needs python3 + ffmpeg.

  python3 tests/e2e_test.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = os.path.join(ROOT, "skills/dating-diary-production/scripts")
PRE = os.path.join(ROOT, "skills/dating-diary-preproduction/scripts")


def sh(*args, ok=(0,)):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-800:], sep="")
    assert r.returncode in ok, f"{args[0]} exited {r.returncode}"
    return r.stdout


def png(path, color):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=540x960", "-frames:v", "1", path], check=True)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def main():
    tmp = tempfile.mkdtemp(prefix="dd_e2e_")
    P = os.path.join(tmp, "ep_test")
    shots = [("01", "reality", ["F", "M"], 1.3, []),
             ("02", "reality", ["F", "M"], 1.2, [("F", "你这个外套……角度系得挺好的。"), ("M", "啊？随便系的。")]),
             ("03", "fantasy", ["M"], 2.3, []),
             ("04", "reality", ["F"], 1.5, [("F", "哦。")])]
    colors = ["red", "green", "blue", "yellow"]
    for (sid, *_), c in zip(shots, colors):
        png(f"{P}/07_keyframes/shot_{sid}.png", c)
    for a in ("F", "M"):
        png(f"{P}/assets/characters/{a}/model_sheet.png", "gray")
        json.dump({"asset_id": a, "appearance_block_en": "x", "identity_anchors": [], "must_not_have": ["glasses"] if a == "M" else []},
                  open(f"{P}/assets/characters/{a}/profile.json", "w"))
    png(f"{P}/06_anchors/reality_anchor.png", "white")
    png(f"{P}/06_anchors/fantasy_anchor.png", "pink")
    man = {"project_id": "ep_test", "handoff_ready": True,
           "assets": {"characters": [{"asset_id": a, "model_sheet": f"assets/characters/{a}/model_sheet.png",
                                      "profile": f"assets/characters/{a}/profile.json"} for a in ("F", "M")]},
           "anchors": {"reality": "06_anchors/reality_anchor.png", "fantasy": "06_anchors/fantasy_anchor.png"},
           "shots": [{"shot_id": s, "layer": l, "characters": c, "duration_hint": d, "keyframe": f"07_keyframes/shot_{s}.png",
                      "dialogue_lines": [{"speaker": sp, "text": t} for sp, t in dl]} for s, l, c, d, dl in shots]}
    os.makedirs(f"{P}/09_handoff")
    json.dump(man, open(f"{P}/09_handoff/preproduction_manifest.json", "w"), ensure_ascii=False)

    # 1. segmentation: reality(01,02) | fantasy(03) | reality(04); fantasy never gets photoreal sheets
    sh(f"{PROD}/build_segments.py", P)
    segs = json.load(open(f"{P}/10_production/segments.json"))["segments"]
    assert [s["shot_ids"] for s in segs] == [["01", "02"], ["03"], ["04"]]
    assert not any("model sheet" in p["role"] or p["role"] == "reality anchor" for p in segs[1]["pictures"])
    assert segs[0]["use_seconds"] >= 1.3 + 4.0, "shot 02 must be stretched to fit its dialogue"
    assert segs[1]["duration"] == 3.0

    # 2. prompts (templated stand-in for what the agent writes) + validation
    for s in segs:
        body = []
        for i, shot in enumerate(s["shots"]):
            ts = "" if i == 0 else f"At 00:{int(shot['start']):02d}.{round(shot['start'] % 1 * 1000):03d}, "
            d = " ".join(f"<d>[Chinese] {l['text']}</d>" for l in shot["dialogue_lines"])
            body.append(f"[Shot {i + 1}] {ts}{d}")
        refs = " ".join(f"<Picture {p['n']}>" for p in s["pictures"])
        json.dump({"subject_definitions": [f"<Subject 1> in {refs}"], "summary": "[reference generation] test",
                   "retention_analysis": [], "overall_soundscape": "", "non_diegetic_music": "N/A",
                   "detailed_description": "Vertical 9:16 framing. No on-screen text or subtitles. " + " ".join(body)},
                  open(f"{P}/{s['prompt_file']}", "w"), ensure_ascii=False)
    sh(f"{PROD}/validate_video_prompts.py", P)

    # 3. render on the mock server (resume path: submit part, then run)
    port = free_port()
    srv = subprocess.Popen([sys.executable, f"{ROOT}/tests/mock_comfy.py", "--port", str(port), "--dir", f"{tmp}/server"])
    time.sleep(1)
    try:
        cfgd = f"{tmp}/cfg"
        os.makedirs(f"{cfgd}/workflows")
        shutil.copy(f"{ROOT}/tests/fixture_workflow_api.json", f"{cfgd}/workflows/minimax_h3_api.json")
        cfg = json.load(open(f"{ROOT}/skills/dating-diary-production/comfy.config.example.json"))
        cfg.update(base_url=f"http://127.0.0.1:{port}", nodes={}, poll_seconds=1, takes_per_segment=2)
        json.dump(cfg, open(f"{cfgd}/comfy.json", "w"))
        sh(f"{PROD}/comfy_run.py", "check", P, "--config", f"{cfgd}/comfy.json")
        sh(f"{PROD}/comfy_run.py", "submit", P, "--config", f"{cfgd}/comfy.json", "--only", "G1")
        sh(f"{PROD}/comfy_run.py", "run", P, "--config", f"{cfgd}/comfy.json")
        st = json.load(open(f"{P}/10_production/production_state.json"))
        assert len(st["jobs"]) == 6 and all(j["status"] == "done" and j["files"] for j in st["jobs"])
        assert len(set(st["uploads"].values())) == len(st["uploads"]), "remote upload names must be unique"
    finally:
        srv.terminate()

    # 4. pick + rough cut
    sh(f"{PROD}/pick_takes.py", P)
    sh(f"{PROD}/assemble.py", P)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                f"{P}/12_rough_cut/rough_cut.mp4"], capture_output=True, text=True).stdout)
    expect = sum(s["use_seconds"] for s in segs)
    assert abs(dur - expect) < 0.3, (dur, expect)

    # 5. preproduction helpers
    json.dump({"shots": man["shots"]}, open(f"{tmp}/shots.json", "w"), ensure_ascii=False)
    sh(f"{PRE}/check_dialogue_timing.py", f"{tmp}/shots.json", ok=(1,))   # shot 02 is too short on purpose
    os.makedirs(f"{P}/03_storyboard", exist_ok=True)
    shutil.copy(f"{tmp}/shots.json", f"{P}/03_storyboard/shots.json")
    sh(f"{PRE}/keyframe_state.py", "init", P, "--force")
    for _ in range(3):
        sh(f"{PRE}/keyframe_state.py", "record", P, "--shot", "01", "--file", "07_keyframes/shot_01.png", "--status", "FAIL", "--issues", "x")
    ks = json.load(open(f"{P}/07_keyframes/keyframe_state.json"))
    assert ks["shots"]["01"]["status"] == "exception"

    print(f"\nALL OK  (rough cut {dur:.1f}s, workdir {tmp})")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
