"""Qdrant simulado para ensaiar scripts/backup.sh e restore.sh sem Docker.

So as rotas que os scripts usam, com o estado em memoria. Uso:
    python3 scripts/validation/fake_qdrant.py PORTA ['{"assistant_a1_v1": 120}']
A chave aceita e a de QDRANT_API_KEY (padrao "chave-ficticia").
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"collections": {}, "aliases": [], "snapshots": {}}
if len(sys.argv) > 2:
    STATE["collections"] = json.loads(sys.argv[2])
    STATE["aliases"] = [{"alias_name": f"assistant_{n.split('_v')[0].split('assistant_')[1]}", "collection_name": n} for n in STATE["collections"]]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, obj, raw=None):
        body = raw if raw is not None else json.dumps({"result": obj, "status": "ok"}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0); return self.rfile.read(n)
    def check(self):
        if self.headers.get("api-key") != os.getenv("QDRANT_API_KEY", "chave-ficticia"):
            self.send_response(401); self.end_headers(); return False
        return True
    def do_GET(self):
        if not self.check(): return
        p = self.path.split("?")[0]
        if p == "/collections": return self.send({"collections": [{"name": n} for n in STATE["collections"]]})
        if p == "/aliases": return self.send({"aliases": STATE["aliases"]})
        m = re.fullmatch(r"/collections/([^/]+)/snapshots/([^/]+)", p)
        if m: return self.send(None, raw=STATE["snapshots"][m.group(2)])
        self.send_response(404); self.end_headers()
    def do_DELETE(self):
        if not self.check(): return
        m = re.fullmatch(r"/collections/([^/]+)/snapshots/([^/]+)", self.path.split("?")[0])
        STATE["snapshots"].pop(m.group(2)); self.send(True)
    def do_POST(self):
        if not self.check(): return
        p = self.path.split("?")[0]; data = self.body()
        m = re.fullmatch(r"/collections/([^/]+)/snapshots", p)
        if m:
            name = f"{m.group(1)}-snap"; STATE["snapshots"][name] = json.dumps({"collection": m.group(1), "points": STATE["collections"][m.group(1)]}).encode()
            return self.send({"name": name})
        m = re.fullmatch(r"/collections/([^/]+)/points/count", p)
        if m: return self.send({"count": STATE["collections"][m.group(1)]})
        m = re.fullmatch(r"/collections/([^/]+)/snapshots/upload", p)
        if m:
            payload = json.loads(data[data.index(b"{"):data.rindex(b"}") + 1])
            STATE["collections"][m.group(1)] = payload["points"]; return self.send(True)
        if p == "/collections/aliases":
            for action in json.loads(data)["actions"]:
                if "delete_alias" in action:
                    STATE["aliases"] = [a for a in STATE["aliases"] if a["alias_name"] != action["delete_alias"]["alias_name"]]
                else:
                    STATE["aliases"].append({"alias_name": action["create_alias"]["alias_name"], "collection_name": action["create_alias"]["collection_name"]})
            return self.send(True)
        self.send_response(404); self.end_headers()

ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
