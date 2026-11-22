# Tiny job server that runs on a rented GPU pod (RunPod).
# It lets this project send shell jobs and files to the pod over HTTPS.
# Every request must carry the X-Secret header that matches the pod's SECRET env var.
import http.server, json, os, subprocess, threading, uuid, urllib.parse

SECRET = os.environ.get("SECRET", "")
JOBS = {}
os.makedirs("/workspace/jobs", exist_ok=True)


def run_job(jid, cmd):
    log = f"/workspace/jobs/{jid}.log"
    with open(log, "w") as f:
        p = subprocess.Popen(["bash", "-lc", cmd], stdout=f, stderr=subprocess.STDOUT)
        JOBS[jid]["pid"] = p.pid
        JOBS[jid]["code"] = p.wait()


class H(http.server.BaseHTTPRequestHandler):
    def _ok(self, body, ctype="application/json", code=200):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if not SECRET or self.headers.get("X-Secret") != SECRET:
            self._ok({"error": "forbidden"}, code=403)
            return False
        return True

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/health":
            return self._ok({"ok": True})
        if not self._auth():
            return
        if u.path == "/job":
            j = JOBS.get(q.get("id"), {})
            log = f"/workspace/jobs/{q.get('id')}.log"
            tail = ""
            if os.path.exists(log):
                with open(log, "rb") as f:
                    f.seek(0, 2); n = f.tell(); f.seek(max(0, n - int(q.get("tail", 4000))))
                    tail = f.read().decode(errors="replace")
            return self._ok({"code": j.get("code"), "running": j.get("code") is None and bool(j), "tail": tail})
        if u.path == "/file":
            with open(q["path"], "rb") as f:
                return self._ok(f.read(), "application/octet-stream")
        self._ok({"error": "not found"}, code=404)

    def do_POST(self):
        if not self._auth():
            return
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        if u.path == "/exec":
            jid = uuid.uuid4().hex[:8]
            JOBS[jid] = {"code": None}
            threading.Thread(target=run_job, args=(jid, json.loads(body)["cmd"]), daemon=True).start()
            return self._ok({"id": jid})
        if u.path == "/file":
            os.makedirs(os.path.dirname(q["path"]) or ".", exist_ok=True)
            with open(q["path"], "wb") as f:
                f.write(body)
            return self._ok({"saved": q["path"], "bytes": len(body)})
        self._ok({"error": "not found"}, code=404)

    def log_message(self, *a):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
