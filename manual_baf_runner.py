#!/usr/bin/env python3
"""
Custom BAF Runner for Cortex Zero Adaptive plugin.
Uses HTTP polling with a manually injected bridge (instance ID: bot_fixed_123).
This bypasses the Chrome Extension tab management for demo purposes.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Optional

from czengine.runners import RawResult


@dataclass
class ManualBAFRunner:
    """Runner that executes BAF commands via HTTP polling to a manually injected bridge."""
    name = "manual-baf"
    _instance_id: str = "tab_1826218890"  # Matches injected bridge instance ID
    _server_url: str = "http://127.0.0.1:9999"
    _allowed_domains: list[str] = None
    _allowed_operations: set[str] = None

    def __post_init__(self):
        if self._allowed_domains is None:
            self._allowed_domains = []
        if self._allowed_operations is None:
            self._allowed_operations = {"navigate", "click", "extract", "evaluate", "screenshot", "wait"}

    def set_policy(self, allowed_domains: list[str], allowed_operations: list[str]) -> None:
        self._allowed_domains = [d.lower().strip() for d in allowed_domains if d.strip()]
        self._allowed_operations = set(allowed_operations)

    def _check_domain_allowed(self, url: str) -> bool:
        if not self._allowed_domains:
            return False  # Fail-closed: empty allowlist denies all
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Strip port if present
            if ':' in domain:
                domain = domain.split(':')[0]
            for allowed in self._allowed_domains:
                if domain == allowed or domain.endswith("." + allowed):
                    return True
            return False
        except Exception:
            return False

    def _check_operation_allowed(self, op: str) -> bool:
        return op in self._allowed_operations

    def _http_post(self, path: str, data: dict, timeout: float = 10.0) -> dict:
        url = f"{self._server_url}{path}"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def _http_get(self, path: str, timeout: float = 10.0) -> dict:
        url = f"{self._server_url}{path}"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def _queue_command(self, cmd_type: str, payload: dict) -> str:
        """Queue a command and return the task ID."""
        import uuid
        task_id = str(uuid.uuid4())
        # Include task_id in the command payload so the bridge can return it
        command = {
            "id": task_id,
            "type": cmd_type,
            "payload": payload
        }
        queue_resp = self._http_post(f"/api/command-queue/{self._instance_id}", command)
        if queue_resp.get('status') != 'queued':
            raise RuntimeError(f"Failed to queue command: {queue_resp}")
        return task_id

    def run(self, argv: list[str], timeout: float, mode: str) -> RawResult:
        t0 = time.monotonic()

        if not argv:
            return RawResult(argv, 1, "empty argv", 0.0)

        cmd = argv[0]

        # Policy check for browser mode
        if mode == "browser":
            if cmd == "baf-navigate" and len(argv) > 1:
                url = argv[1]
                if not self._check_domain_allowed(url):
                    return RawResult(argv, 126, f"blocked by policy: domain not allowed: {url}", 0.0)

            op = cmd.replace("baf-", "")
            if not self._check_operation_allowed(op):
                return RawResult(argv, 126, f"blocked by policy: operation not allowed: {op}", 0.0)

        # Map commands to server commands
        try:
            if cmd == "baf-navigate":
                url = argv[1] if len(argv) > 1 else ""
                task_id = self._queue_command("NAVIGATE", {"url": url})

            elif cmd == "baf-click":
                selector = argv[1] if len(argv) > 1 else ""
                task_id = self._queue_command("REACT_CLICK", {"selector": selector})

            elif cmd == "baf-extract":
                selector = argv[1] if len(argv) > 1 else "body"
                extract_type = argv[2] if len(argv) > 2 else "innerText"
                attr_name = argv[3] if len(argv) > 3 else None

                if extract_type == "innerText":
                    code = f"document.querySelector('{selector}')?.innerText || ''"
                elif extract_type == "html":
                    code = f"document.querySelector('{selector}')?.outerHTML || ''"
                elif extract_type == "attribute" and attr_name:
                    code = f"document.querySelector('{selector}')?.getAttribute('{attr_name}') || ''"
                else:
                    code = f"document.querySelector('{selector}')?.innerText || ''"

                task_id = self._queue_command("EVAL", {"code": code})

            elif cmd == "baf-evaluate":
                code = " ".join(argv[1:]) if len(argv) > 1 else ""
                task_id = self._queue_command("EVAL", {"code": code})

            elif cmd == "baf-wait":
                selector = argv[1] if len(argv) > 1 else ""
                wait_timeout = int(argv[2]) if len(argv) > 2 else 5000
                code = f"new Promise((resolve, reject) => {{ const el = document.querySelector('{selector}'); if (el) {{ resolve('found'); }} else {{ const observer = new MutationObserver(() => {{ const el2 = document.querySelector('{selector}'); if (el2) {{ observer.disconnect(); resolve('found'); }} }}); observer.observe(document.body, {{ childList: true, subtree: true }}); setTimeout(() => {{ observer.disconnect(); reject('timeout'); }}, {wait_timeout}); }})"
                task_id = self._queue_command("EVAL", {"code": code})

            else:
                return RawResult(argv, 1, f"Unknown BAF command: {cmd}", round(time.monotonic() - t0, 3))

            # Poll for result
            for _ in range(int(timeout)):
                try:
                    result_resp = self._http_get(f"/api/result/{self._instance_id}/{task_id}")
                    if result_resp.get('status') != 'not_found':
                        output = result_resp.get('output', '')
                        if isinstance(output, dict) or isinstance(output, list):
                            output = json.dumps(output)
                        elif output is None:
                            output = ''
                        
                        # Check if output indicates an error (BAF server returns 'completed' for both success and error)
                        rc = 0
                        if isinstance(output, str):
                            try:
                                parsed = json.loads(output)
                                if isinstance(parsed, dict) and ('error' in parsed or parsed.get('statusCode', 0) >= 400):
                                    rc = 1
                            except:
                                pass
                        
                        return RawResult(argv, rc, str(output)[:8000], round(time.monotonic() - t0, 3))
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        time.sleep(1)
                        continue
                    raise

            return RawResult(argv, 124, "Command timed out", round(time.monotonic() - t0, 3))

        except urllib.error.HTTPError as e:
            return RawResult(argv, e.code, f"HTTP error: {e.read().decode()}", round(time.monotonic() - t0, 3))
        except Exception as e:
            return RawResult(argv, 1, f"Execution error: {e}", round(time.monotonic() - t0, 3))


def get_manual_baf_runner() -> ManualBAFRunner:
    return ManualBAFRunner()