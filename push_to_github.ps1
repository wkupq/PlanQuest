# Plan-Quest → GitHub 푸시 스크립트
# 사용법: PowerShell 에서 .\push_to_github.ps1
# 또는 한 줄씩 직접 복붙

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==== Plan-Quest GitHub Push ====" -ForegroundColor Cyan
Write-Host ""

# 0) 프로젝트 루트로 이동
Set-Location "C:\Users\guswl\OneDrive\Desktop\Plan-quest"

# 1) 잠금 파일 정리 (이전 작업 잔여물)
if (Test-Path ".git\index.lock") {
    Write-Host "[1/6] index.lock 제거" -ForegroundColor Yellow
    Remove-Item ".git\index.lock" -Force
} else {
    Write-Host "[1/6] index.lock 없음 (OK)" -ForegroundColor Green
}

# 2) 인덱스 손상 시 리셋 (안전)
Write-Host "[2/6] git reset (스테이징 초기화)" -ForegroundColor Yellow
git reset 2>&1 | Out-Null

# 3) .gitignore 에 따라 모든 변경사항 add
Write-Host "[3/6] git add ." -ForegroundColor Yellow
git add .

# 4) 변경사항 요약 (push 전 미리보기)
Write-Host ""
Write-Host "[4/6] 변경 요약:" -ForegroundColor Cyan
git diff --cached --stat | Select-Object -Last 30
Write-Host ""

# 5) 커밋
$commitMsg = @"
Week 3-4 D 역할 완료: RAG 메모리 + 게임 상태 인식 AI

[W3 Day 4-6] RAG 메모리 (ChromaDB)
- backend/memory_engine.py : ChromaDB 영속 저장 + 임베딩 + 임계값 엔진
- backend/routers/memory.py : /api/memory/{add,search,stats,cleanup,delete}
- models.py : UserMemory 테이블 추가

[W3 Day 7-10] 외부 연동 스캐폴드
- backend/integrations/google_calendar.py : Google Calendar 클라이언트
- backend/integrations/email_client.py : Gmail API + IMAP fallback
- backend/integrations/README_연동가이드.md : OAuth 설정 단계별
- tools/calendar_tools.py, email_tools.py : 실 연동 시도 → 실패 시 mock

[W4] 게임 상태 인식 + 능동 추천
- backend/tools/game_state_tools.py : 6개 게임 상태 도구
- backend/proactive_ai.py : 패턴 분석 + 추천 엔진
- backend/routers/proactive.py : /api/proactive/{suggestions,insights,context}
- agent_core.py : 메모리 + 게임 상태 결합한 개인화 컨텍스트 자동 주입

[캐릭터 시스템]
- frontend/public/images/characters/flame_dino.png : 노란 공룡 (배경 제거)
- backend/add_flame_dino.py : DB 등록 스크립트
- frontend/src/styles/global.css : 캐릭터 입체감 강화 (다층 drop-shadow)

[기타]
- backend/migrate_db.py : DB 컬럼 자동 마이그레이션
- requirements.txt : chromadb, langchain, google-* 추가
- WEEK3-4_ROADMAP_D.md, WEEK4_COMPLETE_D.md : 문서
"@

Write-Host "[5/6] git commit" -ForegroundColor Yellow
git commit -m $commitMsg

# 6) 푸시
Write-Host "[6/6] git push origin main" -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "==== 완료 ====" -ForegroundColor Green
Write-Host "확인: https://github.com/wkupq/Plan-quest-UI" -ForegroundColor Cyan
Write-Host ""
