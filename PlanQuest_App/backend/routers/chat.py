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
# 주의: "추가해", "등록해" 단독 사용 금지 — "추가해야할", "등록해서" 등 오탐 발생
# 반드시 명시적 명령형(줘/주세요) 또는 완전한 구문만 포함
_CREATE_INTENT_KEYWORDS = [
    "추가해줘", "등록해줘", "넣어줘", "만들어줘",
    "추가해 줘", "등록해 줘", "넣어 줘", "만들어 줘",
    "추가해주세요", "등록해주세요", "넣어주세요",
    "캘린더에 추가", "일정에 넣어", "알람 설정해줘", "알림 설정해줘",
    # "잡아줘" 계열 — 일정 잡아줘, 약속 잡아줘 등
    "잡아줘", "잡아 줘", "잡아주세요", "잡아줄래", "잡아줄래요",
    # 메일 기반 일정 추출 요청
    "메일에서 일정", "메일 내용으로 일정", "메일 일정 추가", "이 메일 일정",
]

# ── 일정 생성 태그 파싱 정규식 ────────────────────────────────────
# AI 응답 마지막에 __CREATE__:{"title":..., "time":..., "days":[], "repeat":bool} 형태
# 중첩 없는 단순 JSON 객체 — 탐욕적 매칭으로 마지막 } 까지 잡음
_CREATE_TAG_RE = _re.compile(r'__CREATE__\s*:\s*(\{[^}]*\})', _re.DOTALL)

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
    r'一-鿿'       # CJK 통합 한자
    r'㐀-䶿'       # CJK 확장 A
    r'぀-ゟ'  # 히라가나 (あ-ん)
    r'゠-ヿ'  # 가타카나 (ア-ン)
    r'　-〿'       # CJK 기호·문장부호
    r'＀-￯'       # 전각 로마자 / 반각 가타카나
    r'⺀-⻿'       # CJK 부수 보충
    r'㇀-㇯'       # CJK 획
    r']+',
    _re.UNICODE
)

# ── 채팅 전용 시스템 프롬프트 ─────────────────────────────────────
_CHAT_SYSTEM = (
    "당신은 한국어 전용 AI 스케줄러 비서입니다.\n"
    "\n"
    "## 절대 규칙 (위반 시 답변 무효)\n"
    "1. 반드시 한국어로만 답변하세요. 중국어(한자 포함), 일본어를 절대 출력하지 마세요.\n"
    "2. <think>...</think> 등 내부 추론 과정을 출력하지 마세요. 최종 답변만 출력하세요.\n"
    "3. 마크다운 문법(**볼드**, ##헤더, `코드`, _이탤릭_, ~~취소선~~)을 절대 사용하지 마세요.\n"
    "4. 서론·인사·'네, 알겠습니다' 같은 불필요한 앞말 없이 바로 핵심만 답변하세요.\n"
    "\n"
    "## 이메일·일정 답변 규칙 (가장 중요)\n"
    "- 오직 아래 [사용자 일정 및 Gmail 데이터] 섹션에 실제로 적혀 있는 내용만 답변하세요.\n"
    "- 데이터에 없는 이메일, 일정, 발신자, 날짜는 절대 만들어내지 마세요.\n"
    "- 찾는 이메일이 데이터에 없으면: '해당 이메일이 없습니다.'라고 하세요.\n"
    "- 찾는 일정이 데이터에 없으면: '해당 일정이 없습니다.'라고 하세요.\n"
    "- 이메일과 일정을 혼동하지 마세요. 메일 질문에 일정 답변, 일정 질문에 메일 답변 금지.\n"
    "- [Gmail 검색 결과] 섹션이 있으면 그 내용만 답변하고, [Gmail 최근 이메일] 섹션은 무시하세요.\n"
    "- [Gmail 검색 결과] 섹션이 없으면 [Gmail 최근 이메일] 섹션으로 답변하세요.\n"
    "- 이메일 목록 형식:\n"
    "  [날짜] 발신자 | 제목\n"
    "  본문: (내용)\n"
    "- 사용자가 '본문', '내용', '전체' 를 요청하면 데이터에 있는 본문을 그대로 출력하세요. 요약하지 마세요.\n"
    "\n"
    "## 일반 대화 규칙\n"
    "- 인사(안녕, 하이 등)에는 짧고 자연스럽게 답하세요. (예: '안녕하세요!')\n"
    "- 질문과 관계없는 내용을 추가하지 마세요.\n"
    "\n"
    "## 일정 등록 규칙\n"
    "사용자가 '추가해줘', '등록해줘', '넣어줘', '만들어줘', '잡아줘'를 명시적으로 말할 때만:\n"
    "STEP 1. 한 줄 확인 문장: '네, [제목] 일정을 등록할게요!'\n"
    "STEP 2. 바로 다음 줄에 태그 (형식 정확히 지킬 것):\n"
    "__CREATE__:{\"title\":\"제목\",\"time\":\"HH:MM\",\"days\":[0],\"repeat\":true}\n"
    "  - days: 0=월,1=화,2=수,3=목,4=금,5=토,6=일 / 없으면 []\n"
    "  - time: HH:MM 형식 / 없으면 \"\"\n"
    "  - repeat: 매주 반복=true, 1회성=false\n"
    "STEP 3. 제목이 없으면 묻고 기다리세요: '어떤 일정인가요? 제목을 알려주세요!'\n"
    "  - 시간만 있고 제목이 없어도 절대 '해당 일정이 없습니다'라고 하지 마세요.\n"
    "  - 일정 생성 요청과 일정 조회 요청을 혼동하지 마세요.\n"
    "  - '추가해줘/잡아줘/등록해줘' = 새 일정 만들기 → __CREATE__ 또는 제목 질문\n"
    "  - '알려줘/보여줘/있어?' = 기존 일정 조회 → 목록 출력\n"
    "주의: 일정 조회·메일 확인·일반 대화에는 __CREATE__ 태그를 절대 쓰지 마세요.\n"
    "\n"
    "## 메일에서 일정 추출 규칙 (중요)\n"
    "사용자가 '이 메일에서 일정 추가해줘', '메일 내용으로 일정 등록해줘' 처럼 메일 기반 일정 추가를 요청할 때:\n"
    "- 반드시 제공된 Gmail 데이터의 본문에서 날짜·시간·일정명을 찾아 추출하세요.\n"
    "- 사용자 메시지가 아닌 메일 본문에서 제목과 날짜를 가져오세요.\n"
    "- 예시: 메일 본문에 'SKCT 심층역량검사 (2026.05.21~23)' 있으면\n"
    "  → __CREATE__:{\"title\":\"SKCT 심층역량검사\",\"time\":\"\",\"days\":[],\"repeat\":false}\n"
    "- 메일에 여러 일정이 있으면 가장 중요한 것 하나만 등록하고 나머지는 안내하세요.\n"
)


# ── RAGChain 초기화 ───────────────────────────────────────────────
try:
    from rag_chain import RAGChain
    from string import Template as _Template

    _CHAT_PROMPT_TMPL = _Template(
        "=== 사용자 일정 및 Gmail 데이터 (이 데이터에만 기반해서 답변할 것) ===\n"
        "$context\n"
        "=== 데이터 끝 (위에 없는 내용은 절대 답변에 포함하지 말 것) ===\n\n"
        "[질문] $question\n"
        "[답변]"
    )

    _chain = RAGChain(
        prompt_template=_CHAT_PROMPT_TMPL,
        use_rag=False,
        system_prompt=_CHAT_SYSTEM,
        temperature=0.3,   # 낮을수록 사실 기반 / 높을수록 창의적(환각 위험)
        max_tokens=1024,   # 과도하게 긴 답변 방지
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
    # 2) <think>...</think> 내부 제거 (qwen3.5 thinking 모드 방어)
    cleaned = _re.sub(r'<think>[\s\S]*?</think>', '', cleaned)
    # 3) 마크다운 기호 제거
    cleaned = _MD_RE.sub('', cleaned)
    # 4) CJK → 공백
    cleaned = _CJK_RE.sub(' ', cleaned)
    # 5) 탭·연속 스페이스 → 단일 스페이스 (줄바꿈은 보존)
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
    # 1-1) <think>...</think> 블록 제거 (qwen3.5 thinking 모드 방어)
    cleaned = _re.sub(r'<think>[\s\S]*?</think>', '', cleaned)
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

def _extract_schedule_nlp(user_message: str) -> dict | None:
    """
    AI 없이 한국어 메시지에서 일정 정보를 직접 추출 (폴백용).
    AI가 __CREATE__ 태그를 누락했을 때 사용.

    처리 패턴:
      "내일 오전 10시에 팀 미팅 추가해줘"
        → {"title":"팀 미팅","time":"10:00","days":[],"repeat":false}
      "매주 월요일 오전 9시 스크럼 등록해줘"
        → {"title":"스크럼","time":"09:00","days":[0],"repeat":true}
    """
    msg = user_message

    # ── 1) 시간 추출 (가장 먼저 — 이후 제목 추출 시 제거) ──────────
    time_str = ""

    def _pm_hour(h: int) -> int:
        return h + 12 if h < 12 else h

    # 순서대로 시도 (더 구체적인 패턴 먼저)
    _time_patterns = [
        (r'오후\s*(\d{1,2})시\s*(\d{1,2})분', lambda m: f"{_pm_hour(int(m.group(1))):02d}:{int(m.group(2)):02d}"),
        (r'오전\s*(\d{1,2})시\s*(\d{1,2})분', lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        (r'오후\s*(\d{1,2})시',               lambda m: f"{_pm_hour(int(m.group(1))):02d}:00"),
        (r'오전\s*(\d{1,2})시',               lambda m: f"{int(m.group(1)):02d}:00"),
        (r'저녁\s*(\d{1,2})시\s*(\d{1,2})분', lambda m: f"{_pm_hour(int(m.group(1))):02d}:{int(m.group(2)):02d}"),
        (r'저녁\s*(\d{1,2})시',               lambda m: f"{_pm_hour(int(m.group(1))):02d}:00"),
        (r'아침\s*(\d{1,2})시\s*(\d{1,2})분', lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        (r'아침\s*(\d{1,2})시',               lambda m: f"{int(m.group(1)):02d}:00"),
        (r'밤\s*(\d{1,2})시\s*(\d{1,2})분',   lambda m: f"{_pm_hour(int(m.group(1))):02d}:{int(m.group(2)):02d}"),
        (r'밤\s*(\d{1,2})시',                 lambda m: f"{_pm_hour(int(m.group(1))):02d}:00"),
        (r'낮\s*(\d{1,2})시\s*(\d{1,2})분',   lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        (r'낮\s*(\d{1,2})시',                 lambda m: f"{int(m.group(1)):02d}:00"),
        (r'(\d{1,2})시\s*(\d{1,2})분',        lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        (r'(\d{1,2}):(\d{2})',                lambda m: f"{int(m.group(1)):02d}:{m.group(2)}"),
        (r'(\d{1,2})시',                      lambda m: f"{int(m.group(1)):02d}:00"),
    ]
    for pat, fmt in _time_patterns:
        m = _re.search(pat, msg)
        if m:
            time_str = fmt(m)
            msg = msg[:m.start()] + " " + msg[m.end():]
            break

    # ── 2) 반복 요일 추출 ────────────────────────────────────────
    days: list[int] = []
    repeat = False
    # "매주 월요일" 처럼 '매주'가 있으면 이후 요일 언급도 repeat=True
    has_weekly = bool(_re.search(r'매주|격주', msg))

    if _re.search(r'매일|날마다', msg):
        days = list(range(7))
        repeat = True
    elif _re.search(r'평일|주중', msg):
        days = [0, 1, 2, 3, 4]
        repeat = True
    elif _re.search(r'주말', msg):
        days = [5, 6]
        repeat = True
    else:
        _day_map = [("월", 0), ("화", 1), ("수", 2), ("목", 3), ("금", 4), ("토", 5), ("일", 6)]
        for name, num in _day_map:
            # "매수요일", "매수" 등 — 반복
            if _re.search(rf'매{name}(?:요일)?', msg):
                days.append(num)
                repeat = True
            # "수요일마다" — 반복 (negative lookbehind: 앞에 한글 없어야 함)
            elif _re.search(rf'(?<![가-힣]){name}요일마다', msg):
                days.append(num)
                repeat = True
            # "수요일" (단순 요일 언급 — 매주 있으면 repeat도 True)
            elif _re.search(rf'(?<![가-힣]){name}요일(?!마다)', msg):
                days.append(num)
                if has_weekly:
                    repeat = True
        days = sorted(set(days))

    # ── 3) 제목 추출 (노이즈 제거 후 남은 한국어) ───────────────
    _remove = [
        r'추가해줘?|등록해줘?|넣어줘?|만들어줘?|잡아줘?|잡아주세요',
        r'추가해|등록해|넣어|만들어|잡아',
        r'일정(?:으로|에|에다가|으로)?(?:\s*추가|등록|넣어)?',
        r'캘린더에?(?:\s*추가|등록)?',
        r'알람\s*설정|알림\s*설정',
        r'내일|오늘|모레|다음\s*주|이번\s*주|매주',
        r'매일|평일|주말|주중',
        r'매[월화수목금토일](?:요일)?|[월화수목금토일]요일마다|[월화수목금토일]요일|[월화수목금토일]마다',
        r'오전|오후|아침|저녁|낮|밤',
        r'\d+시간|\d+분|\d+초',
        r'해줘?|알려줘?|주세요|해주세요',
        r'(?<![가-힣])에(?=[^서]|$)',  # 조사 "에" (에서 제외)
        r'에서|에게|한테|한테서|로부터|부터',
    ]
    title_msg = msg
    for pat in _remove:
        title_msg = _re.sub(pat, ' ', title_msg)
    title = _re.sub(r'\s+', ' ', title_msg).strip('?!.,~"\' ()')
    title = title.strip()

    if not title or len(title) < 1:
        # 제목 없지만 시간·요일 정보가 있으면 기본 제목 사용
        if time_str or days:
            title = "새 일정"
            logger.info("NLP 일정 추출: 제목 없음 → 기본값 '새 일정' 사용 (원본='%s')", user_message[:60])
        else:
            logger.warning("NLP 일정 추출: 제목·시간 모두 없음 — 생성 불가 (원본='%s')", user_message[:60])
            return None

    result = {
        "title": title[:100],
        "time": time_str,
        "days": days,
        "repeat": repeat,
    }
    logger.info("NLP 일정 추출 성공: %s", result)
    return result


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

# 발신자 패턴 감지용 키워드 (이 단어 다음에 오는 토큰이 발신자)
_SENDER_TRIGGERS = ("에서", "로부터", "한테서", "이", "가")

def _extract_gmail_keywords(user_message: str) -> str:
    """
    Gmail 검색 쿼리 추출.

    핵심 설계:
    - Gmail 검색에서 공백 = AND, 'OR' 키워드 = OR
    - OR는 관련 없는 메일도 반환하므로 AND(공백) 방식 사용
    - 발신자 패턴('skala에서') → from: 연산자로 변환
    - 대괄호 안 주요 키워드 우선 추출 (메일 제목에 많음)
    - 일정 생성 요청(추가해줘 등)은 Gmail 검색 불필요 → 빈 문자열 반환
    - 가장 길고 고유한 키워드 상위 2개만 AND 검색
    """
    josa_suffixes = (
        "에서는", "에서도", "에게는", "로부터", "으로부터", "한테서",
        "으로서", "에게도", "에서", "에게", "한테", "로서",
        "에도", "에는", "로도", "에", "의", "은", "는",
        "이", "가", "을", "를", "와", "과", "도", "로", "으로", "만",
    )
    skip_words = {
        "메일", "이메일", "gmail", "있어", "있나요", "있나", "있어요",
        "보여줘", "알려줘", "확인해줘", "해줘", "찾아줘", "검색해줘",
        "7일간", "7일동안", "오늘", "최근", "관련", "뭐", "어떤",
        "몇", "개", "건", "있습니다", "없습니다", "주세요", "해주세요",
        "뭔데", "뭐야", "뭔가요", "알려", "알고", "싶어", "궁금",
        "어디", "어때", "어떻게", "좀", "제발", "혹시", "그거",
        "잘", "내용", "봐", "확인", "찾아봐", "확인해봐", "찾아",
        "관한", "대한", "관해", "대해", "결과", "발표",
        "날짜", "시간", "언제", "일정", "추가", "등록", "넣어",
        "추가해줘", "등록해줘", "넣어줘", "만들어줘", "추가해", "등록해",
        # 본문 조회 요청 시 검색 쿼리 오염 방지
        "전체", "본문", "전부", "모두", "다", "뭐라고", "왔어", "왔어요",
        "뭐야", "어떻게", "됐어", "됐나요", "합격", "불합격", "결과",
        "읽어줘", "읽어", "내용이", "내용은", "내용을",
        # 의문형 어미 — 검색 키워드로 오탐 방지
        "뭐왔어", "뭐왔어요", "왔나", "왔나요", "왔냐", "있냐",
        "뭔지", "뭔데", "뭐있어", "뭐있나", "뭐가",
    }

    # 0) 일정 생성 요청은 Gmail 검색 불필요 (AI가 직접 __CREATE__ 태그 처리)
    _strong_create = ("추가해줘", "등록해줘", "넣어줘", "만들어줘", "일정에 추가", "일정에 넣어")
    if any(k in user_message for k in _strong_create):
        return ""

    # 1) 대괄호 안 키워드 우선 추출 (예: "[SK주식회사(AX)] SKALA")
    bracket_words = _re.findall(r'\[([^\]]+)\]', user_message)
    # 대괄호로 감싸진 원본 문자열 범위 — 중복 추출 방지용
    bracket_spans = set()
    for m in _re.finditer(r'\[[^\]]+\]', user_message):
        bracket_spans.add(m.start())

    priority_keywords: list[str] = []
    for bw in bracket_words:
        # 소괄호도 분리 ("SK주식회사(AX)" → "SK주식회사", "AX")
        sub_tokens = _re.split(r'[\s()]+', bw)
        for tok in sub_tokens:
            tok = tok.strip(",.~[]")
            if len(tok) >= 2 and tok.lower() not in skip_words:
                priority_keywords.append(tok)

    # 2) 발신자 패턴 감지 (예: "skala에서 온 메일" → from:skala)
    from_parts: list[str] = []
    sender_words: set[str] = set()  # from: 발신자 단어 → body_keywords에서 중복 제외
    msg_tokens = user_message.strip().split()

    # 대괄호 포함 토큰은 이미 처리됐으므로 스킵
    bracket_token_re = _re.compile(r'^\[')

    for tok in msg_tokens:
        for sfx in ("에서", "로부터", "한테서"):
            if tok.endswith(sfx) and len(tok) > len(sfx) + 1:
                sender_word = tok[: -len(sfx)].strip("?!.,~[]()").lower()
                if len(sender_word) >= 2 and sender_word not in skip_words:
                    from_parts.append(f"from:{sender_word}")
                    sender_words.add(sender_word)
                break

    # 3) 일반 토큰 키워드 추출 (조사 제거)
    keywords: list[str] = []
    for tok in msg_tokens:
        # 대괄호로 시작하는 토큰은 이미 bracket 처리됨 → 스킵
        if bracket_token_re.match(tok):
            continue
        # 괄호·대괄호·특수문자 제거
        word = _re.sub(r'[\[\](){}]', '', tok).strip("?!.,~\"' ")
        # 조사 제거
        for sfx in sorted(josa_suffixes, key=len, reverse=True):
            if word.endswith(sfx) and len(word) > len(sfx) + 1:
                word = word[: -len(sfx)]
                break
        word = word.strip("?!.,~\"' ")
        if len(word) < 2 or word.lower() in skip_words:
            continue
        # 영숫자+한글 혼합 토큰 처리 (예: "skct봐야하" → "skct")
        # 단, 한글 부분이 4자 이상이면 의미 있는 단어로 판단해 전체 유지
        # (예: "ai역량면접" → 한글 4자 이상 → 전체 유지)
        ascii_match = _re.match(r'^([A-Za-z0-9_\-\.]+)', word)
        if ascii_match and len(ascii_match.group(1)) >= 2:
            korean_suffix = word[len(ascii_match.group(1)):]
            if 0 < len(korean_suffix) <= 3:
                # 3자 이하 한글 접미사 = 조사/어미로 판단 → 영문만
                word = ascii_match.group(1)
            # 4자 이상이면 의미 있는 한글 → word 그대로 유지
        keywords.append(word)

    # 4) 중복 제거 + 길이 내림차순 (긴 단어 = 더 구체적)
    #    - from: 발신자 단어는 body_keywords에서 제외 (중복 방지)
    seen: set[str] = set(sender_words)  # 발신자 단어는 이미 from:으로 처리됨
    ordered: list[str] = []
    for w in priority_keywords + keywords:
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            ordered.append(w)
    ordered.sort(key=len, reverse=True)

    # 5) 결과 없으면 빈 문자열 (Gmail 검색 생략)
    body_keywords = ordered[:2]  # 상위 2개 AND 검색
    parts = from_parts + body_keywords
    return " ".join(parts) if parts else ""


def _decode_body_data(data: str, max_chars: int) -> str:
    """base64url → UTF-8 텍스트 디코딩. 오류 시 빈 문자열."""
    import base64
    try:
        text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        text = _re.sub(r'\r\n', '\n', text)
        text = _re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()[:max_chars]
    except Exception:
        return ""


def _strip_html(html: str, max_chars: int) -> str:
    """HTML 태그 제거 후 텍스트 추출."""
    text = _re.sub(r'<style[\s\S]*?</style>', '', html, flags=_re.IGNORECASE)
    text = _re.sub(r'<script[\s\S]*?</script>', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    text = _re.sub(r'[ \t]{2,}', ' ', text)
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()[:max_chars]


def _extract_email_body(payload: dict, max_chars: int = 1000) -> str:
    """
    Gmail 메시지 payload에서 본문 추출 (최대 max_chars자).
    우선순위: text/plain → text/html(태그 제거) → 멀티파트 재귀
    보안: base64 디코딩 오류 시 빈 문자열 반환.
    """
    mime = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and data:
        return _decode_body_data(data, max_chars)

    if mime == "text/html" and data:
        raw = _decode_body_data(data, max_chars * 5)  # HTML은 태그 포함이라 넉넉히
        return _strip_html(raw, max_chars) if raw else ""

    # 멀티파트: text/plain 우선, 없으면 text/html
    if "multipart" in mime:
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("mimeType") == "text/plain":
                result = _extract_email_body(part, max_chars)
                if result:
                    return result
        for part in parts:
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

            # 본문: 실제 텍스트 추출 (최대 1000자 — AI 컨텍스트 창 고려)
            body = ""
            if include_body:
                body = _extract_email_body(msg["payload"], max_chars=1000)
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

            # 최근 주요 메일 — 광고·소셜·업데이트·포럼 명시적 제외
            _INBOX_QUERY = (
                "in:inbox"
                " -category:promotions"
                " -category:social"
                " -category:updates"
                " -category:forums"
            )
            # "오늘" 관련 쿼리일 때 당일 날짜 필터 추가
            if user_query and any(kw in user_query for kw in ("오늘", "today")):
                today_filter = datetime.now().strftime("%Y/%m/%d")
                _INBOX_QUERY = f"after:{today_filter} " + _INBOX_QUERY

            recent = _fetch_gmail_messages(
                gmail, _INBOX_QUERY, 7, seen_ids, include_body=True
            )
            lines.append("")
            lines.append("=== Gmail 최근 이메일 (받은편지함, 광고/소셜 제외) ===")
            if recent:
                for m in recent:
                    lines.append(f"- [{m['date']}] {m['sender']} | {m['subject']}")
                    if m.get("body"):
                        lines.append(f"  본문 요약: {m['body'][:300]}")
            else:
                lines.append("최근 이메일 없음")

            if user_query:
                keywords = _extract_gmail_keywords(user_query)
                if keywords:
                    keyword_seen: set = set()
                    keyword_results = _fetch_gmail_messages(
                        gmail, keywords, 5, keyword_seen, include_body=True
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


# 단순 인사말/일상 대화 패턴 (Gmail/캘린더 조회 불필요)
_SMALL_TALK_RE = _re.compile(
    r'^(안녕|하이|헬로|hello|hi|ㅎㅇ|ㅋㅋ|ㅎㅎ|네|응|어|아|오|오오|아아'
    r'|감사|고마워|고맙|수고|잘부탁|잘 부탁|반가워|반갑|좋아|싫어'
    r'|ㅇㅋ|ok|okay|ㅂㅂ|바이|bye|굿바이'
    r'|뭐야|뭐임|뭐지|뭔가요|뭔데|왜|어떻게|어때'
    r'|테스트|test)[!?~.ㅋㅎ\s]*$',
    _re.IGNORECASE,
)

# Gmail/캘린더 조회가 필요한 키워드 (있으면 무조건 Google 컨텍스트 가져옴)
_GOOGLE_TRIGGER_KEYWORDS = (
    "메일", "이메일", "gmail", "캘린더", "일정", "미팅", "회의", "약속",
    "예약", "스케줄", "언제", "오늘", "내일", "이번 주", "다음 주",
    "추가해줘", "등록해줘", "넣어줘", "만들어줘", "알람", "알림",
    # 팔로업 검색 요청 (대화 흐름에서 Gmail 재조회 필요)
    "찾아봐", "찾아봐줘", "다시 찾아", "더 찾아", "한번 더",
)


def _needs_google_context(message: str) -> bool:
    """Gmail/캘린더 컨텍스트가 필요한 메시지인지 판단"""
    msg = message.strip()
    # 단순 인사말이면 불필요
    if _SMALL_TALK_RE.match(msg):
        return False
    # Google 트리거 키워드가 있으면 필요
    if any(kw in msg for kw in _GOOGLE_TRIGGER_KEYWORDS):
        return True
    # 10자 이하 짧은 메시지 + 트리거 없으면 불필요
    if len(msg) <= 10:
        return False
    # 그 외 일반 질문은 일정 컨텍스트만 (Gmail은 생략)
    return False


def _build_context(message: str, db: Session) -> str:
    """일정 DB + (필요 시) Gmail 컨텍스트 조합"""
    schedule_ctx = build_schedule_context(db)
    parts = [schedule_ctx]

    if _needs_google_context(message):
        google_ctx = _try_get_google_context(user_query=message)
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
            # ── 일정 생성 의도: 비스트리밍으로 전체 응답 받아 파싱 ──────
            if is_create:
                # asyncio.to_thread: 동기 함수를 스레드 풀에서 실행 (이벤트 루프 블로킹 없음)
                try:
                    raw_reply = await asyncio.wait_for(
                        asyncio.to_thread(_chain.ask, user_message, extra_context=context),
                        timeout=130,
                    )
                except asyncio.TimeoutError:
                    raw_reply = ""
                except Exception as ask_err:
                    logger.error("is_create _chain.ask 오류: %s", ask_err)
                    raw_reply = ""

                if not raw_reply:
                    if _check_ollama_alive():
                        msg = "응답 시간이 초과됐어요. ⏱ 잠시 후 다시 시도해 주세요."
                    else:
                        msg = "Ollama 서버가 응답하지 않아요. 'ollama serve'를 실행해 주세요."
                    yield f"data: {_json.dumps({'token': msg, 'done': False}, ensure_ascii=False)}\n\n"
                    yield f"data: {_json.dumps({'token': '', 'done': True})}\n\n"
                    return

                logger.info("AI raw_reply (is_create) 길이=%d: %s", len(raw_reply), raw_reply[:200])

                # ① AI 응답에서 __CREATE__ 태그 파싱 시도
                clean_reply, schedule_data = _parse_create_tag(raw_reply)
                clean_reply = _clean_korean(clean_reply)

                # ② AI가 태그를 누락했으면 NLP 폴백으로 직접 추출
                # 단, 메일 기반 요청일 때는 사용자 메시지에 일정 정보가 없으므로 NLP 폴백 생략
                _is_email_based = any(kw in user_message for kw in (
                    "메일에서 일정", "메일 내용으로 일정", "메일 일정 추가", "이 메일 일정",
                ))
                if not schedule_data and not _is_email_based:
                    logger.warning("AI가 __CREATE__ 태그 미생성 → NLP 폴백 시도")
                    schedule_data = _extract_schedule_nlp(user_message)
                elif not schedule_data and _is_email_based:
                    logger.warning("메일 기반 요청이나 AI가 __CREATE__ 미생성 — NLP 폴백 생략")

                # ③ DB 저장 — SessionLocal() 직접 관리 (context manager 버전 호환 문제 방지)
                schedule_result = None
                if schedule_data:
                    new_db = SessionLocal()
                    try:
                        schedule_result = _create_habit_from_data(schedule_data, new_db)
                        logger.info("일정 생성 결과: %s", schedule_result)
                    except Exception as db_err:
                        logger.error("일정 DB 저장 오류: %s", db_err)
                        new_db.rollback()
                    finally:
                        new_db.close()
                else:
                    logger.warning("schedule_data 없음 — 일정 생성 불가")

                # ④ 응답 스트리밍
                # AI가 의미 있는 답변을 생성했으면 그것을 사용, 아니면 기본 메시지
                if not clean_reply.strip() and schedule_result:
                    clean_reply = f"'{schedule_result['title']}' 일정을 등록했어요!"

                for word in clean_reply.split(' '):
                    if word:
                        sent_any = True
                        payload = _json.dumps({"token": word + ' ', "done": False}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                        await asyncio.sleep(0.02)

                # ⑤ 일정 등록 확인 메시지 (프론트 onScheduleCreated 트리거용 ✅ 포함)
                if schedule_result:
                    confirm = f"\n\n✅ '{schedule_result['title']}' 일정이 등록됐어요! 일정 탭에서 확인해보세요."
                    sent_any = True
                    yield f"data: {_json.dumps({'token': confirm, 'done': False}, ensure_ascii=False)}\n\n"
                elif is_create and not schedule_result:
                    # 일정 생성 실패 안내
                    fail_msg = "\n\n일정 제목이나 시간 정보를 더 명확히 알려주세요. (예: '내일 오전 10시 팀 미팅 추가해줘')"
                    sent_any = True
                    yield f"data: {_json.dumps({'token': fail_msg, 'done': False}, ensure_ascii=False)}\n\n"

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
                    try:
                        reply = await asyncio.wait_for(
                            asyncio.to_thread(_chain.ask, user_message, extra_context=context),
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


@router.post("/test-schedule")
async def test_schedule_creation(req: ChatRequest, db: Session = Depends(get_db)):
    """
    일정 생성 파이프라인 단위 테스트 엔드포인트.
    AI 없이 NLP 추출 → DB 저장까지 전 과정을 직접 테스트.
    보안: 개발 디버그 용도 (프로덕션에서는 제거 또는 비활성화 권고).
    """
    msg = req.message.strip()
    if not msg:
        raise HTTPException(400, "메시지가 비어 있습니다.")

    # 1) NLP 추출
    nlp_result = _extract_schedule_nlp(msg)

    # 2) __CREATE__ 태그 파싱 테스트 (있으면)
    tag_result = None
    test_tag = f'__CREATE__:{{"title":"NLP테스트","time":"09:00","days":[0],"repeat":true}}'
    _, tag_result = _parse_create_tag(test_tag)

    # 3) DB 저장 시도 (NLP 결과로)
    db_result = None
    db_error = None
    if nlp_result:
        new_db = SessionLocal()
        try:
            db_result = _create_habit_from_data(nlp_result, new_db)
        except Exception as e:
            db_error = str(e)
            new_db.rollback()
        finally:
            new_db.close()

    return {
        "input":          msg,
        "nlp_extracted":  nlp_result,
        "tag_parse_ok":   tag_result is not None,
        "db_saved":       db_result,
        "db_error":       db_error,
        "is_create_kw":   any(kw in msg for kw in _CREATE_INTENT_KEYWORDS),
    }
