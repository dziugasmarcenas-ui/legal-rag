"""Publish the measured numbers as data, not as test artefacts.

The container excludes eval/ (the benchmark belongs to the repo, not the image),
so /status could not read the results there. This writes the same summaries to
data/quality.json, which the image does carry.
"""

import json

from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "quality.json"
SOURCES = {
    "code_served": ROOT / "eval" / "results_serving.json",
    "delegated": ROOT / "eval" / "results_sources.json",
}


def main():
    quality = {}
    for name, path in SOURCES.items():
        if path.exists():
            quality[name] = json.loads(path.read_text(encoding="utf-8")).get("summary")
    OUT.write_text(json.dumps(quality, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")
    for name, summary in quality.items():
        print(f"  {name}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
