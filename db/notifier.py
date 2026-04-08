from plyer import notification
import sqlite3
from datetime import datetime

DB_PATH = "assistant.db"

def send_notification(title: str, message: str):
    """Windows 알림 발송"""
    notification.notify(
        title=title,
        message=message,
        app_name="AI Assistant",
        timeout=5  # 5초 후 자동 사라짐
    )
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 알림 발송: {title} - {message}")

def check_and_notify():
    """임계값 체크 후 알림 발송"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 대화 개수 확인
    cursor.execute("SELECT COUNT(*) FROM memories WHERE memory_type = 'conversation'")
    conv_count = cursor.fetchone()[0]
    if conv_count >= 30:
        send_notification(
            "대화 정리 필요",
            f"대화가 {conv_count}개 쌓였어요. 정리를 시작합니다."
        )

    # 이메일 개수 확인
    cursor.execute("SELECT COUNT(*) FROM memories WHERE memory_type = 'email'")
    email_count = cursor.fetchone()[0]
    if email_count >= 50:
        send_notification(
            "이메일 정리 필요",
            f"이메일이 {email_count}개 쌓였어요. 정리를 시작합니다."
        )

    # 일정 알림
    cursor.execute(
        "SELECT content FROM memories WHERE memory_type = 'calendar' ORDER BY created_at DESC LIMIT 1"
    )
    result = cursor.fetchone()
    if result:
        send_notification("일정 알림", result[0])

    conn.close()

if __name__ == "__main__":
    print("=== 알림 테스트 ===")

    # 직접 알림 테스트
    send_notification("AI 비서 테스트", "알림 기능이 정상 동작합니다.")

    # 임계값 기반 알림 테스트
    print("\n=== 임계값 기반 알림 체크 ===")
    check_and_notify()