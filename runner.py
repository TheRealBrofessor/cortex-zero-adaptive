"""Small self-contained BAF runner layer for the installable Hermes plugin."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class RawResult:
    argv: list[str]
    rc: int
    out: str
    seconds: float


class BAFRunner:
    def __init__(self):
        self._server_url = "http://127.0.0.1:9999"
        self._server_started = False
        self._active_client_id = None
        self._allowed_domains: list[str] = []
        self._allowed_operations: set[str] = {"navigate", "click", "extract", "wait", "screenshot"}

    def set_policy(self, allowed_domains, allowed_operations):
        self._allowed_domains = [d.lower().strip() for d in (allowed_domains or []) if d.strip()]
        self._allowed_operations = set(allowed_operations or [])

    def _get(self, path):
        with urllib.request.urlopen(self._server_url + path, timeout=2) as response:
            return json.loads(response.read())

    def _post(self, path, payload):
        request = urllib.request.Request(
            self._server_url + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def _client(self):
        try:
            tabs = self._get("/api/ext/tabs").get("tabs", [])
        except Exception:
            return None
        for tab in tabs:
            if tab.get("isInjected"):
                return tab.get("instanceId") or f"tab_{tab.get('tabId')}"
        if tabs:
            tab = tabs[0]
            return tab.get("instanceId") or f"tab_{tab.get('tabId')}"
        return None

    def _send(self, client_id, command, payload):
        queued = self._post(f"/api/command-queue/{client_id}", {"type": command, "payload": payload})
        task_id = queued.get("taskId")
        if not task_id:
            return queued
        for _ in range(60):
            time.sleep(1)
            try:
                result = self._get(f"/api/result/{client_id}/{task_id}")
                if result.get("status") != "not_found":
                    return result
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
        raise TimeoutError(f"BAF command {command} timed out")

    def run(self, argv, timeout, mode):
        started = time.monotonic()
        if not argv:
            return RawResult(argv, 1, "empty argv", 0.0)
        command = argv[0]
        operation = command.removeprefix("baf-")
        if operation not in self._allowed_operations:
            return RawResult(argv, 126, f"blocked by policy: operation not allowed: {operation}", 0.0)
        if command == "baf-navigate" and len(argv) > 1 and self._allowed_domains:
            from urllib.parse import urlparse
            domain = urlparse(argv[1]).hostname or ""
            if not any(domain == allowed or domain.endswith("." + allowed) for allowed in self._allowed_domains):
                return RawResult(argv, 126, f"blocked by policy: domain not allowed: {domain}", 0.0)
        try:
            if not self._server_started:
                self._get("/health")
                self._server_started = True
            client_id = self._active_client_id or self._client()
            if not client_id:
                return RawResult(argv, 1, "No browser client connected.", round(time.monotonic() - started, 3))
            self._active_client_id = client_id
            if command == "baf-navigate":
                result = self._send(client_id, "NAVIGATE", {"url": argv[1]})
            elif command == "baf-click":
                result = self._send(client_id, "REACT_CLICK", {"selector": argv[1]})
            elif command == "baf-extract":
                selector = argv[1] if len(argv) > 1 else "body"
                result = self._send(client_id, "EVAL", {"code": f"document.querySelector({selector!r})?.innerText || ''"})
            elif command == "baf-wait":
                result = self._send(client_id, "WAIT", {"selector": argv[1]})
            else:
                return RawResult(argv, 126, "baf-evaluate is disabled by default", 0.0)
            output = result.get("output", result.get("result", ""))
            status = result.get("status", "completed")
            return RawResult(argv, 0 if status in ("completed", "success", "ok") else 1, str(output), round(time.monotonic() - started, 3))
        except Exception as exc:
            return RawResult(argv, 1, str(exc), round(time.monotonic() - started, 3))


class MockBAFRunner:
    def __init__(self):
        self._allowed_domains = []
        self._allowed_operations = {"navigate", "click", "extract", "wait", "screenshot"}

    def set_policy(self, allowed_domains, allowed_operations):
        self._allowed_domains = list(allowed_domains or [])
        self._allowed_operations = set(allowed_operations or [])

    def run(self, argv, timeout, mode):
        started = time.monotonic()
        if not argv:
            return RawResult(argv, 1, "empty argv", 0.0)
        operation = argv[0].removeprefix("baf-")
        if operation not in self._allowed_operations:
            return RawResult(argv, 126, f"blocked by policy: operation not allowed: {operation}", 0.0)
        if argv[0] == "baf-navigate" and len(argv) > 1 and "404" in argv[1]:
            return RawResult(argv, 1, "Navigation failed: 404 Not Found", 0.1)
        if argv[0] == "baf-extract" and len(argv) > 1 and "non-existent" in argv[1]:
            return RawResult(argv, 1, "Element not found", 0.1)
        output = "Example Domain" if argv[0] == "baf-extract" else "Mock operation succeeded"
        return RawResult(argv, 0, output, round(time.monotonic() - started, 3))


_BAF = BAFRunner()
_MOCK = MockBAFRunner()


def get_baf_runner():
    return _BAF


def get_mock_baf_runner():
    return _MOCK
