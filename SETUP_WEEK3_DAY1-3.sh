#!/bin/bash
# Week 3 Day 1-3 Setup Script

echo "🚀 Plan-Quest Week 3 Day 1-3 Setup 시작"
echo "========================================="

cd "$(dirname "$0")/backend" || exit 1

# Step 1: 의존성 설치
echo ""
echo "📦 Step 1: 의존성 설치"
echo "pip install -r requirements.txt 실행 중..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ 의존성 설치 실패!"
    exit 1
fi

echo "✅ 의존성 설치 완료"

# Step 2: 모델 다운로드 확인
echo ""
echo "📥 Step 2: Ollama 모델 확인"

# Ollama가 설치되어 있는지 확인
if ! command -v ollama &> /dev/null; then
    echo "⚠️ Ollama가 설치되어 있지 않습니다."
    echo "https://ollama.ai 에서 설치해주세요."
else
    echo "✅ Ollama 설치 확인됨"
    echo "📥 qwen2.5 모델 다운로드 중..."
    ollama pull qwen2.5:latest
fi

# Step 3: 프로젝트 구조 확인
echo ""
echo "📂 Step 3: 프로젝트 구조 확인"
echo "생성된 파일들:"
ls -la tools/ 2>/dev/null || echo "❌ tools 디렉토리 없음"
ls -la agent_core.py 2>/dev/null || echo "❌ agent_core.py 없음"

# Step 4: Python 문법 검사
echo ""
echo "🔍 Step 4: Python 문법 검사"
python -m py_compile agent_core.py
python -m py_compile tools/habit_tools.py
python -m py_compile tools/calendar_tools.py
python -m py_compile tools/email_tools.py

if [ $? -eq 0 ]; then
    echo "✅ 문법 검사 완료 (에러 없음)"
else
    echo "❌ 문법 검사 실패!"
    exit 1
fi

# Step 5: 테스트 실행 준비
echo ""
echo "========================================="
echo "✅ Week 3 Day 1-3 Setup 완료!"
echo ""
echo "다음 단계:"
echo "1. Ollama 서버 시작: ollama serve"
echo "2. 백엔드 실행: python main.py"
echo "3. 테스트: curl -X POST http://localhost:8000/api/chat/stream -H 'Content-Type: application/json' -d '{\"message\": \"내일 회의 있고, 중요한 메일 있으면 알려줘\"}'"
echo ""
echo "📖 자세한 정보: WEEK3_DAY1-3_SUMMARY.md 참고"
