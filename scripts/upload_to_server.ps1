# Скрипт для загрузки файлов на сервер через SCP
# Использование: .\scripts\upload_to_server.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIP,
    
    [Parameter(Mandatory=$false)]
    [string]$User = "root",
    
    [Parameter(Mandatory=$false)]
    [string]$RemotePath = "/opt/maptrack/MapTrack"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Загрузка файлов на сервер $ServerIP..." -ForegroundColor Cyan

# Проверка наличия SCP (через OpenSSH или Git Bash)
$scpCommand = "scp"
if (-not (Get-Command $scpCommand -ErrorAction SilentlyContinue)) {
    Write-Host "❌ SCP не найден. Установите OpenSSH или используйте Git Bash" -ForegroundColor Red
    exit 1
}

# Файлы и директории для загрузки
$itemsToUpload = @(
    "src",
    "docker",
    "config",
    "requirements.txt"
)

Write-Host "📦 Загрузка файлов..." -ForegroundColor Yellow

foreach ($item in $itemsToUpload) {
    if (Test-Path $item) {
        Write-Host "  → Загрузка $item..." -ForegroundColor Gray
        if (Test-Path $item -PathType Container) {
            # Директория
            scp -r $item "${User}@${ServerIP}:${RemotePath}/"
        } else {
            # Файл
            scp $item "${User}@${ServerIP}:${RemotePath}/"
        }
        Write-Host "  ✅ $item загружен" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $item не найден, пропускаю..." -ForegroundColor Yellow
    }
}

Write-Host "`n✅ Загрузка завершена!" -ForegroundColor Green
Write-Host "`nТеперь на сервере выполните:" -ForegroundColor Cyan
Write-Host "  cd $RemotePath/config" -ForegroundColor White
Write-Host "  docker-compose down" -ForegroundColor White
Write-Host "  docker-compose up -d --build" -ForegroundColor White






