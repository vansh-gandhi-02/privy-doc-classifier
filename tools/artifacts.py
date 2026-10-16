"""Pack the cached results the Colab notebook needs into artifacts/ (about 30 MB), or unpack them into data/.

Cached because they are slow or cannot run on Colab:
- text.jsonl: OCR of every dev-sample document (about an hour on 6 cores)
- pages.npz:  DiT page features (minutes on a GPU, longer on CPU)
- l3_calls.jsonl: the LLM answers, made through `claude -p` on a Claude
  subscription, which Colab cannot use
- the lockbox results: each lockbox is run once (D15, D27, D29, D30), never again
- the measured CPU times (costs/timing.py) and the splitter evaluation (scripts/eval_splitter.py)

Run: python -m tools.artifacts pack | unpack
"""
from __future__ import annotations

import shutil
import sys

from common.config import DATA_DIR, ROOT

FILES = [
    "bench.json",
    "sample/labels.csv", "sample/manifest.csv", "sample/pages.npz", "sample/text.jsonl", "sample/l3_calls.jsonl",
    "sample/timing_samples.json", "sample/masker_check.json", "sample/splitter_eval.json", "sample/contact_sheet.jpg",
    "lockbox_a/final_metrics.json", "lockbox_a/final_predictions.csv",
    "lockbox_b/final_metrics.json", "lockbox_b/final_predictions.csv", "lockbox_b/diagnostics.json",
    "lockbox_c/final_metrics.json", "lockbox_c/final_predictions.csv",
    "lockbox_d/final_metrics.json", "lockbox_d/final_predictions.csv",
]
ART = ROOT / "artifacts"


def main(action: str) -> None:
    for rel in FILES:
        src, dst = (DATA_DIR / rel, ART / rel) if action == "pack" else (ART / rel, DATA_DIR / rel)
        if not src.exists():
            print(f"  missing, skipped: {rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    print(f"{action}ed {len(FILES)} files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pack")
