# Cortex Zero Adaptive — Hermes Plugin

**Local 1B model directed adaptive browser automation with failure recovery.**

Implements the full adaptive loop: **OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY**

## Overview

This plugin provides Cortex Zero adaptive intelligence as a native Hermes plugin. The local 1B model (llama-3.2-1b-cz-router) selects actions from a structured catalog of permitted browser automation tools, encounters failures, analyzes them, and autonomously chooses alternative approaches — all within configured domain and operation boundaries.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CORTEX ZERO ADAPTIVE                         │
├─────────────────────────────────────────────────────────────────┤
│  AdaptiveEngine                                                 │
│  ├── 1B Router Model (llama-3.2-1b-cz-router:latest)           │
│  │   ├── Chooses actions from catalog                          │
│  │   ├── Analyzes failures                                     │
│  │   └── Plans adaptations                                     │
│  ├── Action Catalog (baf-navigate, baf-click, baf-extract,     │
│  │                    baf-wait)                                │
│  ├── Policy Enforcement (domain allowlist, operation allowlist) │
│  ├── Execution State Persistence                               │
│  ├── Failure Classification                                    │
│  └── Independent Verification                                  │
├─────────────────────────────────────────────────────────────────┤
│  Local Infrastructure:                                          │
│  ├── Self-contained adaptive runner and evidence store          │
│  ├── BAF Runner (BrowserAutomationFramework HTTP API)          │
│  ├── BAF Server (AutomationServer on port 9999)                │
│  └── Local evidence and policy state                            │
└─────────────────────────────────────────────────────────────────┘
```

## Tools

| Tool | Description |
|------|-------------|
| `cz_adaptive_run` | Run an adaptive browser automation session |
| `cz_adaptive_status` | Get status of current/last session |
| `cz_adaptive_demo` | Run predefined failure recovery demonstrations |
| `cz_adaptive_config` | Get engine configuration |

## Quick Start

### 1. Prerequisites

- Ollama running with `llama-3.2-1b-cz-router:latest` (131072 context)
- BAF AutomationServer running on `http://127.0.0.1:9999`
- BAF Chrome Extension loaded and tab injected (for real browser)

### 2. Run a Demo (Mock BAF - No Browser Required)

```python
# Via Hermes tool
cz_adaptive_demo({
    "demo": "navigation_failure"  # or "element_not_found", "policy_blocked"
})
```

### 3. Run Custom Adaptive Session

```python
cz_adaptive_run({
    "objective": "Navigate to target and extract proof of compromise",
    "initial_plan": [
        {
            "action": "baf-navigate",
            "argv": ["baf-navigate", "https://example.com"],
            "description": "Navigate to target site",
            "expected": "Page loads successfully"
        },
        {
            "action": "baf-extract",
            "argv": ["baf-extract", "h1", "innerText"],
            "description": "Extract H1 heading",
            "expected": "Get page heading"
        }
    ],
})
```

## Adaptive Loop

The engine executes the full **OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY** cycle:

1. **OBSERVE** - Collect execution evidence (DOM, network, output)
2. **REASON** - 1B model analyzes current state vs objective
3. **SELECT** - Model chooses next action from permitted catalog
4. **EXECUTE** - Python invokes BAF runner with policy checks
5. **ANALYZE** - Model classifies failure and understands cause
6. **ADAPT** - Model selects alternative permitted action
7. **VERIFY** - Independent success verification (not model self-report)

## Failure Recovery Demonstrations

Three controlled failure scenarios:

| Demo | Failure Type | Recovery |
|------|-------------|----------|
| `navigation_failure` | 404/navigation error | Model analyzes, tries alternative URL/approach |
| `element_not_found` | Selector misses target | Model tries fallback selectors |
| `policy_blocked` | Domain not in allowlist | Model navigates to allowed domain |

## Policy Enforcement

- **Domain Allowlist**: Only permitted domains can be navigated
- **Operation Allowlist**: Only permitted BAF operations (navigate, click, extract, wait, screenshot) by default
- **JavaScript evaluation**: `baf-evaluate` is excluded from the default allowlist and requires explicit user configuration
- **Scope Boundaries**: Model cannot widen engagement scope on failure
- **Consent Gates**: Actions require explicit confirmation (handled by CZE)

## Evidence & Audit

All sessions logged to `$HERMES_HOME/plugin-data/cortex-zero-adaptive/evidence/session_<id>.jsonl`:
- Step execution with inputs/outputs
- Failure classifications
- Model analysis and adaptation decisions
- Final verification results

## Configuration

```python
cz_adaptive_config({"action": "get"})
```

Returns:
- Model: llama-3.2-1b-cz-router:latest
- Ollama: http://127.0.0.1:11434
- Context: 131072 tokens
- Max steps: 10
- Max retries per step: 2
- Step timeout: 30s

## Development

### Run Tests

```bash
cd /home/professor/.hermes/plugins/cortex-zero-adaptive
python test_adaptive_demo.py
```

### Plugin Structure

```
cortex-zero-adaptive/
├── plugin.yaml          # Hermes plugin manifest
├── __init__.py          # Tool exports
├── engine.py            # AdaptiveEngine core
├── tools.py             # Hermes tool handlers
├── test_adaptive_demo.py # Demonstration tests
└── evidence/            # Session logs (gitignored)
```

## Integration with Cortex Zero

The plugin keeps the adaptive loop and BAF transport self-contained so it installs without a machine-specific checkout. The 1B model is limited to:
- Action selection from catalog
- Failure analysis
- Adaptation planning

All execution, validation, and verification remain in deterministic Python code.

## Hackathon Submission

**Project**: Cortex Zero Adaptive  
**Category**: Local Model Directed Automation  
**Model**: llama-3.2-1b-cz-router (1.2B params, 128K context)  
**Demo**: Real browser automation with autonomous failure recovery  

Key Differentiators:
- ✅ Genuine model-directed adaptation (not scripted fallbacks)
- ✅ Real BAF browser automation (not simulated)
- ✅ Policy-bounded recovery (model cannot escape allowlists)
- ✅ Independent verification (not model self-report)
- ✅ Installs without a machine-specific Cortex Zero checkout

## License

Part of Cortex Zero Engine project. See parent repository LICENSE.
