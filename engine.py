"""
Cortex Zero Adaptive Engine — Local 1B model directed adaptive browser automation.

Implements: OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY

The 1B model selects actions from a structured catalog of permitted tools.
Python handles tool invocation, validation, browser observations, failure classification,
execution-state persistence, policy enforcement, and deterministic verification.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from hermes_constants import get_hermes_home

from runner import RawResult, get_baf_runner, get_mock_baf_runner


class StepStatus(Enum):
    """Status of an adaptive step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class FailureType(Enum):
    """Classification of execution failures."""
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    NAVIGATION_FAILED = "navigation_failed"
    POLICY_BLOCKED = "policy_blocked"
    VERIFICATION_FAILED = "verification_failed"
    UNEXPECTED_OUTPUT = "unexpected_output"
    UNKNOWN = "unknown"


@dataclass
class AdaptiveStep:
    """A single step in the adaptive execution loop."""
    step_id: str
    action: str                    # e.g., "baf-navigate", "baf-extract", "baf-click"
    argv: list[str]                # Command arguments
    description: str               # Human-readable description
    expected_outcome: str          # What success looks like
    failure_classification: Optional[FailureType] = None
    status: StepStatus = StepStatus.PENDING
    result: Optional[RawResult] = None
    analysis: str = ""             # Model's analysis of the result
    adaptation: str = ""           # How the model adapted
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


@dataclass
class AdaptiveSession:
    """Complete adaptive session state."""
    session_id: str
    objective: str
    steps: list[AdaptiveStep] = field(default_factory=list)
    current_step_idx: int = -1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed: bool = False
    success: bool = False
    final_verification: str = ""
    evidence_log: list[dict] = field(default_factory=list)


class AdaptiveEngine:
    """
    Adaptive execution engine using local 1B model for decision making.
    
    The model chooses from permitted actions, analyzes results, and adapts on failure.
    All actions remain within authorized engagement boundaries.
    """
    
    def __init__(
        self,
        model_name: str = "llama-3.2-1b-cz-router:latest",
        ollama_url: str = "http://127.0.0.1:11434",
        use_mock_baf: bool = False,
        max_steps: int = 10,
        max_retries_per_step: int = 2,
        step_timeout: float = 30.0,
        evidence_dir: Path | None = None,
        allowed_domains: list[str] = None,
        allowed_operations: list[str] = None,
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.use_mock_baf = use_mock_baf
        self.max_steps = max_steps
        self.max_retries_per_step = max_retries_per_step
        self.step_timeout = step_timeout
        self.evidence_dir = evidence_dir or (get_hermes_home() / "plugin-data" / "cortex-zero-adaptive" / "evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        # Policy
        self.allowed_domains = [d.lower().strip() for d in (allowed_domains or []) if d.strip()]
        self.allowed_operations = set(allowed_operations or [
            "navigate", "click", "extract", "wait", "screenshot"
        ])
        
        # Initialize BAF runner
        self.baf_runner = get_baf_runner() if not use_mock_baf else get_mock_baf_runner()
        self.mock_baf_runner = get_mock_baf_runner()
        
        # Session state
        self.session: Optional[AdaptiveSession] = None
        self.action_catalog = self._build_action_catalog()
        
    def _build_action_catalog(self) -> list[dict]:
        """Build the catalog of permitted actions the model can choose from."""
        return [
            {
                "id": "baf-navigate",
                "name": "Navigate to URL",
                "description": "Navigate browser to a target URL",
                "argv_template": ["baf-navigate", "{url}"],
                "params": ["url"],
                "category": "navigation",
            },
            {
                "id": "baf-click",
                "name": "Click element",
                "description": "Click a React/web element by selector",
                "argv_template": ["baf-click", "{selector}"],
                "params": ["selector"],
                "category": "interaction",
            },
            {
                "id": "baf-extract",
                "name": "Extract content",
                "description": "Extract text/HTML/attribute from element",
                "argv_template": ["baf-extract", "{selector}", "{extract_type}", "{attr_name?}"],
                "params": ["selector", "extract_type", "attr_name?"],
                "category": "extraction",
            },
            {
                "id": "baf-evaluate",
                "name": "Evaluate JavaScript",
                "description": "Execute arbitrary JavaScript in browser context",
                "argv_template": ["baf-evaluate", "{code}"],
                "params": ["code"],
                "category": "evaluation",
            },
            {
                "id": "baf-wait",
                "name": "Wait for element",
                "description": "Wait for element to appear in DOM",
                "argv_template": ["baf-wait", "{selector}", "{timeout_ms?}"],
                "params": ["selector", "timeout_ms?"],
                "category": "wait",
            },
        ]
    
    def _check_policy(self, action: str, argv: list[str]) -> tuple[bool, str]:
        """Check if action is allowed by policy."""
        # Check operation
        op = action.replace("baf-", "")
        if op not in self.allowed_operations:
            return False, f"Operation '{op}' not in allowed operations: {self.allowed_operations}"
        
        # Check domain for navigate
        if action == "baf-navigate" and len(argv) > 1:
            url = argv[1]
            # If allowed_domains is explicitly set (not None), enforce it
            # Empty list = fail-closed (deny all), non-empty list = allowlist
            if self.allowed_domains is not None:
                from urllib.parse import urlparse
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower()
                    # Strip port if present
                    if ':' in domain:
                        domain = domain.split(':')[0]
                    # Empty allowlist = deny all (fail-closed)
                    if not self.allowed_domains:
                        return False, f"Domain '{domain}' not in allowed domains: (empty allowlist - fail-closed)"
                    allowed = any(domain == d or domain.endswith("." + d) for d in self.allowed_domains)
                    if not allowed:
                        return False, f"Domain '{domain}' not in allowed domains: {self.allowed_domains}"
                except Exception:
                    return False, f"Invalid URL: {url}"
        
        return True, ""
    
    def _classify_failure(self, result: RawResult, action: str) -> FailureType:
        """Classify the type of failure from execution result."""
        if result.rc == 124 or "timeout" in result.out.lower():
            return FailureType.TIMEOUT
        if result.rc == 126 or "blocked by policy" in result.out.lower():
            return FailureType.POLICY_BLOCKED
        if "no browser client" in result.out.lower() or "not connected" in result.out.lower():
            return FailureType.NETWORK_ERROR
        if "element_not_found" in result.out.lower() or "not found" in result.out.lower():
            return FailureType.ELEMENT_NOT_FOUND
        if "navigation" in result.out.lower() or "failed to navigate" in result.out.lower():
            return FailureType.NAVIGATION_FAILED
        if result.rc != 0:
            return FailureType.UNKNOWN
        return FailureType.UNEXPECTED_OUTPUT
    
    def _format_catalog_for_model(self) -> str:
        """Format action catalog for model prompt."""
        lines = ["Available actions (choose ONE by ID):"]
        for a in self.action_catalog:
            params = ", ".join(a["params"])
            lines.append(f"  {a['id']}: {a['description']} — params: [{params}]")
        return "\n".join(lines)
    
    def _build_adaptive_prompt(
        self,
        objective: str,
        step: AdaptiveStep,
        previous_results: list[AdaptiveStep],
        failure_context: str = ""
    ) -> str:
        """Build prompt for model to choose next action or analyze failure."""
        catalog = self._format_catalog_for_model()
        
        history = ""
        if previous_results:
            history = "\nExecution history:\n"
            for i, s in enumerate(previous_results):
                status = s.status.value
                outcome = s.result.out[:100] if s.result else "no result"
                history += f"  {i+1}. {s.action} ({status}): {outcome}\n"
                if s.analysis:
                    history += f"     Analysis: {s.analysis}\n"
                if s.adaptation:
                    history += f"     Adaptation: {s.adaptation}\n"
        
        failure_info = f"\nFailure context: {failure_context}\n" if failure_context else ""
        
        prompt = (
            f"OBJECTIVE: {objective}\n"
            f"{history}"
            f"{failure_info}"
            f"Current step: {step.description}\n"
            f"Expected: {step.expected_outcome}\n"
            f"{catalog}\n"
            f"Return JSON with: {{\"action_id\": \"<action_id>\", \"params\": {{...}}, \"reasoning\": \"...\"}}"
        )
        return prompt
    
    def _build_analysis_prompt(
        self,
        objective: str,
        step: AdaptiveStep,
        result: RawResult,
        failure_type: FailureType
    ) -> str:
        """Build prompt for model to analyze failure and suggest adaptation."""
        # Show parameter format for each action
        param_examples = []
        for a in self.action_catalog:
            params = a["params"]
            if params:
                param_str = ", ".join(f'"{p}": "..."' for p in params)
                param_examples.append(f'  {a["id"]}: {{{param_str}}}')
            else:
                param_examples.append(f'  {a["id"]}: {{}}')
        param_guide = "\n".join(param_examples)
        
        # Specific guidance for common failure types
        failure_guidance = ""
        if failure_type == FailureType.NAVIGATION_FAILED:
            failure_guidance = "\nNAVIGATION FAILURE GUIDANCE: The page failed to load (404, network error, etc.). The correct adaptation is to try a DIFFERENT URL with baf-navigate. Do NOT try to extract from the failed page."
        elif failure_type == FailureType.ELEMENT_NOT_FOUND:
            failure_guidance = "\nELEMENT NOT FOUND GUIDANCE: The selector did not match any element. Try a DIFFERENT SELECTOR with baf-extract, or navigate to a different page."
        elif failure_type == FailureType.POLICY_BLOCKED:
            failure_guidance = "\nPOLICY BLOCKED GUIDANCE: The action was blocked by policy. Try a DIFFERENT URL (for navigate) or DIFFERENT SELECTOR (for extract/click) that is within allowed domains/operations."
        
        return (
            f"OBJECTIVE: {objective}\n"
            f"Action executed: {step.action} with args {step.argv}\n"
            f"Expected: {step.expected_outcome}\n"
            f"Result: exit_code={result.rc}, output={result.out[:500]}\n"
            f"Failure type: {failure_type.value}\n"
            f"{failure_guidance}\n"
            f"Analyze what went wrong and suggest ONE alternative action from the catalog.\n"
            f"Parameter format for each action:\n{param_guide}\n"
            f"Return JSON: {{\"analysis\": \"...\", \"adaptation\": \"...\", \"next_action_id\": \"...\", \"next_params\": {{\"param_name\": \"value\"}}}}\n"
            f"Example for baf-navigate: {{\"next_action_id\": \"baf-navigate\", \"next_params\": {{\"url\": \"http://example.com\"}}}}"
        )
    
    def _build_verification_prompt(self, objective: str, session: AdaptiveSession) -> str:
        """Build prompt for final verification."""
        summary = f"OBJECTIVE: {objective}\n\nExecution summary (including adaptations):\n"
        for i, s in enumerate(session.steps):
            summary += f"  {i+1}. {s.action}: {s.status.value}\n"
            if s.result:
                summary += f"     Output: {s.result.out[:200]}\n"
            if s.analysis:
                summary += f"     Analysis: {s.analysis}\n"
            if s.adaptation:
                summary += f"     Adaptation: {s.adaptation}\n"
        summary += "\nIMPORTANT: The objective may have been achieved through ADAPTATION (recovery from failures).\n"
        summary += "Consider the FINAL state after all steps, not just the initial plan.\n"
        summary += "\nReturn ONLY valid JSON in this exact format:\n"
        summary += '{"success": true, "verification": "objective achieved because..."}\n'
        summary += 'OR\n'
        summary += '{"success": false, "verification": "objective not achieved because..."}\n'
        summary += "\nDo not include any other text."
        return summary
    
    def _call_model_for_choice(self, prompt: str, valid_action_ids: list[str]) -> dict:
        """Call the 1B model for a structured choice."""
        schema = {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "enum": valid_action_ids},
                "params": {"type": "object"},
                "reasoning": {"type": "string"},
            },
            "required": ["action_id", "params", "reasoning"],
        }
        
        body = {
            "model": self.model_name,
            "stream": False,
            "format": schema,
            "keep_alive": "30m",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.1, "seed": 42, "num_predict": 256},
        }
        
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            self.ollama_url + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.step_timeout) as r:
                data = json.loads(r.read())
            raw = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if not raw:
                raw = (data.get("message") or {}).get("content", "")
            return json.loads(raw)
        except Exception as e:
            return {"action_id": "none", "params": {}, "reasoning": f"Model error: {e}"}
    
    def _call_model_for_analysis(self, prompt: str) -> dict:
        """Call the 1B model for failure analysis."""
        schema = {
            "type": "object",
            "properties": {
                "analysis": {"type": "string"},
                "adaptation": {"type": "string"},
                "next_action_id": {"type": "string"},
                "next_params": {"type": "object"},
            },
            "required": ["analysis", "adaptation", "next_action_id", "next_params"],
        }
        
        body = {
            "model": self.model_name,
            "stream": False,
            "format": schema,
            "keep_alive": "30m",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.2, "seed": 42, "num_predict": 512},
        }
        
        import urllib.request
        req = urllib.request.Request(
            self.ollama_url + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.step_timeout) as r:
                data = json.loads(r.read())
            raw = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if not raw:
                raw = (data.get("message") or {}).get("content", "")
            return json.loads(raw)
        except Exception as e:
            return {
                "analysis": f"Model error: {e}",
                "adaptation": "fallback to next catalog action",
                "next_action_id": "none",
                "next_params": {},
            }
    
    def _call_model_for_verification(self, prompt: str) -> dict:
        """Call the 1B model for final verification."""
        schema = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "verification": {"type": "string"},
            },
            "required": ["success", "verification"],
        }
        
        body = {
            "model": self.model_name,
            "stream": False,
            "format": schema,
            "keep_alive": "30m",
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 256},
        }
        
        import urllib.request
        req = urllib.request.Request(
            self.ollama_url + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.step_timeout) as r:
                data = json.loads(r.read())
            raw = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if not raw:
                raw = (data.get("message") or {}).get("content", "")
            return json.loads(raw)
        except Exception as e:
            return {"success": False, "verification": f"Verification error: {e}"}
    
    def start_session(self, objective: str, allowed_domains: list[str] = None) -> AdaptiveSession:
        """Start a new adaptive session."""
        if allowed_domains:
            self.allowed_domains = [d.lower().strip() for d in allowed_domains if d.strip()]
        
        self.session = AdaptiveSession(
            session_id=str(uuid.uuid4())[:8],
            objective=objective,
        )
        self._log_evidence({"event": "session_start", "objective": objective, "session_id": self.session.session_id})
        return self.session
    
    def _log_evidence(self, entry: dict) -> None:
        """Log evidence to session and file."""
        entry["timestamp"] = time.time()
        entry["session_id"] = self.session.session_id if self.session else "none"
        if self.session:
            self.session.evidence_log.append(entry)
        
        # Write to file
        evidence_file = self.evidence_dir / f"session_{self.session.session_id}.jsonl" if self.session else self.evidence_dir / "orphan.jsonl"
        with evidence_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    
    def _execute_step(self, step: AdaptiveStep) -> RawResult:
        """Execute a single step via BAF runner."""
        # Policy check
        allowed, reason = self._check_policy(step.action, step.argv)
        if not allowed:
            return RawResult(step.argv, 126, f"Policy blocked: {reason}", 0.0)
        
        # Select runner
        runner = self.baf_runner if not self.use_mock_baf else self.mock_baf_runner
        
        # Set policy on runner
        if hasattr(runner, 'set_policy'):
            runner.set_policy(self.allowed_domains, list(self.allowed_operations))
        
        # Execute with timeout
        try:
            result = runner.run(step.argv, self.step_timeout, "browser")
            return result
        except Exception as e:
            return RawResult(step.argv, 1, f"Execution exception: {e}", 0.0)
    
    def run_adaptive_loop(self, objective: str, initial_plan: list[dict] = None) -> AdaptiveSession:
        """
        Run the full adaptive loop: OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY
        """
        self.start_session(objective)
        valid_action_ids = [a["id"] for a in self.action_catalog]
        
        # If initial plan provided, use it; otherwise let model plan
        if initial_plan:
            for i, plan_step in enumerate(initial_plan):
                if i >= self.max_steps:
                    break
                step = AdaptiveStep(
                    step_id=f"step_{i+1}",
                    action=plan_step["action"],
                    argv=plan_step["argv"],
                    description=plan_step.get("description", plan_step["action"]),
                    expected_outcome=plan_step.get("expected", "Success"),
                )
                self.session.steps.append(step)
        else:
            # Model creates initial plan - for now use a default navigate+extract
            step = AdaptiveStep(
                step_id="step_1",
                action="baf-navigate",
                argv=["baf-navigate", "https://example.com"],
                description="Navigate to target site",
                expected_outcome="Page loads successfully",
            )
            self.session.steps.append(step)
        
        # Execute each step with adaptive recovery
        for idx, step in enumerate(self.session.steps):
            self.session.current_step_idx = idx
            step.status = StepStatus.RUNNING
            self._log_evidence({"event": "step_start", "step": asdict(step)})
            
            # Execute with retries
            for attempt in range(self.max_retries_per_step + 1):
                step.retry_count = attempt
                result = self._execute_step(step)
                step.result = result
                
                if result.rc == 0:
                    step.status = StepStatus.SUCCESS
                    self._log_evidence({"event": "step_success", "step_id": step.step_id, "result": asdict(result)})
                    break
                else:
                    # Failure - analyze and adapt
                    failure_type = self._classify_failure(result, step.action)
                    step.failure_classification = failure_type
                    
                    if attempt < self.max_retries_per_step:
                        # Ask model to analyze and adapt
                        analysis_prompt = self._build_analysis_prompt(
                            objective, step, result, failure_type
                        )
                        analysis = self._call_model_for_analysis(analysis_prompt)
                        
                        step.analysis = analysis.get("analysis", "")
                        step.adaptation = analysis.get("adaptation", "")
                        
                        # Try the adapted action
                        next_action = analysis.get("next_action_id", "none")
                        if next_action != "none" and next_action in valid_action_ids:
                            next_params = analysis.get("next_params", {})
                            # Build argv from template
                            action_def = next(a for a in self.action_catalog if a["id"] == next_action)
                            argv = []
                            for part in action_def["argv_template"]:
                                if part.startswith("{") and part.endswith("}"):
                                    param = part[1:-1].rstrip("?")
                                    argv.append(next_params.get(param, ""))
                                else:
                                    argv.append(part)
                            
                            step.action = next_action
                            step.argv = argv
                            step.description = analysis.get("adaptation", f"Retry with {next_action}")
                            self._log_evidence({
                                "event": "adaptation",
                                "step_id": step.step_id,
                                "attempt": attempt + 1,
                                "analysis": step.analysis,
                                "adaptation": step.adaptation,
                                "new_action": next_action,
                            })
                            continue
                    
                    # Max retries exceeded
                    step.status = StepStatus.FAILED
                    self._log_evidence({"event": "step_failed", "step_id": step.step_id, "result": asdict(result)})
                    break
        
        # Final verification
        verification_prompt = self._build_verification_prompt(objective, self.session)
        verification = self._call_model_for_verification(verification_prompt)
        
        self.session.completed = True
        self.session.success = verification.get("success", False)
        self.session.final_verification = verification.get("verification", "")
        self.session.updated_at = time.time()
        
        self._log_evidence({
            "event": "session_complete",
            "success": self.session.success,
            "verification": self.session.final_verification,
        })
        
        return self.session
    
    def get_session_report(self) -> dict:
        """Get a complete session report."""
        if not self.session:
            return {"error": "No active session"}
        
        return {
            "session_id": self.session.session_id,
            "objective": self.session.objective,
            "completed": self.session.completed,
            "success": self.session.success,
            "final_verification": self.session.final_verification,
            "steps": [asdict(s) for s in self.session.steps],
            "evidence_log": self.session.evidence_log,
            "duration_seconds": self.session.updated_at - self.session.created_at,
        }


# Global instance for tool handlers
_ADAPTIVE_ENGINE: Optional[AdaptiveEngine] = None


def get_adaptive_engine(**kwargs) -> AdaptiveEngine:
    """Get or create the global adaptive engine instance."""
    global _ADAPTIVE_ENGINE
    if _ADAPTIVE_ENGINE is None:
        _ADAPTIVE_ENGINE = AdaptiveEngine(**kwargs)
    return _ADAPTIVE_ENGINE
