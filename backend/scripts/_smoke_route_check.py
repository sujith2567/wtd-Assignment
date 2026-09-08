import os
import sys
import traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

print("=== importing app ===")
from backend.app.main import app
print("  ok")

print("\n=== app.openapi() routes ===")
spec = app.openapi()
for path, methods in sorted(spec.get("paths", {}).items()):
    for method in methods:
        if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            print(f"  {method.upper():6s} {path}")

print("\n=== baseline-candidates query params from openapi ===")
import json
b = spec.get("paths", {}).get("/api/v1/matching/jobs/{job_id}/baseline-candidates", {})
for method, info in b.items():
    print(f"  {method.upper()}:")
    for p in info.get("parameters", []):
        print(f"    {p['name']:30s} in={p['in']:8s} required={p.get('required', False)}  schema={p.get('schema', {}).get('type')}")
