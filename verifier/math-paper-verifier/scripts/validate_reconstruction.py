#!/usr/bin/env python3
"""Validate reconstruction artifacts and input integrity without running workers."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "run"))
from reconstruction import check_inputs, check_pair, check_review, read_json, validate_plan, validate_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["plan", "result", "pair", "review"])
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--worker", choices=["a", "b"], help="required for result")
    args = parser.parse_args()
    try:
        run = args.run.expanduser().absolute()
        if args.kind == "plan":
            meta = check_inputs(run, "plan")
            validate_plan(read_json(run / "plan.json"), meta["scope"])
            print("Plan structure and input hashes are valid; target completeness is not proven.")
        elif args.kind == "result":
            if not args.worker:
                parser.error("result requires --worker a|b")
            meta = check_inputs(run, "pair")
            worker = run / args.worker
            tracked = {item["path"][2:] for item in meta["staged_files"]
                       if item["path"].startswith(f"{args.worker}/input/")}
            validate_result(read_json(worker / "result.json"), meta["target_id"], worker, tracked)
            print("Result structure and input hashes are valid; mathematics has not been adjudicated.")
        else:
            result = check_review(run) if args.kind == "review" else check_pair(run)
            print(json.dumps(result, indent=2))
            return 2 if result["status"] == "incomplete" else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
