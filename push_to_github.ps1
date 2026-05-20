# Plan-Quest → GitHub Push (간단 버전 - here-string 없음)
# 사용법: .\push_to_github.ps1

Set-Location "C:\Users\guswl\OneDrive\Desktop\Plan-quest"

# UTF-8 인코딩
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

git config --local i18n.commitencoding utf-8
git config --local i18n.logoutputencoding utf-8

if (Test-Path ".git\index.lock") { Remove-Item ".git\index.lock" -Force }

git add .

# 커밋 메시지 — 줄 단위 배열로 만들어서 join (here-string 우회)
$lines = @(
    "Week 6 D 역할 완료: 자동 추천 + 슬래시 커맨드 + 피드백 + 캐릭터 6마리",
    "",
    "[W6 D1-2] AI 자동 일정 추천 엔진",
    "- routers/suggestions.py 신규",
    "- /api/suggestions/{habits, empty-slots, best-time}",
    "- 4 카테고리 라이브러리 + 사용자 패턴 점수",
    "",
    "[W6 D3] 챗봇 슬래시 커맨드 12개",
    "- slash_commands.py 신규",
    "- /help /hearts /summary /today /list /history /pattern /stats /suggest /add /complete",
    "- LLM 없이도 즉시 실행 (Ollama 안 켜져도 OK)",
    "",
    "[W6 D4] AI 응답 피드백 시스템",
    "- routers/feedback.py 신규",
    "- POST /api/feedback/rate (good/bad)",
    "- good=high importance memory, bad=low importance",
    "",
    "[W6 D5] 통합 + 문서",
    "- test_d_features.py W6 항목 3개 추가 (13/13 통과)",
    "- WEEK6_COMPLETE_D.md 신규",
    "",
    "[캐릭터 6마리 신규]",
    "- 불꽃펭귄, 호랑햄스터, 음악수달 (rare)",
    "- 무지개여우 (unique), 별자리양 (unique), 라벤더냥 (rare)",
    "- 14마리 분포: common 8 / rare 3 / unique 3",
    "",
    "[게임 밸런스 + 버그 fix]",
    "- 모든 캐릭터 가격 x2",
    "- 보유/배치 초기화 스크립트 (reset_owned_double_price.py)",
    "- 캐릭터 이동 시 다른 캐릭터 옮겨지던 버그 수정",
    "- PATCH /placed-items/id/position 신규",
    "- 등급별 시간당 하트 (common 6h/1, rare 4h/2, unique 3h/3)",
    "- 신비한고목 -> 소나무, 잉카알파카 -> 알파카 이름 변경"
)
$msg = [string]::Join("`n", $lines)

# BOM 없는 UTF-8 파일로 저장
[IO.File]::WriteAllText("$PWD\commit_msg.txt", $msg, [Text.UTF8Encoding]::new($false))

git commit -F .\commit_msg.txt
git push origin main
Remove-Item .\commit_msg.txt

Write-Host ""
Write-Host "==== 완료 ====" -ForegroundColor Green
Write-Host "https://github.com/wkupq/Plan-quest-UI" -ForegroundColor Cyan
