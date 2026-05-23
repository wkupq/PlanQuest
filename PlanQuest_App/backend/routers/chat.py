"""chat.py — AI 챗봇 라우터 (RAGChain + 일정 + Google 컨텍스트 + 일정 등록)"""
import sys
import os
import re as _re
import asyncio
import json as _json
import subprocess
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Habit, UserProfile, TreeOnMap

logger = logging.getLogger(__name__)

# project-files 경로 추가
PROJECT_FILES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../project-files")
)
if PROJECT_FILES_PATH not in sys.path:
    sys.path.insert(0, PROJECT_FILES_PATH)

# ── Google 스코프 ─────────────────────────────────────────────────
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# ── 스케줄 의도 키워드 ────────────────────────────────────────────
_SCHEDULE_INTENTS = [
    "일정", "약속", "미팅", "회의", "예약", "등록", "추가", "넣어",
    "스케줄", "날짜", "시간", "장소", "초대", "참석",
]

# ── 일정 생성 의도 키워드 (채팅 → DB 저장) ───────────────────────
_CREATE_INTENT_KEYWORDS = [
    "추가해줘", "등록해줘", "넣어줘", "만들어줘", "추가해", "등록해",
    "일정으로", "캘린더에 추가", "일정 추가", "일정 등록",
    "알람 설정", "알림 설정", "잊지 않게", "일정에 넣어",
]

# ── 일정 생성 태그 파싱 정규식 ────────────────────────────────────
# AI 응답 마지막에 __CREATE__:{"title":..., "time":..., "days":[], "repeat":bool} 형태
_CREATE_TAG_RE = _re.compile(r'__CREATE__:\s*(\{.*?\})', _re.DOTALL)

# ── 마크다운 제거 ─────────────────────────────────────────────────
_MD_RE = _re.compile(
    r'\*{1,3}|'      # * ** ***
    r'#{1,6}\s*|'    # # ## ### ...
    r'`{1,3}|'       # ` `` ```
    r'_{1,2}|'       # _ __
    r'~~|'           # ~~취소선~~
    r'>\s*',         # > 인용
    _re.UNICODE
)

# ── CJK 제거 ─────────────────────────────────────────────────────
_CJK_RE = _re.compile(
    r'['
    r'一-鿿'   # CJK 통합 한자
    r'㐀-䶿'   # CJK 확장 A
    r'　-〿'   # CJK 기호·문장부호
    r'＀-￯'   # 전각 로마자 / 반각 가타카나
    r'⺀-⻿'   # CJK 부수 보충
    r'㇀-㇯'   # CJK 획
    r']+',
    _re.UNICODE
)

# ── 채팅 전용 시스템 프롬프트 ─────────────────────────────────────
_CHAT_SYSTEM = (
    "당신은 한국어 전용 AI 스케줄러 비서입니다.\n"
    "\n"
    "## 절대 규칙\n"
    "1. 반드시 한국어로만 답변하세요. 중국어(한자), 일본어를 절대 사용하지 마세요.\n"
    "2. 내부 생각(thinking/reasoning) 과정을 출력하지 마세요. 최종 답변만 출력하세요.\n"
    "3. 단어 사이 띄어쓰기를 반드시 지키세요.\n"
    "4. 제공된 [사용자 일정 및 Gmail 데이터]를 반드시 참고해서 답변하세요.\n"
    "5. 데이터에 없는 내용은 '해당 정보가 없습니다'라고 명확히 말하세요.\n"
    "\n"
    "## 답변 형식\n"
    "- 짧고 명확하게 핵심만 답변하세요. 서론 없이 바로 시작하세요.\n"
    "- 여러 항목(이메일 목록, 일정 목록 등)은 반드시 한 항목씩 줄바꿈(\\n)으로 구분하세요.\n"
    "- 절대 여러 항목을 한 줄에 이어 쓰지 마세요. 반드시 줄바꿈하세요.\n"
    "- 마크다운 문법(**볼드**, ##헤더, `코드`, _이탤릭_)을 절대 사용하지 마세요.\n"
    "- 이모지는 꼭 필요한 경우만 1~2개 사용하세요.\n"
    "\n"
    "## 이메일/일정 목록 형식 예시\n"
    "이메일이 여러 개 있을 때는 반드시 이렇게 출력하세요:\n"
    "1번 메일: [날짜] 보낸사람 | 제목\n"
    "2번 메일: [날짜] 보낸사람 | 제목\n"
    "(절대 '-[날짜]보낸사람|제목-[날짜]...' 처럼 이어 쓰지 마세요)\n"
    "\n"
    "## 일정 등록 기능\n"
    "사용자가 '추가해줘', '등록해줘', '넣어줘' 같이 명시적으로 일정 등록을 요청할 때만:\n"
    "1. 자연스럽게 확인 답변을 먼저 작성하세요.\n"
    "2. 답변 마지막에 아래 태그를 단독 줄로 추가하세요:\n"
    '   __CREATE__:{"title":"제목","time":"HH:MM","days":[요일숫자],"repeat":true}\n'
    "   - days: 0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일 (없으면 [])\n"
    "   - time: 없으면 빈 문자열\n"
    "   - repeat: 반복 일정 true, 1회성 false\n"
    "3. 필요한 정보(제목, 시간, 반복여부)가 부족하면 먼저 물어보세요.\n"
    "4. 일정 조회·메일 확인·일반 대화에는 __CREATE__ 태그를 절대 사용하지 마세요.\n"
)


# ── RAGChain 초기화 ───────────────────────────────────────────────
try:
    from rag_chain import RAGChain
    from string import Template as _Template

    _CHAT_PROMPT_TMPL = _Template(
        "[사용자 일정 및 Gmail 데이터]\n"
        "$context\n\n"
        "[질문] $question\n"
        "[답변]"
    )

    _chain = RAGChain(
        prompt_template=_CHAT_PROMPT_TMPL,
        use_rag=False,
        system_prompt=_CHAT_SYSTEM,
    )
    _ai_available = True
    logger.info("RAGChain 로드 성공")
except Exception as e:
    _chain = None
    _ai_available = False
    logger.warning("RAGChain 로드 실패 — AI 비활성화: %s", e)


# ── 텍스트 정제 ───────────────────────────────────────────────────

def _clean_token(token: str) -> str:
    """
    스트리밍 토큰 경량 정제 — 단어 간 공백 보존 (strip 없음).
    마크다운·CJK만 제거하고 앞뒤 공백은 그대로 유지해야
    프론트에서 토큰을 이어붙일 때 단어 사이가 붙지 않는다.
    """
    # 1) __CREATE__ 이후 제거
    cleaned = _re.sub(r'__CREATE__[\s\S]*', '', token)
    # 2) 마크다운 기호 제거
    cleaned = _MD_RE.sub('', cleaned)
    # 3) CJK → 공백
    cleaned = _CJK_RE.sub(' ', cleaned)
    # 4) 탭·연속 스페이스 → 단일 스페이스 (줄바꿈은 보존)
    cleaned = _re.sub(r'[ \t]{2,}', ' ', cleaned)
    # strip 하지 않음 — 토큰 앞뒤 공백이 단어 구분자 역할
    return cleaned


def _clean_korean(text: str) -> str:
    """
    완성된 응답 전체 정제 (비스트리밍 · 일정 생성 경로).
    1. __CREATE__ 태그 제거
    2. 마크다운 기호 제거
    3. CJK(중국어/일본어) 문자 → 공백
    4. 파이프(|) 구분 메일 목록 → 줄바꿈으로 변환
    5. 줄바꿈 정규화 (가독성)
    6. 연속 공백 정리
    """
    # 1) __CREATE__ 태그 제거
    cleaned = _re.sub(r'__CREATE__[\s\S]*', '', text)
    # 2) 마크다운 기호 제거
    cleaned = _MD_RE.sub('', cleaned)
    # 3) CJK → 공백
    cleaned = _CJK_RE.sub(' ', cleaned)
    # 4) "N번메일:" 또는 "|N번메일:" 패턴을 줄바꿈으로 변환 (메일 목록 가독성)
    cleaned = _re.sub(r'\s*\|\s*(\d+번메일)', r'\n\1', cleaned)
    cleaned = _re.sub(r'\s*\|\s*(\d+번)', r'\n\1', cleaned)
    # 5) 인라인 리스트 ".- " 패턴 → 줄바꿈
    cleaned = _re.sub(r'\.\s*-\s+', '.\n- ', cleaned)
    # 6) 연속 공백 → 단일 공백, 3줄 이상 빈 줄 → 2줄
    cleaned = _re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = _re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


# ── 일정 생성 관련 함수 ───────────────────────────────────────────

def _parse_create_tag(text: str) -> tuple:
    """
    AI 응답에서 __CREATE__ 태그를 파싱하고 제거.
    Returns: (cleaned_text, schedule_dict | None)
    """
    match = _CREATE_TAG_RE.search(text)
    if not match:
        return text, None
    try:
        data = _json.loads(match.group(1))
        cleaned = _CREATE_TAG_RE.sub('', text).strip()
        return cleaned, data
    except _json.JSONDecodeError:
        logger.warning("__CREATE__ 태그 JSON 파싱 실패: %s", match.group(1))
        return text, None


def _create_habit_from_data(data: dict, db: Session) -> dict | None:
    """
    AI가 추출한 데이터로 Habit + TreeOnMap 생성.
    보안: title 길이 제한, days/time 유효성 검사.
    """
    try:
        title = str(data.get("title", "")).strip()[:100]
        if not title:
            logger.warning("일정 생성 실패: 제목 없음")
            return None

        # 시간: HH:MM 형식만 허용
        time_str = str(data.get("time", "")).strip()
        times = [time_str] if time_str and _re.match(r'^\d{2}:\d{2}$', time_str) else []

        # 요일: 0~6 정수만 허용, 중복 제거
        days_raw = data.get("days", [])
        days = sorted({
            int(d) for d in (days_raw if isinstance(days_raw, list) else [])
            if isinstance(d, (int, float)) and 0 <= int(d) <= 6
        })

        # UserProfile id=1 없으면 생성 (싱글유저 앱이므로 항상 1행이어야 함)
        from sqlalchemy import text as _sql_text
        user_exists = db.query(UserProfile).filter(UserProfile.id == 1).first()
        if not user_exists:
            db.add(UserProfile(id=1))
            db.flush()

        new_habit = Habit(
            user_id=1,          # 명시적으로 user_id 지정
            title=title,
            repeat_days=days,
            times=times,
            alarm_enabled=True,
            hearts_reward=1,
        )
        db.add(new_habit)
        db.flush()  # ID 확보 (commit 전)

        tree_count = db.query(TreeOnMap).count()
        tree = TreeOnMap(
            habit_id=new_habit.id,
            grid_x=tree_count % 6,
            grid_y=tree_count // 6,
            growth_stage=0,
            hearts_available=0,
        )
        db.add(tree)
        db.commit()
        db.refresh(new_habit)

        logger.info("채팅으로 일정 생성 — id=%d, title='%s'", new_habit.id, title)
        return {"id": new_habit.id, "title": title}

    except Exception as e:
        db.rollback()
        logger.error("일정 생성 DB 오류: %s", e)
        return None


def _check_ollama_alive() -> bool:
    """Ollama 서버 생존 확인 (타임아웃 감지 후 호출)"""
    try:
        import requests as _req
        r = _req.get("http://127.0.0.1:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


# ── Gmail 키워드 추출 ─────────────────────────────────────────────

def _extract_gmail_keywords(user_message: str) -> str:
    josa_suffixes = (
        "에서", "에게", "한테", "로부터", "으로부터",
        "에서는", "에서도", "에게는", "로서", "으로서",
        "에게도", "한테서", "에도", "에는", "로도",
        "에", "의", "은", "는", "이", "가", "을", "를",
        "와", "과", "도", "로", "으로", "만",
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
        word = tok
        for sfx in sorted(josa_suffixes, key=len, reverse=True):
            if word.endswith(sfx) and len(word) > len(sfx) + 1:
                word = word[: -len(sfx)]
                break
        word = word.strip("?!.,~")
        if len(word) < 2 or word in skip_words:
            continue
        keywords.append(word)

    msg_lower = user_message
    is_schedule_query = any(k in msg_lower for k in _SCHEDULE_INTENTS)
    if is_schedule_query:
        return "일정 OR 약속 OR 미팅 OR 회의 OR 예약 OR 초대"
    return " OR ".join(keywords) if keywords else ""


def _extract_email_body(payload: dict, max_chars: int = 500) -> str:
    """
    Gmail 메시지 payload에서 text/plain 본문 추출 (최대 max_chars자).
    멀티파트 메시지도 재귀 탐색.
    보안: base64 디코딩 오류 시 빈 문자열 반환.
    """
    import base64

    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                # 연속 공백·빈 줄 정리
                text = _re.sub(r'\r\n', '\n', text)
                text = _re.sub(r'\n{3,}', '\n\n', text)
                return text.strip()[:max_chars]
            except Exception:
                return ""
    # 멀티파트: text/plain 파트 재귀 탐색
    if "multipart" in mime:
        for part in payload.get("parts", []):
            result = _extract_email_body(part, max_chars)
            if result:
                return result
    return ""


def _fetch_gmail_messages(
    gmail_svc,
    query: str,
    max_results: int,
    seen_ids: set,
    include_body: bool = False,
) -> list:
    """
    Gmail API 메시지 목록 조회.
    - seen_ids: 중복 제거
    - include_body: True면 본문 텍스트(최대 500자) 포함
      (snippet은 200자 자동 미리보기, body는 실제 텍스트)
    """
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

            # 본문 필요 시 format=full, 아니면 metadata만
            fmt = "full" if include_body else "metadata"
            msg = gmail_svc.users().messages().get(
                userId="me", id=m["id"],
                format=fmt,
                metadataHeaders=["Subject", "From", "Date"] if not include_body else None,
            ).execute()

            headers = msg["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(제목 없음)")
            sender  = next((h["value"] for h in headers if h["name"] == "From"),    "(발신자 없음)")
            date    = next((h["value"] for h in headers if h["name"] == "Date"),    "")

            # 본문: 실제 텍스트 추출 (snippet보다 정확한 날짜/시간 정보 포함 가능)
            body = ""
            if include_body:
                body = _extract_email_body(msg["payload"])
                if not body:
                    # 본문 추출 실패 시 snippet 폴백
                    body = msg.get("snippet", "")[:300]

            result.append({
                "subject": subject[:80],
                "sender":  sender[:50],
                "date":    date[:25],
                "body":    body,
            })
        return result
    except Exception as e:
        logger.warning("Gmail 메시지 조회 실패: %s", e)
        return []


def _try_get_google_context(user_query: str = "") -> str:
    """Google Calendar + Gmail 컨텍스트. 실패 시 빈 문자열."""
    try:
        from auth_manager import get_credentials
        from googleapiclient.discovery import build

        creds = get_credentials(GOOGLE_SCOPES)
        lines = []

        # ── Google Calendar ──
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

        # ── Gmail ──
        try:
            gmail = build("gmail", "v1", credentials=creds)
            seen_ids: set = set()

            unread = _fetch_gmail_messages(gmail, "is:unread", 5, seen_ids)
            lines.append("")
            lines.append("=== Gmail 최근 미확인 이메일 ===")
            if unread:
                for m in unread:
                    lines.append(f"- [{m['date']}] {m['sender']} | {m['subject']}")
            else:
                lines.append("미확인 이메일 없음")

            if user_query:
                keywords = _extract_gmail_keywords(user_query)
                if keywords:
                    # 키워드 검색: 실제 본문 텍스트(최대 500자) 포함 — 날짜·시간 정보 추출 정확도 향상
                    keyword_results = _fetch_gmail_messages(
                        gmail, keywords, 5, seen_ids, include_body=True
                    )
                    lines.append("")
                    lines.append(f"=== Gmail 검색 결과 (키워드: {keywords}) ===")
                    if keyword_results:
                        for m in keyword_results:
                            lines.append(f"- [{m['date']}] {m['sender']}")
                            lines.append(f"  제목: {m['subject']}")
                            if m.get("body"):
                                lines.append(f"  본문:\n{m['body']}")
                    else:
                        lines.append(f"'{keywords}' 관련 이메일 없음")

        except Exception as gmail_err:
            lines.append(f"=== Gmail 로드 실패: {gmail_err} ===")

        return "\n".join(lines)

    except Exception as e:
        logger.warning("Google 컨텍스트 로드 실패 (인증 필요): %s", e)
        return ""


# ── 라우터 ────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/chat", tags=["chat"])

DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


def build_schedule_context(db: Session) -> str:
    """DB 일정/습관 데이터를 AI 컨텍스트 문자열로 변환"""
    now = datetime.now()
    today_weekday = now.weekday()
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
        status = "완료" if h.completed_today else "미완료"
        streak_str = f"{h.streak}일 연속" if h.streak > 0 else "시작 전"

        lines.append(
            f"- [{status}] {h.title} | 반복: {days_str} | 시간: {times_str} | 스트릭: {streak_str}"
        )

        if today_weekday in repeat:
            today_habits.append(h)
            for t in times:
                if t > current_time and not h.completed_today:
                    upcoming_habits.append((h.title, t))

    lines.append("")
    lines.append(f"=== 오늘({DAY_NAMES[today_weekday]}요일) 일정 ===")
    if today_habits:
        for h in today_habits:
            status = "완료" if h.completed_today else "미완료"
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


def _build_context(message: str, db: Session) -> str:
    """일정 DB + Gmail 컨텍스트 조합"""
    schedule_ctx = build_schedule_context(db)
    google_ctx = _try_get_google_context(user_query=message)
    parts = [schedule_ctx]
    if google_ctx:
        parts.append(google_ctx)
    return "\n\n".join(parts)


# ── 비스트리밍 채팅 ───────────────────────────────────────────────

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
        context = _build_context(req.message, db)
        raw_reply = _chain.ask(req.message, extra_context=context)

        # 일정 생성 태그 파싱
        clean_reply, schedule_data = _parse_create_tag(raw_reply)
        clean_reply = _clean_korean(clean_reply)

        if schedule_data:
            created = _create_habit_from_data(schedule_data, db)
            if created:
                clean_reply += f"\n\n✅ '{created['title']}' 일정이 등록됐어요!"

        return ChatResponse(reply=clean_reply, ai_available=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 응답 오류: {str(e)}")


# ── SSE 스트리밍 채팅 ─────────────────────────────────────────────

@router.post("/stream")
async def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """SSE 스트리밍 — ChatDashboard.js 사용"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어 있습니다.")

    if not _ai_available or _chain is None:
        async def error_stream():
            msg = _json.dumps(
                {"token": "⚠️ AI 모듈이 로드되지 않았습니다. 백엔드를 재시작해주세요.", "done": False},
                ensure_ascii=False,
            )
            yield f"data: {msg}\n\n"
            yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # DB 세션 유효 시점에 컨텍스트 빌드
    try:
        context = _build_context(req.message, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨텍스트 빌드 오류: {str(e)}")

    user_message = req.message
    is_create = any(kw in user_message for kw in _CREATE_INTENT_KEYWORDS)

    async def token_stream():
        sent_any = False

        try:
            # ── 일정 생성 의도: 논스트리밍으로 전체 응답 받아 파싱 ──────
            if is_create:
                loop = asyncio.get_event_loop()
                try:
                    raw_reply = await asyncio.wait_for(
                        loop.run_in_executor(
                            None,
                            lambda: _chain.ask(user_message, extra_context=context),
                        ),
                        timeout=130,
                    )
                except asyncio.TimeoutError:
                    raw_reply = ""

                if not raw_reply:
                    # 타임아웃 → Ollama 상태 확인 후 안내
                    if _check_ollama_alive():
                        msg = "응답 시간이 초과됐어요. ⏱ 잠시 후 다시 시도해 주세요."
                    else:
                        msg = "Ollama 서버가 응답하지 않아요. 'ollama serve'를 실행해 주세요."
                    yield f"data: {_json.dumps({'token': msg, 'done': False}, ensure_ascii=False)}\n\n"
                    yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"
                    return

                # 태그 파싱 + 마크다운 정제
                clean_reply, schedule_data = _parse_create_tag(raw_reply)
                clean_reply = _clean_korean(clean_reply)

                # 일정 DB 저장 (새 세션 — 요청 세션과 별도)
                schedule_result = None
                if schedule_data:
                    with SessionLocal() as new_db:
                        schedule_result = _create_habit_from_data(schedule_data, new_db)

                # 단어 단위로 스트리밍
                for word in clean_reply.split(' '):
                    if word:
                        sent_any = True
                        payload = _json.dumps({"token": word + ' ', "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                        await asyncio.sleep(0.02)

                # 일정 등록 확인 메시지
                if schedule_result:
                    confirm = f"\n\n✅ '{schedule_result['title']}' 일정이 등록됐어요! 일정 탭에서 확인해보세요."
                    sent_any = True
                    yield f"data: {_json.dumps({'token': confirm, 'done': False}, ensure_ascii=False)}\n\n"

            # ── 일반 스트리밍 ────────────────────────────────────────
            else:
                if hasattr(_chain, "ask_stream"):
                    async for token in _chain.ask_stream(user_message, extra_context=context):
                        # _clean_token: strip 없이 공백 보존 → 단어 사이 붙는 현상 방지
                        clean = _clean_token(token)
                        if clean.strip():  # 내용이 없는 순수 공백 토큰만 제외
                            sent_any = True
                            payload = _json.dumps({"token": clean, "done": False}, ensure_ascii=False)
                            yield f"data: {payload}\n\n"
                        await asyncio.sleep(0)
                else:
                    # 폴백: 전체 응답 → 단어 스트리밍
                    loop = asyncio.get_event_loop()
                    try:
                        reply = await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                lambda: _chain.ask(user_message, extra_context=context),
                            ),
                            timeout=130,
                        )
                    except asyncio.TimeoutError:
                        reply = ""

                    reply = _clean_korean(reply)
                    for word in reply.split(' '):
                        if word:
                            sent_any = True
                            payload = _json.dumps({"token": word + ' ', "done": False}, ensure_ascii=False)
                            yield f"data: {payload}\n\n"
                            await asyncio.sleep(0.02)

            # ── 아무 토큰도 못 보낸 경우 (타임아웃 / 빈 응답) ──────────
            if not sent_any:
                if _check_ollama_alive():
                    fallback = "응답이 너무 오래 걸렸어요. ⏱ 잠시 후 다시 질문해 주세요."
                else:
                    fallback = "Ollama 서버가 응답하지 않아요. 'ollama serve'를 실행해 주세요."
                yield f"data: {_json.dumps({'token': fallback, 'done': False}, ensure_ascii=False)}\n\n"

            yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"

        except Exception as e:
            logger.error("token_stream 오류: %s", e)
            err = _json.dumps({"error": str(e), "done": True}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── 헬스체크 ─────────────────────────────────────────────────────

TARGET_MODEL = "qwen3.5:9b"


@router.get("/health")
async def chat_health():
    """Ollama 실행 상태 확인 — OllamaPopup.js 및 ChatDashboard.js 사용"""
    ollama_installed = False
    ollama_running = False
    model_loaded = False
    error_msg = None

    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        ollama_installed = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        ollama_installed = False

    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_running = True
                ollama_installed = True
                tags = resp.json().get("models", [])
                model_loaded = any(
                    TARGET_MODEL.split(":")[0] in m.get("name", "").lower()
                    for m in tags
                )
    except Exception as e:
        error_msg = str(e)

    return {
        "ollama_installed": ollama_installed,
        "ollama_running":   ollama_running,
        "model_loaded":     model_loaded,
        "model":            TARGET_MODEL,
        "ai_available":     _ai_available,
        "error":            error_msg,
    }


@router.post("/setup-ollama")
async def setup_ollama():
    """Ollama 설치/모델 확인 — OllamaPopup.js 사용"""
    steps = []
    success = True
    error_msg = None

    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            steps.append({"step": "ollama_check", "status": "ok", "message": "Ollama가 실행 중입니다."})
        else:
            steps.append({"step": "ollama_check", "status": "error",
                          "message": "Ollama를 찾을 수 없습니다. https://ollama.ai 에서 설치하세요."})
            success = False
    except FileNotFoundError:
        steps.append({"step": "ollama_check", "status": "error",
                      "message": "Ollama가 설치되어 있지 않습니다. https://ollama.ai 에서 설치하세요."})
        success = False
    except subprocess.TimeoutExpired:
        steps.append({"step": "ollama_check", "status": "error", "message": "Ollama 응답 시간 초과."})
        success = False
    except Exception as e:
        steps.append({"step": "ollama_check", "status": "error", "message": str(e)})
        success = False
        error_msg = str(e)

    if success:
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5,
            )
            if "qwen3.5" in result.stdout.lower() or "qwen2.5" in result.stdout.lower():
                steps.append({"step": "model_check", "status": "ok",
                               "message": "Qwen 모델이 설치되어 있습니다."})
            else:
                steps.append({"step": "model_check", "status": "warning",
                               "message": "터미널에서 'ollama pull qwen3.5:9b' 또는 'ollama pull qwen2.5:7b'를 실행하세요."})
        except Exception as e:
            steps.append({"step": "model_check", "status": "error", "message": str(e)})

    return {"success": success, "steps": steps, "error": error_msg}


@router.get("/debug-context")
async def debug_context(q: str = "skala 메일 있어?", db: Session = Depends(get_db)):
    """컨텍스트 확인용 (개발/디버그 전용)"""
    schedule_ctx = build_schedule_context(db)
    google_ctx = _try_get_google_context(user_query=q)
    parts = [schedule_ctx]
    if google_ctx:
        parts.append(google_ctx)
    full_context = "\n\n".join(parts)
    return {
        "query":                q,
        "schedule_ctx_len":     len(schedule_ctx),
        "google_ctx_len":       len(google_ctx),
        "google_ctx_present":   bool(google_ctx),
        "total_context_len":    len(full_context),
        "preview":              full_context[:2000],
    }
