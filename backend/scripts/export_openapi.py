import argparse
import json
from pathlib import Path

from flyttsignal.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "apps" / "web" / "openapi.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export FlyttSignal's deterministic OpenAPI contract."
    )
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when the exported contract is stale.",
    )
    args = parser.parse_args()

    output = args.output.resolve()
    rendered = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"OpenAPI contract is stale: {output}")
        print(f"OpenAPI contract is current: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Exported OpenAPI contract: {output}")


if __name__ == "__main__":
    main()
