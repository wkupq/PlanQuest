import sqlite3
import chromadb
import pickle
import os
from typing import Optional

DB_PATH = "assistant.db"

def safe_db_connect(db_path: str = DB_PATH) -> Optional[sqlite3.Connection]:
    """
    DB 연결을 안전하게 처리
    실패하면 None 반환
    """
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"DB 연결 실패: {e}")
        return None

def safe_load_bm25() -> Optional[dict]:
    """
    BM25 인덱스를 안전하게 불러오기
    파일 없으면 None 반환
    """
    try:
        if not os.path.exists("bm25_index.pkl"):
            print("BM25 인덱스 파일 없음 -> indexer.py 실행 필요")
            return None
        with open("bm25_index.pkl", "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"BM25 로드 실패: {e}")
        return None

def safe_chromadb_query(
    collection,
    query: str,
    top_k: int = 3
) -> Optional[list[str]]:
    """
    ChromaDB 검색을 안전하게 처리
    실패하면 None 반환
    """
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "distances"]
        )
        documents = results["documents"]
        return documents[0] if documents else []
    except Exception as e:
        print(f"ChromaDB 검색 실패: {e}")
        return None

def safe_save_memory(
    memory_type: str,
    content: str
) -> bool:
    """
    메모리 저장을 안전하게 처리
    성공하면 True, 실패하면 False 반환
    """
    try:
        from memory import save_memory
        save_memory(memory_type, content)
        return True
    except Exception as e:
        print(f"메모리 저장 실패: {e}")
        return False

def safe_backup() -> bool:
    """
    백업을 안전하게 처리
    성공하면 True, 실패하면 False 반환
    """
    try:
        from backup import backup
        backup()
        return True
    except Exception as e:
        print(f"백업 실패: {e}")
        return False

if __name__ == "__main__":
    print("=== 에러 핸들링 테스트 ===\n")

    # 1. DB 연결 테스트
    print("[ DB 연결 테스트 ]")
    conn = safe_db_connect()
    if conn:
        print("DB 연결 성공")
        conn.close()
    else:
        print("DB 연결 실패")

    # 2. BM25 로드 테스트
    print("\n[ BM25 로드 테스트 ]")
    data = safe_load_bm25()
    if data:
        print(f"BM25 로드 성공 ({len(data['documents'])}개)")
    else:
        print("BM25 로드 실패")

    # 3. 메모리 저장 테스트
    print("\n[ 메모리 저장 테스트 ]")
    result = safe_save_memory("conversation", "에러 핸들링 테스트")
    print(f"메모리 저장: {'성공' if result else '실패'}")

    # 4. 백업 테스트
    print("\n[ 백업 테스트 ]")
    result = safe_backup()
    print(f"백업: {'성공' if result else '실패'}")

    print("\n=== 테스트 완료 ===")
    