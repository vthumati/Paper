"""Dump the FastAPI OpenAPI schema to a JSON file, so the frontend can generate
TypeScript types from it (see apps/web: `npm run gen:api`). No running server
needed — the app is imported and `app.openapi()` is serialised.

Usage:
    python scripts/dump_openapi.py [output_path]   # default: ../web/openapi.json
"""
import json
import pathlib
import sys

# make the api root (parent of scripts/) importable however this is invoked
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

DEFAULT_OUT = pathlib.Path(__file__).resolve().parents[2] / "web" / "openapi.json"


def main() -> None:
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
