import chromadb
import pickle

def check_index_consistency():
    """ChromaDB와 BM25 인덱스 정합성 검사"""

    # 1. ChromaDB 문서 수 확인
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="memory")
    chroma_count = collection.count()
    print(f"ChromaDB 문서 수: {chroma_count}개")

    # 2. BM25 인덱스 문서 수 확인
    try:
        with open("bm25_index.pkl", "rb") as f:
            data = pickle.load(f)
        bm25_count = len(data["documents"])
        print(f"BM25 문서 수: {bm25_count}개")
    except FileNotFoundError:
        print("BM25 인덱스 파일 없음 -> 재생성 필요")
        return False

    # 3. 정합성 비교
    if chroma_count == bm25_count:
        print("정합성 검사 통과 -> 두 인덱스 일치")
        return True
    else:
        print(f"정합성 검사 실패 -> 불일치 감지 (ChromaDB: {chroma_count}개 / BM25: {bm25_count}개)")
        print("조치 필요: indexer.py 다시 실행해서 인덱스 동기화 필요")
        return False

if __name__ == "__main__":
    print("=== BM25 인덱스 정합성 검사 ===")
    result = check_index_consistency()
    print(f"\n최종 결과: {'통과' if result else '실패'}")