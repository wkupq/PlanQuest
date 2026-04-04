import chromadb
import pickle
from rank_bm25 import BM25Okapi

# ChromaDB 초기화
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

def tokenize(text):
    """텍스트를 단어 단위로 쪼개기"""
    return text.split()

def add_documents(documents: list[str], ids: list[str]):
    """
    ChromaDB + BM25 두 곳에 동시 저장
    documents: 저장할 텍스트 리스트
    ids: 각 텍스트의 고유 ID 리스트
    """
    # 1. ChromaDB에 저장 (의미 기반 검색용)
    collection.add(
        documents=documents,
        ids=ids
    )
    print(f"✅ ChromaDB 저장 완료: {len(documents)}개")

    # 2. BM25 인덱스 구축 (키워드 검색용)
    tokenized = [tokenize(doc) for doc in documents]
    bm25 = BM25Okapi(tokenized)

    # 3. BM25 인덱스를 파일로 저장 (pickle 직렬화)
    with open("bm25_index.pkl", "wb") as f:
        pickle.dump({
            "bm25": bm25,
            "documents": documents,
            "ids": ids
        }, f)
    print("✅ BM25 인덱스 저장 완료")

def load_bm25():
    """저장된 BM25 인덱스 불러오기"""
    with open("bm25_index.pkl", "rb") as f:
        return pickle.load(f)

# 테스트 실행
if __name__ == "__main__":
    sample_docs = [
        "오늘 오전 9시에 팀 회의가 있다",
        "점심은 회사 근처 식당에서 먹을 예정이다",
        "오후 3시에 클라이언트 미팅이 잡혀 있다",
        "내일까지 보고서 제출 마감이다",
        "주간 업무 계획을 정리해야 한다"
    ]
    sample_ids = ["doc_001", "doc_002", "doc_003", "doc_004", "doc_005"]

    # 저장
    add_documents(sample_docs, sample_ids)

    # BM25 키워드 검색 테스트
    data = load_bm25()
    query = "회의 일정"
    scores = data["bm25"].get_scores(tokenize(query))
    best_idx = scores.argmax()
    print(f"✅ BM25 검색 결과: '{data['documents'][best_idx]}'")