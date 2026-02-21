import logging
from pathlib import Path

import gradio as gr

from medgemma_impact_challenge.config import DATA_DIR
from medgemma_impact_challenge.schemas import Recommendation
from medgemma_impact_challenge.utils import load_patient

# Custom CSS with Google Colors
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap');

.gradio-container {
    font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    max-width: 1600px !important;
    margin: 0 auto !important;
}

.header {
    text-align: center;
    padding: 3rem 2rem;
    background: #D2E3FC;
    border-radius: 12px;
    margin-bottom: 2rem;
    border: 2px solid #4285F4;
}
.header h1 { margin: 0; font-size: 2.5rem; font-weight: 500; color: #4285F4; }
.header p { margin: 0.5rem 0 0 0; color: #4285F4; }

button.primary { background: #4285F4 !important; }
button.primary:hover { background: #3367D6 !important; }

/* Shared card reset: Gradio applies elem_classes to both .block (outer) and .prose (inner).
   Style the outer wrapper, reset the inner to avoid box-in-box. */
.block.question-box, .block.recommendation-box, .block.patient-info-section,
.block.eval-request, .block.eval-response {
    border-radius: 8px !important;
    padding: 1rem !important;
    border: 1px solid #dadce0 !important;
    box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.15) !important;
}
.prose.question-box, .prose.recommendation-box, .prose.patient-info-section,
.prose.eval-request, .prose.eval-response {
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

/* App-specific cards */
.block.question-box { background: #FEEFC3 !important; border-left: 4px solid #FBBC04 !important; line-height: 1.6; }
.block.recommendation-box { background: #CEEAD6 !important; border-left: 4px solid #34A853 !important; line-height: 1.6; min-height: 400px; }
.block.patient-info-section { background: #D2E3FC !important; border-left: 4px solid #4285F4 !important; }

/* Eval-specific cards */
.block.eval-request, .block.eval-response { max-height: 80vh !important; overflow-y: auto !important; }
.block.eval-request { background: #D2E3FC !important; border-left: 4px solid #4285F4 !important; }
.block.eval-response { background: #CEEAD6 !important; border-left: 4px solid #34A853 !important; }
.prose.eval-request, .prose.eval-response { max-height: none !important; overflow: visible !important; }

.footer {
    text-align: center;
    padding: 2rem 1rem;
    color: #5f6368;
    font-size: 0.875rem;
    border-top: 1px solid #dadce0;
    margin-top: 2rem;
}
.footer-colors { display: inline-block; margin-top: 0.5rem; }
.footer-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin: 0 4px;
}
"""

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def find_latest_log(patient_id: int) -> Path | None:
    """Find the latest log file for a given patient ID."""
    logs_dir = DATA_DIR / "logs"
    if not logs_dir.exists():
        return None
    log_files = sorted(logs_dir.glob(f"run_p{patient_id}_*.log"))
    if not log_files:
        return None
    print(log_files[-1])
    return log_files[-1]


def parse_recommendation_from_log(log_path: Path) -> Recommendation | None:
    """Parse the Recommendation JSON from a log file.

    Handles two log formats:
    - Triple-quoted: text=\"\"\"{ ... }\"\"\"  (multi-line, used when text has special chars)
    - Single-quoted: text='{ ... }'  (single-line)
    """
    content = log_path.read_text(encoding="utf-8")

    # Find TherapyRecommender final event with actual content (not Content: None)
    marker = "Author: TherapyRecommender, Type: Event, Final: True, Content: parts=[Part("
    idx = content.find(marker)
    if idx == -1:
        logging.warning(f"No TherapyRecommender recommendation found in {log_path.name}")
        return None

    # The text block starts right after the marker line. Try triple-quoted first, then single-quoted.
    # Limit search to a reasonable window after the marker to avoid matching the Validator's text.
    search_window = content[idx : idx + 100]

    # Try triple-quoted format: text="""{...}"""
    triple_marker = 'text="""'
    triple_pos = search_window.find(triple_marker)
    if triple_pos != -1:
        abs_start = idx + triple_pos + len(triple_marker)
        json_end = content.find('"""', abs_start)
        if json_end != -1:
            json_str = content[abs_start:json_end].strip()
            return Recommendation.model_validate_json(json_str)

    # Try single-quoted format: text='{...}'
    single_marker = "text='"
    single_pos = search_window.find(single_marker)
    if single_pos != -1:
        abs_start = idx + single_pos + len(single_marker)
        # End pattern: closing quote before )] role='model'
        end_pattern = "'\n)] role='model'"
        json_end = content.find(end_pattern, abs_start)
        if json_end != -1:
            json_str = content[abs_start:json_end].strip()
            return Recommendation.model_validate_json(json_str)

    logging.warning(f"No text block found after TherapyRecommender marker in {log_path.name}")
    return None


def on_patient_select(patient_label: str) -> tuple:
    """Load patient data, CT images, and latest recommendation for display."""
    patient_id = int(patient_label.split()[-1])

    # Patient data (with imaging text for display)
    patient = load_patient(patient_id)
    clinical_info_md = patient.clinical_information.replace("\n", "\n\n")
    question_md = f"**{patient.question_for_tumorboard}**"

    # CT scan images
    ct_dir = DATA_DIR / "ct-scans" / str(patient_id)
    ct_images = [str(p) for p in sorted(ct_dir.iterdir()) if p.suffix.lower() in IMAGE_EXTENSIONS]

    # Parse latest log for recommendation
    log_path = find_latest_log(patient_id)
    if log_path is None:
        return (
            clinical_info_md,
            question_md,
            ct_images,
            "*No log files found for this patient.*",
            "",
        )

    recommendation = parse_recommendation_from_log(log_path)
    if recommendation is None:
        recommendation_md = "*No recommendation found in the latest log file.*"
    else:
        recommendation_md = str(recommendation)

    return clinical_info_md, question_md, ct_images, recommendation_md


def create_ui():
    """Create the Gradio UI for viewing tumor board recommendations."""

    with gr.Blocks(title="NET Tumor Board Agent") as demo:
        # Header
        gr.HTML("""
            <div class="header">
                <h1>NET Tumor Board Agent</h1>
                <p>Evidence-based treatment recommendations</p>
            </div>
        """)

        with gr.Row():
            # Left column: Patient Selection + Clinical Info + CT Scans
            with gr.Column(scale=2):
                gr.Markdown("### Patient Selection")
                patient_dropdown = gr.Dropdown(
                    choices=["Patient 1", "Patient 2", "Patient 3"],
                    value="Patient 1",
                )

                gr.Markdown("### Clinical Information")
                clinical_info_md = gr.Markdown(
                    elem_classes=["patient-info-section"],
                )

                gr.Markdown("### CT Scans")
                ct_gallery = gr.Gallery(
                    label="CT Scans",
                    columns=3,
                    rows=1,
                    height=350,
                )

            # Right column: Question + Recommendation
            with gr.Column(scale=3):
                gr.Markdown("### Question for Tumor Board")
                question_display_md = gr.Markdown(elem_classes=["question-box"])

                gr.Markdown("### Recommendation")
                recommendation_md = gr.Markdown(
                    elem_classes=["recommendation-box"],
                )

        # Footer
        gr.HTML("""
            <div class="footer">
                <p>NET Tumor Board Recommendation System</p>
                <div class="footer-colors">
                    <span class="footer-dot" style="background: #4285F4;"></span>
                    <span class="footer-dot" style="background: #EA4335;"></span>
                    <span class="footer-dot" style="background: #FBBC04;"></span>
                    <span class="footer-dot" style="background: #34A853;"></span>
                </div>
            </div>
        """)

        # Event handlers
        outputs = [clinical_info_md, question_display_md, ct_gallery, recommendation_md]

        patient_dropdown.change(
            fn=on_patient_select,
            inputs=[patient_dropdown],
            outputs=outputs,
        )

        demo.load(
            fn=on_patient_select,
            inputs=[patient_dropdown],
            outputs=outputs,
        )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(css=CUSTOM_CSS, share=True)
