# Puente MedSemiotics → secretario-clinico

MedSemiotics ya no maneja el calendario del docente. El sílabo oficial sigue siendo la fuente de
verdad de las clases; **secretario-clinico** es el único sistema que las lleva a la agenda clínica y
a Google Calendar.

```
silabo_*_v2.yaml ──export_teaching_bridge.py──▶ docs/puente_secretario/eventos_docentes_<semestre>.json
                                                         │
                         secretario-clinico: scripts/import_medsemiotics_events.py
                                                         ▼
                                   data/agenda.json → calendario/*.md / *.ics → Google Calendar
```

## Flujo tras cambiar el sílabo

1. Edite `config/syllabi/<semestre>/silabo_*_v2.yaml` (clase dictada, reprogramación…).
2. `python scripts/sync_syllabus_v2_to_config.py`
3. `python scripts/export_teaching_bridge.py`
4. Haga commit del JSON junto con el cambio de sílabo.
5. En `secretario-clinico`: `uv run python scripts/import_medsemiotics_events.py --dry-run`, revise los cambios y ejecútelo sin `--dry-run`.

## Contrato `medsemiotics.teaching-events/v1`

| Campo | Significado |
| :--- | :--- |
| `schema` | Siempre `medsemiotics.teaching-events/v1`. Un cambio incompatible exige `v2`. |
| `semester_id` | Semestre, p. ej. `2026-2`. |
| `timezone` | `America/Guayaquil`; todas las horas son locales. |
| `owner_of_calendar_writes` | `secretario-clinico`. |
| `sources` | Sílabos oficiales de los que se derivó el documento. |
| `events[]` | Una entrada por semana de cada curso (ver abajo). |

Cada evento:

| Campo | Ejemplo |
| :--- | :--- |
| `event_id` | `medsemiotics-2026-2-NEURO-w14`: **estable por semestre, curso y semana** |
| `course_code` / `course_name` | `NEURO` / `Cátedra de Neurología Clínica y Semiótica` |
| `week`, `topic_id`, `title` | `14`, `desmielinizantes-em`, `Sem 14 - Enfermedades desmielinizantes…` |
| `date`, `start_local`, `end_local` | `2026-09-22`, `16:00`, `17:30` |
| `location`, `web_module` | `Aula de Administración`, URL del módulo |
| `status` | `completed` o `projected`, copiado del sílabo |

### Invariantes

- El `event_id` no depende de la fecha ni del tema: una reprogramación **actualiza** el evento
  existente en lugar de duplicarlo.
- El documento no lleva marca de tiempo; el mismo sílabo produce el mismo archivo, byte a byte.
- El documento es contenido público de planificación docente: nunca incluye estudiantes,
  pacientes ni credenciales.
- El `.ics` de `docs/` sigue generándose para importaciones manuales, pero ya no es el canal hacia
  secretario-clinico (sus UID incluyen la fecha y duplicaban las clases reprogramadas).
