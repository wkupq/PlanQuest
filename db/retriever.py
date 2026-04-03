import chromadb
import pickle
from rank_bm25 import BM25Okapi

# ChromaDB 초기화
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

def tokenize(text):
    return text.split()

def load_bm25():
    with open("bm25_index.pkl", "rb") as f:
        return pickle.load(f)

def rrf_search(query: str, top_k: int = 3):
    """
    ChromaDB + BM25 결과를 RRF로 합쳐서 반환
    query: 검색어
    top_k: 반환할 결과 개수
    """
    # 1. ChromaDB 검색 (의미 기반)
    chroma_results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    chroma_docs = chroma_results["documents"][0]
    print(f"ChromaDB 결과: {chroma_docs}")

    # 2. BM25 검색 (키워드 기반)
    data = load_bm25()
    scores = data["bm25"].get_scores(tokenize(query))
    bm25_ranking = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )[:top_k]
    bm25_docs = [data["documents"][i] for i in bm25_ranking]
    print(f"BM25 결과: {bm25_docs}")

    # 3. RRF 점수 계산
    k = 60  # RRF 상수 (보통 60 사용)
    rrf_scores = {}

    # ChromaDB 순위로 점수 계산
    for rank, doc in enumerate(chroma_docs):
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)

    # BM25 순위로 점수 계산
    for rank, doc in enumerate(bm25_docs):
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)

    # 4. 최종 점수 높은 순으로 정렬
    final_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]

    print(f"\n✅ RRF 최종 결과:")
    for i, (doc, score) in enumerate(final_results):
        print(f"  {i+1}위 (점수: {score:.4f}): {doc}")

    return [doc for doc, score in final_results]

# 테스트 실행
if __name__ == "__main__":
    rrf_search("회의 일정")