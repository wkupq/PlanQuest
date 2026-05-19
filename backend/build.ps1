# Plan-Quest 빌드 스크립트 (Windows PowerShell)
# 사용법: cd backend; .\build.ps1
#
# 단계:
#   1) frontend npm build (선택, 단일 .exe 로 만들고 싶으면)
#   2) pyinstaller plan_quest.spec
#   3) dist/PlanQuest/ 에 결과물

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

$ROOT = (Get-Item ".").Parent.FullName
$BACKEND = (Get-Item ".").FullName
$FRONTEND = Join-Path $ROOT "frontend"

Write-Host "==== Plan-Quest 패키징 빌드 ====" -ForegroundColor Cyan
Write-Host ""

# 1) PyInstaller 설치 확인
Write-Host "[1/4] PyInstaller 설치 확인..." -ForegroundColor Yellow
$pi = python -m pip show pyinstaller 2>$null
if (-not $pi) {
    Write-Host "  PyInstaller 설치 중..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}

# 2) 프론트엔드 빌드 (선택)
$skipFrontend = $args -contains "--skip-frontend"
if (-not $skipFrontend -and (Test-Path "$FRONTEND\package.json")) {
    Write-Host ""
    Write-Host "[2/4] 프론트엔드 빌드 (frontend/build)..." -ForegroundColor Yellow
    Push-Location $FRONTEND
    if (-not (Test-Path "node_modules")) {
        Write-Host "  npm install 실행..." -ForegroundColor Yellow
        npm install
    }
    npm run build
    Pop-Location

    if (Test-Path "$FRONTEND\build\index.html") {
        Write-Host "  ✅ frontend/build 생성됨" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ frontend/build 실패 — 백엔드만 빌드 진행" -ForegroundColor Yellow
    }
} else {
    Write-Host "[2/4] 프론트엔드 빌드 스킵" -ForegroundColor Gray
}

# 3) 기존 dist/build 정리
Write-Host ""
Write-Host "[3/4] 이전 빌드 정리..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

# 4) PyInstaller 실행
Write-Host ""
Write-Host "[4/4] PyInstaller 실행 (5~10분 걸릴 수 있음)..." -ForegroundColor Yellow
pyinstaller plan_quest.spec --clean --noconfirm

if (Test-Path "dist\PlanQuest\PlanQuest.exe") {
    Write-Host ""
    Write-Host "==== 빌드 완료! ====" -ForegroundColor Green
    Write-Host "결과물: $BACKEND\dist\PlanQuest\" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "실행:" -ForegroundColor Cyan
    Write-Host "  .\dist\PlanQuest\PlanQuest.exe"
    Write-Host ""
    Write-Host "이 폴더 전체를 zip 으로 압축하면 배포 가능합니다." -ForegroundColor Cyan
    Write-Host "단, Ollama 는 별도 설치 필요 (사용자가 ollama.ai 에서 다운로드)" -ForegroundColor Yellow

    # 크기 출력
    $size = (Get-ChildItem "dist\PlanQuest" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host ""
    Write-Host "전체 크기: $([math]::Round($size, 1)) MB" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "==== 빌드 실패 ====" -ForegroundColor Red
    Write-Host "PACKAGING_GUIDE.md 의 트러블슈팅 섹션 참고." -ForegroundColor Yellow
}
