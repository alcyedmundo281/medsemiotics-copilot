# Ejecutor local de tareas docentes de MedSemiotics Teaching Copilot.
#
# Nada en este archivo es especifico de una maquina: las rutas y el token se pasan como
# parametros o por variables de entorno. No commitee rutas locales ni credenciales aqui.
param (
    [string]$Course = 'NEURO',
    [string]$Section = 'Segundo Hemisemestre',
    # Carpeta local (por ejemplo la de Drive) donde copiar el documento de clase.
    [string]$MaterialsDir = $env:MEDSEMIOTICS_MATERIALS_DIR,
    # Repositorio local del sitio web. Si se omite, el paso de publicacion web se salta.
    [string]$SiteRepo = $env:MEDSEMIOTICS_SITE_REPO
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "MEDSEMIOTICS TEACHING COPILOT - TAREAS DOCENTES LOCALES" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan

# 1. Entorno local. El token nunca se escribe en el repositorio: se genera si no existe uno.
Write-Host "[1/3] Configurando entorno local..." -ForegroundColor Yellow
$env:PYTHONPATH = "src"
if (-not $env:MEDSEMIOTICS_API_TOKEN) {
    $env:MEDSEMIOTICS_API_TOKEN = [System.Convert]::ToBase64String([System.Guid]::NewGuid().ToByteArray())
    Write-Host "      Token de sesion generado en memoria (no se guarda en disco)." -ForegroundColor DarkGray
}

# 2. Documento de clase y borrador para Classroom del proximo tema pendiente del silabo.
Write-Host "[2/3] Preparando el material de la proxima clase de $Course..." -ForegroundColor Yellow
Push-Location $RepoRoot
try {
    $prepareArgs = @('scripts/prepare_class_material.py', '--course', $Course, '--section', $Section)
    if ($MaterialsDir) { $prepareArgs += @('--materials-dir', $MaterialsDir) }
    python @prepareArgs
}
finally {
    Pop-Location
}

# 3. Publicacion del sitio web, solo si se indico su repositorio local.
if (-not $SiteRepo) {
    Write-Host "[3/3] Sin -SiteRepo configurado: se omite la publicacion web." -ForegroundColor DarkGray
}
elseif (-not (Test-Path $SiteRepo)) {
    Write-Host "[3/3] La ruta -SiteRepo no existe: se omite la publicacion web." -ForegroundColor Red
}
else {
    Write-Host "[3/3] Publicando el sitio web desde $SiteRepo..." -ForegroundColor Yellow
    Push-Location $SiteRepo
    try {
        git add .
        git commit -m "feat: actualizar materiales de clase del sitio"
        git push origin main
    }
    finally {
        Pop-Location
    }
}

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "LISTO. El documento y el borrador de Classroom quedan para su revision." -ForegroundColor Green
Write-Host "Nada fue publicado automaticamente en Classroom ni en Calendar." -ForegroundColor White
Write-Host "=====================================================================" -ForegroundColor Cyan
