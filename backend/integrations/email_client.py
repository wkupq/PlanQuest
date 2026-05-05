"""
Gmail (또는 IMAP) 이메일 클라이언트 — 스캐폴드.

지원 모드:
  1) Gmail API (OAuth) — 권장. credentials.json 필요.
  2) IMAP (이메일 + 앱 비밀번호) — 간단하지만 보안 취약.
     환경변수: PLAN_QUEST_EMAIL, PLAN_QUEST_EMAIL_APP_PASSWORD

현재 스캐폴드 단계:
  - is_ready() == False 면 mock 또는 안내 반환
  - 실제 메서드는 # TODO(연동) 표시된 부분에서 구현 필요
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Gmail API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GOOGLE_LIBS = True
except ImportError:
    HAS_GOOGLE_LIBS = False

# IMAP fallback (표준 라이브러리)
import imaplib
import email
from email.header import decode_header


# ─── 설정 ────────────────────────────────────────────────
CREDENTIALS_DIR = Path.home() / ".plan-quest"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "gmail_token.json"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class EmailClient:
    """이메일 클라이언트. Gmail API 우선, 환경변수로 IMAP fallback."""

    def __init__(self):
        self.mode = "none"          # "gmail_api" | "imap" | "none"
        self.service = None         # Gmail API
        self.imap = None            # IMAP 연결
        self.imap_user = None
        self._initialize()

    def _initialize(self):
        # 1) Gmail API 시도
        if HAS_GOOGLE_LIBS and CREDENTIALS_FILE.exists():
            try:
                creds = self._load_or_refresh_creds()
                if creds and creds.valid:
                    self.service = build("gmail", "v1", credentials=creds)
                    self.mode = "gmail_api"
                    return
            except Exception as e:
                print(f"[EmailClient] Gmail API 초기화 실패: {e}")

        # 2) IMAP fallback (환경변수)
        user = os.environ.get("PLAN_QUEST_EMAIL")
        pwd = os.environ.get("PLAN_QUEST_EMAIL_APP_PASSWORD")
        host = os.environ.get("PLAN_QUEST_EMAIL_IMAP_HOST", "imap.gmail.com")
        if user and pwd:
            try:
                self.imap = imaplib.IMAP4_SSL(host)
                self.imap.login(user, pwd)
                self.imap_user = user
                self.mode = "imap"
                return
            except Exception as e:
                print(f"[EmailClient] IMAP 로그인 실패: {e}")
                self.imap = None

    def _load_or_refresh_creds(self):
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_FILE), GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(creds.to_json())
        return creds

    # ─── 공개 메서드 ─────────────────────────────────
    def is_ready(self) -> bool:
        return self.mode != "none"

    def setup_instructions(self) -> str:
        msg = ["이메일 연동이 설정되지 않았습니다.", ""]
        msg.append("[옵션 A] Gmail API (권장):")
        if not HAS_GOOGLE_LIBS:
            msg.append("  pip install google-auth-oauthlib google-api-python-client")
        msg.append(f"  {CREDENTIALS_FILE} 위치에 credentials.json 두기")
        msg.append("")
        msg.append("[옵션 B] IMAP (간단):")
        msg.append("  환경변수 PLAN_QUEST_EMAIL, PLAN_QUEST_EMAIL_APP_PASSWORD 설정")
        msg.append("  Gmail 이면 '앱 비밀번호' 발급 받아 사용 (계정 비밀번호 X)")
        msg.append("")
        msg.append("자세한 내용: backend/integrations/README_연동가이드.md")
        return "\n".join(msg)

    def list_recent(self, max_results: int = 10) -> List[Dict]:
        """최근 이메일 N 건.

        반환 형식:
            [{"subject": str, "sender": str, "snippet": str, "date": str, "id": str}, ...]
        """
        if self.mode == "gmail_api":
            return self._gmail_list_recent(max_results)
        elif self.mode == "imap":
            return self._imap_list_recent(max_results)
        return []

    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """키워드 검색."""
        if self.mode == "gmail_api":
            return self._gmail_search(query, max_results)
        elif self.mode == "imap":
            return self._imap_search(query, max_results)
        return []

    def get_important(self, max_results: int = 10) -> List[Dict]:
        """중요 메일 (Gmail 의 IMPORTANT 라벨 또는 IMAP 의 \\Flagged).

        # TODO(연동): "중요" 정의를 세분화 필요.
          - Gmail 의 IMPORTANT 라벨만?
          - 사용자가 별표 표시한 것?
          - AI 가 분류한 것?
        """
        if self.mode == "gmail_api":
            return self._gmail_list_recent(max_results, query="is:important")
        elif self.mode == "imap":
            return self._imap_search("FLAGGED", max_results)
        return []

    # ─── Gmail API 구현부 ────────────────────────────
    def _gmail_list_recent(self, max_results: int, query: str = "") -> List[Dict]:
        results = self.service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()
        msgs = results.get("messages", [])

        out = []
        for m in msgs:
            full = self.service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
            out.append({
                "id": m["id"],
                "subject": headers.get("Subject", "(제목 없음)"),
                "sender":  headers.get("From", ""),
                "date":    headers.get("Date", ""),
                "snippet": full.get("snippet", ""),
            })
        return out

    def _gmail_search(self, query: str, max_results: int) -> List[Dict]:
        return self._gmail_list_recent(max_results, query=query)

    # ─── IMAP 구현부 ─────────────────────────────────
    def _imap_list_recent(self, max_results: int) -> List[Dict]:
        if not self.imap:
            return []
        try:
            self.imap.select("INBOX")
            typ, data = self.imap.search(None, "ALL")
            ids = data[0].split()[-max_results:][::-1]
            return [self._fetch_imap(i) for i in ids if i]
        except Exception as e:
            print(f"[EmailClient.imap] 실패: {e}")
            return []

    def _imap_search(self, query: str, max_results: int) -> List[Dict]:
        if not self.imap:
            return []
        try:
            self.imap.select("INBOX")
            # query 가 IMAP 검색 키 ("FLAGGED") 거나 본문 키워드일 수 있음
            if query.upper() in ("FLAGGED", "UNSEEN", "SEEN"):
                criterion = query.upper()
            else:
                criterion = f'(BODY "{query}")'
            typ, data = self.imap.search(None, criterion)
            ids = data[0].split()[-max_results:][::-1]
            return [self._fetch_imap(i) for i in ids if i]
        except Exception as e:
            print(f"[EmailClient.imap.search] 실패: {e}")
            return []

    def _fetch_imap(self, msg_id) -> Dict:
        typ, data = self.imap.fetch(msg_id, "(RFC822)")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        def _decode(s):
            if not s:
                return ""
            parts = decode_header(s)
            return "".join(
                (p.decode(c or "utf-8", errors="ignore") if isinstance(p, bytes) else p)
                for p, c in parts
            )

        return {
            "id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
            "subject": _decode(msg["Subject"]),
            "sender":  _decode(msg["From"]),
            "date":    msg["Date"] or "",
            "snippet": "",
        }

    def close(self):
        try:
            if self.imap:
                self.imap.close()
                self.imap.logout()
        except Exception:
            pass


# ─── 싱글톤 ─────────────────────────────────────────────
_client: Optional[EmailClient] = None


def get_email_client() -> EmailClient:
    global _client
    if _client is None:
        _client = EmailClient()
    return _client
