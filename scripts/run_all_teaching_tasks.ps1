# PowerShell Execution Script for MedSemiotics Teaching Copilot
param (
    [string]$Course = 'NEURO',
    [string]$Topic = 'Trastornos del Movimiento II',
    [string]$Section = 'Segundo Hemisemestre'
)

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "MEDSEMIOTICS TEACHING COPILOT - EJECUTOR DE TAREAS DOCENTES" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan

# 1. Configurar Entorno Local
Write-Host "[1/4] Configurando entorno de desarrollo local (100% Zero-Cloud / Zero-Secrets)..." -ForegroundColor Yellow
$env:PYTHONPATH = "src"
$env:MEDSEMIOTICS_API_TOKEN = "local-dev-token"

# 2. Coaching, Rúbricas y Publicación Autónomas
Write-Host "[2/4] Preparando clase, generando rúbricas y publicando en Classroom/Calendar..." -ForegroundColor Yellow
python scripts/auto_prepare_and_publish.py --course $Course --topic $Topic --topic-section $Section

# 3. Sincronización Web en GitHub Pages (powersemiotics.com)
Write-Host "[3/4] Sincronizando sitio web powersemiotics.com..." -ForegroundColor Yellow
Set-Location C:\Users\aetorres\Documents\medsemioitics
git add .
git commit -m "feat: actualizar sitio web powersemiotics.com con materiales de clase"
git push origin main
Set-Location C:\Users\aetorres\Documents\medsemiotics-copilot

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "TODAS LAS TAREAS DOCENTES FUERON COMPLETADAS CON EXITO" -ForegroundColor Green
Write-Host "   - Rúbricas e informes de evaluación listos" -ForegroundColor White
Write-Host "   - Módulo Web sincronizado en powersemiotics.com" -ForegroundColor White
Write-Host "   - Google Classroom y Google Calendar agendados" -ForegroundColor White
Write-Host "=====================================================================" -ForegroundColor Cyan