# Plan-Quest → GitHub Push (D 역할 W3-4 최종)
# 사용법: PowerShell 에서 .\push_to_github.ps1
# 또는 한 줄씩 직접 복붙

Set-Location "C:\Users\guswl\OneDrive\Desktop\Plan-quest"

Write-Host "==== Plan-Quest GitHub Push ====" -ForegroundColor Cyan

# 1) index.lock 정리
if (Test-Path ".git\index.lock") {
    Remove-Item ".git\index.lock" -Force
    Write-Host "[1/4] lock 제거" -ForegroundColor Yellow
}

# 2) 인덱스 초기화 + 모든 변경 add
Write-Host "[2/4] git add ." -ForegroundColor Yellow
git reset 2>&1 | Out-String | Write-Host
git add .

# 3) 변경 요약
Write-Host ""
Write-Host "변경 요약:" -ForegroundColor Cyan
git diff --cached --stat | Select-Object -Last 20

# 4) 커밋
$msg = @"
Week 3-4 D 역할 최종: 캘린더 히트맵 + 18개 AI 도구 + 게임 UI 재설계

[캘린더 시스템]
- HabitCompletion 테이블 (히트맵용 완료 기록)
- /api/calendar/{month,day} API
- CalendarPanel: 5단계 색상 히트맵 + 날짜 클릭 디테일

[AI 도구 18개 (15→18)]
- get_completion_history(today/week/month)
- get_today_progress
- analyze_weak_pattern

[proactive_ai 강화]
- 실 완료 기록 기반 best_dow/weak_dow
- weak_day_today 추천 추가

[배치도 게임 흐름 변경]
- 그리드 5x4 → 7x5 = 35칸
- 빌보드 레이어 (캐릭터 회전 X, 진짜 2.5D)
- 역산 hit-test (정확한 클릭 위치)
- 씨앗/나무 SVG 4단계 + 사용자 PNG (seed_stage_1)
- 시간 카운트다운 배지 (분 단위)
- 캐릭터/나무 이동 + 회수 기능

[캐릭터 starter 4마리]
- 불꽃포메, 달빛토끼, 눈구름냥, 우주거북

[기타]
- test_d_features.py 통합 검증
- WEEK4_COMPLETE_D.md 최종 문서
- 새싹 PNG 길이 단축
- AmbientDecorations 제거
"@

Write-Host "[3/4] git commit" -ForegroundColor Yellow
git commit -m $msg

# 5) 푸시
Write-Host "[4/4] git push origin main" -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "==== 완료 ====" -ForegroundColor Green
Write-Host "확인: https://github.com/wkupq/Plan-quest-UI" -ForegroundColor Cyan
