import re
from pathlib import Path

import gradio as gr
from pydantic import BaseModel

from app import CUSTOM_CSS
from medgemma_impact_challenge.config import DATA_DIR
from medgemma_impact_challenge.schemas import (
    CTReport,
    GuidelineMatch,
    PatientData,
    Recommendation,
    TrialMatch,
    ValidationResult,
)

# Agent base type -> Pydantic schema for parsing responses
AGENT_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "CTImageAnalyzer": CTReport,
    "PatientDataAnalyzer": PatientData,
    "GuidelineMatcher": GuidelineMatch,
    "TrialMatcher": TrialMatch,
    "TherapyRecommender": Recommendation,
    "Validator": ValidationResult,
}

MAX_INTERACTIONS = 10

AGENT_NAME_RE = re.compile(r'Your internal name is "([^"]+)"')
RESPONSE_EVENT_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}).*"
    r"\[Event\] Author: (.+?), Type: Event, Final: True, Content: parts=\[Part\("
)


class AgentInteraction:
    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        iteration: int,
        system_instruction: str,
        response_json: str | None = None,
        response_parsed: str | None = None,
        char_offset: int = 0,
    ):
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.iteration = iteration
        self.system_instruction = system_instruction
        self.response_json = response_json
        self.response_parsed = response_parsed
        self.char_offset = char_offset


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------


def get_agent_base_type(agent_name: str) -> str:
    for prefix in AGENT_SCHEMA_MAP:
        if agent_name == prefix or agent_name.startswith(prefix + "_"):
            return prefix
    return agent_name


def parse_request_blocks(log_content: str) -> list[dict]:
    blocks = []
    parts = log_content.split("\nLLM Request:\n")
    for i, part in enumerate(parts[1:], start=1):
        offset = sum(len(p) + len("\nLLM Request:\n") for p in parts[:i]) - len("\nLLM Request:\n")

        lines = part.split("\n")
        in_instruction = False
        instruction_lines: list[str] = []
        sep_count = 0
        for line in lines:
            if line.startswith("---"):
                sep_count += 1
                if sep_count == 1:
                    continue
                if sep_count == 2:
                    in_instruction = False
                    break
            elif sep_count == 1:
                if line == "System Instruction:":
                    in_instruction = True
                    continue
                if in_instruction:
                    instruction_lines.append(line)

        system_instruction = "\n".join(instruction_lines)
        name_match = AGENT_NAME_RE.search(system_instruction)
        if not name_match:
            continue

        agent_name = name_match.group(1)
        system_instruction = AGENT_NAME_RE.sub("", system_instruction).rstrip()

        blocks.append(
            {
                "agent_name": agent_name,
                "system_instruction": system_instruction,
                "char_offset": offset,
            }
        )
    return blocks


def parse_response_events(log_content: str) -> list[dict]:
    events = []
    for m in RESPONSE_EVENT_RE.finditer(log_content):
        timestamp = m.group(1)
        agent_name = m.group(2)
        event_start = m.end()

        search_window = log_content[event_start : event_start + 200]
        json_str = None

        triple_marker = 'text="""'
        triple_pos = search_window.find(triple_marker)
        if triple_pos != -1:
            abs_start = event_start + triple_pos + len(triple_marker)
            json_end = log_content.find('"""', abs_start)
            if json_end != -1:
                json_str = log_content[abs_start:json_end].strip()
        else:
            single_marker = "text='"
            single_pos = search_window.find(single_marker)
            if single_pos != -1:
                abs_start = event_start + single_pos + len(single_marker)
                end_pattern = "'\n)] role='model'"
                json_end = log_content.find(end_pattern, abs_start)
                if json_end != -1:
                    json_str = log_content[abs_start:json_end].strip()

        if json_str is None:
            continue

        events.append(
            {
                "agent_name": agent_name,
                "json_str": json_str,
                "timestamp": timestamp,
                "char_offset": m.start(),
            }
        )
    return events


def _to_markdown(text: str) -> str:
    """Convert schema __str__ output to proper markdown with line breaks.

    Adds trailing double-space to each non-empty, non-header line so that
    Markdown renders hard line breaks.
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
        elif stripped.startswith("#"):
            if result and result[-1] != "":
                result.append("")
            result.append(line)
        else:
            result.append(line + "  ")  # trailing spaces for <br>
    return "\n".join(result)


def parse_response_json(json_str: str, agent_base_type: str) -> str:
    schema_cls = AGENT_SCHEMA_MAP.get(agent_base_type)
    if schema_cls is None:
        return f"```json\n{json_str}\n```"
    try:
        instance = schema_cls.model_validate_json(json_str)
        return _to_markdown(str(instance))
    except Exception:
        # LLMs sometimes produce invalid escapes like \' in JSON - fix and retry
        try:
            fixed = json_str.replace("\\'", "'")
            instance = schema_cls.model_validate_json(fixed)
            return _to_markdown(str(instance))
        except Exception:
            return f"*(Schema parse failed, raw JSON)*\n```json\n{json_str}\n```"


def parse_log_file(log_path: Path) -> list[AgentInteraction]:
    content = log_path.read_text(encoding="utf-8")
    requests = parse_request_blocks(content)
    responses = parse_response_events(content)

    used_responses: set[int] = set()
    interactions: list[AgentInteraction] = []
    iteration_counts: dict[str, int] = {}

    for req in requests:
        agent_name = req["agent_name"]
        base_type = get_agent_base_type(agent_name)

        iteration_counts[agent_name] = iteration_counts.get(agent_name, 0) + 1
        iteration = iteration_counts[agent_name]

        matched_response = None
        for j, resp in enumerate(responses):
            if j in used_responses:
                continue
            if resp["agent_name"] == agent_name and resp["char_offset"] > req["char_offset"]:
                matched_response = resp
                used_responses.add(j)
                break

        response_json = matched_response["json_str"] if matched_response else None
        response_parsed = parse_response_json(response_json, base_type) if response_json else None

        interactions.append(
            AgentInteraction(
                agent_name=agent_name,
                agent_type=base_type,
                iteration=iteration,
                system_instruction=req["system_instruction"],
                response_json=response_json,
                response_parsed=response_parsed,
                char_offset=req["char_offset"],
            )
        )

    return interactions


# ---------------------------------------------------------------------------
# Log file discovery
# ---------------------------------------------------------------------------


def list_log_files() -> list[str]:
    logs_dir = DATA_DIR / "logs"
    if not logs_dir.exists():
        return []
    return [p.name for p in sorted(logs_dir.glob("run_*.log"), reverse=True)]


# ---------------------------------------------------------------------------
# Feedback I/O
# ---------------------------------------------------------------------------


def get_feedback_path(log_path: Path) -> Path:
    return log_path.with_name(log_path.stem + "_feedback.txt")


def load_feedback(log_path: Path) -> dict[str, str]:
    fb_path = get_feedback_path(log_path)
    if not fb_path.exists():
        return {}
    content = fb_path.read_text(encoding="utf-8")
    feedback: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in content.split("\n"):
        m = re.match(r"^=== (.+) ===$", line)
        if m:
            if current_key is not None:
                feedback[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)
    if current_key is not None:
        feedback[current_key] = "\n".join(current_lines).strip()
    return feedback


def save_feedback(log_path: Path, feedback: dict[str, str]) -> None:
    fb_path = get_feedback_path(log_path)
    lines: list[str] = []
    for key, value in feedback.items():
        lines.append(f"=== {key} ===")
        lines.append(value)
        lines.append("")
    fb_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def create_eval_ui() -> gr.Blocks:
    with gr.Blocks(title="NET Tumor Board Eval") as demo:
        log_path_state = gr.State(value=None)

        # Header
        gr.HTML("""
            <div class="header">
                <h1>NET Tumor Board Eval</h1>
                <p>Review agent request/response pairs</p>
            </div>
        """)

        # Controls
        with gr.Row():
            log_files = list_log_files()
            log_dropdown = gr.Dropdown(
                choices=log_files,
                value=log_files[0] if log_files else None,
                label="Log File",
                scale=3,
            )
        # Pre-allocate interaction cards
        headers = []
        instructions = []
        responses = []
        feedbacks = []

        for _ in range(MAX_INTERACTIONS):
            header_md = gr.Markdown()
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### LLM Request")
                    instruction_md = gr.Markdown(
                        elem_classes=["eval-request"],
                    )
                with gr.Column(scale=1):
                    gr.Markdown("### LLM Response")
                    response_md = gr.Markdown(
                        elem_classes=["eval-response"],
                    )
                    feedback_tb = gr.Textbox(
                        label="Feedback",
                        placeholder="Type your feedback for this agent...",
                        lines=2,
                    )

            headers.append(header_md)
            instructions.append(instruction_md)
            responses.append(response_md)
            feedbacks.append(feedback_tb)

        save_btn = gr.Button("Save All Feedback", variant="primary")
        save_status = gr.Markdown()

        # Footer
        gr.HTML("""
            <div class="footer">
                <p>NET Tumor Board Evaluation</p>
                <div class="footer-colors">
                    <span class="footer-dot" style="background: #4285F4;"></span>
                    <span class="footer-dot" style="background: #EA4335;"></span>
                    <span class="footer-dot" style="background: #FBBC04;"></span>
                    <span class="footer-dot" style="background: #34A853;"></span>
                </div>
            </div>
        """)

        # --- Event handlers ---

        def on_log_select(log_filename):
            if not log_filename:
                return [None, "", "", ""] + [
                    gr.update(visible=False),
                    "",
                    "",
                    "",
                    "",
                ] * MAX_INTERACTIONS

            log_path = DATA_DIR / "logs" / log_filename
            interactions = parse_log_file(log_path)
            existing_feedback = load_feedback(log_path)

            outputs: list = [str(log_path)]

            for i in range(MAX_INTERACTIONS):
                if i < len(interactions):
                    inter = interactions[i]
                    key = f"{inter.agent_name}:{inter.iteration}"
                    fb = existing_feedback.get(key, "")
                    iter_label = f" (Iteration {inter.iteration})" if inter.iteration > 1 else ""
                    outputs.extend(
                        [
                            f"## Step {i}: {inter.agent_name}{iter_label} Agent",
                            inter.system_instruction,
                            inter.response_parsed or "*No response captured*",
                            fb,
                        ]
                    )
                else:
                    outputs.extend(
                        [
                            "",
                            "",
                            "",
                            "",
                        ]
                    )

            return outputs

        all_outputs = [log_path_state]
        for i in range(MAX_INTERACTIONS):
            all_outputs.extend([headers[i], instructions[i], responses[i], feedbacks[i]])

        log_dropdown.change(
            fn=on_log_select,
            inputs=[log_dropdown],
            outputs=all_outputs,
        )

        def on_save_feedback(log_path_str, *feedback_values):
            if not log_path_str:
                return "No log file selected."
            log_path = Path(log_path_str)
            interactions = parse_log_file(log_path)
            feedback: dict[str, str] = {}
            for i, inter in enumerate(interactions):
                key = f"{inter.agent_name}:{inter.iteration}"
                value = feedback_values[i] if i < len(feedback_values) else ""
                if value and value.strip():
                    feedback[key] = value.strip()
            save_feedback(log_path, feedback)
            return f"Feedback saved to `{get_feedback_path(log_path).name}`"

        save_btn.click(
            fn=on_save_feedback,
            inputs=[log_path_state] + feedbacks,
            outputs=[save_status],
        )

        # Load default log on startup
        demo.load(
            fn=on_log_select,
            inputs=[log_dropdown],
            outputs=all_outputs,
        )

    return demo


if __name__ == "__main__":
    demo = create_eval_ui()
    demo.launch(css=CUSTOM_CSS)
