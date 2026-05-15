import sqlite3
import chromadb
import pickle
from datetime import datetime
from rank_bm25 import BM25Okapi

DB_PATH = "assistant.db"
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

def get_expired_ids():
    """SQLite에서 만료된 메모리 ID 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM memories WHERE expires_at < ?",
        (datetime.now(),)
    )
    # expires_at이 지금보다 이전인 것 = 만료된 것
    expired_ids = [str(row[0]) for row in cursor.fetchall()]
    conn.close()
    return expired_ids

def delete_from_chromadb(expired_ids: list[str]):
    """ChromaDB에서 만료된 벡터 삭제"""
    if not expired_ids:
        print("삭제할 ChromaDB 데이터 없음")
        return

    try:
        collection.delete(ids=expired_ids)
        print(f"ChromaDB에서 {len(expired_ids)}개 삭제 완료")
    except Exception as e:
        print(f"ChromaDB 삭제 중 오류: {e}")

def rebuild_bm25():
    """ChromaDB 기준으로 BM25 인덱스 재구축"""
    all_data = collection.get()
    # ChromaDB에 남아있는 전체 데이터 가져오기

    if not all_data["documents"]:
        print("ChromaDB가 비어있음 -> BM25 인덱스 초기화")
        with open("bm25_index.pkl", "wb") as f:
            pickle.dump({
                "bm25": None,
                "documents": [],
                "ids": []
            }, f)
        return

    documents = all_data["documents"]
    ids = all_data["ids"]

    # BM25 인덱스 재구축
    tokenized = [doc.split() for doc in documents]
    bm25 = BM25Okapi(tokenized)

    with open("bm25_index.pkl", "wb") as f:
        pickle.dump({
            "bm25": bm25,
            "documents": documents,
            "ids": ids
        }, f)
    print(f"BM25 인덱스 재구축 완료 ({len(documents)}개)")

def cleanup_and_sync():
    """만료 데이터 삭제 + BM25 동기화 전체 실행"""
    print("=== ChromaDB 정리 + BM25 동기화 ===\n")

    # 1. 만료된 ID 가져오기
    expired_ids = get_expired_ids()
    print(f"만료된 데이터: {len(expired_ids)}개")

    # 2. ChromaDB에서 삭제
    delete_from_chromadb(expired_ids)

    # 3. BM25 재구축
    print("BM25 인덱스 재구축 중...")
    rebuild_bm25()

    # 4. 정합성 검사
    from check_index import check_index_consistency
    print("\n정합성 검사:")
    check_index_consistency()

    print("\n=== 정리 완료 ===")

if __name__ == "__main__":
    cleanup_and_sync()