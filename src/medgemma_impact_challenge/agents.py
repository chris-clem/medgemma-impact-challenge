import re

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent

from medgemma_impact_challenge.callbacks import (
    aggregate_guideline_matches,
    aggregate_trial_matches,
    format_ct_report,
    format_patient_data,
    format_recommendation,
    format_validation_result,
    strip_for_context,
)
from medgemma_impact_challenge.config import (
    MAX_ITERATIONS,
)
from medgemma_impact_challenge.schemas import (
    CTReport,
    Guideline,
    GuidelineMatch,
    PatientData,
    Recommendation,
    Trial,
    TrialMatch,
    ValidationResult,
)
from medgemma_impact_challenge.utils import ModelType, load_prompt


def create_ct_image_analyzer(model: ModelType) -> LlmAgent:
    """Create the CTImageAnalyzer agent that analyzes CT scan images."""
    return LlmAgent(
        name="CTImageAnalyzer",
        model=model,
        instruction=load_prompt("00_CT_IMAGE_ANALYZER"),
        output_schema=CTReport,
        output_key="ct_report",
        after_agent_callback=format_ct_report,
    )


def create_patient_analyzer(model: ModelType) -> LlmAgent:
    """Create the PatientDataAnalyzer agent."""
    return LlmAgent(
        name="PatientDataAnalyzer",
        model=model,
        instruction=load_prompt("01_PATIENT_DATA_ANALYZER"),
        include_contents="none",
        before_model_callback=strip_for_context,
        output_schema=PatientData,
        output_key="patient_data",
        after_agent_callback=format_patient_data,
    )


def create_guideline_matcher(guideline: Guideline, model: ModelType) -> LlmAgent:
    """Create a guideline matcher agent for a specific guideline."""

    template = load_prompt("02_GUIDELINE_MATCHER")
    instruction = template.format(
        guideline_name=guideline.name,
        guideline_content=guideline.content,
    )

    guideline_slug = re.sub(r"[^a-z0-9]", "_", guideline.name.lower())[:50]

    return LlmAgent(
        name=f"GuidelineMatcher_{guideline_slug}",
        model=model,
        instruction=instruction,
        include_contents="none",
        before_model_callback=strip_for_context,
        output_schema=GuidelineMatch,
        output_key=f"guideline_match_{guideline_slug}",
    )


def create_trial_matcher(trial: Trial, model: ModelType) -> LlmAgent:
    """Create a trial matcher agent for a specific clinical trial."""

    template = load_prompt("03_TRIAL_MATCHER")
    instruction = template.format(
        trial=trial,
        trial_nct_id=trial.nct_id,
    )

    return LlmAgent(
        name=f"TrialMatcher_{trial.nct_id}",
        model=model,
        instruction=instruction,
        include_contents="none",
        before_model_callback=strip_for_context,
        output_schema=TrialMatch,
        output_key=f"trial_match_{trial.nct_id}",
    )


def create_recommender(model: ModelType) -> LlmAgent:
    """Create the TherapyRecommender agent."""
    return LlmAgent(
        name="TherapyRecommender",
        model=model,
        instruction=load_prompt("04_RECOMMENDER"),
        include_contents="none",
        before_model_callback=strip_for_context,
        output_schema=Recommendation,
        output_key="recommendation",
        after_agent_callback=format_recommendation,
    )


def create_validator(model: ModelType) -> LlmAgent:
    """Create the Validator agent."""
    return LlmAgent(
        name="Validator",
        model=model,
        instruction=load_prompt("05_VALIDATOR"),
        include_contents="none",
        before_model_callback=strip_for_context,
        output_schema=ValidationResult,
        output_key="validation_result",
        after_agent_callback=format_validation_result,
    )


def create_tumor_board_agent(
    guidelines: list[Guideline],
    trials: list[Trial],
    model: ModelType,
) -> SequentialAgent:
    """Create the complete tumor board agent.

    Args:
        guidelines: List of Guideline models
        trials: List of Trial models
        model: The model to use for all agents

    Returns:
        SequentialAgent representing the tumor board agent
    """
    # Create all sub-agents
    ct_image_analyzer = create_ct_image_analyzer(model=model)
    patient_analyzer = create_patient_analyzer(model=model)
    guideline_matchers = [create_guideline_matcher(g, model=model) for g in guidelines]
    trial_matchers = [create_trial_matcher(t, model=model) for t in trials]
    recommender = create_recommender(model=model)
    validator = create_validator(model=model)

    # Create ParallelAgents with callbacks to aggregate results
    guideline_matcher_parallel = ParallelAgent(
        name="GuidelineMatcherParallel",
        sub_agents=guideline_matchers,
        after_agent_callback=aggregate_guideline_matches,
    )

    trial_matcher_parallel = ParallelAgent(
        name="TrialMatcherParallel",
        sub_agents=trial_matchers,
        after_agent_callback=aggregate_trial_matches,
    )

    recommendation_loop = LoopAgent(
        name="RecommendationLoop",
        max_iterations=MAX_ITERATIONS,
        sub_agents=[recommender, validator],
    )

    net_tumorboard_agent = SequentialAgent(
        name="TumorBoardAgent",
        sub_agents=[
            ct_image_analyzer,
            patient_analyzer,
            guideline_matcher_parallel,
            trial_matcher_parallel,
            recommendation_loop,
        ],
    )

    return net_tumorboard_agent
