"""How much Indian PII does the L3 masker remove before text goes to the LLM? (D25 4a, D27)

Uses somukandula/maskara-indian-pii-200k (MIT, synthetic): short texts with
labelled PII spans. A span counts as masked when none of its characters
survive in the masked text, i.e. the span's text no longer appears.

Reported per PII type, on the template_disjoint_eval split (templates the
dataset's own model never saw) and the real_world_eval split. Names and
addresses are expected to leak: the masker uses patterns, not a name model
(stated limitation).

Run: python -m scripts.check_masker
"""
from __future__ import annotations

import json
import re
from collections import Counter

from huggingface_hub import hf_hub_download

from common.config import DATA_DIR
from pipeline.l3_llm.llm import mask


def main() -> None:
    import pyarrow.parquet as pq
    out = {}
    for split in ("template_disjoint_eval", "real_world_eval"):
        path = hf_hub_download("somukandula/maskara-indian-pii-200k", f"data/{split}-00000-of-00001.parquet", repo_type="dataset")
        rows = pq.read_table(path).to_pylist()
        hit, total = Counter(), Counter()
        for r in rows:
            text = r["text"]
            spans = r.get("entities") or r.get("spans") or []
            if isinstance(spans, str):
                spans = json.loads(spans)
            masked = mask(text).lower()
            for s in spans:
                value = text[s["start"]:s["end"]]
                if len(value.strip()) < 3:
                    continue
                total[s["label"]] += 1
                # removed only if no word of 3+ characters from the span survives; for number-type PII
                # only the words with digits count (spans often include a label such as "UID:")
                words = [w for w in re.findall(r"[A-Za-z0-9]{3,}", value) if any(ch.isdigit() for ch in w)]
                # text-type PII (names, emails, addresses): the whole span must be gone, since unmasked
                # names elsewhere in the text would otherwise count against an email that was masked
                hit[s["label"]] += (not any(w.lower() in masked for w in words)) if words else value.lower() not in masked
        out[split] = {k: dict(n=total[k], masked=hit[k] / total[k]) for k in sorted(total)}
        print(f"\n{split} ({len(rows)} texts): share of PII spans removed by the masker")
        for k in sorted(total, key=lambda k: -total[k]):
            print(f"  {k:16} {hit[k] / total[k]:6.1%}  (n={total[k]})")
    json.dump(out, open(DATA_DIR / "sample" / "masker_check.json", "w"), indent=1)


if __name__ == "__main__":
    main()
