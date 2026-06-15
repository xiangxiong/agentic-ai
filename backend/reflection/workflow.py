from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import Settings, get_settings
from display import print_section
from llm import ZhipuClient, parse_json_object
from database import execute_sql, get_schema


@dataclass
class WorkflowResult:
    question: str
    schema: str
    sql_v1: str
    df_v1: pd.DataFrame
    feedback: str
    sql_v2: str
    df_v2: pd.DataFrame


def generate_sql(
    question: str,
    schema: str,
    *,
    client: ZhipuClient,
    model: str,
    temperature: float,
) -> str:
    prompt = f"""
You are a SQL assistant. Given the schema and the user's question, write a SQL query for SQLite.

Schema:
{schema}

User question:
{question}

Respond with the SQL only.
""".strip()
    sql = client.chat(prompt, model=model, temperature=temperature)
    return sql.removeprefix("```sql").removesuffix("```").strip()


def refine_sql(
    question: str,
    sql_query: str,
    schema: str,
    *,
    client: ZhipuClient,
    model: str,
    temperature: float,
) -> tuple[str, str]:
    """Reflect on SQL text only (no execution output)."""
    prompt = f"""
You are a SQL reviewer and refiner.

User asked:
{question}

Original SQL:
{sql_query}

Table Schema:
{schema}

Step 1: Briefly evaluate if the SQL OUTPUT fully answers the user's question.
Step 2: If improvement is needed, provide a refined SQL query for SQLite.
If the original SQL is already correct, return it unchanged.

Return STRICT JSON with two fields:
{{
  "feedback": "<1-3 sentences explaining the gap or confirming correctness>",
  "refined_sql": "<final SQL to run>"
}}
""".strip()
    content = client.chat(prompt, model=model, temperature=temperature)
    return _parse_reflection(content, sql_query)


def refine_sql_external_feedback(
    question: str,
    sql_query: str,
    df_feedback: pd.DataFrame,
    schema: str,
    *,
    client: ZhipuClient,
    model: str,
    temperature: float,
) -> tuple[str, str]:
    """Reflect using actual SQL execution output as external feedback."""
    prompt = f"""
You are a SQL reviewer and refiner.

User asked:
{question}

Original SQL:
{sql_query}

SQL Output:
{df_feedback.to_markdown(index=False)}

Table Schema:
{schema}

Step 1: Briefly evaluate if the SQL output answers the user's question.
Step 2: If the SQL could be improved, provide a refined SQL query.
If the original SQL is already correct, return it unchanged.

Return a strict JSON object with two fields:
- "feedback": brief evaluation and suggestions
- "refined_sql": the final SQL to run
""".strip()
    content = client.chat(prompt, model=model, temperature=temperature)
    return _parse_reflection(content, sql_query)


def _parse_reflection(content: str, fallback_sql: str) -> tuple[str, str]:
    try:
        obj = parse_json_object(content)
        feedback = str(obj.get("feedback", "")).strip()
        refined_sql = str(obj.get("refined_sql", fallback_sql)).strip()
        if not refined_sql:
            refined_sql = fallback_sql
        return feedback, refined_sql
    except Exception:
        return content.strip(), fallback_sql


def run_sql_workflow(
    db_path: str,
    question: str,
    *,
    client: ZhipuClient | None = None,
    settings: Settings | None = None,
    model_generation: str | None = None,
    model_evaluation: str | None = None,
    verbose: bool = True,
) -> WorkflowResult:
    settings = settings or get_settings()
    client = client or ZhipuClient(settings)
    model_generation = model_generation or settings.zhipu_model_generation
    model_evaluation = model_evaluation or settings.zhipu_model_evaluation

    schema = get_schema(db_path)
    if verbose:
        print_section("Step 1 — Extract Database Schema", schema)

    sql_v1 = generate_sql(
        question,
        schema,
        client=client,
        model=model_generation,
        temperature=settings.zhipu_temperature_generation,
    )
    if verbose:
        print_section("Step 2 — Generate SQL (V1)", sql_v1)

    df_v1 = execute_sql(sql_v1, db_path)
    if verbose:
        print_section("Step 3 — Execute V1 (SQL Output)", df_v1)

    feedback, sql_v2 = refine_sql_external_feedback(
        question,
        sql_v1,
        df_v1,
        schema,
        client=client,
        model=model_evaluation,
        temperature=settings.zhipu_temperature_evaluation,
    )
    if verbose:
        print_section("Step 4 — Reflect on V1 (Feedback)", feedback)
        print_section("Step 4 — Refined SQL (V2)", sql_v2)

    df_v2 = execute_sql(sql_v2, db_path)
    if verbose:
        print_section("Step 5 — Execute V2 (Final Answer)", df_v2)

    return WorkflowResult(
        question=question,
        schema=schema,
        sql_v1=sql_v1,
        df_v1=df_v1,
        feedback=feedback,
        sql_v2=sql_v2,
        df_v2=df_v2,
    )
