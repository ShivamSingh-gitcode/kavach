"""
run_evaluation.py

Runs every script in data/test_scripts/ through the REAL pipeline
(backend/pipeline.py, using the offline 'lite' matcher) and reports honest,
reproducible numbers:

  - For scam scripts: did the engine reach HIGH/CRITICAL, and did it do so
    BEFORE the financial-demand line (i.e. before the scammer actually asked
    for money)?
  - For benign control scripts: does the engine correctly stay at LOW/MEDIUM
    (a false-positive check)?

This script produces exactly the numbers that should be quoted in the deck
and the README -- nothing here is hand-picked or pre-computed; run it
yourself and the numbers will regenerate the same way (the 'lite' backend is
deterministic).

Usage:
    cd kavach
    python tests/run_evaluation.py
    python tests/run_evaluation.py --markdown > docs/evaluation_results.md
"""

import sys
import os
import glob
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pipeline import KavachPipeline  # noqa: E402


def load_script(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run_one(path, backend="lite"):
    lines = load_script(path)
    pipeline = KavachPipeline(backend=backend)
    events = pipeline.run_script(lines)
    summary = pipeline.summary()
    return lines, events, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="lite", choices=["lite", "labse"])
    parser.add_argument("--markdown", action="store_true", help="print a markdown table")
    parser.add_argument("--verbose", action="store_true", help="print chunk-by-chunk trace")
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "test_scripts")
    scam_paths = sorted(glob.glob(os.path.join(data_dir, "script_*.txt")))
    control_paths = sorted(glob.glob(os.path.join(data_dir, "control_*.txt")))

    if not args.markdown:
        print(f"Kavach evaluation -- backend: {args.backend}")
        print(f"Scam scripts: {len(scam_paths)}   Control (benign) scripts: {len(control_paths)}\n")

    scam_rows = []
    for path in scam_paths:
        name = os.path.basename(path)
        lines, events, summary = run_one(path, args.backend)
        # actual transcript-chunk index at which FINANCIAL_DEMAND first fired
        # (None if the script never contains a financial-demand line at all)
        fd_chunk_index = next(
            (e.chunk_index for e in events if e.matched_stage == "FINANCIAL_DEMAND"), None
        )
        warned_before_money = (
            fd_chunk_index is not None and _tier_reached_before(events, fd_chunk_index)
        )
        scam_rows.append({
            "name": name, "score": summary["score"], "tier": summary["tier"],
            "stages": summary["fired_stages"], "fd_pos": fd_chunk_index,
            "warned_before_money": warned_before_money,
        })
        if args.verbose:
            _print_trace(name, events)

    control_rows = []
    for path in control_paths:
        name = os.path.basename(path)
        lines, events, summary = run_one(path, args.backend)
        control_rows.append({
            "name": name, "score": summary["score"], "tier": summary["tier"],
            "stages": summary["fired_stages"],
        })
        if args.verbose:
            _print_trace(name, events)

    n_reached_high = sum(1 for r in scam_rows if r["tier"] in ("HIGH", "CRITICAL"))
    n_warned_before_money = sum(1 for r in scam_rows if r["warned_before_money"])
    n_control_stayed_low = sum(1 for r in control_rows if r["tier"] in ("LOW", "MEDIUM"))

    if args.markdown:
        _print_markdown(scam_rows, control_rows, n_reached_high, n_warned_before_money,
                         n_control_stayed_low, len(scam_rows), len(control_rows), args.backend)
    else:
        _print_plain(scam_rows, control_rows, n_reached_high, n_warned_before_money,
                      n_control_stayed_low, len(scam_rows), len(control_rows))


def _tier_reached_before(events, fd_chunk_index):
    """True if the engine was already at HIGH/CRITICAL strictly before the
    chunk where FINANCIAL_DEMAND first fired (i.e. the warning would have
    reached the user before the scammer actually asked for money)."""
    for e in events:
        if e.chunk_index < fd_chunk_index and e.tier in ("HIGH", "CRITICAL"):
            return True
    return False


def _print_trace(name, events):
    print(f"--- {name} ---")
    for e in events:
        tag = f"[{e.matched_stage}]" if e.matched_stage else "[-]"
        print(f"  chunk {e.chunk_index:>2} {tag:<18} score={e.score:>3} tier={e.tier:<8} conf={e.confidence}")
    print()


def _print_plain(scam_rows, control_rows, n_high, n_before, n_low, n_scam, n_ctrl):
    print("SCAM SCRIPTS")
    print("-" * 70)
    for r in scam_rows:
        flag = "reached HIGH/CRITICAL before money asked" if r["warned_before_money"] else "did NOT warn before money asked"
        print(f"  {r['name']:<32} score={r['score']:>3}  tier={r['tier']:<8}  {flag}")
    print()
    print("BENIGN CONTROL SCRIPTS (false-positive check)")
    print("-" * 70)
    for r in control_rows:
        print(f"  {r['name']:<32} score={r['score']:>3}  tier={r['tier']:<8}")
    print()
    print("SUMMARY")
    print("-" * 70)
    print(f"  {n_high}/{n_scam} scam scripts reached HIGH or CRITICAL risk tier")
    print(f"  {n_before}/{n_scam} scam scripts reached HIGH/CRITICAL BEFORE the financial-demand line")
    print(f"  {n_low}/{n_ctrl} benign control scripts correctly stayed at LOW/MEDIUM (no false alarm)")


def _print_markdown(scam_rows, control_rows, n_high, n_before, n_low, n_scam, n_ctrl, backend):
    print(f"# Kavach Evaluation Results\n")
    print(f"_Backend: `{backend}` (offline TF-IDF lite matcher). Generated by "
          f"`tests/run_evaluation.py` -- reproducible, not hand-picked._\n")
    print("## Scam scripts\n")
    print("| Script | Final Score | Tier | Warned before money was asked? |")
    print("|---|---|---|---|")
    for r in scam_rows:
        mark = "Yes" if r["warned_before_money"] else "No"
        print(f"| {r['name']} | {r['score']} | {r['tier']} | {mark} |")
    print()
    print("## Benign control scripts (false-positive check)\n")
    print("| Script | Final Score | Tier |")
    print("|---|---|---|")
    for r in control_rows:
        print(f"| {r['name']} | {r['score']} | {r['tier']} |")
    print()
    print("## Summary\n")
    print(f"- **{n_high}/{n_scam}** scam scripts reached HIGH or CRITICAL risk tier")
    print(f"- **{n_before}/{n_scam}** scam scripts reached HIGH/CRITICAL *before* the financial-demand line")
    print(f"- **{n_low}/{n_ctrl}** benign control scripts correctly stayed at LOW/MEDIUM (no false alarm)")


if __name__ == "__main__":
    main()
