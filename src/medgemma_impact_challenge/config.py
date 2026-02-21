from pathlib import Path

import dotenv

dotenv.load_dotenv()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

MAX_ITERATIONS = 2

VLLM_API_BASE = "http://localhost:8000/v1"
VLLM_MAX_TOKENS = 8192

DEFAULT_MODEL = "gemini-3-flash-preview"
MEDGEMMA_MODELS = {
    "medgemma-1.5-4b-it": "hosted_vllm/google/medgemma-1.5-4b-it",
    "medgemma-27b-it": "hosted_vllm/google/medgemma-27b-it",
}
