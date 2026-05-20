"""
Day 9 — 팀원 B+C 공동 작업
plyer 기반 크로스 플랫폼 알림 (Mac + Windows 모두 동작)
알림 종류: 일정 / 이메일 / 루틴
"""

from plyer import notification
import platform

# 공통 알림 전송 함수
def send_notification(title: str, message: str, timeout: int = 5):
    """
    OS에 관계없이 데스크탑 알림 전송.
    - Windows: 우측 하단 토스트 알림
    - Mac    : 상단 우측 알림 센터
    """
    try:
        notification.notify(
            title=title,
            message=message,
            app_name='PlanQuest AI Assistant',
            timeout=timeout
        )
    except Exception as e:
        # 알림 실패 시 터미널 출력으로 fallback
        print(f"[알림 fallback] {title}: {message} (오류: {e})")

# 종류별 알림 함수
def notify_calendar(event_title: str, start_time: str):
    """일정 알림"""
    send_notification(
        title='📅 일정 알림',
        message=f'{event_title}\n시작: {start_time}'
    )


def notify_email(sender: str, subject: str):
    """새 이메일 알림"""
    send_notification(
        title='📧 새 메일 도착',
        message=f'보낸사람: {sender}\n제목: {subject}'
    )


def notify_routine(routine_name: str, message: str = '루틴을 수행할 시간입니다.'):
    """루틴 알림"""
    send_notification(
        title=f'🔔 루틴: {routine_name}',
        message=message
    )

# 동작 확인용 테스트
if __name__ == '__main__':
    os_name = platform.system()
    print(f"현재 OS: {os_name}")
    print("알림 테스트를 시작합니다...\n")

    notify_calendar('팀 스크럼 미팅', '오전 10:00')
    print("✅ 일정 알림 전송")

    notify_email('team@example.com', 'Week1 진행 상황 공유')
    print("✅ 이메일 알림 전송")

    notify_routine('Deep Work', '집중 작업 시간입니다.')
    print("✅ 루틴 알림 전송")

    print("\n알림 테스트 완료!")
