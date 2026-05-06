"""
google_sync.py — Gmail + Google Calendar DB 동기화
----------------------------------------------------
- Gmail: historyId 기반 증분 동기화 (중복 없음, 7일 만료 시 재설정)
- Calendar: 7일치 이벤트 전체 재동기화 (upsert)
- DB: SQLAlchemy (habit_forest.db) 사용
- 보안: 외부 입력은 security.sanitize_input() 통과
"""

from __future__ import annotations

import logging
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

# project-files 경로 추가 (auth_manager, security 접근용)
_PROJECT_FILES = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../project-files")
)
if _PROJECT_FILES not in sys.path:
    sys.path.insert(0, _PROJECT_FILES)

from database import SessionLocal
from models import GoogleCalendarEvent, GmailMessage

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# Google OAuth 스코프
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# sync_checkpoint 키
_GMAIL_CHECKPOINT_KEY = "gmail_history_id"
_CALENDAR_CHECKPOINT_KEY = "calendar_synced_at"


# ── 체크포인트 헬퍼 (별도 테이블 없이 간단 파일 기반) ──────────────
import json as _json

_CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), ".sync_checkpoint.json")


def _load_checkpoint() -> dict:
    try:
        with open(_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return {}


def _save_checkpoint(data: dict) -> None:
    try:
        with open(_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("체크포인트 저장 실패: %s", e)


def _get_checkpoint(key: str) -> Optional[str]:
    return _load_checkpoint().get(key)


def _set_checkpoint(key: str, value: str) -> None:
    data = _load_checkpoint()
    data[key] = value
    _save_checkpoint(data)


# ── Google 인증 ───────────────────────────────────────────────────

def _get_credentials():
    """auth_manager로 Google OAuth 자격증명 반환. 실패 시 None."""
    try:
        from auth_manager import get_credentials
        return get_credentials(GOOGLE_SCOPES)
    except Exception as e:
        logger.warning("Google 인증 실패 (토큰 없음): %s", e)
        return None


# ── 입력 sanitize 헬퍼 ────────────────────────────────────────────

def _safe(text: str, max_len: int = 500) -> str:
    """외부 데이터 sanitize + 길이 제한"""
    try:
        from security import sanitize_input
        text = sanitize_input(str(text or ""))
    except Exception:
        text = str(text or "")
    return text[:max_len]


# ── Calendar 동기화 ───────────────────────────────────────────────

def sync_calendar(db: Session) -> int:
    """
    Google Calendar에서 오늘~7일 이벤트를 DB에 upsert.
    반환값: 동기화된 이벤트 수
    """
    creds = _get_credentials()
    if not creds:
        return 0

    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.error("Calendar 서비스 빌드 실패: %s", e)
        return 0

    now_utc = datetime.now(timezone.utc)
    week_later = now_utc + timedelta(days=7)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=now_utc.isoformat(),
            timeMax=week_later.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        logger.error("Calendar API 호출 실패: %s", e)
        return 0

    events = result.get("items", [])
    synced = 0

    for e in events:
        google_event_id = e.get("id", "")
        if not google_event_id:
            continue

        # 시작/종료 시간 파싱
        start_raw = e.get("start", {})
        end_raw = e.get("end", {})
        is_all_day = "date" in start_raw and "dateTime" not in start_raw

        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None
        start_date = start_raw.get("date", "")
        end_date = end_raw.get("date", "")

        if not is_all_day:
            try:
                start_dt = datetime.fromisoformat(
                    start_raw.get("dateTime", "").replace("Z", "+00:00")
                )
                end_dt = datetime.fromisoformat(
                    end_raw.get("dateTime", "").replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # upsert: google_event_id 기준
        existing = db.query(GoogleCalendarEvent).filter_by(
            google_event_id=google_event_id
        ).first()

        if existing:
            existing.title       = _safe(e.get("summary", "(제목 없음)"), 200)
            existing.start_dt    = start_dt
            existing.end_dt      = end_dt
            existing.start_date  = start_date
            existing.end_date    = end_date
            existing.location    = _safe(e.get("location", ""), 200)
            existing.description = _safe(e.get("description", ""), 500)
            existing.is_all_day  = is_all_day
            existing.synced_at   = datetime.utcnow()
        else:
            db.add(GoogleCalendarEvent(
                google_event_id = google_event_id,
                title           = _safe(e.get("summary", "(제목 없음)"), 200),
                start_dt        = start_dt,
                end_dt          = end_dt,
                start_date      = start_date,
                end_date        = end_date,
                location        = _safe(e.get("location", ""), 200),
                description     = _safe(e.get("description", ""), 500),
                is_all_day      = is_all_day,
                synced_at       = datetime.utcnow(),
            ))
        synced += 1

    try:
        db.commit()
        logger.info("Calendar 동기화 완료 — %d개 이벤트", synced)
    except Exception as e:
        db.rollback()
        logger.error("Calendar DB 저장 실패: %s", e)
        return 0

    _set_checkpoint(_CALENDAR_CHECKPOINT_KEY, now_utc.isoformat())
    return synced


# ── Gmail 동기화 ──────────────────────────────────────────────────

def _fetch_message_meta(service, msg_id: str) -> Optional[dict]:
    """Gmail 메시지 메타데이터(Subject, From, Date, snippet) 조회"""
    try:
        msg = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
    except Exception as e:
        logger.warning("메시지 조회 실패 (id=%s): %s", msg_id, e)
        return None

    headers = msg.get("payload", {}).get("headers", [])
    subject  = next((h["value"] for h in headers if h["name"] == "Subject"), "(제목 없음)")
    sender   = next((h["value"] for h in headers if h["name"] == "From"), "")
    date_str = next((h["value"] for h in headers if h["name"] == "Date"), "")
    snippet  = msg.get("snippet", "")
    label_ids = msg.get("labelIds", [])
    is_unread = "UNREAD" in label_ids

    # Date 파싱 (RFC 2822 형식)
    received_at: Optional[datetime] = None
    if date_str:
        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str)
            # timezone-aware → naive UTC 변환
            if received_at.tzinfo is not None:
                received_at = received_at.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

    # 일정 관련 키워드 감지
    schedule_keywords = ["일정", "회의", "미팅", "예약", "appointment", "meeting", "schedule", "invite"]
    is_schedule = any(kw in subject.lower() or kw in snippet.lower() for kw in schedule_keywords)

    return {
        "gmail_message_id": msg_id,
        "subject":           _safe(subject, 200),
        "sender":            _safe(sender, 200),
        "received_at":       received_at,
        "snippet":           _safe(snippet, 300),
        "is_unread":         is_unread,
        "is_schedule_related": is_schedule,
    }


def sync_gmail(db: Session) -> int:
    """
    Gmail historyId 기반 증분 동기화.
    - 최초 실행: 현재 historyId를 저장하고 최근 20건 초기 로드
    - 이후 실행: 변경 내역(신규 메일)만 DB에 저장
    반환값: 동기화된 메시지 수
    """
    creds = _get_credentials()
    if not creds:
        return 0

    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error("Gmail 서비스 빌드 실패: %s", e)
        return 0

    saved_history_id = _get_checkpoint(_GMAIL_CHECKPOINT_KEY)
    synced = 0

    # ── 최초 실행: 초기 데이터 로드 ──
    if not saved_history_id:
        logger.info("Gmail 최초 동기화 — 최근 20건 초기 로드")
        try:
            profile = service.users().getProfile(userId="me").execute()
            current_history_id = str(profile["historyId"])

            # 최근 20건 가져오기
            result = service.users().messages().list(
                userId="me", maxResults=20
            ).execute()
            msg_ids = [m["id"] for m in result.get("messages", [])]

            for msg_id in msg_ids:
                if db.query(GmailMessage).filter_by(gmail_message_id=msg_id).first():
                    continue
                meta = _fetch_message_meta(service, msg_id)
                if meta:
                    db.add(GmailMessage(**meta, synced_at=datetime.utcnow()))
                    synced += 1

            db.commit()
            _set_checkpoint(_GMAIL_CHECKPOINT_KEY, current_history_id)
            logger.info("Gmail 초기 로드 완료 — %d건, historyId=%s", synced, current_history_id)
        except Exception as e:
            db.rollback()
            logger.error("Gmail 초기 로드 실패: %s", e)
        return synced

    # ── 증분 동기화 ──
    logger.info("Gmail 증분 동기화 — historyId=%s 이후", saved_history_id)
    try:
        response = service.users().history().list(
            userId="me",
            startHistoryId=saved_history_id,
            historyTypes=["messageAdded"],
        ).execute()
    except Exception as e:
        error_str = str(e)
        # historyId 만료 (7일 이상 경과) → 체크포인트 초기화 후 재시도
        if "historyId" in error_str or "404" in error_str:
            logger.warning("Gmail historyId 만료 — 체크포인트 초기화")
            _set_checkpoint(_GMAIL_CHECKPOINT_KEY, "")
            return sync_gmail(db)  # 재귀 호출로 초기 로드 수행
        logger.error("Gmail history API 실패: %s", e)
        return 0

    new_msg_ids = []
    for record in response.get("history", []):
        for msg in record.get("messagesAdded", []):
            new_msg_ids.append(msg["message"]["id"])

    if not new_msg_ids:
        logger.info("Gmail 새 메시지 없음")
    else:
        for msg_id in new_msg_ids:
            # 중복 체크
            if db.query(GmailMessage).filter_by(gmail_message_id=msg_id).first():
                continue
            meta = _fetch_message_meta(service, msg_id)
            if meta:
                db.add(GmailMessage(**meta, synced_at=datetime.utcnow()))
                synced += 1

        try:
            db.commit()
            logger.info("Gmail 증분 동기화 완료 — %d건 추가", synced)
        except Exception as e:
            db.rollback()
            logger.error("Gmail DB 저장 실패: %s", e)
            return 0

    # 최신 historyId 갱신
    latest_id = response.get("historyId", saved_history_id)
    _set_checkpoint(_GMAIL_CHECKPOINT_KEY, str(latest_id))
    return synced


# ── 통합 동기화 진입점 ────────────────────────────────────────────

def run_sync() -> dict:
    """
    Gmail + Calendar 전체 동기화 실행.
    APScheduler 또는 서버 시작 시 호출.
    반환값: {"calendar": int, "gmail": int, "error": str|None}
    """
    db: Session = SessionLocal()
    result = {"calendar": 0, "gmail": 0, "error": None}
    try:
        result["calendar"] = sync_calendar(db)
        result["gmail"]    = sync_gmail(db)
        logger.info(
            "전체 동기화 완료 — Calendar: %d, Gmail: %d",
            result["calendar"], result["gmail"],
        )
    except Exception as e:
        result["error"] = str(e)
        logger.error("동기화 중 예외 발생: %s", e)
    finally:
        db.close()
    return result


# ── CLI 테스트 ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Google Sync 수동 실행 ===")
    res = run_sync()
    print(f"Calendar: {res['calendar']}개 동기화")
    print(f"Gmail:    {res['gmail']}개 동기화")
    if res["error"]:
        print(f"오류: {res['error']}")
