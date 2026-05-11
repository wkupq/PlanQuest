# Plan-Quest → GitHub Push (W5 D 역할)
# 사용법: .\push_to_github.ps1

Set-Location "C:\Users\guswl\OneDrive\Desktop\Plan-quest"

# UTF-8 인코딩 강제 (한글 commit 메시지 안 깨지게)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

git config --local i18n.commitencoding utf-8
git config --local i18n.logoutputencoding utf-8

if (Test-Path ".git\index.lock") { Remove-Item ".git\index.lock" -Force }

git add .
git diff --cached --stat | Select-Object -Last 15

# 메시지 파일로 (인코딩 안전)
@"
Week 5 D 역할 완료: AI 인사이트 + 메모리 자동화 + WebSocket 알림

[W5 D1-2] AI 주간/월간 인사이트 리포트
- routers/insights.py 신규
- LLM (Ollama) 기반 자연어 분석 (없으면 템플릿 폴백)
- /api/insights/{weekly,monthly,quick}
- 통계 + 인사이트 + 추천 행동 3가지

[W5 D3] 메모리 자동 카테고리화
- memory_engine: auto_categorize, auto_importance
- 6개 카테고리 자동 분류 (habit/preference/schedule/game_event/emotion/personal)
- 길이 + 강조 단어로 중요도 자동 산정
- /api/memory/auto-add, /api/memory/recategorize

[W5 D4] WebSocket 실시간 알림
- routers/notifications.py 신규
- /ws/notifications WebSocket
- 백그라운드 폴러 (30초 주기)
- 능동 추천 변화 push + 일정 알람 시간 push
- 폴링 → 푸시로 효율 + UX 향상

[W5 D5] 통합 + 문서
- test_d_features.py: W5 항목 3개 추가 (총 10개 검증)
- WEEK5_COMPLETE_D.md 신규 문서
"@ | Out-File -FilePath ".\commit_msg.txt" -Encoding utf8

git commit -F .\commit_msg.txt
git push origin main
Remove-Item .\commit_msg.txt

Write-Host "==== 완료 ====" -ForegroundColor Green
Write-Host "https://github.com/wkupq/Plan-quest-UI"
