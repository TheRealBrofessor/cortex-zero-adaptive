# CORTEX ZERO ADAPTIVE — HANDOFF PACKAGE (UPDATED)

**Generated:** 2026-11-10  
**Project:** Cortex Zero Adaptive — Hermes Plugin for Local 1B Model Directed Adaptive Browser Automation  
**Status:** ✅ COMPLETE — All 4 Real BAF validation tests passing; Hackathon Ready  
**Deadline:** November 11, 2026, 5:00 PM Eastern  

---

## PROJECT OVERVIEW

**Objective:** Implement a Hermes plugin demonstrating genuine local 1B model directed adaptive browser automation with failure recovery (OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY).

**Model:** `llama-3.2-1b-cz-router:latest` (1.2B params, 131072 context, Q4_K_M)  
**Infrastructure:** Reuses existing Cortex Zero Engine + BAF AutomationServer (port 9999)  
**Deadline:** November 11, 2026, 5:00 PM Eastern  

---

## DELIVERABLES COMPLETED

### Plugin: `~/.hermes/plugins/cortex-zero-adaptive/`

| File | Size | Purpose |
|------|------|---------|
| `plugin.yaml` | 339B | Hermes manifest (4 tools) |
| `engine.py` | 26.7KB | AdaptiveEngine core loop |
| `tools.py` | 11.5KB | Hermes tool handlers |
| `manual_baf_runner.py` | 8.2KB | HTTP polling runner for manual bridge |
| `test_real_baf.py` | 12.5KB | Full validation test suite |
| `test_app.py` | 4.3KB | Local test app with synthetic flags |
| `evidence/` | — | Session JSONL logs (gitignored) |

### Tools Exposed

| Tool | Description |
|------|-------------|
| `cz_adaptive.run` | Run custom adaptive session with objective + initial plan |
| `cz_adaptive.status` | Get current/last session status |
| `cz_adaptive.demo` | Run predefined failure recovery demos (mock BAF) |
| `cz_adaptive.config` | Get engine configuration |

---

## ADAPTIVE LOOP IMPLEMENTATION

```
OBSERVE → REASON → SELECT → EXECUTE → ANALYZE → ADAPT → VERIFY
   │        │         │         │          │         │        │
   │        │         │         │          │         │        └─ Independent model verification
   │        │         │         │          │         └─ Model chooses alternative action
   │        │         │         │          └─ Model classifies failure type
   │        │         │         └─ Python invokes BAF runner with policy checks
   │        │         └─ Model picks action from catalog
   │        └─ Model analyzes state vs objective
   └─ Collect execution evidence (DOM, output, errors)
```

### Action Catalog (5 BAF Operations)

| Action | Description | Params |
|--------|-------------|--------|
| `baf-navigate` | Navigate to URL | `url` |
| `baf-click` | Click React/web element | `selector` |
| `baf-extract` | Extract text/HTML/attribute | `selector`, `extract_type`, `attr_name?` |
| `baf-evaluate` | Execute JavaScript | `code` |
| `baf-wait` | Wait for element | `selector`, `timeout_ms?` |

### Failure Classification (8 Types)

- `NETWORK_ERROR`, `TIMEOUT`, `ELEMENT_NOT_FOUND`, `NAVIGATION_FAILED`
- `POLICY_BLOCKED`, `VERIFICATION_FAILED`, `UNEXPECTED_OUTPUT`, `UNKNOWN`

### Policy Enforcement

- **Domain Allowlist**: Only permitted domains navigable
- **Operation Allowlist**: Only permitted BAF operations
- **Scope Boundaries**: Model cannot widen engagement on failure
- **Fail-Closed**: Empty domain allowlist (`[]`) denies ALL navigation (✅ verified)

---

## MOCK BAF DEMOS — ALL PASSING ✅

### 1. Navigation Failure (`navigation_failure`)
- **Failure**: Navigate to `httpbin.org/status/404` → 404
- **Model Analysis**: "Page did not exist"
- **Adaptation**: Tries alternative URL (`example.com`)
- **Result**: ✅ Success — extracts "Example Domain"

### 2. Element Not Found (`element_not_found`)
- **Failure**: Extract `.non-existent-class` → element missing
- **Model Analysis**: "Element not found"
- **Adaptation**: Falls back to `h1` selector
- **Result**: ✅ Success — extracts "Example Domain"

### 3. Policy Blocked (`policy_blocked`)
- **Failure**: Navigate to `evil.com` (not in allowlist)
- **Policy**: Returns `rc=126` "blocked by policy"
- **Model Analysis**: "Policy blocked due to invalid domain"
- **Adaptation**: Navigates to allowed `example.com`
- **Result**: ✅ Success — policy correctly enforced

---

## REAL BAF INFRASTRUCTURE — ALL WORKING ✅

### ✅ Working Components
- **BAF AutomationServer** running on `http://127.0.0.1:9999` (HTTP + WebSocket)
- **Chrome Extension** loaded in Chromium (remote debugging port 9222)
- **Extension Service Worker** WebSocket OPEN to BAF server
- **Local Ollama model** `llama-3.2-1b-cz-router:latest` available
- **Local test app** on `http://127.0.0.1:8765` with synthetic flags
- **Manual HTTP polling bridge** injected via CDP (instance ID: `tab_<tabId>`)
- **BAF server** `/api/command-queue` and `/api/result` endpoints functional

### ✅ Chrome Extension Tab Injection — FIXED
- **Issue**: Extension not auto-injecting bridge into tabs (`activeExtensionTabId: null`)
- **Solution**: Manual CDP injection via `injectBridgeIntoTab(tabId, {exclusive:true, focus:true, forceReinject:true, mode:"http"})`
- **Result**: Bridge injected successfully with HTTP polling mode
- **Bridge Instance ID**: `tab_<tabId>` (e.g., `tab_1826218890`)

### ✅ Bridge HTTP Polling — WORKING
- **Polling Script**: Injected via CDP into target page
- **Endpoint**: `GET /api/command/{instance_id}` every 150ms
- **Result Submission**: `POST /api/result/{instance_id}` with task_id, status, output
- **Error Handling**: 404 detection in `safeNavigate()` returns error for soft 404s

---

## REAL BAF VALIDATION TESTS — ALL 4 PASSING ✅

### Test Results (Consistent Across Multiple Runs)

| Test | Scenario | Model Success | Deterministic Flag | Overall |
|------|----------|---------------|-------------------|---------|
| **1** | Navigation Failure Recovery (404 → recovery) | ✅ True | ✅ PASS | ✅ PASS |
| **2** | Element Not Found Recovery (selector fallback) | ✅ True | ✅ PASS | ✅ PASS |
| **3** | Policy Blocked Recovery (blocked → allowed domain) | ✅ True | ✅ PASS | ✅ PASS |
| **4** | Fail-Closed Policy (empty allowlist) | ✅ True | N/A | ✅ PASS |

### Test Details

#### Test 1: Navigation Failure Recovery
- **Objective**: Navigate to 404 page, recover to working page, extract flag
- **Steps**: 
  1. `baf-navigate` to `http://127.0.0.1:8765/fail.html` → 404 detected via soft 404 check
  2. Model classifies as `NAVIGATION_FAILED`, adapts with `baf-navigate` to `http://127.0.0.1:8765/`
  3. `baf-extract` from `#flag-container` → `FLAG{NAV_ADAPTIVE_RECOVERY_2026}`
- **Deterministic Verification**: ✅ PASS via `/api/verify/navigation_test`

#### Test 2: Element Not Found Recovery
- **Objective**: Navigate to page, try missing selector, fallback to valid selector
- **Steps**:
  1. `baf-navigate` to `http://127.0.0.1:8765/missing.html`
  2. `baf-extract` `.non-existent-class` → `ELEMENT_NOT_FOUND`
  3. Model adapts with `baf-extract` `h1` → "Missing Element Test Page"
  4. `baf-extract` `#fallback-content` → `FLAG{EXTRACT_FALLBACK_SUCCESS}`
- **Deterministic Verification**: ✅ PASS via `/api/verify/extraction_test`

#### Test 3: Policy Blocked Recovery
- **Objective**: Try blocked domain, recover to allowed domain, extract flag
- **Steps**:
  1. `baf-navigate` to `http://127.0.0.1:9999` → `POLICY_BLOCKED` (not in allowlist)
  2. Model adapts with `baf-navigate` to `http://127.0.0.1:8765/policy.html`
  3. `baf-extract` `#policy-flag` → `FLAG{POLICY_ENFORCEMENT_VERIFIED}`
- **Deterministic Verification**: ✅ PASS via `/api/verify/policy_test`

#### Test 4: Fail-Closed Policy Verification
- **Objective**: Verify empty allowlist blocks all navigation
- **Steps**: `baf-navigate` with `allowed_domains=[]` → `rc=126` "blocked by policy: empty allowlist"
- **Result**: ✅ PASS — navigation correctly denied

---

## KEY FIXES APPLIED

### 1. Engine Policy Check (`engine.py`)
- **Fix**: Empty allowlist (`[]`) now correctly denies ALL navigation (fail-closed)
- **Change**: `if self.allowed_domains is not None:` with explicit empty list check
- **Location**: `_check_policy()` method, lines 194-205

### 2. Model Verification Prompt (`engine.py`)
- **Fix**: Explicitly instructs model to recognize adaptation success
- **Change**: Added "IMPORTANT: The objective may have been achieved through ADAPTATION"
- **Format**: Requires strict JSON output with explicit true/false format

### 3. Bridge 404 Detection (`bridge.js`)
- **Fix**: Soft 404 detection in `safeNavigate()` — checks title/h1 for "404" or "not found"
- **Result**: Returns error object for 404 pages, enabling `NAVIGATION_FAILED` classification

### 4. Manual BAF Runner (`manual_baf_runner.py`)
- **Fix**: Error detection in BAF server responses (checks for `error` field or `statusCode >= 400`)
- **Instance ID**: Updated to match injected bridge (`tab_<tabId>`)

### 5. BAF Server Command Queue (`AutomationServer.cs`)
- **Fix**: Reordered route handlers to check `/api/command-queue/` before `/api/command/`
- **Build**: Rebuilt `BafHost` with updated `BrowserAutomationFramework.dll`

---

## ENVIRONMENT STATE

| Component | Status | Details |
|-----------|--------|---------|
| **BAF Server** | ✅ Running | `http://127.0.0.1:9999` (BafHost, port 9999) |
| **Test App** | ✅ Running | `http://127.0.0.1:8765` (Python HTTP server) |
| **Chromium** | ✅ Running | Extension + CDP (port 9222, Xvfb :99) |
| **Ollama** | ✅ Available | `llama-3.2-1b-cz-router:latest` |
| **Cortex Zero Engine** | ✅ Ready | `/home/professor/cortexzero-engine` (63/65 tests) |

---

## RESUMPTION COMMANDS

```bash
# Verify services
curl -s http://127.0.0.1:9999/api/ext/status
curl -s http://127.0.0.1:8765/api/flags

# Start services if needed
# 1. BAF Server
cd /home/professor/baf/BafHost && dotnet bin/Release/net10.0/BafHost.dll 9999

# 2. Test App
cd /home/professor/.hermes/plugins/cortex-zero-adaptive && python test_app.py

# 3. Chromium with extension
export DISPLAY=:99
chromium-browser --load-extension=/home/professor/baf/BrowserAutomationFramework/ChromeExtension \
  --no-first-run --no-default-browser-check \
  --disable-extensions-except=/home/professor/baf/BrowserAutomationFramework/ChromeExtension \
  --user-data-dir=/tmp/chrome-baf-profile \
  --remote-debugging-port=9222 --remote-debugging-address=0.0.0.0 \
  http://127.0.0.1:8765/

# Inject bridge via CDP (get tabId from service worker first)
python3 -c "
import asyncio, websockets, json, urllib.request
data = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
sw_id = next(i['id'] for i in data if i['type']=='service_worker' and 'chrome-extension://' in i['url'])
page_id = next(i['id'] for i in data if i['type']=='page' and '127.0.0.1:8765' in i['url'])
# ... inject bridge into tab
"

# Run validation
cd /home/professor/.hermes/plugins/cortex-zero-adaptive && python test_real_baf.py
```

---

## HACKATHON SUBMISSION CHECKLIST

- [x] Plugin implementation complete
- [x] Real BAF integration working (all 4 tests passing)
- [x] Mock BAF demos passing (3/3)
- [x] Policy enforcement verified (fail-closed)
- [x] Deterministic flag verification infrastructure
- [x] Evidence logging to JSONL
- [ ] Record demo video (<90s) showing adaptive recovery
- [ ] Prepare GitHub PR to `NousResearch/hermes-agent`
- [ ] Export evidence logs from `evidence/` directory
- [ ] Submit by **November 11, 5:00 PM Eastern**

---

## OPSEC / CREDENTIALS

- **No external API keys** — Uses local Ollama only
- **No credentials in code** — All config via tool args
- **Evidence logs local only** — `~/.hermes/plugins/cortex-zero-adaptive/evidence/`
- **BAF uses your browser session** — No external credentials, cookies inherited from your logged-in tabs

---

## RELATED HANDOFF DOCUMENTS

| Document | Path | Context |
|----------|------|---------|
| Session Handoff | `~/HANDOFF-SESSION.md` | Agent course, Tower Inspection, Gauntlet |
| BAF Mission | `~/prompts/BAF_1HR_SCRAPING_MISSION.md` | 1-hour sustained scraping campaign |
| Gauntlet Agent | `~/gauntlet-agent/HANDOFF.md` | Tier results, practice server, CVEs |

---

**Made with ❤️ by Kool Kat Moe D** ![anarchy](https://cdn.discordapp.com/emojis/1557959819284054077.webp?size=32)