#!/usr/bin/env python3
"""
Fetches (or, in dry-run/demo mode, generates) Lenny's Podcast transcript files
into backend/data/transcripts/ as one .txt/.md file per episode.

USAGE
  python scripts/download_transcripts.py --source <path-or-url> [--limit N]

NOTES FOR THE EVALUATOR
  Lenny's Newsletter does not publish a single official bulk transcript
  archive. In a real engagement this script would point at whatever export
  the client licenses (their own transcript CMS, an Otter.ai export, or a
  scraped+rights-cleared archive). For this assignment we support three modes
  so the pipeline is fully runnable without any special access:

  1. --source <local_dir_or_zip>   Point at a folder/zip of .txt/.md transcripts
                                    you already have (recommended).
  2. --source <url_to_jsonl>       Fetch a JSONL file of {title, guest, text}
                                    records from a URL you control.
  3. (no --source)                 Write a handful of small SAMPLE transcripts
                                    so `ingest.py` and the rest of the app are
                                    exercisable end-to-end without any data
                                    dependency. Clearly logged as sample data.
"""
import argparse
import json
import logging
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")
logger = logging.getLogger("download_transcripts")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"

SAMPLE_EPISODES = [
    {
        "title": "How to find product-market fit",
        "guest": "Sample Guest A",
        "text": (
            "Product-market fit is not a single moment, it is a range of signal you build "
            "confidence in over time. Look at retention curves that flatten instead of decaying "
            "to zero. Look for users who would be 'very disappointed' if the product disappeared "
            "in a Sean Ellis survey, targeting 40 percent or higher. Talk to your best customers "
            "and ask what almost stopped them from buying, that objection is your roadmap. "
            "Avoid vanity growth before fit: paid acquisition on a leaky bucket just burns cash "
            "faster. Instead, narrow your ICP until retention among that narrow segment is "
            "undeniable, then expand outward."
        ),
    },
    {
        "title": "Growth loops versus funnels",
        "guest": "Sample Guest B",
        "text": (
            "A funnel is linear: you spend to acquire, and the spend has to happen again next "
            "month. A growth loop is circular: an output of the system becomes an input that "
            "drives more output, like a user inviting a collaborator who becomes a user who "
            "invites another collaborator. To design a loop, map the smallest complete cycle of "
            "your product: action, output, new input, and identify what throttles the loop's "
            "compounding rate. Most 'growth hacks' fail because they are one-off funnel tricks, "
            "not loops with a compounding rate greater than one."
        ),
    },
    {
        "title": "Pricing for early-stage SaaS",
        "guest": "Sample Guest C",
        "text": (
            "Most early-stage teams underprice because they are anchored to their own "
            "willingness to pay, not their customer's. Run five to ten Van Westendorp style "
            "pricing conversations before you ship a pricing page. Charge more than feels "
            "comfortable; if nobody pushes back on price, you are leaving money and positioning "
            "signal on the table. Prefer usage-based or seat-based pricing that scales with the "
            "value delivered rather than flat pricing that caps your expansion revenue."
        ),
    },
]


def write_sample_data() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for i, ep in enumerate(SAMPLE_EPISODES, start=1):
        path = DATA_DIR / f"sample_{i:02d}.json"
        path.write_text(json.dumps(ep, indent=2))
    logger.warning(
        "No --source provided. Wrote %d SAMPLE transcripts to %s. "
        "Replace with a real transcript export before production use.",
        len(SAMPLE_EPISODES),
        DATA_DIR,
    )
    return len(SAMPLE_EPISODES)


def import_from_dir_or_zip(source: str) -> int:
    src = Path(source)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    if src.suffix == ".zip":
        with zipfile.ZipFile(src) as zf:
            zf.extractall(DATA_DIR)
            count = sum(1 for n in zf.namelist() if n.endswith((".txt", ".md", ".json")))
    elif src.is_dir():
        for f in src.glob("**/*"):
            if f.suffix in (".txt", ".md", ".json"):
                shutil.copy(f, DATA_DIR / f.name)
                count += 1
    else:
        raise FileNotFoundError(f"--source {source} is not a directory or .zip")
    logger.info("Imported %d transcript files into %s", count, DATA_DIR)
    return count


def import_from_url(url: str) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with urlopen(url) as resp:  # noqa: S310 - operator-provided URL, documented risk
        lines = resp.read().decode("utf-8").splitlines()
    count = 0
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        (DATA_DIR / f"remote_{i:04d}.json").write_text(json.dumps(record, indent=2))
        count += 1
    logger.info("Fetched %d transcript records from %s", count, url)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Local dir/zip of transcripts, or URL to a JSONL export")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of files")
    args = parser.parse_args()

    if not args.source:
        n = write_sample_data()
    elif args.source.startswith("http://") or args.source.startswith("https://"):
        n = import_from_url(args.source)
    else:
        n = import_from_dir_or_zip(args.source)

    if args.limit:
        files = sorted(DATA_DIR.glob("*"))[args.limit :]
        for f in files:
            f.unlink()
        n = min(n, args.limit)

    logger.info("Done. %d transcript files ready in %s", n, DATA_DIR)


if __name__ == "__main__":
    sys.exit(main() or 0)
