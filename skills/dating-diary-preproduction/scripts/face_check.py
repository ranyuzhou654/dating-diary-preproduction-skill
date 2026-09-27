#!/usr/bin/env python3
"""Objective identity check for photoreal keyframes.

Compares every face found in a keyframe against the faces on one or more character
model sheets (a model sheet usually contains many views of the same person; all of
them are used). For each reference, the best cosine similarity found in the keyframe
is reported. A reference whose best match is below the threshold fails the check.

  python3 face_check.py --image 07_keyframes/shot_03_try1.png \
      --ref assets/characters/male_date_002/model_sheet.png \
      --ref assets/characters/female_lin_yuan_v01/model_sheet.png \
      [--threshold 0.45] [--json]

Not meaningful for 3D chibi frames: skip those.
Needs: pip install insightface onnxruntime opencv-python-headless
Exit code: 0 = pass, 1 = fail, 3 = dependency missing, 4 = no face found in keyframe.
"""
import argparse
import json
import os
import sys


def load_app():
    try:
        import cv2  # noqa: F401
        from insightface.app import FaceAnalysis
    except ImportError:
        print("face_check needs: pip install insightface onnxruntime opencv-python-headless", file=sys.stderr)
        sys.exit(3)
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


def embeddings(app, path):
    import cv2
    import numpy as np
    img = cv2.imread(path)
    if img is None:
        sys.exit(f"cannot read image {path}")
    faces = app.get(img)
    embs = []
    for f in faces:
        e = f.normed_embedding if getattr(f, "normed_embedding", None) is not None else f.embedding / np.linalg.norm(f.embedding)
        embs.append(e)
    return embs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--ref", action="append", required=True, help="model sheet of a character that must appear; repeatable")
    ap.add_argument("--threshold", type=float, default=0.45)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    app = load_app()
    import numpy as np
    shot = embeddings(app, a.image)
    if not shot:
        out = {"image": a.image, "status": "FAIL", "reason": "no face detected in keyframe", "results": {}}
        print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else out["reason"])
        return 4
    results, ok = {}, True
    for ref in a.ref:
        refs = embeddings(app, ref)
        if not refs:
            results[os.path.basename(ref)] = {"similarity": None, "pass": False, "note": "no face found on reference sheet"}
            ok = False
            continue
        best = max(float(np.dot(s, r)) for s in shot for r in refs)
        passed = best >= a.threshold
        ok &= passed
        results[os.path.basename(ref)] = {"similarity": round(best, 3), "pass": passed}
    out = {"image": a.image, "threshold": a.threshold, "status": "PASS" if ok else "FAIL", "faces_in_keyframe": len(shot), "results": results}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for k, v in results.items():
            print(f"{k}: {v['similarity']} {'OK' if v['pass'] else 'BELOW THRESHOLD'}")
        print(out["status"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
