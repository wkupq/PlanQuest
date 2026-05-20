"""
Google Calendar 연동 — 스캐폴드.

현재 상태:
  - OAuth 자격증명 (credentials.json) 이 없으면 is_ready() == False
  - 실제 API 호출 메서드는 시그니처만 있고 NotImplementedError 발생 직전에 mock 반환
  - 사용자가 credentials.json 을 받아 ~/.plan-quest/credentials.json 에 두면 동작 시작

연동 절차:
  README_연동가이드.md 참고

채워야 할 곳에는 # TODO(연동) 주석이 붙어 있음.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Google API 라이브러리는 미설치여도 import 만 안 깨지면 OK
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GOOGLE_LIBS = True
except ImportError:
    HAS_GOOGLE_LIBS = False


# ─── 설정 ────────────────────────────────────────────────
CREDENTIALS_DIR = Path.home() / ".plan-quest"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"  # OAuth client secrets
TOKEN_FILE = CREDENTIALS_DIR / "calendar_token.json"     # 사용자 동의 후 저장됨

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Google Cloud Console → OAuth consent screen → Calendar API scope


class GoogleCalendarClient:
    """Google Calendar 클라이언트.

    사용:
        client = GoogleCalendarClient()
        if not client.is_ready():
            print(client.setup_instructions())
            return
        events = client.list_events(start=datetime.now(), days=7)
    """

    def __init__(self):
        self.service = None
        self._initialize()

    def _initialize(self):
        """자격증명 확인 후 서비스 객체 생성."""
        if not HAS_GOOGLE_LIBS:
            return  # 라이브러리 미설치 → service=None 상태 유지

        if not CREDENTIALS_FILE.exists():
            return  # credentials.json 없음 → 미설정 상태

        try:
            creds = self._load_or_refresh_creds()
            if creds and creds.valid:
                self.service = build("calendar", "v3", credentials=creds)
        except Exception as e:
            print(f"[GoogleCalendar] 초기화 실패: {e}")

    def _load_or_refresh_creds(self) -> Optional["Credentials"]:
        """저장된 토큰 로드, 없으면 OAuth 흐름 실행."""
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # 처음 인증 — 브라우저 열려서 사용자 동의
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # 다음 실행 위해 저장
            CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(creds.to_json())

        return creds

    # ─── 공개 메서드 ─────────────────────────────────
    def is_ready(self) -> bool:
        """API 호출 가능한 상태인지."""
        return self.service is not None

    def setup_instructions(self) -> str:
        """미설정 시 사용자에게 보여줄 안내."""
        msg = ["Google Calendar 연동이 설정되지 않았습니다.", ""]
        if not HAS_GOOGLE_LIBS:
            msg.append("1. 라이브러리 설치:")
            msg.append("   pip install google-auth-oauthlib google-api-python-client")
            msg.append("")
        msg.append(f"2. {CREDENTIALS_FILE} 위치에 credentials.json 두기")
        msg.append("   (Google Cloud Console → OAuth client ID 다운로드)")
        msg.append("")
        msg.append("3. 첫 실행 시 브라우저로 동의 → calendar_token.json 자동 생성")
        msg.append("")
        msg.append("자세한 내용: backend/integrations/README_연동가이드.md")
        return "\n".join(msg)

    def list_events(
        self,
        start: Optional[datetime] = None,
        days: int = 7,
        max_results: int = 20,
    ) -> List[Dict]:
        """기간 내 캘린더 이벤트 조회.

        반환 형식:
            [{"summary": str, "start": ISO str, "end": ISO str, "location": str}, ...]
        """
        if not self.is_ready():
            return []

        start = start or datetime.utcnow()
        end = start + timedelta(days=days)

        # TODO(연동): 여기서 실제 API 호출
        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        return [
            {
                "summary": e.get("summary", "(제목 없음)"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
                "end":   e.get("end",   {}).get("dateTime", e.get("end",   {}).get("date")),
                "location": e.get("location", ""),
            }
            for e in events
        ]

    def search_events(self, query: str, days: int = 30) -> List[Dict]:
        """키워드로 이벤트 검색."""
        if not self.is_ready():
            return []

        start = datetime.utcnow()
        end = start + timedelta(days=days)

        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            q=query,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        return [
            {
                "summary": e.get("summary", "(제목 없음)"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
            }
            for e in events_result.get("items", [])
        ]

    def sync_to_db(self, db_session, user_id: int = 1):
        """캘린더 이벤트 → Plan-Quest DB 동기화 (선택).

        # TODO(연동): 실제 동기화 정책 정해서 구현.
          - 새 이벤트는 Habit 으로 등록할지?
          - 기존과 중복되면 어떻게 처리?
          - 양방향 sync 인지 단방향인지?
        """
        if not self.is_ready():
            return {"synced": 0, "skipped": "not_ready"}
        # 자리만 만들어 둠
        return {"synced": 0, "todo": "동기화 정책 결정 후 구현"}


# ─── 싱글톤 ─────────────────────────────────────────────
_client: Optional[GoogleCalendarClient] = None


def get_calendar_client() -> GoogleCalendarClient:
    global _client
    if _client is None:
        _client = GoogleCalendarClient()
    return _client
