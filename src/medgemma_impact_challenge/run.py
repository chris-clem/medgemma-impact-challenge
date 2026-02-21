import asyncio
import logging
import warnings

from fire import Fire
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from langfuse import get_client
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

from medgemma_impact_challenge.agents import create_tumor_board_agent
from medgemma_impact_challenge.config import DEFAULT_MODEL
from medgemma_impact_challenge.utils import (
    create_ct_image_input,
    load_guidelines,
    load_patient,
    load_trials,
    resolve_model,
    setup_logging,
)

warnings.filterwarnings("ignore")

# Tracing with langfuse
langfuse = get_client()

if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

GoogleADKInstrumentor().instrument()


async def run_tumor_board_async(patient_id: int, model_name: str):
    """Run the tumor board recommendation system for a given patient."""
    logging.info(f"Running tumor board for patient {patient_id}")

    # Model
    model = resolve_model(model_name=model_name)
    logging.info(f"Using model: {model}")

    # Data (load patient without CT imaging text — CT analysis comes from images)
    patient = load_patient(patient_id)
    guidelines = load_guidelines()
    trials = load_trials()

    # Create agent
    tumor_board_agent = create_tumor_board_agent(guidelines, trials, model=model)

    # Create session with pre-populated clinical info (without CT imaging text)
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="TumorBoardApp",
        user_id="user",
        session_id=f"patient_{patient_id}",
        state={"clinical_info": str(patient)},
    )
    app_name = session.app_name
    user_id = session.user_id
    session_id = session.id

    # Create runner
    runner = Runner(
        agent=tumor_board_agent,
        app_name=app_name,
        session_service=session_service,
    )

    # Create first message: CT images only (clinical text is in session state)
    input_parts = create_ct_image_input(patient_id)
    content = types.Content(role="user", parts=input_parts)

    # Run
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        logging.debug(
            f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}"
        )


def main(patient_id: int, model_name: str = DEFAULT_MODEL):
    """CLI entry point for running the tumor board recommendation system.

    Args:
        patient_id: The patient ID to process (1, 2, or 3)
        model_name: Model name (e.g. "gemini-3-flash-preview", "medgemma-1.5-4b-it")
    """
    setup_logging(patient_id, model_name)

    asyncio.run(run_tumor_board_async(patient_id=patient_id, model_name=model_name))


if __name__ == "__main__":
    Fire(main)
