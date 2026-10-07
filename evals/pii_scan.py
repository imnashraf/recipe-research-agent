"""Check 6: PII scan across state dumps, the dataset, the outputs and the logs.

Ground truth: every commenter / reviewer / author name found on the 25 ORIGINAL (unsanitised)
pages, collected here in memory and never written out. Each artifact is scanned for those names,
for emails (including "x at y dot com"), phone numbers, @handles and avatar links, and for given
names from the gazetteer (reported for review; food words and common English words are excluded).

    python evals/pii_scan.py
"""

import asyncio
import json
import re
import sys
from collections import Counter

from _common import OUTPUT_DIR, REPORTS, ROOT, latest_states, md_table, urls

from bs4 import BeautifulSoup
from pypdf import PdfReader

from recipe_agent.fetch import PageFetcher
from recipe_agent.pii import find_pii
from recipe_agent.sanitize import collect_names, jsonld_person_names

STATE_DUMPS = OUTPUT_DIR / "state_dumps"


def ground_truth_names() -> set[str]:
    fetcher = PageFetcher("snapshot")
    names = set()
    for url in urls():
        soup = BeautifulSoup(fetcher.fetch(url).html, "lxml")
        names |= collect_names(soup, jsonld_person_names(soup))
    # names that are also words used in the dataset's own vocabulary would only produce noise
    return {n for n in names if len(n) >= 3}


def dump_states() -> list:
    STATE_DUMPS.mkdir(parents=True, exist_ok=True)
    states = asyncio.run(latest_states(OUTPUT_DIR / "checkpoints.sqlite"))
    paths = []
    for tid, st in states.items():
        p = STATE_DUMPS / (re.sub(r"[^\w-]", "_", tid) + ".json")
        p.write_text(json.dumps(st, indent=1, ensure_ascii=False, default=str))
        paths.append(p)
    return paths


def targets() -> dict[str, list]:
    pdf = OUTPUT_DIR / "recipe_dataset.pdf"
    return {
        "state dumps (latest checkpoint per thread)": dump_states(),
        "dataset": [OUTPUT_DIR / "dataset.json", OUTPUT_DIR / "dataset.jsonl", *sorted((OUTPUT_DIR / "records").glob("*.json")),
                    *sorted((OUTPUT_DIR / "failures").glob("*.json"))],
        "outputs (PDF text, email draft)": [pdf, *sorted((OUTPUT_DIR / "handoff").glob("*"))],
        "logs": sorted((OUTPUT_DIR / "logs").glob("*")),
        "eval reports": sorted(p for p in REPORTS.glob("*.md") if p.name != "06_pii_scan.md"),
    }


def read_text(p) -> str:
    if p.suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
    return p.read_text(encoding="utf-8", errors="ignore")


ALLOW = json.loads((ROOT / "evals" / "pii_allowlist.json").read_text())["words"]


def site_tokens() -> set[str]:
    toks = set()
    for url in urls():
        host = url.split("/")[2].removeprefix("www.")
        toks |= {host.split(".")[0], host}
    return toks


def classify(kind: str, match: str, sites: set[str]) -> str:
    if kind in ("email", "obfuscated_email") and match.endswith("@example.com"):
        return "placeholder address from the n8n workflow config / SMTP message id (example.com)"
    if kind == "known_commenter_name" and match.lower() in sites:
        return "site name: the blog posted replies under its own site name (e.g. 'zenbelly'); it is in our source URLs"
    if kind == "known_commenter_name" and match in ALLOW:
        return "reviewed: " + ALLOW[match]
    return "UNEXPLAINED"


def context(text: str, match: str) -> str:
    i = text.find(match)
    return re.sub(r"\s+", " ", text[max(0, i - 50): i + len(match) + 50]) if i >= 0 else ""


def main() -> int:
    names = ground_truth_names()
    sites = site_tokens()
    rows, findings, gaz = [], [], Counter()
    for group, files in targets().items():
        files = [f for f in files if f.exists()]
        counts = Counter()
        for f in files:
            text = read_text(f)
            for kind, match in sorted(set(find_pii(text, names))):
                if kind == "gazetteer_name":
                    gaz[match] += 1
                    continue
                verdict = classify(kind, match, sites)
                counts["unexplained" if verdict == "UNEXPLAINED" else "explained"] += 1
                findings.append([group, f.relative_to(ROOT), kind, match, verdict, context(text, match)])
        rows.append([group, len(files), counts["explained"], counts["unexplained"]])
    unexplained = [f for f in findings if f[4] == "UNEXPLAINED"]
    out = [
        "# Check 6: PII scan",
        "",
        f"Ground truth: {len(names)} distinct commenter/author name strings (full names and their parts) collected "
        "from the 25 original, unsanitised pages at scan time; the list itself is never saved.",
        "Also scanned for: emails (plain and 'name at domain dot com'), phone numbers, @handles, gravatar links, and "
        "given names from a gazetteer.",
        "",
        f"**Unexplained hits: {len(unexplained)}.** Every other hit is listed below with its context and the reason it "
        "is not personal data.",
        "",
        md_table(rows, ["artifact group", "files scanned", "hits explained", "hits unexplained"]),
        "",
        "## Every hit, with context",
        "",
        md_table([[g, f, k, m, v, c] for g, f, k, m, v, c in findings], ["group", "file", "kind", "match", "verdict", "context"]),
        "",
        "## Gazetteer given-name review",
        "",
        md_table([[w, c] for w, c in gaz.most_common()], ["word", "occurrences"]) if gaz else
        "No capitalised given names (outside common English and food words) found in any artifact.",
        "",
    ]
    (REPORTS / "06_pii_scan.md").write_text("\n".join(out) + "\n")
    print("\n".join(out[:12]))
    for f in unexplained:
        print("UNEXPLAINED", f)
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
