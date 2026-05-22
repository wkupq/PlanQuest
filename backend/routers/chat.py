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

_SCHEDULE_INTENTS = [
    "일정", "약속", "미팅", "회의", "예약", "등록", "추가", "넣어",
    "스케줄", "날짜", "시간", "장소", "초대", "참석",
]

def _extract_gmail_keywords(user_message: str) -> str:
    """
    사용자 메시지에서 Gmail 검색용 키워드를 추출한다.
    - 공백 기준으로 토큰 분리 → 한국어 조사 접미사 제거 → 불용어 스킵
    - '일정에 넣어야 할' 류 스케줄 질문은 schedule 전용 키워드로 치환
    """
    # 공백 단위로 분리해서 각 토큰 끝의 조사/어미 제거
    josa_suffixes = (
        "에서", "에게", "한테", "로부터", "으로부터",
        "에서는", "에서도", "에게는", "로서", "으로서",
        "에게도", "한테서", "에도", "에는", "로도",
        "에", "의", "은", "는", "이", "가", "을", "를",
        "와", "과", "도", "로", "으로", "만", "도",
    )
    skip_words = {
        "메일", "이메일", "gmail", "있어", "있나요", "있나", "있어요",
        "보여줘", "알려줘", "확인해줘", "해줘", "찾아줘", "검색해줘",
        "7일간", "7일동안", "오늘", "최근", "관련", "뭐", "어떤",
        "몇", "개", "건", "있습니다", "없습니다", "주세요", "해주세요",
        "뭔데", "뭐야", "뭔가요", "알려", "알고", "싶어", "궁금",
        "어디", "어때", "어떻게", "좀", "제발", "혹시", "그거",
    }

    tokens = user_message.strip().split()
    keywords = []
    for tok in tokens:
        # 조사 접미사 제거
        word = tok
        for sfx in sorted(josa_suffixes, key=len, reverse=True):
            if word.endswith(sfx) and len(word) > len(sfx) + 1:
                word = word[: -len(sfx)]
                break
        word = word.strip("?!.,~")
        if len(word) < 2 or word in skip_words:
            continue
        keywords.append(word)

    # 스케줄 관련 질문인지 감지
    msg_lower = user_message
    is_schedule_query = any(k in msg_lower for k in _SCHEDULE_INTENTS)

    if is_schedule_query:
        # 스케줄 의도: Gmail에서 일정 관련 메일 검색
        return "일정 OR 약속 OR 미팅 OR 회의 OR 예약 OR 초대"

    # 키워드들을 OR로 연결 → 하나라도 포함된 메일 검색 (AND보다 훨씬 넓게 검색)
    return " OR ".join(keywords) if keywords else ""


def _fetch_gmail_messages(gmail_svc, query: str, max_results: int, seen_ids: set) -> list:
    """Gmail API로 메시지 목록 가져오기. seen_ids로 중복 제거."""
    try:
        res = gmail_svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = res.get("messages", [])
        result = []
        for m in messages:
            if m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])
            msg = gmail_svc.users().messages().get(
                userId="me", id=m["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = msg["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(제목 없음)")
            sender  = next((h["value"] for h in headers if h["name"] == "From"),    "(발신자 없음)")
            date    = next((h["value"] for h in headers if h["name"] == "Date"),    "")
            result.append({"subject": subject[:60], "sender": sender[:40], "date": date[:25]})
        return result
    except Exception:
        return []


def _try_get_google_context(user_query: str = "") -> str:
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

        # ── Gmail: 최근 미확인 5건 + 키워드 검색 결과 ──
        try:
            gmail = build("gmail", "v1", credentials=creds)
            seen_ids: set = set()

            # 1) 최근 미확인 이메일 5건
            unread = _fetch_gmail_messages(gmail, "is:unread", 5, seen_ids)
            lines.append("")
            lines.append("=== Gmail 최근 미확인 이메일 ===")
            if unread:
                for m in unread:
                    lines.append(f"- [{m['date']}] 보낸사람: {m['sender']} | 제목: {m['subject']}")
            else:
                lines.append("미확인 이메일 없음")

            # 2) 사용자 질문 키워드로 추가 검색 (키워드가 있을 때만)
            if user_query:
                keywords = _extract_gmail_keywords(user_query)
                if keywords:
                    keyword_results = _fetch_gmail_messages(gmail, keywords, 20, seen_ids)
                    lines.append("")
                    lines.append(f"=== Gmail 검색 결과 (키워드: {keywords}) ===")
                    if keyword_results:
                        for m in keyword_results:
                            lines.append(f"- [{m['date']}] 보낸사람: {m['sender']} | 제목: {m['subject']}")
                    else:
                        lines.append(f"'{keywords}' 관련 이메일 없음")

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
    1. CJK(중국어/일본어) 문자를 공백으로 치환 → 인접 단어 붙음 방지
    2. 연속 공백 정리
    3. 앞뒤 공백 제거
    순수 중국어 토큰은 빈 문자열 반환 (호출부에서 스킵)
    """
    cleaned = _CJK_RE.sub(' ', text)
    cleaned = _re.sub(r'  +', ' ', cleaned).strip()
    return cleaned


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

        # 2. Google Calendar + Gmail 컨텍스트 (인증된 경우에만, 키워드 검색 포함)
        google_ctx = _try_get_google_context(user_query=req.message)

        # 3. 전체 컨텍스트 조합
        context_parts = [schedule_ctx]
        if google_ctx:
            context_parts.append(google_ctx)
        full_context = "\n\n".join(context_parts)

        full_prompt = _build_prompt_korean(req.message, full_context)
        reply = _clean_korean(_chain.ask(full_prompt))
        return ChatResponse(reply=reply, ai_available=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 오류: {str(e)}")


def _build_prompt_korean(message: str, full_context: str) -> str:
    """한국어 전용 프롬프트 빌더"""
    return (
        "<|im_start|>system\n"
        "당신은 한국어 전용 AI 스케줄러 비서입니다.\n"
        "절대 규칙:\n"
        "- 오직 한국어로만 답하세요.\n"
        "- 중국어(한자), 일본어, 영어를 절대 사용하지 마세요.\n"
        "- 내부 생각(思考/thinking) 과정을 출력하지 마세요. 최종 답변만 출력하세요.\n"
        "- 단어 사이 띄어쓰기를 지키세요.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"[사용자 일정 데이터]\n{full_context}\n\n"
        f"[질문] {message}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def _build_full_prompt(message: str, db: Session) -> str:
    """공통 프롬프트 빌더 — 일반 응답과 스트리밍 모두 사용"""
    schedule_ctx = build_schedule_context(db)
    # 사용자 메시지를 키워드 검색에 활용
    google_ctx = _try_get_google_context(user_query=message)
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
        # AI 비활성화 시 토큰 먼저 보내고 done 따로 전송 (프론트 done 우선 처리 버그 우회)
        async def error_stream():
            msg = _json.dumps({"token": "⚠️ AI 모듈이 로드되지 않았습니다. 백엔드 터미널에서 pip install requests chromadb sentence-transformers rank-bm25 를 실행하고 서버를 재시작해주세요.", "done": False}, ensure_ascii=False)
            yield f"data: {msg}\n\n"
            yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # 프롬프트는 동기적으로 미리 빌드 (DB 세션 유효 시점에)
    try:
        full_prompt = _build_full_prompt(req.message, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨텍스트 빌드 오류: {str(e)}")

    async def token_stream():
        try:
            sent_any = False  # 실제로 사용자에게 보낸 토큰이 있는지 추적

            if hasattr(_chain, "ask_stream"):
                # 스트리밍 모드: 토큰마다 CJK 제거 후 전송
                async for token in _chain.ask_stream(full_prompt):
                    clean = _clean_korean(token)
                    if clean:
                        sent_any = True
                        payload = _json.dumps({"token": clean, "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)
            else:
                # 폴백: 전체 응답 한 번에 받아서 정리 후 전송
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, _chain.ask, full_prompt)
                reply = _clean_korean(reply)
                for word in reply.split(" "):
                    if word:
                        sent_any = True
                        payload = _json.dumps({"token": word + " ", "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                    await asyncio.sleep(0.02)

            # 중국어로만 응답해서 아무것도 전달 못 했을 때 안내 메시지
            if not sent_any:
                fallback = _json.dumps(
                    {"token": "죄송해요, 다시 한번 질문해 주시겠어요? 🙏", "done": False},
                    ensure_ascii=False,
                )
                yield f"data: {fallback}\n\n"

            yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"

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


TARGET_MODEL = "qwen3.5:9b"

@router.get("/health")
async def chat_health():
    """Ollama 실행 상태 확인 — OllamaPopup.js 및 ChatDashboard.js가 사용"""
    ollama_installed = False
    ollama_running = False
    model_loaded = False
    error_msg = None

    # 1. Ollama 바이너리 설치 여부 확인
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        ollama_installed = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        ollama_installed = False

    # 2. Ollama 서버 실행 여부 + 모델 목록 확인
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_running = True
                ollama_installed = True   # 실행 중이면 설치도 된 것
                tags = resp.json().get("models", [])
                model_loaded = any(
                    TARGET_MODEL.split(":")[0] in m.get("name", "").lower()
                    for m in tags
                )
    except Exception as e:
        error_msg = str(e)

    return {
        "ollama_installed": ollama_installed,
        "ollama_running": ollama_running,
        "model_loaded": model_loaded,
        "model": TARGET_MODEL,
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
        # 2. qwen3.5:14b 모델이 있는지 확인 (pull은 시간이 오래 걸리므로 안내만)
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "qwen3.5" in result.stdout.lower():
                steps.append({"step": "model_check", "status": "ok", "message": "qwen3.5 모델이 이미 설치되어 있습니다."})
            else:
                steps.append({
                    "step": "model_check",
                    "status": "warning",
                    "message": "qwen3.5:14b 모델이 없습니다. 터미널에서 'ollama pull qwen3.5:14b' 를 실행하세요.",
                })
        except Exception as e:
            steps.append({"step": "model_check", "status": "error", "message": str(e)})

    return {"success": success, "steps": steps, "error": error_msg}
