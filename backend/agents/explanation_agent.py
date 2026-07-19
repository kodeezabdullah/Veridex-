"""Databricks Foundation Model explanation agent with MLflow tracing."""

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import mlflow
import requests
from dotenv import load_dotenv


MODEL_FALLBACK_CHAIN = [
    "databricks-meta-llama-3-3-70b-instruct",
]

REQUIRED_ROW_FIELDS = (
    "unique_id",
    "capability",
    "evidence_status",
    "trust_score",
    "trust_score_pct",
    "field_source",
    "text_span",
    "score",
    "richness_prior",
    "confirm_message",
)

UNCERTAIN_LANGUAGE = {
    "weak_signal": (
        "limited evidence suggests",
        "limited evidence indicates",
        "some evidence suggests",
        "some evidence indicates",
        "weak evidence suggests",
        "weak evidence indicates",
        "partial evidence suggests",
        "partial evidence indicates",
        "weak signal",
        "uncertain",
        "could not be independently confirmed",
        "not independently confirmed",
        "limited confidence",
        "low confidence",
    ),
    "no_signal": (
        "no signal",
        "did not find",
        "could not find",
        "not find any",
        "no evidence",
        "no indication",
        "could not be confirmed",
        "cannot be confirmed",
        "unresolved",
        "no-call",
        "lack of evidence",
        "absence of evidence",
    ),
}

OVERCONFIDENT_LANGUAGE = (
    "high confidence",
    "definitely",
    "clearly proves",
    "is confirmed",
    "is verified",
    "certainly",
)


class ExplanationValidationError(ValueError):
    """Raised when a model response violates planner-facing output rules."""


def _configure_mlflow() -> None:
    """Use an explicit local file store unless a tracking URI is configured."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
        tracking_uri = (Path(__file__).resolve().parents[2] / "mlruns").as_uri()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)


def _validate_input(row: dict, validator_flags: list[dict]) -> None:
    missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
    if missing:
        raise ValueError("Missing capability_evidence fields: " + ", ".join(missing))

    if row["evidence_status"] not in {
        "verified",
        "likely",
        "weak_signal",
        "no_signal",
    }:
        raise ValueError(f"Unsupported evidence_status: {row['evidence_status']}")

    for flag in validator_flags:
        if set(flag) != {"rule", "reason"}:
            raise ValueError(
                "Each validator flag must contain exactly 'rule' and 'reason'."
            )


def _build_prompt(row: dict, validator_flags: list[dict]) -> list[dict[str, str]]:
    status_guidance = {
        "verified": "Use verified/high-confidence language without overstating it.",
        "likely": "Use likely/moderate-confidence language, not certainty.",
        "weak_signal": (
            "Use explicitly uncertain language such as 'limited evidence suggests' "
            "or 'this could not be independently confirmed'."
        ),
        "no_signal": (
            "State that there is no signal or that the capability is unresolved; "
            "do not imply the capability exists."
        ),
    }[row["evidence_status"]]

    system_prompt = (
        "You explain healthcare facility evidence to a non-technical NGO planner. "
        "Use only the supplied evidence; never add facts or certainty. Return exactly "
        "3 plain-language sentences: (1) what was or was not found, naming in natural "
        "language which facility field the evidence came from and summarizing what that "
        "field says, with the evidence_status and trust_score_pct confidence; "
        "(2) explain every validator flag in plain language, or say no validator flags "
        "were raised; (3) reproduce confirm_message exactly. Do not use bullets, headings, "
        "or text after confirm_message."
    )
    user_payload = {
        "capability_evidence": row,
        "validator_flags": validator_flags,
        "confidence_instruction": status_guidance,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _extract_content(response_payload: dict) -> str:
    choices = response_payload.get("choices") or []
    if not choices:
        raise ExplanationValidationError("Foundation Model response had no choices.")

    content = choices[0].get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ]
        return "".join(text_parts).strip()
    raise ExplanationValidationError("Foundation Model response contained no text.")


def _check_confidence_language(explanation: str, evidence_status: str) -> None:
    """Explicitly reject confidence language stronger than the evidence status."""
    lowered = explanation.lower()

    if evidence_status in UNCERTAIN_LANGUAGE:
        if not any(
            phrase in lowered for phrase in UNCERTAIN_LANGUAGE[evidence_status]
        ):
            raise ExplanationValidationError(
                f"{evidence_status} output did not contain required uncertainty language."
            )
        forbidden = [phrase for phrase in OVERCONFIDENT_LANGUAGE if phrase in lowered]
        if forbidden:
            raise ExplanationValidationError(
                f"{evidence_status} output used overconfident language: "
                + ", ".join(forbidden)
            )
    elif evidence_status == "verified":
        if "verified" not in lowered and "high confidence" not in lowered:
            raise ExplanationValidationError(
                "verified output did not state its confidence level."
            )
    elif evidence_status == "likely":
        if "likely" not in lowered and "moderate confidence" not in lowered:
            raise ExplanationValidationError(
                "likely output did not state its confidence level."
            )
        forbidden = [
            phrase
            for phrase in ("definitely", "clearly proves", "certainly")
            if phrase in lowered
        ]
        if forbidden:
            raise ExplanationValidationError(
                "likely output used overconfident language: " + ", ".join(forbidden)
            )


def _validate_explanation(explanation: str, row: dict) -> None:
    if not explanation.endswith(row["confirm_message"]):
        raise ExplanationValidationError(
            "Explanation does not end with confirm_message exactly."
        )

    sentence_count = len(re.findall(r"[.!?](?:[\"']?)(?=\s|$)", explanation))
    if sentence_count not in (2, 3):
        raise ExplanationValidationError(
            f"Explanation must contain 2-3 sentences; found {sentence_count}."
        )

    _check_confidence_language(explanation, row["evidence_status"])


def _foundation_model_url(server_hostname: str, model: str) -> str:
    hostname = server_hostname.removeprefix("https://").removeprefix("http://")
    return f"https://{hostname}/serving-endpoints/{model}/invocations"


def _call_model(
    model: str,
    messages: list[dict[str, str]],
    row: dict,
    validator_flags: list[dict],
    server_hostname: str,
    token: str,
) -> tuple[str, float]:
    request_payload = {
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.1,
        "stream": False,
    }
    started = time.perf_counter()

    with mlflow.start_run(
        run_name=f"explanation-{model}",
        nested=mlflow.active_run() is not None,
    ):
        mlflow.log_params(
            {
                "model": model,
                "unique_id": str(row["unique_id"]),
                "capability": str(row["capability"]),
                "evidence_status": str(row["evidence_status"]),
            }
        )
        mlflow.log_dict(
            {
                "row": row,
                "validator_flags": validator_flags,
                "messages": messages,
            },
            "input.json",
        )

        try:
            response = requests.post(
                _foundation_model_url(server_hostname, model),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=90,
            )
            response.raise_for_status()
            response_payload: dict[str, Any] = response.json()
            latency = time.perf_counter() - started
            explanation = _extract_content(response_payload)

            mlflow.log_metric("latency_seconds", latency)
            mlflow.log_dict(response_payload, "raw_output.json")
            mlflow.set_tag("model_responded", "true")

            _validate_explanation(explanation, row)
            mlflow.log_dict(
                {"explanation": explanation, "validation": "passed"},
                "validated_output.json",
            )
            mlflow.set_tag("output_validation", "passed")
            return explanation, latency
        except Exception as error:
            latency = time.perf_counter() - started
            mlflow.log_metric("latency_seconds", latency)
            mlflow.log_dict(
                {"error_type": type(error).__name__, "error": str(error)},
                "error_output.json",
            )
            mlflow.set_tag("attempt_status", "failed")
            raise


def generate_explanation(row: dict, validator_flags: list[dict]) -> dict:
    """Generate and validate one planner explanation using the locked model."""
    _validate_input(row, validator_flags)
    load_dotenv()
    _configure_mlflow()

    server_hostname = os.getenv("DATABRICKS_SERVER_HOSTNAME")
    token = os.getenv("DATABRICKS_TOKEN")
    if not server_hostname or not token:
        return {
            "ok": False,
            "error": "Databricks Foundation Model credentials are unavailable.",
            "attempts": [],
        }

    messages = _build_prompt(row, validator_flags)
    model = MODEL_FALLBACK_CHAIN[0]
    try:
        explanation, latency = _call_model(
            model,
            messages,
            row,
            validator_flags,
            server_hostname,
            token,
        )
        return {
            "ok": True,
            "model": model,
            "latency_seconds": round(latency, 3),
            "explanation": explanation,
            "field_source": row["field_source"],
            "text_span": row["text_span"],
            "attempt_errors": [],
        }
    except Exception as error:
        return {
            "ok": False,
            "error": "Databricks Foundation Model endpoint failed.",
            "attempts": [
                {
                    "model": model,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            ],
        }
