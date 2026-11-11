#!/usr/bin/env python3
"""
Real BAF Adaptive Test — Demonstrates model-directed failure recovery with real browser automation.
Uses the manual BAF runner with a manually injected bridge in Chromium.
Includes deterministic verification via test app API.
"""

import sys
import json
import time
import urllib.request
sys.path.insert(0, '/home/professor/cortexzero-engine')
sys.path.insert(0, '/home/professor/.hermes/plugins/cortex-zero-adaptive')

from engine import AdaptiveEngine
from manual_baf_runner import get_manual_baf_runner


def deterministic_verify_flag(flag_name: str) -> bool:
    """Deterministic verification: check flag via test app API."""
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:8765/api/verify/{flag_name}", timeout=5)
        data = json.loads(resp.read().decode())
        return data.get("valid", False)
    except Exception as e:
        print(f"  Verification error: {e}")
        return False


def test_real_baf_adaptive():
    """Run adaptive session with real BAF (manual runner)."""
    print("=" * 60)
    print("REAL BAF ADAPTIVE TEST — Hackathon Validation")
    print("=" * 60)
    
    # Create engine with manual runner
    manual_runner = get_manual_baf_runner()
    manual_runner.set_policy(['127.0.0.1'], ['navigate', 'evaluate', 'extract', 'click', 'wait'])
    
    # Monkey-patch the engine to use manual runner
    import engine
    original_get_baf_runner = engine.get_baf_runner
    engine.get_baf_runner = lambda: manual_runner
    
    all_passed = True
    
    try:
        # Test 1: Navigation failure recovery
        print("\n[TEST 1] Navigation Failure Recovery")
        print("-" * 40)
        objective = "Navigate to a page that fails (404), then recover to a working page and extract the navigation flag"
        initial_plan = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "http://127.0.0.1:8765/fail.html"],
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
        
        eng = AdaptiveEngine(
            model_name="llama-3.2-1b-cz-router:latest",
            ollama_url="http://127.0.0.1:11434",
            use_mock_baf=False,
            max_steps=5,
            max_retries_per_step=2,
            step_timeout=30.0,
            allowed_domains=["127.0.0.1"],
            allowed_operations=["navigate", "evaluate", "extract", "click", "wait"],
        )
        eng.baf_runner = manual_runner
        
        session = eng.run_adaptive_loop(objective, initial_plan)
        report = eng.get_session_report()
        
        print(f"Session: {session.session_id}")
        print(f"Steps executed: {len(session.steps)}")
        print(f"Model-reported success: {session.success}")
        print(f"Model verification: {session.final_verification}")
        
        # Deterministic verification: check if we got the navigation flag
        nav_flag_verified = deterministic_verify_flag("navigation_test")
        print(f"  Deterministic flag verification (navigation_test): {'✓ PASS' if nav_flag_verified else '✗ FAIL'}")
        
        for step in session.steps:
            if step.action == "baf-navigate" and step.status.value == "success":
                print(f"  ✓ Navigation succeeded to: {step.argv[1] if len(step.argv) > 1 else 'unknown'}")
            elif step.action == "baf-extract" and step.status.value == "success":
                print(f"  ✓ Extraction succeeded: {step.result.out[:100] if step.result else 'no result'}")
        
        test1_pass = session.success and nav_flag_verified
        all_passed = all_passed and test1_pass
        print(f"  Test 1 overall: {'✓ PASS' if test1_pass else '✗ FAIL'}")
        
        # Test 2: Element not found recovery
        print("\n[TEST 2] Element Not Found Recovery")
        print("-" * 40)
        eng2 = AdaptiveEngine(
            model_name="llama-3.2-1b-cz-router:latest",
            ollama_url="http://127.0.0.1:11434",
            use_mock_baf=False,
            max_steps=5,
            max_retries_per_step=2,
            step_timeout=30.0,
            allowed_domains=["127.0.0.1"],
            allowed_operations=["navigate", "evaluate", "extract", "click", "wait"],
        )
        eng2.baf_runner = manual_runner
        
        objective2 = "Navigate to a page, try to extract a missing element, then fall back to a valid selector and get the extraction flag"
        initial_plan2 = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "http://127.0.0.1:8765/missing.html"],
                "description": "Navigate to missing element test page",
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
        
        session2 = eng2.run_adaptive_loop(objective2, initial_plan2)
        report2 = eng2.get_session_report()
        
        print(f"Session: {session2.session_id}")
        print(f"Steps executed: {len(session2.steps)}")
        print(f"Model-reported success: {session2.success}")
        print(f"Model verification: {session2.final_verification}")
        
        # Deterministic verification: check extraction flag
        extract_flag_verified = deterministic_verify_flag("extraction_test")
        print(f"  Deterministic flag verification (extraction_test): {'✓ PASS' if extract_flag_verified else '✗ FAIL'}")
        
        for step in session2.steps:
            if step.action == "baf-navigate" and step.status.value == "success":
                print(f"  ✓ Navigation succeeded to: {step.argv[1] if len(step.argv) > 1 else 'unknown'}")
            elif step.action == "baf-extract" and step.status.value == "success":
                print(f"  ✓ Extraction succeeded: {step.result.out[:100] if step.result else 'no result'}")
        
        test2_pass = session2.success and extract_flag_verified
        all_passed = all_passed and test2_pass
        print(f"  Test 2 overall: {'✓ PASS' if test2_pass else '✗ FAIL'}")
        
        # Test 3: Policy blocked recovery
        print("\n[TEST 3] Policy Blocked Recovery")
        print("-" * 40)
        eng3 = AdaptiveEngine(
            model_name="llama-3.2-1b-cz-router:latest",
            ollama_url="http://127.0.0.1:11434",
            use_mock_baf=False,
            max_steps=5,
            max_retries_per_step=2,
            step_timeout=30.0,
            allowed_domains=["127.0.0.1"],
            allowed_operations=["navigate", "evaluate", "extract", "click", "wait"],
        )
        eng3.baf_runner = manual_runner
        
        objective3 = "Try to navigate to a blocked domain (wrong port), get blocked by policy, then navigate to allowed domain and get policy flag"
        initial_plan3 = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "http://127.0.0.1:9999"],  # Wrong port - will be blocked by policy if not in allowlist
                "description": "Navigate to blocked/wrong URL",
                "expected": "Navigation fails",
            },
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "http://127.0.0.1:8765/policy.html"],
                "description": "Navigate to allowed policy test page",
                "expected": "Page loads successfully",
            },
            {
                "action": "baf-extract",
                "argv": ["baf-extract", "#policy-flag", "innerText"],
                "description": "Extract policy flag",
                "expected": "Get policy flag",
            },
        ]
        
        session3 = eng3.run_adaptive_loop(objective3, initial_plan3)
        report3 = eng3.get_session_report()
        
        print(f"Session: {session3.session_id}")
        print(f"Steps executed: {len(session3.steps)}")
        print(f"Model-reported success: {session3.success}")
        print(f"Model verification: {session3.final_verification}")
        
        # Deterministic verification: check policy flag
        policy_flag_verified = deterministic_verify_flag("policy_test")
        print(f"  Deterministic flag verification (policy_test): {'✓ PASS' if policy_flag_verified else '✗ FAIL'}")
        
        for step in session3.steps:
            if step.action == "baf-navigate" and step.status.value == "success":
                print(f"  ✓ Navigation succeeded to: {step.argv[1] if len(step.argv) > 1 else 'unknown'}")
            elif step.action == "baf-extract" and step.status.value == "success":
                print(f"  ✓ Extraction succeeded: {step.result.out[:100] if step.result else 'no result'}")
        
        test3_pass = session3.success and policy_flag_verified
        all_passed = all_passed and test3_pass
        print(f"  Test 3 overall: {'✓ PASS' if test3_pass else '✗ FAIL'}")
        
        # Test 4: Fail-closed policy verification (empty allowlist)
        print("\n[TEST 4] Fail-Closed Policy Verification")
        print("-" * 40)
        eng4 = AdaptiveEngine(
            model_name="llama-3.2-1b-cz-router:latest",
            ollama_url="http://127.0.0.1:11434",
            use_mock_baf=False,
            max_steps=3,
            max_retries_per_step=1,
            step_timeout=10.0,
            allowed_domains=[],  # Empty allowlist - should deny ALL
            allowed_operations=["navigate"],
        )
        eng4.baf_runner = manual_runner
        
        objective4 = "Verify empty allowlist blocks navigation"
        initial_plan4 = [
            {
                "action": "baf-navigate",
                "argv": ["baf-navigate", "http://127.0.0.1:8765/"],
                "description": "Navigate with empty allowlist (should be blocked)",
                "expected": "Policy blocks navigation",
            },
        ]
        
        session4 = eng4.run_adaptive_loop(objective4, initial_plan4)
        
        print(f"Session: {session4.session_id}")
        print(f"Steps executed: {len(session4.steps)}")
        print(f"Model-reported success: {session4.success}")
        
        # Check if navigation was blocked (rc=126)
        nav_blocked = False
        for step in session4.steps:
            if step.action == "baf-navigate" and step.result and step.result.rc == 126:
                nav_blocked = True
                print(f"  ✓ Navigation correctly blocked: {step.result.out[:80]}")
                break
        
        if not nav_blocked:
            print(f"  ✗ FAIL: Navigation was NOT blocked (empty allowlist should deny all)")
        
        test4_pass = nav_blocked
        all_passed = all_passed and test4_pass
        print(f"  Test 4 overall: {'✓ PASS' if test4_pass else '✗ FAIL'}")
        
        # Summary
        print("\n" + "=" * 60)
        print("HACKATHON VALIDATION SUMMARY")
        print("=" * 60)
        tests = [
            ("Navigation Failure Recovery + Flag Verify", test1_pass),
            ("Element Not Found Recovery + Flag Verify", test2_pass),
            ("Policy Blocked Recovery + Flag Verify", test3_pass),
            ("Fail-Closed Policy (empty allowlist)", test4_pass),
        ]
        for name, success in tests:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"  {status}: {name}")
        
        print(f"\nOverall: {'ALL TESTS PASSED — HACKATHON READY' if all_passed else 'SOME TESTS FAILED — NEEDS FIXES'}")
        
        return all_passed
        
    finally:
        engine.get_baf_runner = original_get_baf_runner


if __name__ == "__main__":
    success = test_real_baf_adaptive()
    sys.exit(0 if success else 1)