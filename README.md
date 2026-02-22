# Kaggle MedGemma Impact Challenge

Multi-agent tumor board recommendation system for neuroendocrine tumor (NET) patients using Google's Agent Development Kit (ADK).

**Competition**: <https://www.kaggle.com/competitions/med-gemma-impact-challenge/overview>

## Research Preview / Non-Clinical Use Disclaimer

This project is a research preview intended for experimentation and education. It is not designed, validated, or approved for clinical use, and must not be used to diagnose, treat, cure, mitigate, or prevent any disease, or to make clinical decisions. Model outputs may be incorrect, non-causal, outdated, or biased and should be treated as unverified information. Any use of this code, model outputs, or derived results is entirely at the user’s own risk.

## Write Up

[WRITEUP.md](WRITEUP.md)

## Download Guidelines

see Guidelines [README.md](data/guidelines/README.md)

## Model Deployment on GPU Server

```bash
uvx --from huggingface_hub hf auth login --token $HF_TOKEN
uvx vllm serve "google/medgemma-1.5-4b-it" --tensor-parallel-size=4 --swap-space=16 --gpu-memory-utilization=0.95 --max-model-len=65536 --max-num-seqs=16 --enable-chunked-prefill --enable-auto-tool-choice --tool-call-parser openai

```

## Run Pipeline

```bash
# Install dependencies
uv sync

# Run pipeline for a single patient
uv run python src/medgemma_impact_challenge/run.py --patient_id=1 --model_name=medgemma-27b-it

# Run for all patients
MODEL_NAME=medgemma-27b-it  # or medgemma-1.5-4b-it
for patient_id in 1 2 3; do
  uv run python src/medgemma_impact_challenge/run.py --patient_id=$patient_id --model_name=$MODEL_NAME
done

# Tumor board app (view patient data, CT scans, recommendations)
uv run gradio app.py

# Eval app (review agent request/response pairs from logs)
uv run gradio eval_app.py
```

## Architecture

```txt
App("tumor_board_app", context_cache_config=...)
└── SequentialAgent("NetTumorBoardAgent")
    ├── LlmAgent("PatientDataAnalyzer")           # CT images + text → structured PatientData
    ├── ParallelAgent("GuidelineMatcherParallel")  # Match against 9 ENET/ESMO guidelines
    │   └── after_agent_callback → aggregate_guideline_matches()
    ├── ParallelAgent("TrialMatcherParallel")      # Assess relevance for clinical trials
    │   └── after_agent_callback → aggregate_trial_matches()
    └── LoopAgent("RecommendationLoop", max_iterations=1)
        ├── LlmAgent("TherapyRecommender")         # Generate guideline-backed recommendation
        └── LlmAgent("Validator")                    # Safety and completeness review
```

## Pipeline Stages

| Stage | Agent                        | Input                               | Output                         |
| ----- | ---------------------------- | ----------------------------------- | ------------------------------ |
| 1     | PatientDataAnalyzer          | Clinical text + CT images           | `PatientData` schema           |
| 2     | GuidelineMatchers (parallel) | Patient data + guideline content    | `GuidelineMatch` per guideline |
| 3     | TrialMatchers (parallel)     | Patient data + trial criteria       | `TrialMatch` per trial         |
| 4     | TherapyRecommender           | Patient + guideline/trial summaries | `Recommendation` schema        |
| 5     | Validator                    | Recommendation + patient data       | Validation text                |

## Features

- **Multimodal input**: Processes CT scan images alongside clinical text
- **Context caching**: Guidelines cached for 30 minutes via `ContextCacheConfig` (Gemini models only)
- **Structured outputs**: Pydantic schemas with `output_schema` for type-safe data exchange
- **Parallel processing**: Guidelines and trials matched concurrently via `ParallelAgent`
- **Validation loop**: Recommendations reviewed for safety and completeness
- **vLLM support**: Run with local MedGemma via `LiteLlm` (`--use_vllm` flag)
- **External prompts**: Agent instructions stored as markdown templates in `data/prompts/`

## Project Structure

```txt
src/medgemma_impact_challenge/
├── config.py          # Configuration (model names, cache settings, vLLM config)
├── schemas.py         # Pydantic models (Patient, Trial, Guideline, PatientData, etc.)
├── utils.py           # Data loading, model resolution, multimodal input creation
├── agents.py          # Agent factory functions for all 5 agent types
├── callbacks.py       # State formatting and aggregation callbacks
├── app.py             # Gradio tumor board UI (patient data + recommendations)
├── eval_app.py        # Gradio eval UI (agent request/response review)
└── run.py             # CLI entry point
```

## Data Structure

```txt
data/
├── patients.json              # 3 patient cases with clinical history
├── trials.json                # Clinical trial data with publications
├── guidelines/md/             # 9 ENET/ESMO guidelines as markdown
│   ├── ESMO 2020 .../
│   ├── ENET 2022 .../
│   └── ENET 2023-2024 .../
├── ct-scans/                  # CT images by patient ID
│   ├── 1/
│   ├── 2/
│   └── 3/
└── prompts/                   # Agent instruction templates
    ├── 01_PATIENT_DATA_ANALYZER.md
    ├── 02_GUIDELINE_MATCHER.md
    ├── 03_TRIAL_MATCHER.md
    ├── 04_RECOMMENDER.md
    └── 05_VALIDATOR.md
```

## Development

```bash
# Lint and format
uv run ruff check . && uv run ruff format .

# Pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files
```
