#!/usr/bin/env python3
"""
Local test application with synthetic flags for Cortex Zero Adaptive demo.
Serves test pages that can be used to demonstrate failure recovery.
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path

# Synthetic flags for testing
FLAGS = {
    "navigation_test": "FLAG{NAV_ADAPTIVE_RECOVERY_2026}",
    "extraction_test": "FLAG{EXTRACT_FALLBACK_SUCCESS}",
    "policy_test": "FLAG{POLICY_ENFORCEMENT_VERIFIED}",
    "click_test": "FLAG{CLICK_ADAPTATION_WORKS}",
}

class TestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the directory containing test pages
        super().__init__(*args, directory=str(Path(__file__).parent / "test_pages"), **kwargs)
    
    def do_GET(self):
        if self.path == "/api/flags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(FLAGS).encode())
            return
        elif self.path.startswith("/api/verify/"):
            flag_name = self.path.split("/api/verify/")[1]
            expected = FLAGS.get(flag_name)
            if expected:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"valid": True, "flag": expected}).encode())
            else:
                self.send_response(404)
                self.end_headers()
            return
        super().do_GET()

def create_test_pages():
    """Create test HTML pages for different failure scenarios."""
    test_dir = Path(__file__).parent / "test_pages"
    test_dir.mkdir(exist_ok=True)
    
    # Page 1: Normal page with flag (for successful extraction)
    (test_dir / "index.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Test App - Main</title></head>
<body>
    <h1>Cortex Zero Adaptive Test Page</h1>
    <div id="flag-container" data-flag="FLAG{NAV_ADAPTIVE_RECOVERY_2026}">Navigation Test Flag: FLAG{NAV_ADAPTIVE_RECOVERY_2026}</div>
    <div id="content">Main content for extraction testing</div>
    <button id="action-btn" onclick="handleClick()">Click Me</button>
    <div id="click-result" style="display:none;">FLAG{CLICK_ADAPTATION_WORKS}</div>
    <script>
        function handleClick() {
            document.getElementById('click-result').style.display = 'block';
        }
    </script>
</body>
</html>""")
    
    # Page 2: Page that returns 404 (for navigation failure test)
    (test_dir / "fail.html").write_text("""<!DOCTYPE html>
<html>
<head><title>404 - Not Found</title></head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>This page simulates a navigation failure.</p>
</body>
</html>""")
    
    # Page 3: Page with missing element (for element_not_found test)
    (test_dir / "missing.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Missing Element Test</title></head>
<body>
    <h1>Missing Element Test Page</h1>
    <div id="existing">This element exists</div>
    <!-- The element .non-existent-class is intentionally missing -->
    <div id="fallback-content">FLAG{EXTRACT_FALLBACK_SUCCESS}</div>
</body>
</html>""")
    
    # Page 4: Policy test - different domain (blocked)
    (test_dir / "policy.html").write_text("""<!DOCTYPE html>
<html>
<head><title>Policy Test</title></head>
<body>
    <h1>Policy Test Page (Allowed Domain)</h1>
    <div id="policy-flag">FLAG{POLICY_ENFORCEMENT_VERIFIED}</div>
</body>
</html>""")
    
    print(f"Test pages created in {test_dir}")

if __name__ == "__main__":
    create_test_pages()
    server = HTTPServer(("127.0.0.1", 8765), TestHandler)
    print("Test app running on http://127.0.0.1:8765")
    print("Available pages:")
    print("  http://127.0.0.1:8765/          - Main page with flag")
    print("  http://127.0.0.1:8765/fail.html - 404 page")
    print("  http://127.0.0.1:8765/missing.html - Missing element page")
    print("  http://127.0.0.1:8765/policy.html - Policy test page")
    print("  http://127.0.0.1:8765/api/flags - Get all flags")
    print("  http://127.0.0.1:8765/api/verify/<flag_name> - Verify flag")
    server.serve_forever()