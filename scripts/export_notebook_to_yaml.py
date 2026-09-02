"""Export Gastroenterology Teaching Coach Notebook to YAML and NotebookLM Source Format."""

import json
from pathlib import Path
from typing import Any
import yaml


def export_notebook_to_yaml(
    notebook_path: Path, output_yaml_path: Path, output_md_path: Path | None = None
) -> None:
    """Parses Jupyter notebook cells and generates structured YAML and Markdown for NotebookLM."""
    with notebook_path.open(encoding="utf-8") as f:
        nb = json.load(f)

    # Structured dictionary representing the teaching coach knowledge base
    doc: dict[str, Any] = {
        "metadata": {
            "title": "Teaching Coach: Gastroenterología y Semiótica Digestiva (Semana 11)",
            "subject": "Colitis Ulcerosa: Semiología, Extensión y Gravedad",
            "institution": "Universidad Central del Ecuador - HCAM",
            "semester": "2026-2",
            "target_session": {
                "week": 11,
                "date": "2026-09-02",
                "time": "16:00-17:30",
                "location": "Aula Lúdica, HCAM",
            },
            "source_notebook": notebook_path.name,
            "total_cells": len(nb.get("cells", [])),
        },
        "syllabus_summary": {
            "course": "Gastroenterología y Semiótica Digestiva",
            "evaluation_rubric_20pts": {
                "anamnesis_semiotica": 6,
                "examen_fisico_abdominal": 6,
                "razonamiento_sindromico": 4,
                "plan_diagnostico_referencias": 4,
            },
            "active_week": 11,
            "topic": "Enfermedad Inflamatoria Intestinal I: Colitis Ulcerosa",
        },
        "clinical_guide": {
            "learning_outcomes": [
                "Reconocer el patrón clínico que hace sospechar colitis ulcerosa.",
                "Excluir causas infecciosas (incluyendo C. difficile) antes de confirmar EII.",
                "Diferenciar extensión anatómica (Montreal) de actividad clínica (Truelove-Witts).",
                "Identificar colitis ulcerosa aguda grave (CUAG) como urgencia médica.",
                "Comparar de forma integral colitis ulcerosa frente a enfermedad de Crohn.",
            ],
            "montreal_classification": [
                {
                    "category": "E1",
                    "name": "Proctitis Ulcerosa",
                    "extent": "Limitada estrictamente al recto.",
                    "clinical_notes": (
                        "Predomina sangrado rectal, urgencia y tenesmo; puede tener heces formes."
                    ),
                },
                {
                    "category": "E2",
                    "name": "Colitis Izquierda",
                    "extent": "Afectación distal al ángulo esplénico.",
                    "clinical_notes": (
                        "Diarrea sanguinolenta franca y dolor cólico en fosa ilíaca izquierda."
                    ),
                },
                {
                    "category": "E3",
                    "name": "Colitis Extensa / Pancolitis",
                    "extent": "Afectación proximal al ángulo esplénico hasta el ciego.",
                    "clinical_notes": (
                        "Afectación difusa, mayor superficie inflamada y riesgo de complicaciones."
                    ),
                },
            ],
            "truelove_witts_criteria_cuag": {
                "mandatory_stools_criterion": ">= 6 deposiciones con sangre al día",
                "systemic_toxicity_signs_min_1": [
                    "Temperatura > 37.8 °C",
                    "Frecuencia cardíaca > 90 lpm",
                    "Hemoglobina < 10.5 g/dL",
                    "VSG > 30 mm/h o PCR elevada (> 30 mg/L)",
                ],
                "clinical_urgency": (
                    "Hospitalización urgente, sigmoidoscopia flexible temprana sin preparación "
                    "agresiva, descarte de megacolon tóxico y valoración por Gastroenterología y Cirugía."
                ),
            },
            "differential_crohn_vs_cu": [
                {
                    "feature": "Distribución",
                    "colitis_ulcerosa": "Continua, ascendente desde el recto, limitada al colon",
                    "enfermedad_crohn": (
                        "Segmentaria, lesiones salteadas (skip lesions), boca al ano"
                    ),
                },
                {
                    "feature": "Profundidad",
                    "colitis_ulcerosa": "Mucosa y submucosa superficial",
                    "enfermedad_crohn": "Transmural (fístulas, abscesos, estenosis)",
                },
                {
                    "feature": "Pistas clínicas",
                    "colitis_ulcerosa": "Hematoquecia, urgencia, tenesmo",
                    "enfermedad_crohn": (
                        "Dolor en FID, enf. perianal, diarrea no siempre sanguinolenta"
                    ),
                },
            ],
        },
        "synthetic_clinical_case": {
            "vignette": (
                "Mujer de 27 años con 6 semanas de diarrea con moco y sangre viva, urgencia y "
                "tenesmo. En los últimos 2 días presenta 7 deposiciones sanguinolentas/día. "
                "T 38.0 °C, FC 104 lpm, PA 108/68 mmHg. Abdomen doloroso en marco cólico "
                "izquierdo sin defensa. Hb 10.2 g/dL, Leucocitos 12.800/mm³, PCR 48 mg/L. "
                "Antecedente de amoxicilina/clavulánico hace 4 semanas."
            ),
            "socratic_qa": [
                {
                    "step": 1,
                    "question": "Construya la Representación del Problema en una sola frase.",
                    "model_answer": (
                        "Mujer joven con diarrea sanguinolenta crónica agudizada, síndrome "
                        "disentérico/urgencia y repercusión sistémica (fiebre, taquicardia, anemia "
                        "leve), con antecedente de antibióticos."
                    ),
                },
                {
                    "step": 2,
                    "question": "¿Qué datos clínicos apoyan diarrea inflamatoria?",
                    "model_answer": (
                        "Hematoquecia macroscópica, moco, tenesmo, fiebre 38.0°C, taquicardia 104 "
                        "lpm, leucocitosis y PCR 48 mg/L."
                    ),
                },
                {
                    "step": 3,
                    "question": "¿Qué diagnósticos infecciosos deben descartarse obligatoriamente?",
                    "model_answer": (
                        "Infección por Clostridioides difficile (por antecedente antibiótico) y "
                        "bacterias invasivas (coprocultivo)."
                    ),
                },
                {
                    "step": 4,
                    "question": "¿Podemos asignar clasificación Montreal (E1-E3) solo con la clínica?",
                    "model_answer": (
                        "No. Montreal es anatómica y exige confirmación endoscópica e histológica."
                    ),
                },
                {
                    "step": 5,
                    "question": "¿Cumple criterios de Colitis Ulcerosa Aguda Grave (CUAG)?",
                    "model_answer": (
                        "Sí (7 deposiciones sanguinolentas/día + fiebre 38.0°C, FC 104 lpm, "
                        "Hb 10.2 g/dL y PCR elevada)."
                    ),
                },
                {
                    "step": 6,
                    "question": "¿Cuáles son las prioridades iniciales de manejo?",
                    "model_answer": (
                        "Hospitalización urgente, reposición hidroelectrolítica, Rx abdomen para "
                        "descartar megacolon tóxico, sigmoidoscopia flexible temprana y valoración "
                        "multidisciplinaria."
                    ),
                },
            ],
        },
        "exit_ticket": [
            {
                "id": 1,
                "question": "Combinación mínima para CUAG según Truelove y Witts",
                "answer": ">= 6 deposiciones con sangre/día + al menos 1 signo de toxicidad sistémica.",
            },
            {
                "id": 2,
                "question": "Infección obligada a descartar",
                "answer": "Clostridioides difficile.",
            },
            {
                "id": 3,
                "question": "Por qué no se define Montreal solo con síntomas",
                "answer": "Porque es una clasificación anatómica endoscópica/histológica.",
            },
        ],
        "references": [
            (
                "American College of Gastroenterology (ACG) Clinical Guideline Update: "
                "Ulcerative Colitis in Adults (2025)"
            ),
            "NICE NG130: Ulcerative colitis: management",
            (
                "Módulo de Gastroenterología: "
                "powersemiotics.com/medsemiotics/gastroenterologia/trastornos-intestinales.html"
            ),
        ],
    }

    output_yaml_path.parent.mkdir(parents=True, exist_ok=True)

    with output_yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"[OK] Exported YAML successfully to: {output_yaml_path.resolve()}")

    if output_md_path:
        sess = doc["metadata"]["target_session"]
        rubric = doc["syllabus_summary"]["evaluation_rubric_20pts"]
        cg = doc["clinical_guide"]
        tw = cg["truelove_witts_criteria_cuag"]
        case = doc["synthetic_clinical_case"]

        md_lines = [
            f"# {doc['metadata']['title']}",
            f"**Tema:** {doc['metadata']['subject']}",
            f"**Institución:** {doc['metadata']['institution']} | **Semestre:** {doc['metadata']['semester']}",
            f"**Sesión:** Semana {sess['week']} ({sess['date']}, {sess['time']}) - {sess['location']}",
            "\n---\n",
            "## 1. Sílabo y Rúbrica de Evaluación",
            f"- **Asignatura:** {doc['syllabus_summary']['course']}",
            "- **Rúbrica HCAM (sobre 20 puntos):**",
            f"  - Anamnesis Semiótica: {rubric['anamnesis_semiotica']} pts",
            f"  - Examen Físico Abdominal: {rubric['examen_fisico_abdominal']} pts",
            f"  - Razonamiento Sindrómico: {rubric['razonamiento_sindromico']} pts",
            f"  - Plan Diagnóstico y Referencias: {rubric['plan_diagnostico_referencias']} pts",
            "\n## 2. Guía Clínica y Criterios Diagnósticos",
            "### Resultados de Aprendizaje:",
        ]
        for obj in cg["learning_outcomes"]:
            md_lines.append(f"- {obj}")

        md_lines.append("\n### Clasificación de Montreal (Extensión Anatómica):")
        for m in cg["montreal_classification"]:
            md_lines.append(f"- **{m['category']} ({m['name']}):** {m['extent']} — *{m['clinical_notes']}*")

        md_lines.append("\n### Criterios de Colitis Ulcerosa Aguda Grave (Truelove y Witts):")
        md_lines.append(f"- **Criterio obligatorio:** {tw['mandatory_stools_criterion']}")
        md_lines.append("- **Signos de toxicidad sistémica (al menos 1):**")
        for s in tw["systemic_toxicity_signs_min_1"]:
            md_lines.append(f"  - {s}")

        md_lines.append("\n## 3. Caso Clínico Central Sintético y Guía Socrática")
        md_lines.append(f"> **Viñeta:** {case['vignette']}\n")
        for qa in case["socratic_qa"]:
            md_lines.append(f"### Pregunta {qa['step']}: {qa['question']}")
            md_lines.append(f"**Respuesta modelo / Clave docente:** {qa['model_answer']}\n")

        md_lines.append("## 4. Ticket de Salida")
        for t in doc["exit_ticket"]:
            md_lines.append(f"{t['id']}. **{t['question']}:** {t['answer']}")

        md_lines.append("\n## 5. Referencias Docentes Verificadas")
        for r in doc["references"]:
            md_lines.append(f"- {r}")

        with output_md_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"[OK] Exported NotebookLM Markdown source to: {output_md_path.resolve()}")


if __name__ == "__main__":
    nb_file = Path("notebooks/coach_gastro_colitis_ulcerosa.ipynb")
    yaml_out = Path("exports/coach_gastro_colitis_ulcerosa.yaml")
    md_out = Path("exports/coach_gastro_colitis_ulcerosa_notebooklm.md")
    export_notebook_to_yaml(nb_file, yaml_out, md_out)
