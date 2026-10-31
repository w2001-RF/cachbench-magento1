"""Serveur de l'interface : une page web et une petite API JSON, sur la seule bibliothèque standard.

Chaque action (expérience, statistiques, génération, conversion, entraînement, test HTTP) lance
la commande `cachebench` ou `scripts/http_replay.py` correspondante dans un sous-processus :
l'interface ne fait rien que la ligne de commande ne sache déjà faire, et une tâche s'annule
en arrêtant son processus. Le journal de la commande est relu par la page au fil de l'eau.

Le serveur n'écoute que sur 127.0.0.1. Les requêtes POST doivent être en JSON (un autre site
ouvert dans le navigateur ne peut donc pas les envoyer) et les fichiers écrits restent dans le
dossier du projet.
"""
from __future__ import annotations

import csv
import itertools
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

STATIC = Path(__file__).with_name("static")
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
MAX_JOBS = 50


class UserError(Exception):
    """Erreur due à la saisie : renvoyée à la page en 400 avec son message."""


# --- tâches ---------------------------------------------------------------------------------

class Job:
    def __init__(self, jid: int, kind: str, title: str, cmd: list[str], cwd: Path, finish=None,
                 cleanup: list[Path] | None = None):
        self.id, self.kind, self.title, self.cmd = jid, kind, title, cmd
        self.status = "running"
        self.lines: list[str] = []
        self.result = None
        self.error = None
        self.started = time.time()
        self.ended = None
        self._finish = finish          # (lignes de sortie) -> résultat affiché par la page
        self._cleanup = cleanup or []
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        self.proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                     errors="replace")
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))
        code = self.proc.wait()
        try:
            if self.status == "cancelled":
                return
            if code != 0:
                self.status, self.error = "failed", f"la commande s'est terminée avec le code {code}"
                return
            if self._finish:
                self.result = self._finish(self.lines)
            self.status = "done"
        except Exception as e:  # noqa: BLE001 - résultat illisible : la tâche échoue, pas le serveur
            self.status, self.error = "failed", str(e)
        finally:
            self.ended = time.time()
            for p in self._cleanup:
                p.unlink(missing_ok=True)

    def cancel(self):
        if self.status == "running":
            self.status = "cancelled"
            self.proc.terminate()

    def view(self, since: int = 0) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title, "status": self.status,
                "command": command_line(self.cmd),
                "lines": self.lines[since:], "next": len(self.lines), "result": self.result,
                "error": self.error, "started": self.started, "ended": self.ended}


class App:
    """État du serveur : dossier du projet et tâches lancées."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.jobs: dict[int, Job] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    # chemins

    def path(self, p: str) -> Path:
        q = Path(p)
        return q if q.is_absolute() else self.root / q

    def writable(self, p: str) -> Path:
        q = self.path(p).resolve()
        if q != self.root and self.root not in q.parents:
            raise UserError(f"{p} : les fichiers écrits doivent rester dans {self.root}")
        return q

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.as_posix()

    # informations

    def info(self) -> dict:
        from ..policies import available
        from ..traces import FORMATS
        return {"root": str(self.root), "python": sys.executable, "policies": available(),
                "formats": list(FORMATS), "experiments": self.experiments(), "files": self.trace_files(),
                "models": sorted(self.rel(p) for p in (self.root / "models").glob("*.json"))}

    def experiments(self) -> list[dict]:
        out = []
        for p in sorted((self.root / "experiments").glob("*.y*ml")):
            try:
                name = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("name") or p.stem
            except yaml.YAMLError:
                name = p.stem
            out.append({"path": self.rel(p), "name": name})
        return out

    def trace_files(self, limit: int = 300) -> list[str]:
        files = []
        for d in ("traces", "data"):
            base = self.root / d
            if base.is_dir():
                files += (self.rel(p) for p in sorted(base.rglob("*")) if p.is_file()
                          and p.suffix.lower() in (".csv", ".gz", ".bin", ".log", ".txt", ".zst"))
        return files[:limit]

    def results(self) -> list[dict]:
        out = []
        base = self.root / "results"
        for p in base.rglob("*.csv"):
            if p.name.endswith("_summary.csv"):
                kind = "summary"
            elif p.name.endswith(".http.csv"):
                kind = "http"
            else:
                continue
            out.append({"path": self.rel(p), "kind": kind, "mtime": p.stat().st_mtime,
                        "name": p.name.removesuffix("_summary.csv").removesuffix(".http.csv"),
                        "folder": self.rel(p.parent)})
        return sorted(out, key=lambda r: -r["mtime"])

    def result(self, path: str) -> dict:
        p = self.path(path)
        if not p.is_file():
            raise UserError(f"fichier introuvable : {path}")
        if p.name.endswith(".http.csv"):
            return {"kind": "http", "path": self.rel(p), **http_summary(p)}
        return {"kind": "summary", "path": self.rel(p), "rows": read_summary(p)}

    def magento(self, root: str) -> dict:
        local = Path(root) / "app" / "etc" / "local.xml"
        if not local.is_file():
            raise UserError(f"{local} introuvable")
        cache = ET.parse(local).getroot().find("global/cache")
        if cache is None:
            return {"local_xml": str(local), "backend": None}
        opts = cache.find("backend_options")
        get = (lambda tag: (opts.findtext(tag) or "").strip() or None) if opts is not None else (lambda _t: None)
        params = {c.tag: (c.text or "").strip() for c in opts.find("params")} if (
            opts is not None and opts.find("params") is not None) else {}
        return {"local_xml": str(local), "backend": (cache.findtext("backend") or "").strip(),
                "policy": get("policy"), "capacity": get("capacity"), "inner_backend": get("inner_backend"),
                "params": params, "trace_file": get("trace_file"), "state_dir": get("state_dir")}

    # expériences

    def config_from(self, body: dict) -> dict:
        if body.get("yaml") is not None:
            try:
                cfg = yaml.safe_load(body["yaml"])
            except yaml.YAMLError as e:
                raise UserError(f"YAML illisible : {e}") from None
        else:
            cfg = body.get("config")
        if not isinstance(cfg, dict):
            raise UserError("configuration vide")
        for key in ("traces", "policies", "cache_sizes"):
            if not cfg.get(key):
                raise UserError(f"il manque « {key} » (au moins un élément)")
        return cfg

    def save_experiment(self, body: dict) -> dict:
        cfg = self.config_from(body)
        name = body.get("path") or f"experiments/{cfg.get('name') or 'experience'}.yaml"
        p = self.writable(name)
        if p.suffix.lower() not in (".yaml", ".yml"):
            raise UserError("le fichier doit finir par .yaml")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body["yaml"] if body.get("yaml") is not None else dump_yaml(cfg), encoding="utf-8")
        return {"path": self.rel(p)}

    # lancement

    def start(self, body: dict) -> Job:
        kind = body.get("kind")
        builders = {"run": self._run, "stats": self._stats, "gen": self._gen, "convert": self._convert,
                    "train": self._train, "http": self._http}
        if kind not in builders:
            raise UserError(f"tâche inconnue : {kind}")
        title, cmd, finish, cleanup = builders[kind](body)
        with self._lock:
            jid = next(self._ids)
            job = Job(jid, kind, title, cmd, self.root, finish, cleanup)
            self.jobs[jid] = job
            for old in sorted(self.jobs)[:-MAX_JOBS]:
                if self.jobs[old].status != "running":
                    del self.jobs[old]
        return job

    def _cli(self, *args) -> list[str]:
        return [sys.executable, "-u", "-m", "cachebench.cli", *map(str, args)]

    @staticmethod
    def _opt(cmd: list[str], flag: str, value):
        if value not in (None, ""):
            cmd += [flag, str(value)]

    def _run(self, body):
        cfg = self.config_from(body)
        name = cfg.get("name") or "experience"
        out = self.writable(body.get("output") or cfg.get("output") or f"results/{name}.csv")
        fd, tmp = tempfile.mkstemp(prefix="cachebench-ui-", suffix=".yaml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(dump_yaml(cfg))
        summary = Path(str(out).replace(".csv", "_summary.csv"))
        return (f"Expérience {name}", self._cli("run", tmp, "-o", out),
                lambda _l: {"output": self.rel(out), "summary": self.rel(summary), "rows": read_summary(summary)},
                [Path(tmp)])

    def _stats(self, body):
        trace = need(body, "trace")
        cmd = self._cli("stats", self.path(trace))
        self._opt(cmd, "--format", body.get("format"))
        self._opt(cmd, "-n", body.get("n"))
        return f"Statistiques de {trace}", cmd, lambda lines: json.loads("\n".join(lines)), None

    def _gen(self, body):
        out = self.writable(need(body, "out"))
        cmd = self._cli("gen-trace", out, "-n", body.get("n") or 100_000, "--seed", body.get("seed") or 1)
        if body.get("params"):
            cmd += ["--params", json.dumps(parse_json(body["params"], "paramètres"))]
        return f"Génération de {self.rel(out)}", cmd, lambda lines: {"output": self.rel(out), **json_tail(lines)}, None

    def _convert(self, body):
        trace, out = need(body, "trace"), self.writable(need(body, "out"))
        cmd = self._cli("convert", self.path(trace), out)
        self._opt(cmd, "--format", body.get("format"))
        self._opt(cmd, "-n", body.get("n"))
        return f"Conversion de {trace}", cmd, lambda lines: {"output": self.rel(out), "message": lines[-1]}, None

    def _train(self, body):
        out = self.writable(need(body, "out"))
        cmd = self._cli("train-drl", out)
        if body.get("trace"):
            cmd += ["--trace", self.path(body["trace"])]
        for flag, key in (("-n", "n"), ("--seed", "seed"), ("--capacity", "capacity"), ("--sizes", "sizes"),
                          ("-k", "k"), ("--horizon", "horizon"), ("--epochs", "epochs"),
                          ("--hidden", "hidden"), ("--batch", "batch"), ("--device", "device")):
            self._opt(cmd, flag, body.get(key))
        return f"Entraînement de {self.rel(out)}", cmd, lambda lines: {"output": self.rel(out), "message": lines[-1]}, None

    def _http(self, body):
        script = self.root / "scripts" / "http_replay.py"
        if not script.is_file():
            raise UserError(f"{script} introuvable")
        trace, base = need(body, "trace"), need(body, "base")
        out = self.writable(body.get("out") or f"results/http/{time.strftime('%Y%m%d-%H%M%S')}.http.csv")
        cmd = [sys.executable, "-u", str(script), str(self.path(trace)), base, "--out", str(out)]
        for flag, key in (("-n", "n"), ("-c", "concurrency"), ("--products", "products"), ("--timeout", "timeout")):
            self._opt(cmd, flag, body.get(key))
        return (f"Test HTTP sur {base}", cmd,
                lambda lines: {"path": self.rel(out), **json_tail(lines), **http_summary(out)}, None)


# --- lecture des résultats --------------------------------------------------------------------

def read_summary(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k not in ("trace", "cache_size", "policy"):
                try:
                    r[k] = float(v)
                except (TypeError, ValueError):
                    pass
    return rows


def _pct(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    i = (len(sorted_vals) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def _times(rows: list[dict]) -> dict:
    ms = sorted(float(r["ms"]) for r in rows)
    ok = sum(1 for r in rows if r["status"] == "200")
    return {"requests": len(rows), "ok": ok, "failed": len(rows) - ok,
            "mean_ms": statistics.fmean(ms) if ms else 0.0, "p50_ms": _pct(ms, 0.5),
            "p95_ms": _pct(ms, 0.95), "p99_ms": _pct(ms, 0.99)}


def http_summary(path: Path) -> dict:
    """Temps des pages d'un fichier écrit par http_replay.py, en tout et par type de page."""
    with Path(path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kinds = sorted({r["kind"] for r in rows})
    return {"overall": _times(rows),
            "by_kind": [{"kind": k, **_times([r for r in rows if r["kind"] == k])} for k in kinds]}


# --- petites aides -----------------------------------------------------------------------------

def command_line(cmd: list[str]) -> str:
    """La commande telle qu'on la taperait : « cachebench run ... », « python scripts/... »."""
    def q(a: str) -> str:
        return f'"{a}"' if " " in a else a
    if cmd[1:4] == ["-u", "-m", "cachebench.cli"]:
        return " ".join(["cachebench", *map(q, cmd[4:])])
    return " ".join(["python", *map(q, cmd[2:])])


def dump_yaml(cfg: dict) -> str:
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True, default_flow_style=None)


def need(body: dict, key: str):
    v = body.get(key)
    if v in (None, ""):
        raise UserError(f"champ obligatoire : {key}")
    return v


def parse_json(text, what: str):
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise UserError(f"{what} : JSON illisible ({e.msg})") from None


def json_tail(lines: list[str]) -> dict:
    """Le dernier objet JSON imprimé par une commande (il peut tenir sur plusieurs lignes)."""
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("{"):
            try:
                return json.loads("\n".join(lines[i:]))
            except json.JSONDecodeError:
                continue
    return {}


# --- HTTP ------------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    app: App
    server_version = "cachebench-ui"

    def log_message(self, *_):  # la console reste lisible
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200):
        self._send(code, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ("127.0.0.1", "localhost", "::1")

    def _dispatch(self, fn):
        if not self._host_ok():
            return self._json({"error": "hôte refusé"}, HTTPStatus.FORBIDDEN)
        try:
            res = fn()
        except UserError as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__} : {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        if res is not None:
            self._json(res)

    def do_GET(self):
        self._dispatch(self._get)

    def do_POST(self):
        self._dispatch(self._post)

    def _get(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        app = self.app
        if url.path in ("/", "/index.html"):
            return self._static("index.html")
        if url.path.startswith("/static/"):
            return self._static(url.path.removeprefix("/static/"))
        if url.path == "/api/info":
            return app.info()
        if url.path == "/api/experiment":
            p = app.path(need(q, "path"))
            text = p.read_text(encoding="utf-8")
            return {"path": app.rel(p), "yaml": text, "config": yaml.safe_load(text)}
        if url.path == "/api/results":
            return app.results()
        if url.path == "/api/result":
            return app.result(need(q, "path"))
        if url.path == "/api/magento":
            return app.magento(need(q, "root"))
        if url.path == "/api/jobs":
            return [j.view(len(j.lines)) | {"lines": []} for j in sorted(app.jobs.values(), key=lambda j: -j.id)]
        if url.path.startswith("/api/jobs/"):
            return self._job(url.path).view(int(q.get("since", 0)))
        self._json({"error": "introuvable"}, HTTPStatus.NOT_FOUND)

    def _post(self):
        # corps lu avant tout refus : une réponse envoyée sans le lire coupe la connexion sous Windows
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise UserError("les requêtes POST doivent être en JSON")
        body = parse_json(raw.decode("utf-8") or "{}", "requête")
        url = urlparse(self.path).path
        app = self.app
        if url == "/api/jobs":
            return app.start(body).view()
        if url.startswith("/api/jobs/") and url.endswith("/cancel"):
            job = self._job(url.removesuffix("/cancel"))
            job.cancel()
            return job.view(len(job.lines))
        if url == "/api/yaml":
            return {"yaml": dump_yaml(app.config_from(body))}
        if url == "/api/parse":
            return {"config": app.config_from(body)}
        if url == "/api/experiment/save":
            return app.save_experiment(body)
        self._json({"error": "introuvable"}, HTTPStatus.NOT_FOUND)

    def _job(self, path: str) -> Job:
        try:
            return self.app.jobs[int(path.rsplit("/", 1)[1])]
        except (KeyError, ValueError):
            raise UserError("tâche inconnue") from None

    def _static(self, name: str):
        p = (STATIC / name).resolve()
        if STATIC.resolve() not in p.parents or not p.is_file():
            return self._json({"error": "introuvable"}, HTTPStatus.NOT_FOUND)
        self._send(200, p.read_bytes(), CONTENT_TYPES.get(p.suffix, "application/octet-stream"))


def make_server(root: str | Path = ".", port: int = 8765) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"app": App(Path(root))})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    return server


def serve(root: str | Path = ".", port: int = 8765, open_browser: bool = True) -> None:
    server = make_server(root, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Interface cachebench : {url}  (Ctrl+C pour arrêter)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in server.RequestHandlerClass.app.jobs.values():
            job.cancel()
        server.server_close()
