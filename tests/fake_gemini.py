"""A tiny fake Gemini server for tests, so the real SDK can be exercised without a key or a quota.

Script it with a list of steps; each request takes the next step, and after the list is used up
every request gets the default step (an ordinary good answer).

    ("ok", {...})                    a good answer (the dict is what the model "said", as JSON)
    ("text", "not json")             a 200 reply whose text is not JSON
    ("empty",)                       a 200 reply with no candidates
    ("error", 503, "UNAVAILABLE")    an error reply; extra keyword details can be passed as a 4th item
    ("delay", seconds)               wait, then answer ok (to trigger the client timeout)
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GOOD_ANSWER = {
    "likely_cause": "fake cause",
    "evidence_lines": [2],
    "confidence": "high",
    "suggested_fix": "fake fix",
}

PER_MINUTE = {
    "details": [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}],
        },
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"},
    ]
}
PER_DAY = {
    "details": [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
        },
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "44520s"},
    ]
}


def error(code, status, details=None, message=None):
    return ("error", code, status, details or {}, message)


def overloaded():
    return error(503, "UNAVAILABLE", message="This model is currently experiencing high demand.")


def deadline():
    return error(504, "DEADLINE_EXCEEDED", message="Deadline expired before operation could complete.")


def per_minute():
    return error(429, "RESOURCE_EXHAUSTED", PER_MINUTE, "You exceeded your current quota.")


def per_day():
    return error(429, "RESOURCE_EXHAUSTED", PER_DAY, "You exceeded your current quota.")


class FakeGemini:
    def __init__(self, script=None, default=None):
        self.script = list(script or [])
        self.default = default or ("ok", GOOD_ANSWER)
        self.paths = []
        self.bodies = []
        self.lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                with owner.lock:
                    owner.paths.append(self.path)
                    owner.bodies.append(body.decode('utf-8', 'replace'))
                    step = owner.script.pop(0) if owner.script else owner.default
                try:
                    owner._respond(self, step)
                except (BrokenPipeError, ConnectionError):
                    pass  # the client gave up (a timeout test)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def requests(self) -> int:
        return len(self.paths)

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @staticmethod
    def _send(handler, status, body):
        data = json.dumps(body).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    @staticmethod
    def _candidate(text):
        return {
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP", "index": 0}
            ]
        }

    def _respond(self, handler, step):
        kind = step[0]
        if kind == "delay":
            time.sleep(step[1])
            kind, step = "ok", ("ok", GOOD_ANSWER)
        if kind == "ok":
            self._send(handler, 200, self._candidate(json.dumps(step[1])))
        elif kind == "text":
            self._send(handler, 200, self._candidate(step[1]))
        elif kind == "empty":
            self._send(handler, 200, {"candidates": []})
        elif kind == "error":
            _, code, status, details, message = step
            body = {"error": {"code": code, "message": message or status, "status": status, **details}}
            self._send(handler, code, body)
        else:  # pragma: no cover
            raise ValueError(f"unknown fake step {step!r}")
