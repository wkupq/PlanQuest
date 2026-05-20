"""chat.py — AI 챗봇 라우터 (RAGChain + 일정 + Google 컨텍스트 주입)"""
import sys
import os
import re as _re
import asyncio
import json as _json
import subprocess
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Habit, UserProfile

# project-files 경로 추가
PROJECT_FILES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../project-files")
)
if PROJECT_FILES_PATH not in sys.path:
    sys.path.insert(0, PROJECT_FILES_PATH)

# Google Calendar / Gmail 연동 (토큰 없으면 비활성화)
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

def _try_get_google_context() -> str:
    """Google Calendar + Gmail에서 컨텍스트 가져오기. 실패 시 빈 문자열 반환."""
    try:
        from auth_manager import get_credentials
        from googleapiclient.discovery import build

        creds = get_credentials(GOOGLE_SCOPES)
        lines = []

        # ── Google Calendar 오늘~7일치 일정 ──
        try:
            cal = build("calendar", "v3", credentials=creds)
            now_utc = datetime.now(timezone.utc)
            week_later = now_utc + timedelta(days=7)
            events_result = cal.events().list(
                calendarId="primary",
                timeMin=now_utc.isoformat(),
                timeMax=week_later.isoformat(),
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = events_result.get("items", [])

            lines.append("=== Google 캘린더 (7일 이내) ===")
            if events:
                for e in events:
                    start = e["start"].get("dateTime", e["start"].get("date", ""))
                    lines.append(f"- {start[:16]} {e.get('summary', '(제목 없음)')}")
            else:
                lines.append("예정된 캘린더 일정 없음")
        except Exception as cal_err:
            lines.append(f"=== Google 캘린더 로드 실패: {cal_err} ===")

        # ── Gmail 최근 미확인 이메일 5건 ──
        try:
            gmail = build("gmail", "v1", credentials=creds)
            results = gmail.users().messages().list(
                userId="me", q="is:unread", maxResults=5
            ).execute()
            messages = results.get("messages", [])

            lines.append("")
            lines.append("=== Gmail 최근 미확인 이메일 ===")
            if messages:
                for m in messages:
                    msg = gmail.users().messages().get(
                        userId="me", id=m["id"],
                        format="metadata",
                        metadataHeaders=["Subject", "From"],
                    ).execute()
                    headers = msg["payload"]["headers"]
                    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(제목 없음)")
                    sender = next((h["value"] for h in headers if h["name"] == "From"), "(발신자 없음)")
                    lines.append(f"- 보낸사람: {sender[:30]} | 제목: {subject[:50]}")
            else:
                lines.append("미확인 이메일 없음")
        except Exception as gmail_err:
            lines.append(f"=== Gmail 로드 실패: {gmail_err} ===")

        return "\n".join(lines)

    except Exception:
        # 토큰 없음 or 인증 안 됨 → 조용히 빈 문자열 반환
        return ""

try:
    from rag_chain import RAGChain
    _chain = RAGChain()
    _ai_available = True
except Exception as e:
    _chain = None
    _ai_available = False
    print(f"[WARN] RAGChain 로드 실패 — AI 비활성화: {e}")

# DataCollector — 실패해도 채팅은 계속 동작
try:
    from data_collector import DataCollector
    _collector = DataCollector()
    print("[INFO] DataCollector 초기화 완료 — 대화 데이터 수집 시작")
except Exception as e:
    _collector = None
    print(f"[WARN] DataCollector 초기화 실패 (수집 비활성화): {e}")


def _log_interaction(user_msg: str, ai_reply: str, context: str = "") -> None:
    """대화를 LoRA 학습 데이터로 저장. 실패해도 무시."""
    if _collector is None or not user_msg.strip() or not ai_reply.strip():
        return
    try:
        _collector.log_interaction(
            question=user_msg,
            answer=ai_reply,
            context_used=context[:500] if context else "",
            source="chat_stream",
        )
    except Exception as e:
        print(f"[WARN] 데이터 수집 실패 (무시): {e}")

# ── 한국어 전용 응답 필터 ─────────────────────────────────────
# CJK 통합 한자(U+4E00–U+9FFF), CJK 확장A(U+3400–U+4DBF) 제거
# 한글(U+AC00–U+D7A3), 한글 자모(U+1100–U+11FF) 는 보존
_CJK_RE = _re.compile(
    '['
    '一-鿿'   # CJK 통합 한자
    '㐀-䶿'   # CJK 확장 A
    ' 0-⩭f' # CJK 확장 B (surrogate)
    '　-〿'   # CJK 기호·문장부호
    '＀-￯'   # 전각 로마자 / 반각 가타카나
    '⺀-⻿'   # CJK 부수 보충
    '㇀-㇯'   # CJK 획
    ']+',
    _re.UNICODE
)

def _clean_korean(text: str) -> str:
    """
    응답을 한국어 전용으로 정리한다.
    1. CJK(중국어/일본어) 문자 제거
    2. 제거로 생긴 연속 공백 정리
    3. 앞뒤 공백 제거
    """
    cleaned = _CJK_RE.sub('', text)
    cleaned = _re.sub(r'  +', ' ', cleaned)   # 연속 공백 → 단일 공백
    return cleaned.strip()


router = APIRouter(prefix="/api/chat", tags=["chat"])

DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


def build_schedule_context(db: Session) -> str:
    """DB에서 일정/습관 데이터를 읽어 AI 컨텍스트 문자열로 변환"""
    now = datetime.now()
    today_weekday = now.weekday()  # 0=월 ~ 6=일
    today_str = now.strftime("%Y년 %m월 %d일 (%a)")
    current_time = now.strftime("%H:%M")

    user = db.query(UserProfile).first()
    habits = db.query(Habit).all()

    if not habits:
        return f"오늘 날짜: {today_str}, 현재 시각: {current_time}\n등록된 일정이 없습니다."

    lines = [
        f"오늘 날짜: {today_str}",
        f"현재 시각: {current_time}",
        f"사용자 레벨: {user.level if user else 1}, 하트: {user.hearts if user else 0}",
        "",
        "=== 전체 습관/일정 목록 ===",
    ]

    today_habits = []
    upcoming_habits = []

    for h in habits:
        repeat = h.repeat_days or []
        times = h.times or []
        days_str = "매일" if len(repeat) == 7 else (
            ", ".join(DAY_NAMES[d] for d in sorted(repeat)) + "요일" if repeat else "반복 없음"
        )
        times_str = ", ".join(times) if times else "시간 미설정"
        status = "✅ 완료" if h.completed_today else "⏳ 미완료"
        streak_str = f"{h.streak}일 연속" if h.streak > 0 else "시작 전"

        lines.append(
            f"- [{status}] {h.title} | 반복: {days_str} | 시간: {times_str} | 스트릭: {streak_str}"
        )

        # 오늘 해당하는 일정 분류
        if today_weekday in repeat:
            today_habits.append(h)
            # 아직 안 온 시간대 = 다음 일정
            for t in times:
                if t > current_time and not h.completed_today:
                    upcoming_habits.append((h.title, t))

    lines.append("")
    lines.append(f"=== 오늘({DAY_NAMES[today_weekday]}요일) 일정 ===")
    if today_habits:
        for h in today_habits:
            status = "✅ 완료" if h.completed_today else "⏳ 미완료"
            times_str = ", ".join(h.times) if h.times else "시간 미설정"
            lines.append(f"- {status} {h.title} ({times_str})")
    else:
        lines.append("오늘 예정된 일정 없음")

    lines.append("")
    lines.append("=== 다음 예정 일정 ===")
    if upcoming_habits:
        upcoming_habits.sort(key=lambda x: x[1])
        for title, t in upcoming_habits[:3]:
            lines.append(f"- {t} {title}")
    else:
        lines.append("남은 일정 없음")

    return "\n".join(lines)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    ai_available: bool


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어 있습니다.")

    if not _ai_available or _chain is None:
        return ChatResponse(
            reply="AI 백엔드가 현재 연결되지 않았습니다. 잠시 후 다시 시도해 주세요.",
            ai_available=False,
        )

    try:
        # 1. 앱 내 습관/일정 컨텍스트
        schedule_ctx = build_schedule_context(db)

        # 2. Google Calendar + Gmail 컨텍스트 (인증된 경우에만)
        google_ctx = _try_get_google_context()

        # 3. 전체 컨텍스트 조합
        context_parts = [schedule_ctx]
        if google_ctx:
            context_parts.append(google_ctx)
        full_context = "\n\n".join(context_parts)

        full_prompt = _build_prompt_korean(req.message, full_context)
        reply = _clean_korean(_chain.ask(full_prompt))
        _log_interaction(req.message, reply, full_prompt[:300])
        return ChatResponse(reply=reply, ai_available=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 오류: {str(e)}")


def _build_prompt_korean(message: str, full_context: str) -> str:
    """한국어 전용 프롬프트 빌더"""
    return (
        "당신은 한국어로만 대화하는 AI 스케줄러 비서입니다.\n"
        "규칙: 반드시 한국어로만 답하세요. 중국어·영어 사용 금지.\n"
        "생각 과정을 출력하지 말고 최종 답변만 출력하세요.\n"
        "단어 사이에 띄어쓰기를 반드시 지키세요.\n\n"
        f"[사용자 일정 데이터]\n{full_context}\n\n"
        f"[질문] {message}\n"
        "[답변]"
    )


def _build_full_prompt(message: str, db: Session) -> str:
    """공통 프롬프트 빌더 — 일반 응답과 스트리밍 모두 사용"""
    schedule_ctx = build_schedule_context(db)
    google_ctx = _try_get_google_context()
    context_parts = [schedule_ctx]
    if google_ctx:
        context_parts.append(google_ctx)
    full_context = "\n\n".join(context_parts)
    return _build_prompt_korean(message, full_context)


@router.post("/stream")
async def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """SSE 스트리밍 응답 — TeamD ChatDashboard.js가 사용"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어 있습니다.")

    if not _ai_available or _chain is None:
        # AI 비활성화 시 단일 이벤트로 에러 전달
        async def error_stream():
            data = _json.dumps({"token": "AI 백엔드가 연결되지 않았습니다.", "done": True}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # 프롬프트는 동기적으로 미리 빌드 (DB 세션 유효 시점에)
    try:
        full_prompt = _build_full_prompt(req.message, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨텍스트 빌드 오류: {str(e)}")

    async def token_stream():
        collected_reply = []
        try:
            if hasattr(_chain, "ask_stream"):
                # 스트리밍 모드: 토큰마다 CJK 제거 후 전송
                async for token in _chain.ask_stream(full_prompt):
                    clean = _clean_korean(token)
                    if clean:
                        collected_reply.append(clean)
                        payload = _json.dumps({"token": clean, "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)
            else:
                # 폴백: 전체 응답 한 번에 받아서 정리 후 전송
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, _chain.ask, full_prompt)
                reply = _clean_korean(reply)
                collected_reply.append(reply)
                for word in reply.split(" "):
                    if word:
                        payload = _json.dumps({"token": word + " ", "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                    await asyncio.sleep(0.02)

            yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"

            # 스트리밍 완료 후 데이터 수집
            full_reply = "".join(collected_reply).strip()
            _log_interaction(req.message, full_reply, full_prompt[:300])

        except Exception as e:
            err = _json.dumps({"error": str(e), "done": True}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        },
    )


@router.get("/health")
async def chat_health():
    """Ollama 실행 상태 확인 — OllamaPopup.js 및 ChatDashboard.js가 사용"""
    ollama_running = False
    model_loaded = False
    error_msg = None

    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_running = True
                tags = resp.json().get("models", [])
                # qwen2.5 계열 모델이 하나라도 있으면 model_loaded=True
                model_loaded = any(
                    "qwen" in m.get("name", "").lower() for m in tags
                )
    except Exception as e:
        error_msg = str(e)

    return {
        "ollama_running": ollama_running,
        "model_loaded": model_loaded,
        "ai_available": _ai_available,
        "error": error_msg,
    }


@router.post("/setup-ollama")
async def setup_ollama():
    """Ollama 자동 설치 및 모델 다운로드 안내 — OllamaPopup.js가 사용"""
    steps = []
    success = True
    error_msg = None

    try:
        # 1. Ollama 프로세스가 실행 중인지 확인
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            steps.append({"step": "ollama_check", "status": "ok", "message": "Ollama가 실행 중입니다."})
        else:
            steps.append({"step": "ollama_check", "status": "error", "message": "Ollama를 찾을 수 없습니다. https://ollama.ai 에서 설치하세요."})
            success = False
    except FileNotFoundError:
        steps.append({"step": "ollama_check", "status": "error", "message": "Ollama가 설치되어 있지 않습니다. https://ollama.ai 에서 설치하세요."})
        success = False
    except subprocess.TimeoutExpired:
        steps.append({"step": "ollama_check", "status": "error", "message": "Ollama 응답 시간 초과."})
        success = False
    except Exception as e:
        steps.append({"step": "ollama_check", "status": "error", "message": str(e)})
        success = False
        error_msg = str(e)

    if success:
        # 2. qwen2.5:14b 모델이 있는지 확인 (pull은 시간이 오래 걸리므로 안내만)
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "qwen2.5" in result.stdout.lower():
                steps.append({"step": "model_check", "status": "ok", "message": "qwen2.5 모델이 이미 설치되어 있습니다."})
            else:
                steps.append({
                    "step": "model_check",
                    "status": "warning",
                    "message": "qwen2.5:14b 모델이 없습니다. 터미널에서 'ollama pull qwen2.5:14b' 를 실행하세요.",
                })
        except Exception as e:
            steps.append({"step": "model_check", "status": "error", "message": str(e)})

    return {"success": success, "steps": steps, "error": error_msg}
