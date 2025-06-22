#!/usr/bin/env python3
"""
Generate OpenAPI schema from FastAPI application.

This script exports the OpenAPI schema from the FastAPI app to openapi.json
for use by the frontend client code generation tools.

Usage:
    python generate_openapi.py

The generated openapi.json file can then be used by the frontend:
    cd client && npm run generate-api
"""

import json
import sys
from pathlib import Path

# Add src directory to path to import the app
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from storytime.api.main import app
except ImportError as e:
    print(f"Error importing FastAPI app: {e}")
    print("Make sure you have installed the dependencies:")
    print("  uv sync")
    print("  # or pip install -e .")
    sys.exit(1)


def generate_openapi_schema():
    """Generate and save OpenAPI schema to openapi.json."""
    try:
        # Get the OpenAPI schema from the FastAPI app
        openapi_schema = app.openapi()

        # Write to openapi.json in the root directory
        output_path = Path(__file__).parent / "openapi.json"

        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)

        print(f"✅ OpenAPI schema exported to {output_path}")
        print(f"   Total endpoints: {len(openapi_schema.get('paths', {}))}")
        print(f"   API version: {openapi_schema.get('info', {}).get('version', 'unknown')}")
        print()
        print("To update frontend types, run:")
        print("  cd client && npm run generate-api")

    except Exception as e:
        print(f"❌ Error generating OpenAPI schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    generate_openapi_schema()
