"""Plan-Quest - Calendar Tool Functions.

연동 상태:
  - Google Calendar 연동되면 (credentials.json 있음) 실제 API 호출
  - 미연동이면 mock 데이터 반환

연동 방법: backend/integrations/README_연동가이드.md
"""
from typing import List, Dict
from datetime import datetime, timedelta
import json

# 실 연동 클라이언트 (없으면 mock 사용)
try:
    from integrations.google_calendar import get_calendar_client
    _HAS_GCAL = True
except ImportError:
    _HAS_GCAL = False


def _try_real_calendar(query: str, days: int = 7) -> str | None:
    """실제 Google Calendar 사용 시도. 실패 시 None 반환."""
    if not _HAS_GCAL:
        return None
    try:
        client = get_calendar_client()
        if not client.is_ready():
            return None
        events = client.search_events(query, days=days) if query else \
                 client.list_events(days=days)
        if not events:
            return f"📅 '{query}' 관련 일정 없음"
        lines = [f"📅 [Google Calendar] '{query}' 관련:"]
        for e in events:
            lines.append(f"- {e.get('start', '')}: {e.get('summary', '')}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[calendar_tools] 실 연동 실패, mock 사용: {e}")
        return None


def search_calendar(query: str = "내일") -> str:
    """
    캘린더에서 일정 검색

    Args:
        query: 검색어 ("내일", "다음주", "회의" 등)

    Returns:
        검색 결과 문자열
    """
    # 1) 실제 Google Calendar 가능하면 그것 사용
    real = _try_real_calendar(query)
    if real is not None:
        return real

    # 2) Mock 데이터 (미연동 시)

    target_date = None
    if "내일" in query:
        target_date = (datetime.now() + timedelta(days=1)).strftime("%Y년 %m월 %d일")
    elif "오늘" in query:
        target_date = datetime.now().strftime("%Y년 %m월 %d일")
    elif "다음주" in query:
        target_date = (datetime.now() + timedelta(days=7)).strftime("%Y년 %m월 %d일")
    else:
        target_date = "검색 일정"

    # 더미 일정 데이터
    dummy_schedule = {
        "내일": [
            {"time": "10:00", "title": "팀 미팅", "location": "회의실 A"},
            {"time": "14:30", "title": "프로젝트 리뷰", "location": "온라인"}
        ],
        "오늘": [
            {"time": "09:00", "title": "일일 스탠드업", "location": "회의실 B"}
        ]
    }

    result = f"📅 {target_date} 일정:\n"

    # 쿼리에서 날짜 추출
    for key, events in dummy_schedule.items():
        if key in query:
            if not events:
                result += "등록된 일정이 없습니다."
            else:
                for event in events:
                    result += f"- {event['time']}: {event['title']} ({event['location']})\n"
            return result

    result += "(Google Calendar API 연동 예정)\n"
    result += "현재는 기본 일정만 조회 가능합니다."

    return result


def get_today_schedule(user_id: int = 1) -> str:
    """
    오늘의 전체 일정 조회

    Args:
        user_id: 사용자 ID

    Returns:
        오늘 일정 문자열
    """
    today = datetime.now().strftime("%Y년 %m월 %d일")

    dummy_today = [
        {"time": "09:00", "title": "아침 루틴", "type": "habit"},
        {"time": "10:00", "title": "팀 미팅", "type": "calendar"},
        {"time": "14:30", "title": "프로젝트 리뷰", "type": "calendar"},
        {"time": "18:00", "title": "저녁 운동", "type": "habit"}
    ]

    result = f"📅 {today} 일정:\n"
    for event in dummy_today:
        icon = "📌" if event["type"] == "habit" else "🗓️"
        result += f"{icon} {event['time']}: {event['title']}\n"

    return result


def get_next_events(days: int = 7, user_id: int = 1) -> str:
    """
    향후 N일간의 주요 일정 조회

    Args:
        days: 조회 기간 (기본: 7일)
        user_id: 사용자 ID

    Returns:
        향후 일정 문자열
    """
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y년 %m월 %d일")

    result = f"🗓️ 향후 {days}일 주요 일정:\n"
    result += f"(~{end_date})\n\n"

    dummy_events = [
        {"date": "내일", "time": "10:00", "title": "팀 미팅"},
        {"date": "모레", "time": "14:30", "title": "프로젝트 마감"},
        {"date": "목요일", "time": "09:00", "title": "클라이언트 미팅"}
    ]

    for event in dummy_events:
        result += f"📌 {event['date']} {event['time']}: {event['title']}\n"

    return result
