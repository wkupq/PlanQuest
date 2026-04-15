import sqlite3
from datetime import datetime, timedelta

DB_PATH = "assistant.db"

# 메모리 종류별 유통기한 설정
TTL_POLICY = {
    "conversation": 30,  # 대화 30일
    "email": 7,          # 이메일 7일
    "routine": 90,       # 루틴 90일
    "calendar": 60       # 일정 60일
}

def init_memory_tables():
    """메모리 테이블 초기화"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 메모리 저장 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("메모리 테이블 초기화 완료")

def save_memory(memory_type: str, content: str):
    """
    메모리 저장
    memory_type: conversation / email / routine / calendar
    content: 저장할 내용
    """
    # TTL 정책에서 유통기한 가져오기
    days = TTL_POLICY.get(memory_type, 30)
    expires_at = datetime.now() + timedelta(days=days)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (memory_type, content, expires_at) VALUES (?, ?, ?)",
        (memory_type, content, expires_at)
    )
    conn.commit()
    conn.close()
    print(f"{memory_type} 메모리 저장 완료 (만료: {expires_at.strftime('%Y-%m-%d')})")

    # 퀘스트 훅 호출
    if memory_type == "conversation":
        on_conversation_saved(content)
    elif memory_type == "email":
        on_email_saved(content)
    elif memory_type == "calendar":
        on_calendar_saved(content)



def delete_expired_memories():
    """만료된 메모리 자동 삭제"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM memories WHERE expires_at < ?",
        (datetime.now(),)
    )
    deleted = cursor.rowcount  # 삭제된 행 수
    conn.commit()
    conn.close()
    print(f"만료 메모리 {deleted}개 삭제 완료")

def get_memory_count():
    """저장된 메모리 개수 확인"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type")
    results = cursor.fetchall()
    conn.close()
    return results

# 테스트 실행
if __name__ == "__main__":
    # 1. 테이블 초기화
    init_memory_tables()

    # 2. 각 종류별 메모리 저장
    save_memory("conversation", "오늘 오전 9시에 팀 회의가 있다")
    save_memory("email", "클라이언트에게 보고서 제출 요청 메일 받음")
    save_memory("routine", "매일 아침 9시 업무 시작")
    save_memory("calendar", "다음주 월요일 프로젝트 마감")

    # 3. 저장된 메모리 개수 확인
    counts = get_memory_count()
    print("\n메모리 현황:")
    for memory_type, count in counts:
        print(f"  {memory_type}: {count}개")

    # 4. 만료 메모리 삭제 테스트
    delete_expired_memories()

    # 퀘스트 이벤트 훅
def on_conversation_saved(content: str):
    """대화 저장될 때마다 퀘스트 진행도 업데이트"""
    count = get_memory_count()
    conv_count = next(
        (c for t, c in count if t == "conversation"), 0
    )
    print(f"퀘스트 진행 - 오늘 대화: {conv_count}번")
    return conv_count

def on_email_saved(content: str):
    """이메일 저장될 때마다 퀘스트 진행도 업데이트"""
    count = get_memory_count()
    email_count = next(
        (c for t, c in count if t == "email"), 0
    )
    print(f"퀘스트 진행 - 이메일 확인: {email_count}개")
    return email_count

def on_calendar_saved(content: str):
    """일정 저장될 때마다 퀘스트 진행도 업데이트"""
    count = get_memory_count()
    calendar_count = next(
        (c for t, c in count if t == "calendar"), 0
    )
    print(f"퀘스트 진행 - 일정 등록: {calendar_count}개")
    return calendar_count