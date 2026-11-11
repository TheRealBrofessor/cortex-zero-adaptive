"""Tool handlers for the Cortex Zero Adaptive Hermes plugin."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure cortex-zero-adaptive is in path
PLUGIN_DIR = Path(__file__).parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from engine import AdaptiveEngine, get_adaptive_engine

_CONFIG: dict = {}


def configure(ctx) -> None:
    """Snapshot plugin settings from Hermes; tool arguments cannot override them."""
    global _CONFIG
    keys = ("router.model", "ollama.url", "allowed.domains", "allowed.operations", "max.steps", "max.retries", "step.timeout")
    _CONFIG = {key: ctx.get_config(key) for key in keys}


def _setting(key: str, default):
    value = _CONFIG.get(key, default)
    return default if value is None else value


def _engine(args: dict) -> AdaptiveEngine:
    """Get adaptive engine from Hermes plugin settings, never model-supplied overrides."""
    return get_adaptive_engine(
        model_name=_setting("router.model", "llama-3.2-1b-cz-router:latest"),
        ollama_url=_setting("ollama.url", "http://127.0.0.1:11434"),
        use_mock_baf=args.get("use_mock_baf", False),
        max_steps=_setting("max.steps", 10),
        max_retries_per_step=_setting("max.retries", 2),
        step_timeout=_setting("step.timeout", 30.0),
        allowed_domains=_setting("allowed.domains", []),
        allowed_operations=_setting("allowed.operations", ["navigate", "click", "extract", "wait", "screenshot"]),
    )


def cz_adaptive_run(args: dict) -> str:
    """
    Run an adaptive browser automation session.
    
    Args:
        objective: The high-level objective (e.g., "extract flag from target page")
        initial_plan: Optional list of initial steps [{action, argv, description, expected}]
        use_mock_baf: Use mock BAF runner for testing
    """
    eng = _engine(args)
    
    objective = args.get("objective", "")
    if not objective:
        return json.dumps({"status": "error", "message": "objective is required"})
    
    initial_plan = args.get("initial_plan")
    session = eng.run_adaptive_loop(objective, initial_plan)
    report = eng.get_session_report()
    
    return json.dumps({
        "status": "completed" if session.completed else "incomplete",
        "success": session.success,
        "session_id": session.session_id,
        "objective": session.objective,
        "steps_executed": len(session.steps),
        "final_verification": session.final_verification,
        "report": report,
    }, default=str)


def cz_adaptive_status(args: dict | None = None) -> str:
    """Get status of the current or last adaptive session."""
    eng = _engine(args or {})
    
    if not hasattr(eng, 'session') or eng.session is None:
        return json.dumps({"status": "no_session", "message": "No adaptive session active"})
    
    report = eng.get_session_report()
    return json.dumps(report, default=str)


def cz_adaptive_demo(args: dict) -> str:
    """
    Run a predefined demonstration of adaptive failure recovery.
    
    Demonstrates the 1B model encountering a failure, analyzing it, and adapting.
    """
    from runner import RawResult
    import time
    
    class DemoMockRunner:
        """Mock runner that simulates specific failures for demo."""
        def __init__(self, fail_on=None):
            self.fail_on = fail_on or {}
            self.call_count = {}
            self.allowed_domains = []
            self.allowed_operations = {"navigate", "click", "extract", "wait", "screenshot"}
            
        def set_policy(self, allowed_domains, allowed_operations):
            self.allowed_domains = [d.lower().strip() for d in (allowed_domains or []) if d.strip()]
            self.allowed_operations = set(allowed_operations or ["navigate", "click", "extract", "wait", "screenshot"])
        
        def _check_domain_allowed(self, url: str) -> bool:
            if not self.allowed_domains:
                return True
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                for allowed in self.allowed_domains:
                    if domain == allowed or domain.endswith("." + allowed):
                        return True
                return False
            except Exception:
                return False
        
        def _check_operation_allowed(self, op: str) -> bool:
            return op in self.allowed_operations
        
        def run(self, argv, timeout, mode):
            t0 = time.monotonic()
            if not argv:
                return RawResult(argv, 1, "empty argv", 0.0)
            
            cmd = argv[0]
            self.call_count[cmd] = self.call_count.get(cmd, 0) + 1
            count = self.call_count[cmd]
            
            # Policy checks
            if mode == "browser":
                if cmd == "baf-navigate" and len(argv) > 1:
                    url = argv[1]
                    if not self._check_domain_allowed(url):
                        return RawResult(argv, 126, f"blocked by policy: domain not allowed: {url}", 0.0)
                op = cmd.replace("baf-", "")
                if not self._check_operation_allowed(op):
                    return RawResult(argv, 126, f"blocked by policy: operation not allowed: {op}", 0.0)
            
            # Check if this command should fail (fail_on stores max fail count)
            should_fail = False
            if cmd in self.fail_on:
                max_fail = self.fail_on[cmd]
                if isinstance(max_fail, int):
                    should_fail = count <= max_fail
                else:
                    should_fail = max_fail
            
            if should_fail:
                if cmd == "baf-navigate":
                    return RawResult(argv, 1, "Navigation failed: 404 Not Found", 0.1)
                elif cmd == "baf-extract":
                    return RawResult(argv, 1, "Element not found", 0.1)
                elif cmd == "baf-click":
                    return RawResult(argv, 1, "Click failed: element not clickable", 0.1)
                else:
                    return RawResult(argv, 1, f"Mock failure for {cmd}", 0.1)
            
            # Success responses
            time.sleep(0.05)
            if cmd == "baf-navigate":
                return RawResult(argv, 0, "Navigated successfully", 0.1)
            elif cmd == "baf-extract":
                selector = argv[1] if len(argv) > 1 else "body"
                if selector == "h1":
                    return RawResult(argv, 0, "Example Domain", 0.1)
                elif ".non-existent" in selector:
                    return RawResult(argv, 1, "Element not found", 0.1)
                return RawResult(argv, 0, "Extracted content", 0.1)
            elif cmd == "baf-click":
                return RawResult(argv, 0, "Clicked element", 0.1)
            elif cmd == "baf-evaluate":
                return RawResult(argv, 0, "Eval result", 0.1)
            elif cmd == "baf-wait":
                return RawResult(argv, 0, "Element found", 0.1)
            else:
                return RawResult(argv, 0, f"Mock {cmd} executed", 0.1)
    
    eng = _engine({**args, "use_mock_baf": True})
    
    demo_type = args.get("demo", "navigation_failure")
    # Replace with demo-specific failing mock
    if demo_type == "navigation_failure":
        eng.mock_baf_runner = DemoMockRunner(fail_on={"baf-navigate": 1})
    elif demo_type == "element_not_found":
        eng.mock_baf_runner = DemoMockRunner(fail_on={"baf-extract": 1})
    elif demo_type == "policy_blocked":
        eng.mock_baf_runner = DemoMockRunner(fail_on={})
        # Policy block handled by allowed_domains
    
    if demo_type == "navigation_failure":
        # Demo: Navigate to a page that will fail, then adapt
        objective = "Navigate to a test page and extract the main heading"
        initial_plan = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "https://httpbin.org/status/404"],
                "description": "Navigate to a page that returns 404",
                "expected": "Page loads (will fail with 404)",
            },
            {
                "action": "baf-extract",
                "argv": ["baf-extract", "h1", "innerText"],
                "description": "Extract H1 from page",
                "expected": "Get heading text",
            },
        ]
        allowed_domains = ["httpbin.org"]
        
    elif demo_type == "element_not_found":
        # Demo: Try to extract non-existent element, then adapt
        objective = "Extract specific data from a page using adaptive recovery"
        initial_plan = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "https://example.com"],
                "description": "Navigate to example.com",
                "expected": "Page loads successfully",
            },
            {
                "action": "baf-extract",
                "argv": ["baf-extract", ".non-existent-class", "innerText"],
                "description": "Extract non-existent element (will fail)",
                "expected": "Get element text (will fail)",
            },
            {
                "action": "baf-extract",
                "argv": ["baf-extract", "h1", "innerText"],
                "description": "Extract H1 as fallback",
                "expected": "Get main heading",
            },
        ]
        allowed_domains = ["example.com"]
        
    elif demo_type == "policy_blocked":
        # Demo: Try to navigate to blocked domain
        objective = "Demonstrate policy enforcement and recovery"
        initial_plan = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "https://evil.com"],
                "description": "Navigate to blocked domain (will be blocked by policy)",
                "expected": "Policy blocks navigation",
            },
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "https://example.com"],
                "description": "Navigate to allowed domain as fallback",
                "expected": "Page loads successfully",
            },
        ]
        allowed_domains = ["example.com"]
        
    else:
        return json.dumps({"status": "error", "message": f"Unknown demo type: {demo_type}"})
    
    eng.allowed_domains = allowed_domains
    session = eng.run_adaptive_loop(objective, initial_plan)
    report = eng.get_session_report()
    
    return json.dumps({
        "status": "completed",
        "demo_type": demo_type,
        "success": session.success,
        "session_id": session.session_id,
        "objective": session.objective,
        "steps_executed": len(session.steps),
        "final_verification": session.final_verification,
        "report": report,
    }, default=str)


def cz_adaptive_config(args: dict) -> str:
    """Get or update adaptive engine configuration."""
    action = args.get("action", "get")
    
    if action == "get":
        return json.dumps({
            "model": _setting("router.model", "llama-3.2-1b-cz-router:latest"),
            "ollama_url": _setting("ollama.url", "http://127.0.0.1:11434"),
            "max_steps": _setting("max.steps", 10),
            "max_retries_per_step": _setting("max.retries", 2),
            "step_timeout": _setting("step.timeout", 30.0),
            "use_mock_baf": False,
            "allowed_domains": _setting("allowed.domains", []),
            "allowed_operations": _setting("allowed.operations", ["navigate", "click", "extract", "wait", "screenshot"]),
        })
    
    return json.dumps({"status": "error", "message": f"Unknown config action: {action}"})
