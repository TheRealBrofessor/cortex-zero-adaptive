"""Test script demonstrating adaptive failure recovery with mock BAF runner."""

import sys
import time
from pathlib import Path

# Add paths
sys.path.insert(0, '/home/professor/cortexzero-engine')
sys.path.insert(0, '/home/professor/.hermes/plugins/cortex-zero-adaptive')

from czengine.runners import RawResult
from engine import AdaptiveEngine


class FailingMockBAFRunner:
    """Mock BAF runner that simulates specific failures for demo."""
    
    def __init__(self, fail_on=None):
        self.fail_on = fail_on or {}  # {"baf-navigate": True, "baf-extract": False}
        self.call_count = {}
        
    def set_policy(self, allowed_domains, allowed_operations):
        pass
    
    def run(self, argv, timeout, mode):
        t0 = time.monotonic()
        if not argv:
            return RawResult(argv, 1, "empty argv", 0.0)
        
        cmd = argv[0]
        self.call_count[cmd] = self.call_count.get(cmd, 0) + 1
        count = self.call_count[cmd]
        
        # Check if this command should fail
        should_fail = self.fail_on.get(cmd, False)
        # Also support fail-on-Nth-call
        if isinstance(self.fail_on.get(cmd), int):
            should_fail = count <= self.fail_on[cmd]
        
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
            return RawResult(argv, 0, "Extracted content", 0.1)
        elif cmd == "baf-click":
            return RawResult(argv, 0, "Clicked element", 0.1)
        elif cmd == "baf-evaluate":
            return RawResult(argv, 0, "Eval result", 0.1)
        elif cmd == "baf-wait":
            return RawResult(argv, 0, "Element found", 0.1)
        else:
            return RawResult(argv, 0, f"Mock {cmd} executed", 0.1)


def test_adaptive_recovery():
    """Test the adaptive engine with simulated failures."""
    print("=" * 60)
    print("CORTEX ZERO ADAPTIVE - Failure Recovery Demo")
    print("=" * 60)
    
    # Test 1: Navigation failure -> model adapts by trying different approach
    print("\n[TEST 1] Navigation Failure Recovery")
    print("-" * 40)
    
    engine = AdaptiveEngine(use_mock_baf=True, max_steps=5, max_retries_per_step=2)
    # Replace runner with failing mock
    engine.mock_baf_runner = FailingMockBAFRunner(fail_on={"baf-navigate": 1})  # Fail first call
    
    session = engine.run_adaptive_loop(
        objective='Navigate to target and extract proof of compromise',
        initial_plan=[
            {
                'action': 'baf-navigate',
                'argv': ['baf-navigate', 'https://target.example.com'],
                'description': 'Navigate to target site',
                'expected': 'Page loads successfully',
            },
            {
                'action': 'baf-extract',
                'argv': ['baf-extract', 'h1', 'innerText'],
                'description': 'Extract H1 heading',
                'expected': 'Get page heading',
            },
        ]
    )
    
    report = engine.get_session_report()
    print(f"Session: {report['session_id']}")
    print(f"Success: {report['success']}")
    print(f"Verification: {report['final_verification']}")
    for s in report['steps']:
        print(f"  {s['step_id']}: {s['action']} -> {s['status']}")
        if s['analysis']:
            print(f"    Analysis: {s['analysis'][:80]}...")
        if s['adaptation']:
            print(f"    Adaptation: {s['adaptation'][:80]}...")
    
    # Test 2: Element not found -> model tries alternative selector
    print("\n[TEST 2] Element Not Found Recovery")
    print("-" * 40)
    
    engine2 = AdaptiveEngine(use_mock_baf=True, max_steps=5, max_retries_per_step=2)
    engine2.mock_baf_runner = FailingMockBAFRunner(fail_on={"baf-extract": 1})  # Fail first extract
    
    session2 = engine2.run_adaptive_loop(
        objective='Extract sensitive data from page',
        initial_plan=[
            {
                'action': 'baf-navigate',
                'argv': ['baf-navigate', 'https://example.com'],
                'description': 'Navigate to page',
                'expected': 'Page loads',
            },
            {
                'action': 'baf-extract',
                'argv': ['baf-extract', '.secret-data', 'innerText'],
                'description': 'Extract secret data (will fail - wrong selector)',
                'expected': 'Get secret data',
            },
            {
                'action': 'baf-extract',
                'argv': ['baf-extract', 'h1', 'innerText'],
                'description': 'Fallback: extract H1',
                'expected': 'Get heading',
            },
        ]
    )
    
    report2 = engine2.get_session_report()
    print(f"Session: {report2['session_id']}")
    print(f"Success: {report2['success']}")
    print(f"Verification: {report2['final_verification']}")
    for s in report2['steps']:
        print(f"  {s['step_id']}: {s['action']} -> {s['status']}")
        if s['analysis']:
            print(f"    Analysis: {s['analysis'][:80]}...")
        if s['adaptation']:
            print(f"    Adaptation: {s['adaptation'][:80]}...")
    
    # Test 3: Policy blocked -> model tries allowed domain
    print("\n[TEST 3] Policy Block Recovery")
    print("-" * 40)
    
    engine3 = AdaptiveEngine(use_mock_baf=True, max_steps=5, max_retries_per_step=2)
    # Simulate policy block by returning rc=126
    class PolicyBlockRunner(FailingMockBAFRunner):
        def run(self, argv, timeout, mode):
            cmd = argv[0]
            if cmd == "baf-navigate" and len(argv) > 1:
                url = argv[1]
                if "blocked" in url:
                    return RawResult(argv, 126, "blocked by policy: domain not allowed: " + url, 0.1)
            return super().run(argv, timeout, mode)
    
    engine3.mock_baf_runner = PolicyBlockRunner(fail_on={})
    
    session3 = engine3.run_adaptive_loop(
        objective='Access target site and extract data',
        initial_plan=[
            {
                'action': 'baf-navigate',
                'argv': ['baf-navigate', 'https://blocked.example.com'],
                'description': 'Navigate to blocked site (will be blocked by policy)',
                'expected': 'Policy blocks navigation',
            },
            {
                'action': 'baf-navigate',
                'argv': ['baf-navigate', 'https://allowed.example.com'],
                'description': 'Navigate to allowed site as fallback',
                'expected': 'Page loads successfully',
            },
        ]
    )
    
    report3 = engine3.get_session_report()
    print(f"Session: {report3['session_id']}")
    print(f"Success: {report3['success']}")
    print(f"Verification: {report3['final_verification']}")
    for s in report3['steps']:
        print(f"  {s['step_id']}: {s['action']} -> {s['status']}")
        if s['analysis']:
            print(f"    Analysis: {s['analysis'][:80]}...")
        if s['adaptation']:
            print(f"    Adaptation: {s['adaptation'][:80]}...")
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE - All three failure scenarios demonstrated")
    print("=" * 60)


if __name__ == "__main__":
    test_adaptive_recovery()