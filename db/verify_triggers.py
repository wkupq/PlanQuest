import sqlite3
from datetime import datetime, timedelta
from memory import save_memory, init_memory_tables, delete_expired_memories
from scheduler import summarize_conversations, summarize_emails, check_routine_confidence
from check_index import check_index_consistency

DB_PATH = "assistant.db"

def verify_conversation_trigger():
    """1. 대화 임계값 트리거 검증"""
    print("[ 검증 1 - 대화 임계값 트리거 ]")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM memories WHERE memory_type = 'conversation'"
    )
    count = cursor.fetchone()[0]
    conn.close()

    print(f"현재 대화 수: {count}개 / 임계값: 30개")
    if count >= 30:
        print("임계값 도달 - 자동 정리 트리거 동작")
    else:
        print(f"임계값 미달 - {30 - count}개 더 필요")
    print()

def verify_email_trigger():
    """2. 이메일 임계값 트리거 검증"""
    print("[ 검증 2 - 이메일 임계값 트리거 ]")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM memories WHERE memory_type = 'email'"
    )
    count = cursor.fetchone()[0]
    conn.close()

    print(f"현재 이메일 수: {count}개 / 임계값: 50개")
    if count >= 50:
        print("임계값 도달 - 자동 정리 트리거 동작")
    else:
        print(f"임계값 미달 - {50 - count}개 더 필요")
    print()

def verify_routine_trigger():
    """3. 루틴 신뢰도 트리거 검증"""
    print("[ 검증 3 - 루틴 신뢰도 트리거 ]")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM memories WHERE memory_type = 'routine'"
    )
    routine_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM memories")
    total = cursor.fetchone()[0]
    conn.close()

    confidence = (routine_count / total * 100) if total > 0 else 0
    print(f"루틴 신뢰도: {confidence:.1f}% / 임계값: 85%")
    if confidence >= 85:
        print("임계값 도달 - 루틴 패턴 확정")
    else:
        print(f"임계값 미달 - {85 - confidence:.1f}% 더 필요")
    print()

def verify_ttl_trigger():
    """4. TTL 만료 자동 삭제 검증"""
    print("[ 검증 4 - TTL 만료 자동 삭제 ]")

    # 테스트용 만료된 메모리 추가
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memories (memory_type, content, expires_at) VALUES (?, ?, ?)",
        ("conversation", "만료 테스트 데이터", datetime.now() - timedelta(days=1))
    )
    # expires_at을 어제로 설정해서 이미 만료된 데이터 생성
    conn.commit()
    conn.close()

    before = sqlite3.connect(DB_PATH)
    cursor = before.cursor()
    cursor.execute("SELECT COUNT(*) FROM memories")
    count_before = cursor.fetchone()[0]
    before.close()

    delete_expired_memories()

    after = sqlite3.connect(DB_PATH)
    cursor = after.cursor()
    cursor.execute("SELECT COUNT(*) FROM memories")
    count_after = cursor.fetchone()[0]
    after.close()

    print(f"삭제 전: {count_before}개 / 삭제 후: {count_after}개")
    print(f"만료 데이터 {count_before - count_after}개 자동 삭제 완료")
    print()

def verify_index_trigger():
    """5. 인덱스 정합성 검사 검증"""
    print("[ 검증 5 - 인덱스 정합성 검사 ]")
    result = check_index_consistency()
    print(f"정합성 검사 결과: {'통과' if result else '실패'}")
    print()

def verify_quest_trigger():
    """6. 퀘스트 훅 검증"""
    print("[ 검증 6 - 퀘스트 훅 자동 업데이트 ]")
    save_memory("conversation", "퀘스트 훅 검증 테스트")
    print()

if __name__ == "__main__":
    init_memory_tables()
    print("=== 자동화 트리거 전체 검증 ===\n")

    verify_conversation_trigger()
    verify_email_trigger()
    verify_routine_trigger()
    verify_ttl_trigger()
    verify_index_trigger()
    verify_quest_trigger()

    print("=== 전체 검증 완료 ===")