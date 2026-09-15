"""
Orchestrates the AI Assistant pipeline (PRD Section 16):

    question -> intent detection -> analytics query -> validated result
             -> structured response -> LLM explanation (or template fallback)

The LLM is given ONLY the already-computed structured result and is
instructed never to introduce numbers not present in it. Every response
includes the time period, filters used, the metrics/evidence backing it, and
limitations -- and explicitly states when there isn't enough data rather
than guessing.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ai.intent import ParsedIntent, parse_intent
from app.ai.llm_client import explain_with_llm, is_llm_available
from app.analytics.fingerprint import run_fingerprint_scan, scan_single_dimension
from app.analytics.metrics import compute_core_metrics
from app.analytics.rca import run_rca
from app.db.session import SessionLocal

SYSTEM_PROMPT = """You are the AI Analyst inside an internal UPI payment-failure intelligence \
platform. You are given a structured, already-validated analytics result. Your job is ONLY to \
explain it clearly in plain language for a Product Manager or Payment Ops audience.

Rules you must follow:
- Never state a number that is not present in the provided structured result.
- Never claim a finding is a "confirmed root cause" -- use "probable contributor" language, \
since this is correlation-based attribution, not a controlled experiment.
- If the structured result indicates insufficient data, say so plainly and do not speculate.
- Keep the explanation to 2-4 sentences.
- Do not mention that you are an AI model or discuss your own architecture."""


def _insufficient_data(intent: ParsedIntent, reason: str) -> dict:
    return {
        "intent": intent.intent,
        "time_period": intent.window_label,
        "filters": {},
        "metrics_used": [],
        "evidence": [],
        "limitations": reason,
        "answer": f"I don't have enough data to answer that for {intent.window_label}. {reason}",
        "deep_link": None,
        "llm_used": False,
    }


def _handle_psr_drop_reason(engine: Engine, intent: ParsedIntent) -> dict:
    rca = run_rca(engine, intent.window_start, intent.window_end, baseline_days=7)

    if not rca["anomaly"]:
        return {
            "intent": intent.intent,
            "time_period": intent.window_label,
            "filters": {},
            "metrics_used": ["observed_psr", "baseline_psr"],
            "evidence": [],
            "limitations": "No statistically/business-significant PSR anomaly was detected in this window.",
            "answer": (
                f"PSR for {intent.window_label} was {rca['observed_psr']}%, close to the "
                f"baseline of {rca['baseline_psr']}% -- no significant anomaly was detected."
            ),
            "deep_link": f"/rca?start={intent.window_start.isoformat()}&end={intent.window_end.isoformat()}",
            "llm_used": False,
        }

    structured = {
        "observed_psr": rca["observed_psr"],
        "baseline_psr": rca["baseline_psr"],
        "psr_drop_pp": rca["psr_drop_pp"],
        "severity": rca["severity"],
        "affected_transactions": rca["affected_transactions"],
        "value_at_risk": rca["value_at_risk"],
        "top_fingerprint": rca["fingerprint"]["label"] if rca["fingerprint"] else None,
        "top_contribution_pct": rca["fingerprint"]["contribution_pct"] if rca["fingerprint"] else None,
    }

    answer = _explain(structured, f"Why did PSR drop for {intent.window_label}?", rca["ai_summary"])

    return {
        "intent": intent.intent,
        "time_period": intent.window_label,
        "filters": {},
        "metrics_used": ["observed_psr", "baseline_psr", "affected_transactions", "value_at_risk"],
        "evidence": rca["evidence"][:5],
        "limitations": rca["disclaimer"],
        "answer": answer,
        "deep_link": f"/rca?start={intent.window_start.isoformat()}&end={intent.window_end.isoformat()}",
        "llm_used": is_llm_available(),
    }


def _handle_top_bank_contributor(engine: Engine, intent: ParsedIntent) -> dict:
    bank_results = scan_single_dimension(engine, "payer_bank", intent.window_start, intent.window_end, baseline_days=7)

    if not bank_results:
        return _insufficient_data(intent, "No single bank showed a statistically significant failure-rate deviation in this window.")

    top = bank_results[0]
    structured = {
        "bank": top["dimensions"]["payer_bank"],
        "contribution_pct": top["contribution_pct"],
        "failure_rate_pct": top["observed_failure_rate_pct"],
        "baseline_failure_rate_pct": top["baseline_failure_rate_pct"],
        "volume": top["volume"],
    }
    answer = _explain(structured, "Which bank contributed most to failures?", None)

    return {
        "intent": intent.intent,
        "time_period": intent.window_label,
        "filters": {"payer_bank": top["dimensions"]["payer_bank"]},
        "metrics_used": ["contribution_pct", "observed_failure_rate_pct"],
        "evidence": [top],
        "limitations": "Based on observed correlation across single-bank segments only; not a causal claim.",
        "answer": answer,
        "deep_link": f"/failures?payer_bank={top['dimensions']['payer_bank']}",
        "llm_used": is_llm_available(),
    }


def _handle_top_fingerprint(engine: Engine, intent: ParsedIntent) -> dict:
    results = run_fingerprint_scan(engine, intent.window_start, intent.window_end, baseline_days=7)
    if not results:
        return _insufficient_data(intent, "No dimension combination met the significance thresholds for a fingerprint in this window.")

    top = results[0]
    structured = {
        "fingerprint_label": top["label"],
        "contribution_pct": top["contribution_pct"],
        "volume": top["volume"],
        "failure_rate_pct": top["observed_failure_rate_pct"],
        "value_at_risk": top["value_at_risk"],
    }
    answer = _explain(structured, "What was the biggest failure fingerprint?", None)

    return {
        "intent": intent.intent,
        "time_period": intent.window_label,
        "filters": top["dimensions"],
        "metrics_used": ["contribution_pct", "observed_failure_rate_pct", "value_at_risk"],
        "evidence": [top],
        "limitations": "Probable contributor based on observed correlation; not confirmed causal evidence.",
        "answer": answer,
        "deep_link": "/rca",
        "llm_used": is_llm_available(),
    }


def _handle_value_at_risk(engine: Engine, intent: ParsedIntent) -> dict:
    metrics = compute_core_metrics(engine, {"start_date": intent.window_start, "end_date": intent.window_end})
    if metrics["total_transactions"] == 0:
        return _insufficient_data(intent, "No transactions were recorded in this window.")

    structured = {
        "value_at_risk": metrics["value_at_risk"],
        "eligible_failed": metrics["eligible_failed"],
        "failure_rate_pct": metrics["failure_rate"],
    }
    answer = _explain(structured, "What is the estimated value at risk?", None)

    return {
        "intent": intent.intent,
        "time_period": intent.window_label,
        "filters": {},
        "metrics_used": ["value_at_risk", "eligible_failed"],
        "evidence": [structured],
        "limitations": "Value at risk reflects failed eligible transaction amounts; it is not a confirmed loss figure.",
        "answer": answer,
        "deep_link": "/failures",
        "llm_used": is_llm_available(),
    }


def _handle_intervention_effectiveness(intent: ParsedIntent) -> dict:
    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT intervention_id, type, hypothesis, actual_impact
                FROM interventions
                WHERE actual_impact IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """)
        ).mappings().first()
    finally:
        db.close()

    if not row:
        return _insufficient_data(intent, "No intervention has had its impact measured yet.")

    impact = row["actual_impact"]
    structured = {
        "intervention_type": row["type"],
        "psr_before": impact["before"]["psr"],
        "psr_after": impact["after"]["psr"],
        "psr_delta_pp": impact["delta"]["psr_pp"],
        "guardrail_status": impact["guardrail_status"],
    }
    answer = _explain(structured, "Did the intervention improve PSR?", None)

    return {
        "intent": intent.intent,
        "time_period": "the measured before/after windows for the most recent intervention",
        "filters": {"intervention_id": str(row["intervention_id"])},
        "metrics_used": ["psr_before", "psr_after", "psr_delta_pp", "guardrail_status"],
        "evidence": [structured],
        "limitations": "Reflects one measured before/after comparison, not a controlled A/B experiment.",
        "answer": answer,
        "deep_link": f"/interventions/{row['intervention_id']}",
        "llm_used": is_llm_available(),
    }


def _handle_general(engine: Engine, intent: ParsedIntent) -> dict:
    metrics = compute_core_metrics(engine, {"start_date": intent.window_start, "end_date": intent.window_end})
    if metrics["total_transactions"] == 0:
        return _insufficient_data(intent, "No transactions were recorded in this window.")

    structured = {
        "psr": metrics["psr"],
        "failure_rate": metrics["failure_rate"],
        "total_transactions": metrics["total_transactions"],
        "value_at_risk": metrics["value_at_risk"],
    }
    answer = _explain(structured, intent.raw_question, None)

    return {
        "intent": "general",
        "time_period": intent.window_label,
        "filters": {},
        "metrics_used": ["psr", "failure_rate", "value_at_risk"],
        "evidence": [structured],
        "limitations": "General summary; ask a more specific question (e.g. about a bank, fingerprint, or intervention) for deeper analysis.",
        "answer": answer,
        "deep_link": "/",
        "llm_used": is_llm_available(),
    }


def _explain(structured_result: dict, question: str, template_fallback: str | None) -> str:
    user_prompt = (
        f"Question: {question}\n\n"
        f"Validated structured result (the only numbers you may use):\n{structured_result}\n\n"
        "Explain this result in plain language for a Product Manager."
    )
    llm_answer = explain_with_llm(SYSTEM_PROMPT, user_prompt)
    if llm_answer:
        return llm_answer

    if template_fallback:
        return template_fallback

    parts = [f"{k.replace('_', ' ')}: {v}" for k, v in structured_result.items() if v is not None]
    return "Based on validated analytics -- " + "; ".join(parts) + "."


def analyze_question(engine: Engine, question: str) -> dict:
    intent = parse_intent(question)

    if intent.intent == "psr_drop_reason":
        result = _handle_psr_drop_reason(engine, intent)
    elif intent.intent == "top_bank_contributor":
        result = _handle_top_bank_contributor(engine, intent)
    elif intent.intent == "top_fingerprint":
        result = _handle_top_fingerprint(engine, intent)
    elif intent.intent == "value_at_risk":
        result = _handle_value_at_risk(engine, intent)
    elif intent.intent == "intervention_effectiveness":
        result = _handle_intervention_effectiveness(intent)
    else:
        result = _handle_general(engine, intent)

    result["question"] = question
    return result
