# Loop 0.9B — Local-only operation

## Why

The Cloud Run deployment was removed by the owner to avoid recurring cost. The supported way to
run the backend is now a loopback server on the instructor's machine.

## Running it

```bash
python scripts/run_local.py     # serves 127.0.0.1:8000
```

The script sets `MEDSEMIOTICS_API_TOKEN` for the loopback server only. Any other way of starting
the application must provide that variable itself: the backend refuses to serve without a token
rather than falling back to a well-known one, which is the same fail-closed rule that applied to
the deployed surface.

```bash
MEDSEMIOTICS_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  uvicorn medsemiotics.api.app:app --host 127.0.0.1 --port 8000
```

## Publishing stays a human action

The Classroom modules build reviewable drafts and never contact Google:

```bash
python scripts/prepare_class_material.py --course NEURO   # draft for the next class
python scripts/publish_material.py --title "..." --mode api
```

Both print a draft and say so. `ClassroomApiPublisher` assembles a request body and holds no
credential; `ClassroomBrowserPublisher` renders the post for the instructor to review and publish.

## Local material and roster locations

Course materials live in the instructor's Drive-synced folders and rosters hold student data.
Neither is tracked here. Point the tooling at them per machine, for example:

```powershell
$env:MEDSEMIOTICS_MATERIALS_DIR = "<ruta local a la carpeta del curso>"
```

`StudentRosterService` reads `<data_root>/<COURSE>.json` from a directory given at call time and
raises `RosterUnavailableError` when none is configured, so no roster reaches the repository.

## Retired

`scripts/cloud_run_setup.sh` and the deployment runbooks in `docs/loop-0.8e`, `0.8f`, `0.8g`, and
`0.8h` describe the retired hosted surface. They remain for reference; the service they provision
no longer exists.

## Nada específico de una máquina se rastrea aquí

El repositorio es público. Rutas locales, nombres de usuario del sistema, carpetas de Drive y
tokens quedan fuera del árbol: se pasan por parámetro o por variable de entorno.

| Dato | Cómo se entrega |
|---|---|
| Carpeta de materiales | `--materials-dir` o `MEDSEMIOTICS_MATERIALS_DIR` |
| Repositorio local del sitio web | `-SiteRepo` o `MEDSEMIOTICS_SITE_REPO` |
| Token del backend | `MEDSEMIOTICS_API_TOKEN`; `run_all_teaching_tasks.ps1` genera uno en memoria si no existe |
| Roster de estudiantes | archivo local fuera del repositorio, leído por `StudentRosterService` |

Los identificadores de calendario que sí están versionados no otorgan acceso por sí mismos, y la
configuración de cursos no contiene datos de estudiantes ni de pacientes.
