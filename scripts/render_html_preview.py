"""Render standalone HTML preview for Gastroenterology Teaching Coach."""

from pathlib import Path


def render_html_preview(output_path: Path) -> None:
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Teaching Coach: Gastroenterología y Semiótica Digestiva (Semana 11)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #1e3a8a;
      --primary-light: #3b82f6;
      --primary-subtle: #eff6ff;
      --text-main: #0f172a;
      --text-muted: #475569;
      --bg-page: #f8fafc;
      --bg-card: #ffffff;
      --border-color: #e2e8f0;
      --danger-bg: #fee2e2;
      --danger-border: #ef4444;
      --danger-text: #991b1b;
      --warning-bg: #fef3c7;
      --warning-border: #f59e0b;
      --warning-text: #92400e;
      --success-bg: #dcfce7;
      --success-border: #22c55e;
      --success-text: #166534;
    }
    * { box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      line-height: 1.6;
      color: var(--text-main);
      background-color: var(--bg-page);
      margin: 0;
      padding: 0;
    }
    .container {
      max-width: 900px;
      margin: 40px auto;
      padding: 0 24px;
    }
    .header-card {
      background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
      color: white;
      padding: 32px;
      border-radius: 12px;
      box-shadow: 0 10px 25px -5px rgba(30, 58, 138, 0.2);
      margin-bottom: 28px;
    }
    .header-card h1 { margin: 0 0 8px 0; font-size: 26px; font-weight: 700; }
    .header-card h2 { margin: 0 0 16px 0; font-size: 18px; font-weight: 400; opacity: 0.9; }
    .badge-bar { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12.5px; }
    .badge {
      background: rgba(255, 255, 255, 0.15);
      padding: 4px 10px;
      border-radius: 6px;
      backdrop-filter: blur(4px);
    }
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .card h3 {
      margin-top: 0;
      font-size: 19px;
      color: var(--primary);
      border-bottom: 2px solid var(--primary-subtle);
      padding-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
      margin: 16px 0;
    }
    th, td {
      padding: 10px 12px;
      border: 1px solid var(--border-color);
      text-align: left;
    }
    th {
      background-color: #1e3a8a;
      color: white;
      font-weight: 600;
    }
    tr:nth-child(even) { background-color: #f8fafc; }
    tr.active-row { background-color: #fef3c7; font-weight: 500; }
    .callout {
      border-left: 4px solid var(--primary-light);
      background: var(--primary-subtle);
      padding: 16px;
      border-radius: 0 8px 8px 0;
      margin: 16px 0;
    }
    .callout.warning {
      border-left-color: var(--warning-border);
      background: var(--warning-bg);
      color: var(--warning-text);
    }
    .callout.danger {
      border-left-color: var(--danger-border);
      background: var(--danger-bg);
      color: var(--danger-text);
    }
    .question-box {
      background: #f1f5f9;
      border-left: 4px solid var(--primary-light);
      padding: 16px;
      border-radius: 6px;
      margin-bottom: 16px;
    }
    .question-box h4 {
      margin: 0 0 8px 0;
      color: var(--primary);
      font-size: 15px;
    }
    details {
      background: white;
      padding: 10px 14px;
      border-radius: 6px;
      border: 1px solid var(--border-color);
      margin-top: 10px;
    }
    summary {
      cursor: pointer;
      font-weight: 600;
      color: #0f766e;
      font-size: 13.5px;
    }
    .calc-interactive {
      background: #f8fafc;
      border: 1px solid var(--border-color);
      padding: 18px;
      border-radius: 8px;
    }
    .btn-calc {
      background: var(--primary);
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      font-size: 13.5px;
    }
    .btn-calc:hover { background: var(--primary-light); }
    footer {
      text-align: center;
      font-size: 13px;
      color: var(--text-muted);
      margin: 40px 0 20px 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header-card">
      <h1>🩺 Teaching Coach: Gastroenterología y Semiótica Digestiva</h1>
      <h2>Sílabo Oficial & Guía Clínica de Colitis Ulcerosa (Semana 11)</h2>
      <div class="badge-bar">
        <span class="badge">🏫 UCE / HCAM — Aula Lúdica</span>
        <span class="badge">📅 Miércoles 16:00 – 17:30</span>
        <span class="badge">⚙️ Semestre 2026-2</span>
        <span class="badge">🛡️ KNOW ➔ REASON ➔ ACT</span>
      </div>
    </div>

    <!-- Section 1: Syllabus -->
    <div class="card">
      <h3>📅 1. Sílabo y Cronograma Académico (18 Semanas)</h3>
      <p style="font-size:13.5px; color:var(--text-muted);">
        Evaluación formativa del 40% mediante Rúbrica Analítica HCAM (<code>6–6–4–4</code> pts: Anamnesis 6, Examen Físico 6, Razonamiento 4, Plan y Bibliografía 4).
      </p>
      <table>
        <thead>
          <tr>
            <th>Sem</th>
            <th>Fecha</th>
            <th>Tema Académico</th>
            <th>Hemisemestre</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>1</td><td>24 Jun 2026</td><td>Semiología digestiva, dolor abdominal y anamnesis</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>2</td><td>01 Jul 2026</td><td>Trastornos esofágicos: Disfagia, ERGE y acalasia</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>3</td><td>08 Jul 2026</td><td>Trastornos gástricos: Dispepsia, gastritis y úlcera péptica</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>4</td><td>15 Jul 2026</td><td>Hemorragia digestiva alta (Variceal y No Variceal)</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>5</td><td>22 Jul 2026</td><td>Hemorragia digestiva baja y proctología básica</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>6</td><td>29 Jul 2026</td><td>Síndromes diarreicos agudos y crónicos</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>7</td><td>05 Ago 2026</td><td>Síndrome de malabsorción y enfermedad celíaca</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>8</td><td>12 Ago 2026</td><td>Semiología hepática básica y pruebas funcionales</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>9</td><td>19 Ago 2026</td><td>Evaluación del Primer Hemisemestre</td><td>1° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr><td>10</td><td>26 Ago 2026</td><td>Trastornos funcionales digestivos y dispepsia funcional</td><td>2° Hemi</td><td>✓ Ejecutada</td></tr>
          <tr class="active-row"><td><b>11</b></td><td><b>02 Sep 2026</b></td><td><b>Enfermedad Inflamatoria Intestinal I: Colitis Ulcerosa</b></td><td><b>2° Hemi</b></td><td><b>🔥 ACTIVA (HOY)</b></td></tr>
          <tr><td>12</td><td>09 Sep 2026</td><td>Enfermedad Inflamatoria Intestinal II: Enfermedad de Crohn</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>13</td><td>16 Sep 2026</td><td>Síndrome de Intestino Irritable y motilidad digestiva</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>14</td><td>23 Sep 2026</td><td>Hepatopatías crónicas, cirrosis e hipertensión portal</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>15</td><td>30 Sep 2026</td><td>Ictericia, colestasis y patología biliar litiásica</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>16</td><td>07 Oct 2026</td><td>Pancreatitis aguda y crónica</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>17</td><td>14 Oct 2026</td><td>Abdomen agudo médico vs quirúrgico y urgencias digestivas</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
          <tr><td>18</td><td>21 Oct 2026</td><td>Evaluación Final Integral del Segundo Hemisemestre</td><td>2° Hemi</td><td>⏳ Proyectada</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Section 2: Clinical Guide -->
    <div class="card">
      <h3>📖 2. Guía Clínica: Colitis Ulcerosa</h3>
      
      <h4>Extensión Anatómica: Clasificación de Montreal</h4>
      <table>
        <thead>
          <tr>
            <th>Categoría</th>
            <th>Extensión Anatómica</th>
            <th>Clave Semiótica y Docente</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>E1</b></td>
            <td><b>Proctitis Ulcerosa</b> (limitada al recto)</td>
            <td>Predomina sangrado rectal, urgencia y tenesmo; heces formes.</td>
          </tr>
          <tr>
            <td><b>E2</b></td>
            <td><b>Colitis Izquierda</b> (hasta ángulo esplénico)</td>
            <td>Diarrea sanguinolenta franca y dolor cólico en fosa ilíaca izquierda.</td>
          </tr>
          <tr>
            <td><b>E3</b></td>
            <td><b>Colitis Extensa / Pancolitis</b> (proximal al ángulo esplénico)</td>
            <td>Afectación difusa, mayor superficie inflamada y riesgo sistémico.</td>
          </tr>
        </tbody>
      </table>

      <div class="callout warning">
        <b>⚠️ Regla de Oro Semiótica:</b> La extensión describe <b>anatomía</b>, NO gravedad. Una proctitis (E1) puede ser sumamente sintomática y una colitis extensa (E3) puede estar en remisión.
      </div>

      <h4>Actividad Clínica: Criterios de Truelove y Witts</h4>
      <div class="callout danger">
        <b>🚨 Definición de Colitis Ulcerosa Aguda Grave (CUAG):</b><br>
        <b>≥ 6 deposiciones sanguinolentas/día</b> + <b>al menos 1 signo de toxicidad sistémica:</b>
        <ul>
          <li>Temperatura > 37.8 °C</li>
          <li>Frecuencia cardíaca > 90 lpm</li>
          <li>Hemoglobina < 10.5 g/dL</li>
          <li>Reactantes de Fase Aguda: VSG > 30 mm/h o PCR elevada (> 30 mg/L)</li>
        </ul>
      </div>

      <h4>Comparación: Colitis Ulcerosa vs. Enfermedad de Crohn</h4>
      <table>
        <thead>
          <tr>
            <th>Dimensión</th>
            <th>Colitis Ulcerosa</th>
            <th>Enfermedad de Crohn</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Distribución</b></td>
            <td>Continua, ascendente desde el recto, limitada al colon</td>
            <td>Segmentaria, lesiones salteadas (<i>skip lesions</i>), boca al ano</td>
          </tr>
          <tr>
            <td><b>Profundidad</b></td>
            <td>Mucosa y submucosa superficial</td>
            <td>Transmural (fístulas, abscesos, estenosis)</td>
          </tr>
          <tr>
            <td><b>Pistas Clínicas</b></td>
            <td>Hematoquecia, urgencia, tenesmo</td>
            <td>Dolor en FID, enf. perianal, masa palpable, diarrea no siempre sanguinolenta</td>
          </tr>
          <tr>
            <td><b>Urgencia</b></td>
            <td>Colitis aguda grave, megacolon tóxico</td>
            <td>Absceso intraabdominal, obstrucción, fístula</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Section 3: Socratic Case Simulation -->
    <div class="card">
      <h3>🧠 3. Teaching Coach: Caso Clínico Central Sintético (HCAM)</h3>
      <div class="callout">
        <b>Viñeta:</b> Mujer de 27 años con 6 semanas de deposiciones frecuentes con moco y sangre viva, urgencia y tenesmo. En los últimos 2 días presenta 7 deposiciones sanguinolentas/día. T 38.0 °C, FC 104 lpm, PA 108/68 mmHg. Abdomen doloroso en marco cólico izquierdo sin peritonismo. Hb 10.2 g/dL, Leucocitos 12.800/mm³, PCR 48 mg/L. Antecedente de amoxicilina/ácido clavulánico hace 4 semanas.
      </div>

      <div class="question-box">
        <h4>1. Representación del Problema</h4>
        <p style="font-size:13.5px;">Construya la Representación del Problema en una sola frase.</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> Mujer joven con diarrea sanguinolenta crónica agudizada, síndrome disentérico/urgencia y repercusión sistémica (fiebre, taquicardia, anemia leve), con antecedente de uso reciente de antibióticos.</p>
        </details>
      </div>

      <div class="question-box">
        <h4>2. Diarrea Inflamatoria vs Infecciosa</h4>
        <p style="font-size:13.5px;">¿Qué datos clínicos y de laboratorio apoyan diarrea inflamatoria?</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> Hematoquecia macroscópica, moco, tenesmo, fiebre 38.0 °C, taquicardia 104 lpm, leucocitosis con desviación a la izquierda y elevación marcada de PCR (48 mg/L).</p>
        </details>
      </div>

      <div class="question-box">
        <h4>3. Descarte de Diagnósticos Infecciosos</h4>
        <p style="font-size:13.5px;">¿Qué diagnóstico infeccioso debe descartarse OBLIGATORIAMENTE?</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> Infección por <i>Clostridioides difficile</i> (reforzada por antecedente de amoxicilina/clavulánico hace 4 semanas) mediante toxinas o PCR en heces, además de coprocultivo para bacterias invasivas.</p>
        </details>
      </div>

      <div class="question-box">
        <h4>4. Clasificación de Montreal</h4>
        <p style="font-size:13.5px;">¿Podemos asignar clasificación E1, E2 o E3 solo con los síntomas?</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> NO. Montreal es estrictamente anatómica y requiere evaluación endoscópica/histológica de la extensión mucosa.</p>
        </details>
      </div>

      <div class="question-box">
        <h4>5. Criterios de Colitis Ulcerosa Aguda Grave (CUAG)</h4>
        <p style="font-size:13.5px;">¿Cumple criterios de gravedad según Truelove y Witts?</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> SÍ. Presenta 7 deposiciones sanguinolentas/día (≥ 6) Y múltiples signos de toxicidad sistémica (Fiebre 38.0 °C > 37.8 °C, FC 104 lpm > 90 lpm, Hb 10.2 g/dL < 10.5 g/dL y PCR 48 mg/L).</p>
        </details>
      </div>

      <div class="question-box">
        <h4>6. Prioridades Hospitalarias Iniciales</h4>
        <p style="font-size:13.5px;">¿Cuáles son las prioridades iniciales de manejo?</p>
        <details>
          <summary>🔍 Ver Clave Docente</summary>
          <p style="font-size:13.5px; color:#1e293b;"><b>Respuesta modelo:</b> Hospitalización inmediata, reposición hidroelectrolítica, Rx simple de abdomen para descartar megacolon tóxico (> 5.5 - 6 cm), sigmoidoscopia flexible temprana sin preparación agresiva y valoración conjunta por Gastroenterología y Cirugía Colorrectal.</p>
        </details>
      </div>
    </div>

    <!-- Section 4: Exit Ticket -->
    <div class="card">
      <h3>🎫 4. Ticket de Salida — Evaluación Formativa</h3>
      <ol style="font-size:14px;">
        <li><b>Combinación mínima para CUAG:</b> ≥ 6 deposiciones con sangre al día + al menos 1 signo de toxicidad sistémica.</li>
        <li><b>Infección clave a descartar:</b> <i>Clostridioides difficile</i>.</li>
        <li><b>Extensión vs Gravedad:</b> Montreal describe anatomía endoscópica, no gravedad clínica.</li>
      </ol>
    </div>

    <footer>
      MedSemiotics Copilot — Cátedra de Gastroenterología UCE / HCAM — Semestre 2026-2
    </footer>
  </div>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[OK] Rendered HTML successfully to: {output_path.resolve()}")


if __name__ == "__main__":
    out_file = Path("coach_gastro_colitis_ulcerosa.html")
    render_html_preview(out_file)
    render_html_preview(Path("notebooks/coach_gastro_colitis_ulcerosa.html"))
