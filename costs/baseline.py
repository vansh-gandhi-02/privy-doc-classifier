"""The brute-force baseline (walkthrough step 9): what the obvious approach costs.

Brute force = OCR every scanned page in full, then send every document's whole
text to the LLM. Priced from our own measurements (costs/timing.py, text.jsonl)
instead of a separate ocrmypdf run, so both sides use the same OCR engine and
the same rates.

Assumptions (the same as the cost model): 9.2M pages, 5.3M of them scanned;
an average page carries the measured mean characters of our full-page reads;
about 4 characters per token; a short prompt and a one-word answer per call.

Run: python -m costs.baseline
"""
from __future__ import annotations

import json

import numpy as np

from common.config import DATA_DIR, load

PAGES, SCANNED_PAGES = 9.2e6, 5.3e6
CHARS_PER_TOKEN = 4
PROMPT_TOKENS, ANSWER_TOKENS = 400, 5
INR_PER_CORE_S = 32 / 8 / 3600


def main() -> None:
    bench = json.load(open(DATA_DIR / "bench.json"))
    brief = load("brief")
    n = brief["n_documents"]
    rows = [json.loads(line) for line in open(DATA_DIR / "sample" / "text.jsonl")]
    page_chars = np.mean([len(r["full1"]) for r in rows if r["full1"]] + [len(r["native"]) / max(r["n_pages"], 1) for r in rows if r["native"]])
    ocr = SCANNED_PAGES * bench["ocr_full_s"] * INR_PER_CORE_S
    tokens_in = n * PROMPT_TOKENS + PAGES * page_chars / CHARS_PER_TOKEN
    llm = tokens_in * brief["rates_inr"]["llm_input_per_million_tokens"] / 1e6 + n * ANSWER_TOKENS * brief["rates_inr"]["llm_output_per_million_tokens"] / 1e6
    reads = n * brief["rates_inr"]["storage_read_per_thousand"] / 1000
    print(f"mean characters per page: {page_chars:,.0f} (about {page_chars / CHARS_PER_TOKEN:,.0f} tokens)")
    print("brute force at 5M documents:")
    print(f"  full OCR of {SCANNED_PAGES / 1e6:.1f}M scanned pages: Rs {ocr:,.0f} on this Mac, Rs {2 * ocr:,.0f} on a 2x slower cloud vCPU")
    print(f"  LLM on every document's full text ({tokens_in / 1e9:.2f}B input tokens): Rs {llm:,.0f}")
    print(f"  storage reads: Rs {reads:,.0f}")
    total = 2 * ocr + llm + reads
    print(f"  total: Rs {total:,.0f}, {total / brief['client_budget_inr']:.1f}x the client's Rs {brief['client_budget_inr']:,} budget")
    json.dump({"ocr_inr_cloud": 2 * ocr, "llm_inr": llm, "reads_inr": reads, "total_inr": total, "page_chars": page_chars},
              open(DATA_DIR / "sample" / "baseline.json", "w"), indent=1)


if __name__ == "__main__":
    main()
