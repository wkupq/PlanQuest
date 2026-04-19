import sqlite3
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

DB_PATH = "assistant.db"

# 임계값 설정
THRESHOLD = {
    "conversation": 30,
    "email": 50,
    "routine_confidence": 85
}

def get_count(memory_type: str):
    """특정 메모리 종류 개수 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
        (memory_type,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def summarize_conversations():
    """대화 30개 넘으면 자동 정리"""
    count = get_count("conversation")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 대화 개수 확인: {count}개")

    if count >= THRESHOLD["conversation"]:
        print(f"대화 임계값 도달! ({count}개) -> 대화 정리 실행")
    else:
        print(f"대화 임계값 미달 ({count}/{THRESHOLD['conversation']}개)")

def summarize_emails():
    """이메일 50개 넘으면 자동 정리"""
    count = get_count("email")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 이메일 개수 확인: {count}개")

    if count >= THRESHOLD["email"]:
        print(f"이메일 임계값 도달! ({count}개) -> 이메일 정리 실행")
    else:
        print(f"이메일 임계값 미달 ({count}/{THRESHOLD['email']}개)")

def check_routine_confidence():
    """루틴 신뢰도 85% 넘으면 루틴 확정"""
    count = get_count("routine")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memories")
    total = cursor.fetchone()[0]
    conn.close()

    if total == 0:
        confidence = 0
    else:
        confidence = (count / total) * 100

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 루틴 신뢰도: {confidence:.1f}%")

    if confidence >= THRESHOLD["routine_confidence"]:
        print(f"루틴 신뢰도 임계값 도달! ({confidence:.1f}%) -> 루틴 패턴 확정")
    else:
        print(f"루틴 신뢰도 미달 ({confidence:.1f}%/{THRESHOLD['routine_confidence']}%)")

def run_scheduler():
    """스케줄러 실행"""
    scheduler = BackgroundScheduler()

    scheduler.add_job(summarize_conversations, 'interval', minutes=1)
    scheduler.add_job(summarize_emails, 'interval', minutes=1)
    scheduler.add_job(check_routine_confidence, 'interval', minutes=1)

    scheduler.start()
    print("스케줄러 시작!")
    print("1분마다 임계값 체크 중... (Ctrl+C 로 종료)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("\n스케줄러 종료")

if __name__ == "__main__":
    print("=== 임계값 즉시 체크 테스트 ===")
    summarize_conversations()
    summarize_emails()
    check_routine_confidence()

    print("\n=== 스케줄러 실행 (Ctrl+C로 종료) ===")
    run_scheduler()