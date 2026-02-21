from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from pydantic import BaseModel

from medgemma_impact_challenge.schemas import (
    CTReport,
    GuidelineMatch,
    PatientData,
    Recommendation,
    TrialMatch,
    ValidationResult,
)


def strip_for_context(callback_context: CallbackContext, llm_request: LlmRequest) -> None:
    """Remove 'For context:' messages injected by ADK's sequential agent state passing."""
    llm_request.contents = [
        c
        for c in llm_request.contents
        if not (
            c.role == "user"
            and c.parts
            and c.parts[0].text
            and c.parts[0].text.strip() == "For context:"
        )
    ]


def _format_state_value(
    callback_context: CallbackContext, key: str, schema: type[BaseModel]
) -> None:
    """Convert a dict in state to its formatted string representation."""
    value = callback_context.state.get(key)
    if value and isinstance(value, dict):
        callback_context.state[key] = str(schema.model_validate(value))


def format_ct_report(callback_context: CallbackContext) -> None:
    _format_state_value(callback_context, "ct_report", CTReport)


def format_patient_data(callback_context: CallbackContext) -> None:
    _format_state_value(callback_context, "patient_data", PatientData)


def format_recommendation(callback_context: CallbackContext) -> None:
    _format_state_value(callback_context, "recommendation", Recommendation)


def format_validation_result(callback_context: CallbackContext) -> None:
    _format_state_value(callback_context, "validation_result", ValidationResult)


def _collect_matches_from_state(state, prefix: str) -> list[dict]:
    """Collect all match dicts with given prefix from state."""
    state_dict = state.to_dict() if hasattr(state, "to_dict") else dict(state)

    matches = []
    for key, value in state_dict.items():
        if not key.startswith(prefix):
            continue
        if value is None:
            continue
        if isinstance(value, dict):
            matches.append(value)
        elif hasattr(value, "model_dump"):
            matches.append(value.model_dump())

    return matches


def _aggregate_matches(
    callback_context: CallbackContext,
    prefix: str,
    schema: type[BaseModel],
    summary_key: str,
    fallback: str,
) -> None:
    """Aggregate parallel match results into a summary string in state."""
    matches = _collect_matches_from_state(callback_context.state, prefix)
    relevant = [m for m in matches if m.get("is_relevant", False)]
    parts = [str(schema.model_validate(m)) for m in relevant]
    callback_context.state[summary_key] = "\n\n".join(parts) if parts else fallback


def aggregate_guideline_matches(callback_context: CallbackContext) -> None:
    _aggregate_matches(
        callback_context,
        "guideline_match_",
        GuidelineMatch,
        "guideline_matches_summary",
        "No relevant guidelines found.",
    )


def aggregate_trial_matches(callback_context: CallbackContext) -> None:
    _aggregate_matches(
        callback_context,
        "trial_match_",
        TrialMatch,
        "trial_matches_summary",
        "No relevant trials found.",
    )
