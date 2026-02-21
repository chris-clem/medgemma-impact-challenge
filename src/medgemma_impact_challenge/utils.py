import json
import logging
from datetime import datetime
from typing import Union

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from medgemma_impact_challenge.config import (
    DATA_DIR,
    MEDGEMMA_MODELS,
    VLLM_API_BASE,
    VLLM_MAX_TOKENS,
)
from medgemma_impact_challenge.schemas import Guideline, Patient, Trial

ModelType = Union[str, BaseLlm]


def setup_logging(patient_id: int, model_name: str):
    """Configure logging with patient and model info in the log filename."""
    (DATA_DIR / "logs").mkdir(exist_ok=True)
    log_file = (
        DATA_DIR / "logs" / f"run_p{patient_id}_{model_name}_{datetime.now():%Y%m%d_%H%M%S}.log"
    )
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
        force=True,
    )
    for name in ("LiteLLM", "httpcore", "openai", "httpx", "asyncio", "google_genai", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def resolve_model(model_name: str) -> ModelType:
    """Return the appropriate model for the pipeline.

    Args:
        model_name: Model name. Gemini models are returned as-is (str).
                    MedGemma models are wrapped in a LiteLlm instance.

    Returns:
        Either the model name string or a LiteLlm wrapper.
    """
    if model_name in MEDGEMMA_MODELS:
        return LiteLlm(
            model=MEDGEMMA_MODELS[model_name],
            api_base=VLLM_API_BASE,
            max_tokens=VLLM_MAX_TOKENS,
        )
    return model_name


def load_patient(patient_id: int) -> Patient:
    """Load patient case from patients JSON file.

    Args:
        patient_id: Patient ID to load
    """
    patients_file = DATA_DIR / "patients.json"
    with patients_file.open() as f:
        patients = [Patient.model_validate(p) for p in json.load(f)]

    patient = next((p for p in patients if p.id == patient_id), None)
    if patient is None:
        raise ValueError(f"Patient with ID {patient_id} not found.")
    return patient


def load_guidelines() -> list[Guideline]:
    """Load guideline markdown files."""
    guidelines_dir = DATA_DIR / "guidelines" / "md"
    return [Guideline.from_path(p) for p in guidelines_dir.glob("*/*.md")]


def load_trials() -> list[Trial]:
    """Load clinical trials from trials.json."""
    trials_file = DATA_DIR / "trials.json"
    with trials_file.open() as f:
        return [Trial.model_validate(t) for t in json.load(f)]


def load_prompt(prompt_name: str) -> str:
    """Load an agent instruction prompt from markdown file."""
    prompt_file = DATA_DIR / "prompts" / f"{prompt_name}.md"
    return prompt_file.read_text(encoding="utf-8")


def create_ct_image_input(patient_id: int) -> list[types.Part]:
    """Create input with CT images only (no clinical text).

    Args:
        patient_id: Patient ID to load CT images for

    Returns:
        List of image Parts, or a text Part if no images are available
    """
    parts = []
    patient_ct_dir = DATA_DIR / "ct-scans" / str(patient_id)
    if patient_ct_dir.exists():
        image_extensions = [".jpg", ".jpeg", ".png"]
        for img_path in sorted(patient_ct_dir.iterdir()):
            if img_path.suffix.lower() in image_extensions:
                img_bytes = img_path.read_bytes()
                mime_type = (
                    "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                )
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
    if not parts:
        raise ValueError(f"No CT images found for patient {patient_id} in {patient_ct_dir}")
    return parts
