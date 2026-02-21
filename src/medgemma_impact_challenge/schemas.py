import re
from pathlib import Path

from pydantic import BaseModel, Field


class Patient(BaseModel):
    """Patient case loaded from patients.json."""

    id: int = Field(alias="ID")
    clinical_information: str
    question_for_tumorboard: str

    def __str__(self) -> str:
        return (
            f"#### Clinical Information\n{self.clinical_information}\n\n"
            f"#### Question for Tumor Board\n{self.question_for_tumorboard}"
        )


class Guideline(BaseModel):
    """Clinical guideline loaded from markdown files."""

    path: Path
    name: str

    @classmethod
    def from_path(cls, p: Path) -> "Guideline":
        return cls(path=p, name=p.parent.name)

    @property
    def content(self) -> str:
        return self.path.read_text()

    def __str__(self) -> str:
        return f"{self.name}\n\n{self.content}"


class Publication(BaseModel):
    """Publication associated with a clinical trial."""

    citation: str
    pmid: str = ""
    type: str = ""  # "RESULT" or "DERIVED"

    def __str__(self) -> str:
        return f"[{self.type}] {self.citation}"


class Trial(BaseModel):
    """Clinical trial loaded from trials.json."""

    nct_id: str
    title: str = ""
    phase: str = ""
    status: str = ""
    condition: str = ""
    intervention: str = ""
    brief_summary: str = ""
    primary_outcome: str = ""
    secondary_outcome: str = ""
    start_date: str = ""
    completion_date: str = ""
    detailed_description: str = ""
    eligibility_criteria: str = ""
    publications: list[Publication] = Field(default_factory=list)
    publications_count: int = 0
    publication_analysis: dict | None = None

    def __str__(self) -> str:
        parts = [
            f"#### {self.nct_id}: {self.title}",
            f"- Phase: {self.phase}",
            f"- Status: {self.status}",
            f"- Condition: {self.condition}",
            f"- Intervention: {self.intervention}",
            f"- Brief Summary: {self.brief_summary}",
            f"- Primary Outcome: {self.primary_outcome}",
            f"- Secondary Outcome: {self.secondary_outcome}",
            f"- Start Date: {self.start_date}",
            f"- Completion Date: {self.completion_date}",
        ]
        if self.detailed_description:
            parts.append(f"- Detailed Description: {self.detailed_description}")
        parts.append(f"\n##### Eligibility Criteria\n{self.eligibility_criteria}")
        if self.publications:
            parts.append("\n##### Publications")
            for pub in self.publications:
                parts.append(f"- {pub}")
        if self.publication_analysis:
            abstracts = self._extract_abstracts()
            if abstracts:
                parts.append("\n##### Publication Abstracts")
                parts.extend(f"- {a}" for a in abstracts)
        return "\n".join(parts)

    def _extract_abstracts(self) -> list[str]:
        """Extract publication abstracts from nested publication_analysis."""
        abstracts = []
        if not self.publication_analysis:
            return abstracts
        online = self.publication_analysis.get("online_search_results", {})
        for source in ["pubmed", "onclive"]:
            source_data = online.get(source, {})
            key = "publications" if source == "pubmed" else "articles"
            for item in source_data.get(key, []):
                abstract = item.get("abstract_text", "")
                title = item.get("title", "")
                if abstract and title:
                    abstracts.append(f"{title}: {abstract[:500]}")
        return abstracts


class CTFinding(BaseModel):
    """Findings from a single CT image."""

    image_index: int  # 1-based index of the image
    anatomical_region: str  # e.g., "upper abdomen", "pelvis"
    findings: list[str]  # individual observations
    impression: str  # brief summary of this image


class CTReport(BaseModel):
    """Structured CT scan report from image analysis."""

    num_images_analyzed: int
    per_image_findings: list[CTFinding]
    overall_impression: str
    primary_tumor_description: str
    metastatic_findings: str
    other_notable_findings: str

    def __str__(self) -> str:
        parts = [
            f"#### CT Scan Report ({self.num_images_analyzed} images analyzed)",
            f"- Overall Impression: {self.overall_impression}",
            f"- Primary Tumor: {self.primary_tumor_description}",
            f"- Metastatic Findings: {self.metastatic_findings}",
            f"- Other Notable Findings: {self.other_notable_findings}",
        ]
        if self.per_image_findings:
            parts.append("\nPer-Image Findings:")
            for finding in self.per_image_findings:
                parts.append(f"  Image {finding.image_index} ({finding.anatomical_region}):")
                for f in finding.findings:
                    parts.append(f"    - {f}")
                parts.append(f"    Impression: {finding.impression}")
        return "\n".join(parts)


class PatientData(BaseModel):
    """Structured patient information extracted from clinical text and imaging."""

    tumor_type: str  # e.g., "small intestine NET G2"
    tumor_grade: str  # G1, G2, G3
    tumor_location: str  # e.g., "small intestine (ileocecal)"
    differentiation_status: (
        str  # "well-differentiated (NET)", "poorly-differentiated (NEC)", or "unknown"
    )
    metastases: list[str]  # e.g., ["liver", "lymph nodes (mesenteric)"]
    pathology_details: str  # Ki-67, mitotic count, IHC, biopsy findings, relevant labs
    sstr_expression_status: (
        str  # e.g., "high on Ga-68 PET/CT", "low on SSTR PET/CT", or "not assessed"
    )
    imaging_findings: list[str]  # one per study with date and modality
    surgical_history: list[str]  # e.g., ["Ileocecal resection with lymphadenectomy (05/2018)"]
    prior_treatments: list[str]  # non-surgical treatments with dates
    current_clinical_status: str  # e.g., "progressive hepatic metastases on SSA"
    question: str  # the tumor board question

    def __str__(self) -> str:
        """Return formatted representation for use in LLM instructions."""
        parts = [
            f"- Tumor Type: {self.tumor_type}",
            f"- Tumor Grade: {self.tumor_grade}",
            f"- Tumor Location: {self.tumor_location}",
            f"- Differentiation: {self.differentiation_status}",
        ]
        if self.metastases:
            parts.append("- Metastases: " + ", ".join(self.metastases))
        else:
            parts.append("- Metastases: None")
        parts.append(f"- Pathology: {self.pathology_details}")
        parts.append(f"- SSTR Expression: {self.sstr_expression_status}")
        if self.imaging_findings:
            parts.append("- Imaging Findings:")
            parts.extend(f"  - {f}" for f in self.imaging_findings)
        if self.surgical_history:
            parts.append("- Surgical History:")
            parts.extend(f"  - {s}" for s in self.surgical_history)
        if self.prior_treatments:
            parts.append("- Prior Treatments (non-surgical):")
            parts.extend(f"  - {t}" for t in self.prior_treatments)
        else:
            parts.append("- Prior Treatments (non-surgical): None")
        parts.append(f"- Current Clinical Status: {self.current_clinical_status}")
        parts.append(f"- Question for Tumor Board: {self.question}")
        return "\n".join(parts)


class GuidelineMatch(BaseModel):
    """Relevant guideline findings."""

    guideline_name: str
    is_relevant: bool
    reason: str
    relevant_sections: list[str]

    def __str__(self) -> str:
        parts = [
            f"#### {self.guideline_name}",
            f"- Is Relevant: {self.is_relevant}",
            f"- Reason: {self.reason}",
        ]
        if self.relevant_sections:
            parts.append("- Relevant Sections:")
            parts.extend(f"  - {s}" for s in self.relevant_sections)
        return "\n".join(parts)


class TrialMatch(BaseModel):
    """Relevant trial findings."""

    trial_id: str
    is_relevant: bool
    reason: str
    relevant_sections: list[str]

    def __str__(self) -> str:
        parts = [
            f"#### Trial ID {self.trial_id}",
            f"- Is Relevant: {self.is_relevant}",
            f"- Reason: {self.reason}",
        ]
        if self.relevant_sections:
            parts.append("- Relevant Sections:")
            parts.extend(f"  - {s}" for s in self.relevant_sections)
        return "\n".join(parts)


def _add_line_breaks(text: str) -> str:
    """Insert markdown line breaks before numbered items like '1)', '2)', etc."""
    return re.sub(r"(?<=[.;]) (\d+)\)", r"\n\n\1)", text)


class ValidationResult(BaseModel):
    """Structured validation feedback from the Validator agent."""

    is_approved: bool
    acute_situation_check: str  # pass/fail + reasoning
    safety_check: str
    completeness_check: str
    evidence_accuracy_check: str
    biomarker_therapy_consistency_check: str = ""
    evidence_strength_check: str
    revision_instructions: str  # empty if approved, specific feedback if not

    def __str__(self) -> str:
        status = "APPROVED" if self.is_approved else "NEEDS REVISION"
        parts = [
            f"#### Validation: {status}",
            f"- Acute Situation: {self.acute_situation_check}",
            f"- Safety: {self.safety_check}",
            f"- Completeness: {self.completeness_check}",
            f"- Evidence Accuracy: {self.evidence_accuracy_check}",
            f"- Biomarker-Therapy Consistency: {self.biomarker_therapy_consistency_check}",
            f"- Evidence Strength: {self.evidence_strength_check}",
        ]
        if self.revision_instructions:
            parts.append(f"\n**Revision Instructions**: {self.revision_instructions}")
        return "\n".join(parts)


class Recommendation(BaseModel):
    """Final tumor board recommendation."""

    recommended_therapy: str
    rationale: str = Field(max_length=5000)
    guideline_support: list[str]
    relevant_trials: list[str]

    def __str__(self) -> str:
        parts = [
            f"#### Recommended Therapy\n{_add_line_breaks(self.recommended_therapy)}\n",
            f"#### Rationale\n{self.rationale}",
        ]
        if self.guideline_support:
            parts.append("\n#### Guideline Support")
            parts.extend(f"- {g}" for g in self.guideline_support)
        if self.relevant_trials:
            parts.append("\n#### Relevant Trials")
            parts.extend(f"- {t}" for t in self.relevant_trials)
            parts.extend("\n")
        return "\n".join(parts)
