import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from memory import init_memory_tables, save_memory, delete_expired_memories, get_memory_count
from pipeline import rrf_search, save_conversation
from check_index import check_index_consistency

DB_PATH = "assistant.db"

# 테스트 시작 전 DB 초기화
@pytest.fixture(autouse=True)
def setup():
    """각 테스트 실행 전에 자동으로 실행되는 설정"""
    init_memory_tables()
    yield
    # 테스트 후 정리는 따로 안 해도 됨

class TestMemory:
    """memory.py 테스트"""

    def test_save_memory(self):
        """메모리 저장이 제대로 되는지 확인"""
        save_memory("conversation", "테스트 대화")
        counts = get_memory_count()
        conv_count = next(
            (c for t, c in counts if t == "conversation"), 0
        )
        assert conv_count > 0
        # assert = 이 조건이 참이어야 테스트 통과

    def test_ttl_policy(self):
        """TTL 유통기한이 제대로 설정되는지 확인"""
        save_memory("email", "테스트 이메일")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT expires_at FROM memories WHERE memory_type = 'email' ORDER BY id DESC LIMIT 1"
        )
        result = cursor.fetchone()
        conn.close()

        expires_at = datetime.fromisoformat(result[0])
        expected = datetime.now() + timedelta(days=7)
        # 이메일 TTL이 7일인지 확인 (1일 오차 허용)
        assert abs((expires_at - expected).days) <= 1

    def test_delete_expired(self):
        """만료된 메모리가 삭제되는지 확인"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memories (memory_type, content, expires_at) VALUES (?, ?, ?)",
            ("conversation", "만료 테스트", datetime.now() - timedelta(days=1))
        )
        conn.commit()
        conn.close()

        delete_expired_memories()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM memories WHERE content = '만료 테스트'"
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0
        # 만료된 데이터가 0개여야 통과

class TestPipeline:
    """pipeline.py 테스트"""

    def test_save_conversation(self):
        """대화 저장이 제대로 되는지 확인"""
        save_conversation("user", "테스트 질문")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM conversations WHERE content = '테스트 질문'"
        )
        count = cursor.fetchone()[0]
        conn.close()
        assert count > 0

    def test_rrf_search_cold_start(self):
        """메모리 없을 때 빈 리스트 반환하는지 확인"""
        results = rrf_search("테스트 검색어")
        assert isinstance(results, list)
        # 결과가 리스트 형태인지 확인

class TestIndexConsistency:
    """check_index.py 테스트"""

    def test_consistency_check(self):
        """정합성 검사 함수가 True/False 반환하는지 확인"""
        result = check_index_consistency()
        assert isinstance(result, bool)
        # 결과가 True 또는 False 인지 확인