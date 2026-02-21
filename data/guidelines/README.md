# Clinical Guidelines

This directory contains ENETS and ESMO clinical guidelines used by the guideline-matching agent. The full-text guideline files are not included in this repository due to copyright restrictions. Follow the instructions below to set them up.

## Setup

1. Download each PDF from the links below.
2. Place all PDFs into `data/guidelines/pdf/`.
3. Convert them to markdown using [marker](https://github.com/VikParuchuri/marker) or a similar tool:

```bash
for pdf in data/guidelines/pdf/*.pdf; do
    uv run marker_single "$pdf" data/guidelines/md/
done
```

The pipeline expects one subdirectory per guideline under `data/guidelines/md/`, each containing a `.md` file (and optionally extracted figures as `.jpeg`).

## Required Guidelines

### ENETS Guidance Papers (Journal of Neuroendocrinology, Wiley)

| Year | Title                                                                    | DOI                                                    |
| ---- | ------------------------------------------------------------------------ | ------------------------------------------------------ |
| 2022 | Carcinoid Syndrome and Carcinoid Heart Disease                           | [10.1111/jne.13146](https://doi.org/10.1111/jne.13146) |
| 2023 | Appendiceal Neuroendocrine Tumours (aNET)                                | [10.1111/jne.13332](https://doi.org/10.1111/jne.13332) |
| 2023 | Colorectal Neuroendocrine Tumours                                        | [10.1111/jne.13309](https://doi.org/10.1111/jne.13309) |
| 2023 | Digestive Neuroendocrine Carcinoma                                       | [10.1111/jne.13249](https://doi.org/10.1111/jne.13249) |
| 2023 | Functioning Pancreatic Neuroendocrine Tumour Syndromes                   | [10.1111/jne.13318](https://doi.org/10.1111/jne.13318) |
| 2023 | Gastroduodenal Neuroendocrine Tumours (NETs) G1-G3                       | [10.1111/jne.13306](https://doi.org/10.1111/jne.13306) |
| 2023 | Nonfunctioning Pancreatic Neuroendocrine Tumours                         | [10.1111/jne.13343](https://doi.org/10.1111/jne.13343) |
| 2024 | Management of Well-Differentiated Small Intestine Neuroendocrine Tumours | [10.1111/jne.13423](https://doi.org/10.1111/jne.13423) |

### ESMO Clinical Practice Guidelines (Annals of Oncology, Elsevier)

| Year | Title                                                                               | DOI                                                                          |
| ---- | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| 2020 | Gastroenteropancreatic Neuroendocrine Neoplasms: Diagnosis, Treatment and Follow-up | [10.1016/j.annonc.2020.03.304](https://doi.org/10.1016/j.annonc.2020.03.304) |
