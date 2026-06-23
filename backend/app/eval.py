from __future__ import annotations

import argparse
import sys

from app.eval_runner import (
    MissingLangSmithConfigError,
    print_local_report,
    run_langsmith_evaluation,
    run_local_evaluation,
    sync_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copilot tool routing evaluation")
    parser.add_argument(
        "--mode",
        choices=["langsmith", "local", "sync"],
        default="langsmith",
        help="langsmith: run LangSmith experiment; local: offline report; sync: upload dataset only",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="copilot-routing",
        help="LangSmith experiment prefix",
    )
    parser.add_argument(
        "--dataset-name",
        default=None,
        help="LangSmith dataset name (defaults to config/env)",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=2,
        help="Maximum concurrent eval requests for LangSmith mode",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing GOLDEN_DATASET to LangSmith before evaluation",
    )
    args = parser.parse_args()

    dataset_name = args.dataset_name
    try:
        if args.mode == "sync":
            dataset_id = sync_dataset(dataset_name=dataset_name) if dataset_name else sync_dataset()
            print(f"Dataset synced: {dataset_id}")
            return 0

        if args.mode == "local":
            report = run_local_evaluation()
            print_local_report(report)
            return 0 if report["passed_cases"] == report["total_cases"] else 1

        results = run_langsmith_evaluation(
            dataset_name=dataset_name,
            experiment_prefix=args.experiment_prefix,
            max_concurrency=args.max_concurrency,
            sync=not args.no_sync,
        )
        experiment_name = getattr(results, "experiment_name", None)
        if experiment_name:
            print(f"LangSmith experiment completed: {experiment_name}")
        else:
            print("LangSmith experiment completed.")
        return 0
    except MissingLangSmithConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
