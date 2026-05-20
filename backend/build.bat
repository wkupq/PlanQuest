@echo off
REM Plan-Quest 빌드 (cmd 버전 — PowerShell 안 쓸 때)
REM 사용법: build.bat

chcp 65001 > nul

echo ==== Plan-Quest 패키징 빌드 ====
echo.

REM 1) PyInstaller 설치 확인
pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo [1/3] PyInstaller 설치...
    pip install pyinstaller
)

REM 2) 프론트엔드 빌드
echo [2/3] 프론트엔드 빌드...
pushd ..\frontend
if not exist node_modules (
    call npm install
)
call npm run build
popd

REM 3) 정리 + PyInstaller
echo [3/3] PyInstaller 실행 (5~10분 소요)...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller plan_quest.spec --clean --noconfirm

if exist dist\PlanQuest\PlanQuest.exe (
    echo.
    echo ==== 빌드 완료! ====
    echo 실행: dist\PlanQuest\PlanQuest.exe
) else (
    echo.
    echo ==== 빌드 실패 — PACKAGING_GUIDE.md 참고 ====
)
pause
