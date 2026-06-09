import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APP_ROOT = "/app"
MAX_OUTPUT_CHARS = 12000
RUN_TIMEOUT_SECONDS = int(os.environ.get("PROVIDER_RUN_TIMEOUT_SECONDS", "1500"))

run_lock = threading.Lock()


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def tail(text):
    if not text:
        return ""
    return text[-MAX_OUTPUT_CHARS:]


def run_script(script):
    started = time.time()
    env = os.environ.copy()
    result = subprocess.run(
        ["python", script],
        cwd=APP_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=RUN_TIMEOUT_SECONDS,
    )
    duration_ms = round((time.time() - started) * 1000)
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
    }


def run_task(task):
    if not run_lock.acquire(blocking=False):
        return 409, {
            "ok": False,
            "error": "provider_already_running",
            "task": task,
        }

    try:
        if task == "signal-8h":
            payload = run_script("engine/signal_8h.py")
            payload["task"] = task
            return (200 if payload["ok"] else 500), payload

        if task == "godview":
            payload = run_script("engine/godview.py")
            payload["task"] = task
            return (200 if payload["ok"] else 500), payload

        if task == "all":
            signal_payload = run_script("engine/signal_8h.py")
            godview_payload = run_script("engine/godview.py")
            ok = signal_payload["ok"] and godview_payload["ok"]
            return (200 if ok else 500), {
                "ok": ok,
                "task": task,
                "results": {
                    "signal-8h": signal_payload,
                    "godview": godview_payload,
                },
            }

        return 404, {
            "ok": False,
            "error": "unknown_task",
            "task": task,
        }
    except subprocess.TimeoutExpired as error:
        return 504, {
            "ok": False,
            "error": "provider_timeout",
            "task": task,
            "timeout_seconds": RUN_TIMEOUT_SECONDS,
            "stdout_tail": tail(error.stdout if isinstance(error.stdout, str) else ""),
            "stderr_tail": tail(error.stderr if isinstance(error.stderr, str) else ""),
        }
    except Exception as error:
        return 500, {
            "ok": False,
            "error": "provider_exception",
            "task": task,
            "message": str(error),
        }
    finally:
        run_lock.release()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

    def handle_request(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path in {"/", "/health", "/ready", "/ping"}:
            json_response(self, 200, {
                "ok": True,
                "service": "fxview-provider-container",
            })
            return

        if path.startswith("/run/"):
            task = path.removeprefix("/run/")
            status, payload = run_task(task)
            json_response(self, status, payload)
            return

        json_response(self, 404, {
            "ok": False,
            "error": "not_found",
        })


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"FXview provider container listening on {port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
