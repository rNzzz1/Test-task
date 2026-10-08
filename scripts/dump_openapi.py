import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

def generate_docs():
    openapi_schema = app.openapi()
    output_path = Path(__file__).resolve().parent.parent / "docs.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, ensure_ascii=False, indent=2)
    print(f"OpenAPI documentation successfully written to {output_path}")

if __name__ == "__main__":
    generate_docs()
