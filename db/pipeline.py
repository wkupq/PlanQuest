import sqlite3
import chromadb
import pickle
from rank_bm25 import BM25Okapi

DB_PATH = "assistant.db"

# ChromaDB 초기화
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

def tokenize(text):
    return text.split()

def load_bm25():
    """BM25 인덱스 불러오기 (없으면 None 반환)"""
    try:
        with open("bm25_index.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def rrf_search(query: str, top_k: int = 3):
    """ChromaDB + BM25 RRF 검색"""
    # 콜드 스타트 처리 (메모리 10개 미만이면 RAG 건너뜀)
    count = collection.count()
    if count < 10:
        print(f"⚠️ 저장된 메모리 {count}개 — RAG 건너뜀 (10개 미만)")
        return []

    # ChromaDB 검색
    chroma_results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    chroma_docs = chroma_results["documents"][0]

    # BM25 검색
    data = load_bm25()
    if data is None:
        return chroma_docs

    scores = data["bm25"].get_scores(tokenize(query))
    bm25_ranking = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )[:top_k]
    bm25_docs = [data["documents"][i] for i in bm25_ranking]

    # RRF 점수 계산
    k = 60
    rrf_scores = {}
    for rank, doc in enumerate(chroma_docs):
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(bm25_docs):
        rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (k + rank + 1)

    final_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]

    return [doc for doc, score in final_results]

def save_conversation(role: str, content: str):
    """대화 내용을 SQLite에 저장"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (role, content) VALUES (?, ?)",
        (role, content)
    )
    conn.commit()
    conn.close()

def run_pipeline(user_input: str):
    """
    RAG 3단계 파이프라인
    1. 관련 기억 검색
    2. 컨텍스트 조합
    3. 대화 저장
    """
    print(f"\n사용자: {user_input}")

    # 1단계 — 관련 기억 검색
    related_memories = rrf_search(user_input)

    # 2단계 — 컨텍스트 조합
    if related_memories:
        context = "\n".join(related_memories)
        print(f"\n📚 관련 기억 찾음:\n{context}")
        prompt = f"관련 정보:\n{context}\n\n질문: {user_input}"
    else:
        print("\n📚 관련 기억 없음 — 기본 응답 모드")
        prompt = user_input

    # 3단계 — 대화 저장
    save_conversation("user", user_input)
    print(f"\n✅ 대화 저장 완료")
    print(f"✅ 최종 프롬프트 완성:\n{prompt}")

    return prompt

# 테스트 실행
if __name__ == "__main__":
    # 콜드 스타트 테스트 (메모리 10개 미만)
    print("=== 콜드 스타트 테스트 ===")
    run_pipeline("오늘 회의 있어?")