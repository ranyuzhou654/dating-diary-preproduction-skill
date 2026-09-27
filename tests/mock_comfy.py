#!/usr/bin/env python3
"""A tiny fake ComfyUI server for testing comfy_run.py without a GPU.

Serves both backends on one port:

  bare ComfyUI   /system_stats, /object_info/<cls>, /upload/image, /prompt, /history/<id>,
                 /view, /queue, /free
  zealman panel  /api/health, /api/gpu/info, /api/gpu/profile, /api/comfy/status, /api/comfy/start,
                 /api/comfy/plugin-availability, /api/comfy/queue-status, /api/comfy/proxy/free,
                 /api/comfy/upload/file, /api/workflow/list, /api/workflow/config/<id>,
                 /api/workflow/save, /api/workflow/generate, /api/workflow/result, /output/...

Each job "renders" a video with ffmpeg: the first reference image held still for the requested
Duration, with a tone as audio. Every submitted workflow is checked the way ComfyUI would be
hard to debug for: reference inputs must be ref_images.ref_image_0..N-1 with no gaps (N <= 9), every
LoadImage must point at an uploaded file, and no other input may be lost. /mock/stats reports
what happened (for assertions).

  python3 tests/mock_comfy.py --port 8189 --dir /tmp/mock_comfy --workflows <dir of saved cards>
"""
import argparse
import json
import os
import re
import subprocess
import threading
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

STATE = {"history": {}, "running": 0, "pending": 0, "max_in_flight": 0, "frees": 0, "jobs": [],
         "comfy_running": True, "starts": [], "saved": []}
MAX_REF_SLOTS = 9
LOCK = threading.Lock()
ROOT = "/tmp/mock_comfy"
WORKFLOWS = None
REF_RE = re.compile(r"^(?P<pre>.*ref_image_)(?P<i>\d+)$")


def validate(wf):
    """Return an error string, or None."""
    for nid, node in wf.items():
        for k, v in node.get("inputs", {}).items():
            if isinstance(v, list) and v and v[0] not in wf:
                return f"#{nid} input {k} links to missing node {v[0]}"
    cond = next((n for n in wf.values() if n.get("class_type") == "MiniMaxH3ReferenceToVideo"), None)
    if cond is None:
        return "no MiniMaxH3ReferenceToVideo node"
    ins = cond["inputs"]
    if "ref_image_size" not in ins:
        return "ref_image_size input was lost"
    slots = sorted((int(m.group("i")), m.group("pre")) for k in ins if (m := REF_RE.match(k)))
    if not slots or [i for i, _ in slots] != list(range(len(slots))) or {p for _, p in slots} != {"ref_images.ref_image_"}:
        return f"bad reference inputs: {sorted(k for k in ins if 'ref_image' in k)}"
    if len(slots) > MAX_REF_SLOTS:
        return f"{len(slots)} reference inputs; the node takes at most {MAX_REF_SLOTS}"
    for n in wf.values():
        if n.get("class_type") == "LoadImage":
            img = n["inputs"]["image"]
            if not os.path.exists(os.path.join(ROOT, "input", img)):
                return f"LoadImage points at {img}, which was never uploaded"
    return None


def refs_of(wf):
    cond = next(n for n in wf.values() if n.get("class_type") == "MiniMaxH3ReferenceToVideo")
    keys = sorted((int(m.group("i")), k) for k in cond["inputs"] if (m := REF_RE.match(k)))
    return [wf[cond["inputs"][k][0]]["inputs"]["image"] for _, k in keys]


def enqueue(wf, source, card=None):
    pid = uuid.uuid4().hex
    with LOCK:
        STATE["pending"] += 1
        STATE["max_in_flight"] = max(STATE["max_in_flight"], STATE["pending"] + STATE["running"])
        STATE["jobs"].append({"prompt_id": pid, "source": source, "refs": refs_of(wf), "card": card})
    threading.Thread(target=render, args=(pid, wf), daemon=True).start()
    return pid


def render(pid, wf):
    time.sleep(0.3)
    with LOCK:
        STATE["pending"] -= 1
        STATE["running"] += 1
    try:
        refs = refs_of(wf)
        dur = next(n["inputs"]["value"] for n in wf.values() if n.get("_meta", {}).get("title", "").lower().startswith("float"))
        prefix = next(n["inputs"]["filename_prefix"] for n in wf.values() if "filename_prefix" in n["inputs"])
        sub, base = os.path.split(prefix)
        out_dir = os.path.join(ROOT, "output", sub)
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{base}_00001_.mp4"
        src = os.path.join(ROOT, "input", refs[0])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", src, "-f", "lavfi", "-i", "sine=f=440:r=48000",
                        "-t", str(dur), "-vf", "scale=544:960:force_original_aspect_ratio=decrease,pad=544:960:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", os.path.join(out_dir, fname)], check=True)
        hist = {"status": {"status_str": "success", "completed": True, "messages": []},
                "outputs": {"92": {"images": [{"filename": fname, "subfolder": sub, "type": "output"}], "animated": [True]}}}
    except Exception as e:  # noqa: BLE001
        hist = {"status": {"status_str": "error", "completed": False,
                           "messages": [["execution_error", {"exception_message": str(e)}]]}, "outputs": {}}
    time.sleep(0.2)
    with LOCK:
        STATE["history"][pid] = hist
        STATE["running"] -= 1


def saved_cards():
    return sorted(f[:-5] for f in os.listdir(WORKFLOWS) if f.endswith(".json")) if WORKFLOWS else []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def file(self, p):
        if not os.path.isfile(p):
            return self.send({"error": "not found"}, 404)
        return self.send(None, raw=open(p, "rb").read(), ctype="video/mp4")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = unquote(u.path)
        # ---- bare ComfyUI
        if path == "/system_stats":
            return self.send({"devices": [{"name": "mock-gpu", "vram_free": 20 * 2**30}]})
        if path.startswith("/object_info/"):
            cls = path.split("/object_info/")[1]
            return self.send({cls: {"input": {"required": {"clip": ["CLIP"], "ref_image_size": [["match"]]},
                                              "optional": {"ref_images": ["COMFY_AUTOGROW_V3", {}]}}}})
        if path.startswith("/history/"):
            pid = path.split("/history/")[1]
            with LOCK:
                h = STATE["history"].get(pid)
            return self.send({pid: h} if h else {})
        if path == "/queue":
            return self.send({"queue_running": [0] * STATE["running"], "queue_pending": [0] * STATE["pending"]})
        if path == "/view":
            return self.file(os.path.join(ROOT, q.get("type", ["output"])[0], q.get("subfolder", [""])[0], q["filename"][0]))
        # ---- zealman panel
        if path == "/api/health":
            return self.send({"status": "ok", "uptime": 1.0})
        if path == "/api/gpu/info":
            return self.send({"success": True, "hasGPU": True,
                              "gpus": [{"name": "mock RTX 5090", "memory_total_mb": 32607, "memory_used_mb": 900}]})
        if path == "/api/gpu/profile":
            return self.send({"available": True, "arch": "blackwell"})
        if path == "/api/comfy/status":
            r = STATE["comfy_running"]
            return self.send({"running": r, "starting": False, "reason": "ready" if r else "process_not_found", "port": 6006})
        if path == "/api/comfy/plugin-availability":
            return self.send({"success": True, "restricted": True, "series": ["U"], "workflowPrefixes": []})
        if path == "/api/comfy/queue-status":
            return self.send({"success": True, "busy": bool(STATE["running"] or STATE["pending"])})
        if path == "/api/workflow/list":
            return self.send({"success": True, "workflows": [{"id": c, "name": c + ".json"} for c in saved_cards()]})
        if path.startswith("/api/workflow/config/"):
            cid = path.split("/api/workflow/config/")[1].removesuffix(".json")
            if cid not in saved_cards():
                return self.send({"success": False, "error": "not found"}, 404)
            return self.send({"success": True, "workflow_template": json.load(open(os.path.join(WORKFLOWS, cid + ".json"))),
                              "api_config": {}})
        if path == "/api/workflow/result":
            pid = q["prompt_id"][0]
            with LOCK:
                h = STATE["history"].get(pid)
            if not h:
                return self.send({"success": True, "pending": True, "prompt_id": pid, "results": []})
            if h["status"]["status_str"] == "error":
                return self.send({"success": True, "pending": False, "prompt_id": pid, "results": [],
                                  "error": h["status"]["messages"]})
            res = [{"type": "video", "url": f"/output/{f['subfolder']}/{f['filename']}", "filename": f["filename"]}
                   for o in h["outputs"].values() for f in o.get("images", [])]
            return self.send({"success": True, "pending": False, "prompt_id": pid,
                              "results": res + [{"type": "text", "text": "ignored"}]})
        if path.startswith("/output/"):
            return self.file(os.path.join(ROOT, "output", path[len("/output/"):]))
        if path == "/mock/stats":
            with LOCK:
                return self.send({k: v for k, v in STATE.items() if k != "history"})
        self.send({"error": "unknown"}, 404)

    def upload(self, body, file_fields):
        msg = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
        fields, fdata, fname = {}, None, None
        for part in msg.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name in file_fields:
                fdata, fname = part.get_payload(decode=True), part.get_filename()
            else:
                fields[name] = part.get_content().strip()
        sub = fields.get("subfolder", "")
        d = os.path.join(ROOT, "input", sub)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, fname), "wb").write(fdata)
        return self.send({"name": fname, "subfolder": sub, "type": "input"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        path = urlparse(self.path).path
        if path == "/upload/image":
            return self.upload(body, ("image",))
        if path == "/api/comfy/upload/file":
            return self.upload(body, ("file", "image", "video", "audio"))
        if path in ("/free", "/api/comfy/proxy/free"):
            with LOCK:
                STATE["frees"] += 1
            return self.send({"success": True})
        if path == "/api/comfy/start":
            STATE["starts"].append(json.loads(body or b"{}"))
            STATE["comfy_running"] = True
            return self.send({"code": 0, "alreadyRunning": False})
        if path == "/prompt":
            wf = json.loads(body)["prompt"]
            err = validate(wf)
            if err:
                return self.send({"error": "invalid prompt", "node_errors": {"mock": err}}, 400)
            return self.send({"prompt_id": enqueue(wf, "prompt"), "number": 0, "node_errors": {}})
        if path == "/api/workflow/generate":
            if not STATE["comfy_running"]:
                return self.send({"success": False, "error": "ComfyUI is not running"}, 503)
            req = json.loads(body)
            wid = req["workflow_id"].removesuffix(".json")
            if wid not in saved_cards():
                return self.send({"success": False, "error": f"workflow {wid} not found"}, 404)
            wf = json.load(open(os.path.join(WORKFLOWS, wid + ".json")))
            for key, val in req.get("input_values", {}).items():
                nid, field = key.split(":", 1)
                if nid not in wf or field not in wf[nid]["inputs"]:
                    return self.send({"success": False, "error": f"unknown input {key}"}, 400)
                wf[nid]["inputs"][field] = val
            err = validate(wf)
            if err:
                return self.send({"success": False, "error": err}, 400)
            return self.send({"success": True, "prompt_id": enqueue(wf, "generate", wid), "number": 1})
        if path == "/api/workflow/save":
            req = json.loads(body)
            wid = req["workflow_id"].removesuffix(".json")
            with open(os.path.join(WORKFLOWS, wid + ".json"), "w") as f:
                json.dump(req["workflow_template"], f, ensure_ascii=False)
            STATE["saved"].append({"id": wid, "api_config": req.get("api_config")})
            return self.send({"success": True})
        self.send({"error": "unknown"}, 404)


def main():
    global ROOT, WORKFLOWS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8189)
    ap.add_argument("--dir", default=ROOT)
    ap.add_argument("--workflows", help="directory of saved panel cards (<id>.json, API format)")
    ap.add_argument("--comfy-stopped", action="store_true", help="panel starts with ComfyUI not running")
    a = ap.parse_args()
    ROOT, WORKFLOWS = a.dir, a.workflows
    STATE["comfy_running"] = not a.comfy_stopped
    os.makedirs(ROOT, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
