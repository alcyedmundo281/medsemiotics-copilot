#!/usr/bin/env python3
"""Generador y preparador de material docente y guías clínicas para Neurología y Gastroenterología."""

import argparse
import sys
import yaml
from pathlib import Path

def prepare_material(course_code: str):
    course_code = course_code.upper()
    yaml_map = {
        "GASTRO": "config/syllabi/2026-2/silabo_gastroenterologia_v2.yaml",
        "NEURO": "config/syllabi/2026-2/silabo_neurologia_v2.yaml"
    }

    yaml_file = yaml_map.get(course_code)
    if not yaml_file or not Path(yaml_file).exists():
        print(f"[!] Curso no valido o archivo no encontrado: {course_code}")
        return

    with open(yaml_file, 'r', encoding='utf-8') as f:
        syllabus = yaml.safe_load(f)

    # Identificar la próxima clase activa (Semana 11)
    target_topic = None
    for t in syllabus['schedule_18_weeks']:
        if t.get('week') == 11:
            target_topic = t
            break

    if not target_topic:
        target_topic = syllabus['schedule_18_weeks'][10]

    title = target_topic['title']
    week = target_topic['week']
    date_str = target_topic['date']
    location = syllabus['course_info']['location']

    print("=" * 75)
    print(f"[+] PREPARANDO MATERIAL DOCENTE: {syllabus['course_info']['name']}")
    print(f"[*] Semana {week:02d} ({date_str}) | Tema: {title}")
    print(f"[*] Ubicacion: {location}")
    print("=" * 75)

    if course_code == "GASTRO":
        content = f"""# 🫁 GUÍA CLÍNICA & INFOGRAFÍA DIAGNÓSTICA: ENFERMEDAD INFLAMATORIA INTESTINAL I
## COLITIS ULCEROSA (CU) — CRITERIOS DE EXTENSIÓN DE MONTREAL Y ESCALA DE TRUELOVE-WITTS
**Cátedra de Gastroenterología y Semiótica Digestiva — Semestre 2026-2**
*Hospital de Especialidades Carlos Andrade Marín (HCAM) | {location}*
*Fecha de Clase: {date_str} (Miércoles 16:00 - 17:30)*

---

### 📌 1. DEFINICIÓN & FISIOPATOLOGÍA SEMIOLÓGICA
La **Colitis Ulcerosa (CU)** es una enfermedad inflamatoria crónica inmunomediada que afecta de forma continua y difusa la mucosa del colon y recto, comenzando invariablemente en el recto y extendiéndose proximalmente sin saltos (*skip lesions*).

---

### 🚨 2. TRÍADA SEMIOLÓGICA CARDINAL
1. **Diarrea Crónica Sanguinolenta (Rectorragia / Hematoquecia):** Presencia constante de moco, pus y sangre en heces (>4 semanas).
2. **Tenesmo Rectal y Pujo:** Sensación constante de evacuación incompleta por hiperreactividad y proctitis inflamatoria.
3. **Dolor Abdominal Cólico en Fosa Ilíaca Izquierda (FII):** Alivio parcial o nulo tras la defecación.

---

### 📊 3. CLASIFICACIÓN DE EXTENSIÓN DE MONTREAL

| Categoría | Extensión Anatómica | Hallazgo Clínico y Endoscópico |
| :--- | :--- | :--- |
| **E1: Proctitis Ulcerosa** | Limitada al recto (distal a la unión rectosigmoidea) | Tenesmo, pujo, sangrado rojo fresco, heces formadas con sangre |
| **E2: Colitis Izquierda** | Distal al ángulo esplénico | Diarrea sanguinolenta, dolor en FII, urgencia defecatoria |
| **E3: Pancolitis (Extensa)** | Proximal al ángulo esplénico (afecta ciego/íleon terminal) | Diarrea profusa, síndrome consuntivo, riesgo de megacolon tóxico |

---

### ⚖️ 4. ESTRATIFICACIÓN DE SEVERIDAD CLÍNICA (TRUELOVE & WITTS)

| Criterio Clínico | Leve | Moderada | Severa (Criterio de Ingreso HCAM) |
| :--- | :---: | :---: | :---: |
| **Deposiciones con sangre / día** | < 4 | 4 – 6 | **≥ 6 deposiciones profusas** |
| **Frecuencia cardíaca (FC)** | Normal (<90 lpm) | < 90 lpm | **> 90 lpm (Taquicardia)** |
| **Temperatura corporal** | Normal (<37.5 °C) | Normal / Febrícula | **> 37.8 °C (Fiebre)** |
| **Hemoglobina (Hb)** | > 11.5 g/dL | 10.5 – 11.5 g/dL | **< 10.5 g/dL (Anemia)** |
| **Velocidad de Sedimentación (VSG)** | < 20 mm/h | 20 – 30 mm/h | **> 30 mm/h o PCR > 45 mg/L** |

---

### 🌲 5. ÁRBOL DE DECISIÓN Y DISCRIMINACIÓN SEMIOLÓGICA

```mermaid
graph TD
    A["Paciente con Diarrea Crónica + Rectorragia (>4 semanas)"] --> B{"¿Descartar Infección?"}
    B -->|"Coprocultivo / Toxina C. difficile (+)"| C["Colitis Infecciosa / Pseudomembranosa"]
    B -->|"Coprocultivo Negativo + Calprotectina Fecal Elevada"| D{"Colonoscopía + Biopsia"}
    D -->|"Afectación continua, mucosa friable, solo recto-colon"| E["COLITIS ULCEROSA (CU)"]
    D -->|"Lesiones parcheadas, úlceras serpiginosas, íleon terminal, granulomas"| F["ENFERMEDAD DE CROHN"]
    
    E --> G{"Estratificación Truelove-Witts"}
    G -->|"Leve (<4 dep/día, afebril)"| H["Manejo Ambulatorio (5-ASA / Mesalazina)"]
    G -->|"Severa (≥6 dep/día + Taquicardia + Fiebre)"| I["Hospitalización HCAM + Corticoides IV + Vigilancia Megacolon"]
```

---

### 📝 6. RÚBRICA DE EVALUACIÓN PARA EL INFORME CLÍNICO (20 PUNTOS)
- **Criterio 1: Anamnesis Semiótica (6 pts):** Cronología de la diarrea, características de la rectorragia, tenesmo y síntomas B.
- **Criterio 2: Examen Físico y Estigmas Extraintestinales (6 pts):** Palpación de cuerda colónica, examen anorrectal, eritema nodoso, pioderma gangrenoso y uveítis.
- **Criterio 3: Estratificación y Diagnóstico Diferencial (4 pts):** Aplicación de Montreal y Truelove-Witts vs Crohn y colitis infecciosa.
- **Criterio 4: Plan Diagnóstico y Referencias (4 pts):** Calprotectina fecal, colonoscopía con biopsia y guías ECCO/ACG 2024.

---
🔗 **Módulo Interactivo:** [https://powersemiotics.com/medsemiotics/gastroenterologia/trastornos-intestinales.html](https://powersemiotics.com/medsemiotics/gastroenterologia/trastornos-intestinales.html)
"""
        out_path = Path("docs/guia_clinica_gastro_colitis_ulcerosa.md")
        out_path.write_text(content, encoding='utf-8')
        print(f"[OK] Guia clinica generada en: {out_path}")

        drive_gastro = Path(r"C:\Users\aetorres\Mi unidad (alcy.torres@powersemiotics.com)\Classroom\Gastroenterología HECAM")
        if drive_gastro.exists():
            (drive_gastro / "Guia_Clinica_Colitis_Ulcerosa.md").write_text(content, encoding='utf-8')
            print(f"[OK] Guia clinica sincronizada en Google Drive: {drive_gastro / 'Guia_Clinica_Colitis_Ulcerosa.md'}")

    elif course_code == "NEURO":
        content = f"""# 🧠 GUÍA CLÍNICA & INFOGRAFÍA DIAGNÓSTICA: TRASTORNOS DEL MOVIMIENTO II
## PARKINSONISMOS ATÍPICOS (PARKINSON PLUS) E HIPERCINESIAS (MDS 2024)
**Cátedra de Neurología Clínica y Semiótica Médica — Semestre 2026-2**
*Hospital de Especialidades Carlos Andrade Marín (HCAM) | {location}*
*Fecha de Clase: {date_str} (Martes 16:00 - 17:30)*

---

### 📌 1. BANDERAS ROJAS (RED FLAGS) DE LA MDS 2024 PARA PARKINSONISMO ATÍPICO
1. **Caídas precoces recurrentes:** En el primer año de evolución (altamente sugestivo de PSP).
2. **Pobre o nula respuesta a levodopa:** A dosis terapéuticas (>600-1000 mg/día).
3. **Disfunción autonómica grave y temprana:** Hipotensión ortostática severa, síncopes o incontinencia urinaria precoz (AMS).
4. **Parálisis supranuclear de la mirada vertical:** Especialmente hacia abajo (signo patognomónico de PSP).
5. **Apraxia, mioclonías corticales o fenómeno de miembro ajeno:** Asimetría marcada (DCB).
6. **Deterioro cognitivo y alucinaciones visuales precoces:** Fluctuaciones de alerta (Demencia por Cuerpos de Lewy - DCL).

---

### 📊 2. TABLA DIFERENCIAL DE PARKINSONISMOS ATÍPICOS (PARKINSON PLUS)

| Entidad Clínica | Fisiopatología / Proteína | Signos Semióticos Cardinales | Signo Clave en Neuroimagen (RMN) |
| :--- | :--- | :--- | :--- |
| **Parálisis Supranuclear Progresiva (PSP)** | Taupatía (4R-Tau) | Parálisis de mirada vertical inferior, caídas precoces, facies de asombro (*staring gaze*), retrocollis | **Signo del colibrí / Pingüino** (Atrofia del tegmento mesencefálico) |
| **Atrofia Multisistémica (AMS)** | Sinucleinopatía (Alfa-sinucleína) | Disautonomía grave, estridor laríngeo nocturno, ataxia cerebelosa (AMS-C) o parkinsonismo simétrico (AMS-P) | **Signo de la cruz de pan / Hot cross bun sign** (Protuberancia) |
| **Degeneración Corticobasal (DCB)** | Taupatía (4R-Tau) | Asimetría extrema, apraxia ideomotora, miembro ajeno (*alien limb*), distonía fija y mioclonías corticales | **Atrofia cortical asimétrica frontoparietal** |
| **Demencia por Cuerpos de Lewy (DCL)** | Sinucleinopatía | Deterioro cognitivo antes o dentro de 1 año del parkinsonismo, alucinaciones visuales complejas, hipersensibilidad a neurolépticos | Preservación del hipocampo vs Alzheimer |

---

### ⚡ 3. SEMIOLOGÍA DE LAS HIPERCINESIAS

- **Corea:** Movimientos involuntarios rápidos, arrítmicos, no predecibles, que fluyen de un grupo muscular a otro (Enfermedad de Huntington, corea de Sydenham).
- **Balismo / Hemibalismo:** Movimientos coreiformes proximales violentos, de gran amplitud, típicamente por lesión del **núcleo subtalámico de Luys** (ej. ACV isquémico).
- **Distonía:** Contracciones musculares sostenidas o intermitentes que causan posturas anormales, torsiones o movimientos repetitivos.
- **Tics:** Movimientos o vocalizaciones estereotipadas, precedidas por una urgencia premonitoria (*urge*) que se alivia al realizarlos.
- **Mioclonías:** Sacudidas breves y fulgurantes tipo choque eléctrico causadas por contracción muscular repentina (positivas) o pérdida repentina de tono (asterixis/mioclonías negativas).

---

### 🌲 4. ÁRBOL DE DECISIÓN DIAGNÓSTICA

```mermaid
graph TD
    A["Paciente con Síndrome Parkinsoniano (Bradicinesia + Rigidez)"] --> B{"¿Respuesta a Levodopa + Asimetría + Temblor de Reposo?"}
    B -->|"SÍ (Excelente respuesta)"| C["ENFERMEDAD DE PARKINSON IDIOPÁTICA (EPI)"]
    B -->|"NO / Pobre respuesta + Red Flags"| D{"Evaluar Fenotipo Dominante"}
    
    D -->|"Parálisis mirada vertical + Caídas tempranas"| E["PARÁLISIS SUPRANUCLEAR PROGRESIVA (PSP)"]
    D -->|"Hipotensión ortostática grave + Disautonomía + Estridor"| F["ATROFIA MULTISISTÉMICA (AMS)"]
    D -->|"Apraxia asimétrica severa + Fenómeno de Miembro Ajeno"| G["DEGENERACIÓN CORTICOBASAL (DCB)"]
    D -->|"Deterioro cognitivo precoz + Alucinaciones visuales"| H["DEMENCIA POR CUERPOS DE LEWY (DCL)"]
```

---

### 📝 5. RÚBRICA DE EVALUACIÓN PARA EL INFORME CLÍNICO (20 PUNTOS)
- **Criterio 1: Anamnesis Semiótica (6 pts):** Cronología de las caídas, respuesta a levodopa, síntomas disautonómicos y cognitivos.
- **Criterio 2: Examen Físico Neurológico (6 pts):** Motilidad ocular vertical, maniobras axiales, tono en rueda dentada vs espasticidad, apraxia y signos cerebelosos.
- **Criterio 3: Discriminación Sindrómica y Red Flags (4 pts):** Diagnóstico diferencial fundado entre PSP, AMS, DCB y EPI bajo criterios MDS 2024.
- **Criterio 4: Plan Diagnóstico y Referencias (4 pts):** RMN de encéfalo volumétrica, SPECT/DaTscan, plan terapéutico y guías MDS/AAN 2024.

---
🔗 **Módulo Interactivo:** [https://powersemiotics.com/medsemiotics/neurologia/trastornos-movimiento-2.html](https://powersemiotics.com/medsemiotics/neurologia/trastornos-movimiento-2.html)
"""
        out_path = Path("docs/guia_clinica_neuro_trastornos_movimiento_2.md")
        out_path.write_text(content, encoding='utf-8')
        print(f"[OK] Guia clinica generada en: {out_path}")

        drive_neuro = Path(r"C:\Users\aetorres\Mi unidad (alcy.torres@powersemiotics.com)\Classroom\Neurologia")
        if drive_neuro.exists():
            (drive_neuro / "Guia_Clinica_Trastornos_Movimiento_2.md").write_text(content, encoding='utf-8')
            print(f"[OK] Guia clinica sincronizada en Google Drive: {drive_neuro / 'Guia_Clinica_Trastornos_Movimiento_2.md'}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", default="NEURO", help="Codigo del curso (GASTRO o NEURO)")
    args = parser.parse_args()
    prepare_material(args.course)