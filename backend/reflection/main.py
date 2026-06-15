#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from config import get_settings
from display import print_section
from llm import ZhipuClient
from database import create_transactions_db, execute_sql, get_schema
from workflow import generate_sql, refine_sql, refine_sql_external_feedback, run_sql_workflow

DEFAULT_QUESTION = "Which color of product has the highest total sales?"

def _resolve_db_path(path: str) -> str:
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent / db_path
    return str(db_path)


def cmd_init_db(args: argparse.Namespace) -> None:
    db_path = _resolve_db_path(args.db)
    create_transactions_db(db_path)


def cmd_schema(args: argparse.Namespace) -> None:
    db_path = _resolve_db_path(args.db)
    print_section("Database Schema", get_schema(db_path))


def cmd_generate(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = ZhipuClient(settings)
    db_path = _resolve_db_path(args.db)
    schema = get_schema(db_path)

    print_section("User Question", args.question)
    sql_v1 = generate_sql(
        args.question,
        schema,
        client=client,
        model=args.model or settings.zhipu_model_generation,
        temperature=settings.zhipu_temperature_generation,
    )
    print_section("SQL Query V1", sql_v1)

    df_v1 = execute_sql(sql_v1, db_path)
    print_section("SQL Output V1", df_v1)


def cmd_refine(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = ZhipuClient(settings)
    db_path = _resolve_db_path(args.db)
    schema = get_schema(db_path)

    print_section("User Question", args.question)
    sql_v1 = generate_sql(
        args.question,
        schema,
        client=client,
        model=args.model_generation or settings.zhipu_model_generation,
        temperature=settings.zhipu_temperature_generation,
    )
    print_section("SQL Query V1", sql_v1)

    df_v1 = execute_sql(sql_v1, db_path)
    print_section("SQL Output V1", df_v1)

    if args.mode == "text":
        feedback, sql_v2 = refine_sql(
            args.question,
            sql_v1,
            schema,
            client=client,
            model=args.model_evaluation or settings.zhipu_model_evaluation,
            temperature=settings.zhipu_temperature_evaluation,
        )
    else:
        feedback, sql_v2 = refine_sql_external_feedback(
            args.question,
            sql_v1,
            df_v1,
            schema,
            client=client,
            model=args.model_evaluation or settings.zhipu_model_evaluation,
            temperature=settings.zhipu_temperature_evaluation,
        )

    print_section("Feedback on V1", feedback)
    print_section("SQL Query V2", sql_v2)

    df_v2 = execute_sql(sql_v2, db_path)
    print_section("SQL Output V2", df_v2)


def cmd_run(args: argparse.Namespace) -> None:
    settings = get_settings()
    run_sql_workflow(
        _resolve_db_path(args.db),
        args.question,
        settings=settings,
        model_generation=args.model_generation,
        model_evaluation=args.model_evaluation,
        verbose=True,
    )


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="SQL reflection workflow powered by Zhipu GLM models.",
    )
    parser.add_argument(
        "--db",
        default=settings.default_db_path,
        help="Path to the SQLite database (default: products.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Create or reset products.db")
    init_db.set_defaults(func=cmd_init_db)

    schema = subparsers.add_parser("schema", help="Print database schema")
    schema.set_defaults(func=cmd_schema)

    generate = subparsers.add_parser("generate", help="Generate SQL V1 only")
    generate.add_argument("--question", "-q", default=DEFAULT_QUESTION)
    generate.add_argument("--model", help="Zhipu model for SQL generation")
    generate.set_defaults(func=cmd_generate)

    refine = subparsers.add_parser("refine", help="Generate V1 then refine to V2")
    refine.add_argument("--question", "-q", default=DEFAULT_QUESTION)
    refine.add_argument(
        "--mode",
        choices=("text", "external"),
        default="external",
        help="text = reflect on SQL only; external = reflect with query output",
    )
    refine.add_argument("--model-generation", help="Zhipu model for SQL generation")
    refine.add_argument("--model-evaluation", help="Zhipu model for reflection")
    refine.set_defaults(func=cmd_refine)

    run = subparsers.add_parser("run", help="Run the full reflection workflow")
    run.add_argument("--question", "-q", default=DEFAULT_QUESTION)
    run.add_argument("--model-generation", help="Zhipu model for SQL generation")
    run.add_argument("--model-evaluation", help="Zhipu model for reflection")
    run.set_defaults(func=cmd_run)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
