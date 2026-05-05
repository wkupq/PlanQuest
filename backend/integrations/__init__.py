"""외부 서비스 연동 패키지.

이 패키지의 모듈들은 모두 "스캐폴드" 상태입니다.
실제 OAuth 자격증명 (credentials.json) 을 받아서 끼워 넣으면 동작합니다.

연동 가이드: README_연동가이드.md 참조

각 클라이언트는 클래스 인스턴스로 사용:
    from integrations.google_calendar import GoogleCalendarClient
    client = GoogleCalendarClient()
    if client.is_ready():
        events = client.list_events(...)
    else:
        # mock 데이터 또는 사용자에게 연동 안내
        pass
"""
