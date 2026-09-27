#!/usr/bin/env python3
"""A tiny fake ComfyUI server for testing comfy_run.py without a GPU.

Implements /system_stats, /object_info/<cls>, /upload/image, /prompt, /history/<id>,
/view and /queue. Each queued job "renders" a video with ffmpeg: the first reference
image held still for the requested Duration, with a tone as audio.

  python3 tests/mock_comfy.py --port 8189 --dir /tmp/mock_comfy
"""
import argparse
import json
import os
import subprocess
import threading
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

STATE = {"history": {}, "running": 0, "pending": 0}
LOCK = threading.Lock()
ROOT = "/tmp/mock_comfy"
REF_SLOTS = 10


def render(pid, wf):
    with LOCK:
        STATE["pending"] -= 1
        STATE["running"] += 1
    try:
        cond = next(n for n in wf.values() if any(k.startswith("ref_image_") for k in n["inputs"]))
        refs = [wf[v[0]]["inputs"]["image"] for k, v in sorted(cond["inputs"].items()) if k.startswith("ref_image_")]
        dur = next(n["inputs"]["value"] for n in wf.values() if n.get("_meta", {}).get("title", "").lower().startswith("float"))
        prefix = next(n["inputs"]["filename_prefix"] for n in wf.values() if "filename_prefix" in n["inputs"])
        sub, base = os.path.split(prefix)
        out_dir = os.path.join(ROOT, "output", sub)
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{base}_00001_.mp4"
        src = os.path.join(ROOT, "input", refs[0])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", src, "-f", "lavfi", "-i", "sine=f=440:r=48000",
                        "-t", str(dur), "-vf", "scale=480:864:force_original_aspect_ratio=decrease,pad=480:864:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", os.path.join(out_dir, fname)], check=True)
        hist = {"status": {"status_str": "success", "completed": True, "messages": []},
                "outputs": {"170": {"images": [{"filename": fname, "subfolder": sub, "type": "output"}], "animated": [True]}}}
    except Exception as e:  # noqa: BLE001
        hist = {"status": {"status_str": "error", "completed": False,
                           "messages": [["execution_error", {"exception_message": str(e)}]]}, "outputs": {}}
    time.sleep(0.2)
    with LOCK:
        STATE["history"][pid] = hist
        STATE["running"] -= 1


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

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/system_stats":
            return self.send({"devices": [{"name": "mock-gpu", "vram_free": 20 * 2**30}]})
        if u.path.startswith("/object_info/"):
            cls = unquote(u.path.split("/object_info/")[1])
            opt = {f"ref_image_{i}": ["IMAGE"] for i in range(REF_SLOTS)}
            return self.send({cls: {"input": {"required": {"clip": ["CLIP"]}, "optional": opt}}})
        if u.path.startswith("/history/"):
            pid = u.path.split("/history/")[1]
            with LOCK:
                h = STATE["history"].get(pid)
            return self.send({pid: h} if h else {})
        if u.path == "/queue":
            return self.send({"queue_running": [0] * STATE["running"], "queue_pending": [0] * STATE["pending"]})
        if u.path == "/view":
            q = parse_qs(u.query)
            p = os.path.join(ROOT, q.get("type", ["output"])[0], q.get("subfolder", [""])[0], q["filename"][0])
            if not os.path.exists(p):
                return self.send({"error": "not found"}, 404)
            return self.send(None, raw=open(p, "rb").read(), ctype="video/mp4")
        self.send({"error": "unknown"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if self.path == "/upload/image":
            msg = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + body)
            fields, fdata, fname = {}, None, None
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "image":
                    fdata, fname = part.get_payload(decode=True), part.get_filename()
                else:
                    fields[name] = part.get_content().strip()
            sub = fields.get("subfolder", "")
            d = os.path.join(ROOT, "input", sub)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, fname), "wb").write(fdata)
            return self.send({"name": fname, "subfolder": sub, "type": "input"})
        if self.path == "/prompt":
            wf = json.loads(body)["prompt"]
            errors = {}
            for nid, node in wf.items():
                for k, v in node.get("inputs", {}).items():
                    if isinstance(v, list) and v and v[0] not in wf:
                        errors[nid] = f"input {k} links to missing node {v[0]}"
            if errors:
                return self.send({"error": "invalid prompt", "node_errors": errors}, 400)
            pid = uuid.uuid4().hex
            with LOCK:
                STATE["pending"] += 1
            threading.Thread(target=render, args=(pid, wf), daemon=True).start()
            return self.send({"prompt_id": pid, "number": 0, "node_errors": {}})
        self.send({"error": "unknown"}, 404)


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8189)
    ap.add_argument("--dir", default=ROOT)
    a = ap.parse_args()
    ROOT = a.dir
    os.makedirs(ROOT, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
