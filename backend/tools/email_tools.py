"""Plan-Quest - Email Tool Functions.

연동 상태:
  - Gmail API 또는 IMAP 연동 가능 (backend/integrations/email_client.py)
  - 미연동이면 mock 데이터 반환

연동 방법: backend/integrations/README_연동가이드.md
"""
from typing import List, Dict

try:
    from integrations.email_client import get_email_client
    _HAS_EMAIL = True
except ImportError:
    _HAS_EMAIL = False


def _try_real_email(query: str = "", max_results: int = 10) -> str | None:
    """실 연동 시도. 실패 시 None → mock 사용."""
    if not _HAS_EMAIL:
        return None
    try:
        client = get_email_client()
        if not client.is_ready():
            return None
        msgs = client.search(query, max_results=max_results) if query \
               else client.list_recent(max_results=max_results)
        if not msgs:
            return f"📧 '{query}' 관련 이메일 없음"
        lines = [f"📧 [{client.mode}] '{query}' 관련 이메일:"]
        for m in msgs:
            lines.append(f"- {m['sender']}: {m['subject']} ({m.get('date', '')})")
        return "\n".join(lines)
    except Exception as e:
        print(f"[email_tools] 실 연동 실패, mock 사용: {e}")
        return None


def search_emails(query: str = "") -> str:
    """
    이메일 검색 (키워드 기반)

    Args:
        query: 검색 키워드

    Returns:
        검색 결과 문자열
    """
    real = _try_real_email(query)
    if real is not None:
        return real

    # Mock 데이터

    dummy_emails = [
        {
            "from": "boss@company.com",
            "subject": "Q1 Project Status",
            "preview": "Please submit the project status report by EOD...",
            "importance": "high",
            "received": "2시간 전"
        },
        {
            "from": "team@company.com",
            "subject": "Team Meeting Tomorrow",
            "preview": "Don't forget about our team meeting tomorrow at 10 AM...",
            "importance": "medium",
            "received": "5시간 전"
        },
        {
            "from": "notification@github.com",
            "subject": "PR Review Requested",
            "preview": "Your PR review has been requested on Plan-Quest repo...",
            "importance": "medium",
            "received": "1일 전"
        }
    ]

    result = f"📧 이메일 검색: '{query}'\n"

    if not query:
        result = "📧 최근 이메일:\n"

    matching = [
        e for e in dummy_emails
        if query.lower() in e["subject"].lower() or query.lower() in e["preview"].lower()
    ] if query else dummy_emails

    if not matching:
        return result + f"'{query}'와 관련된 이메일이 없습니다."

    for email in matching:
        importance_icon = "⭐" if email["importance"] == "high" else "📌"
        result += f"{importance_icon} [{email['importance'].upper()}] {email['from']}\n"
        result += f"   제목: {email['subject']}\n"
        result += f"   {email['received']}\n\n"

    return result


def get_important_emails(user_id: int = 1) -> str:
    """
    중요한 이메일 필터링 (우선순위 높은 것만)

    Args:
        user_id: 사용자 ID

    Returns:
        중요한 이메일 문자열
    """
    dummy_important = [
        {
            "from": "boss@company.com",
            "subject": "Q1 Project Status - ACTION REQUIRED",
            "preview": "Please submit the project status report by EOD today...",
            "importance": "high",
            "received": "2시간 전"
        },
        {
            "from": "client@external.com",
            "subject": "Urgent: Contract Review Needed",
            "preview": "We need to review the contract ASAP before the deadline...",
            "importance": "high",
            "received": "30분 전"
        }
    ]

    result = "⭐ 중요한 이메일 (우선 처리):\n\n"

    if not dummy_important:
        return result + "중요한 이메일이 없습니다."

    for email in dummy_important:
        result += f"🔴 [{email['from']}]\n"
        result += f"   제목: {email['subject']}\n"
        result += f"   {email['received']}\n"
        result += f"   {email['preview'][:60]}...\n\n"

    return result


def classify_emails(user_id: int = 1) -> str:
    """
    AI 기반 이메일 자동 분류 (카테고리별)

    Args:
        user_id: 사용자 ID

    Returns:
        분류된 이메일 카테고리 문자열
    """
    result = "📊 이메일 분류 결과:\n\n"

    categories = {
        "업무": 5,
        "회의": 3,
        "프로젝트": 4,
        "알림": 8,
        "스팸": 12
    }

    for category, count in categories.items():
        result += f"• {category}: {count}건\n"

    result += "\n💡 추천: 업무와 회의 이메일부터 확인하시겠습니까?"

    return result
