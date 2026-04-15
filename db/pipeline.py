import sqlite3
import chromadb
import pickle
from rank_bm25 import BM25Okapi

DB_PATH = "assistant.db"

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

# 유사도 기준점 (이 값보다 높으면 관련 없다고 판단)
SIMILARITY_THRESHOLD = 0.9

def tokenize(text):
    return text.split()

def load_bm25():
    try:
        with open("bm25_index.pkl", "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def rrf_search(query: str, top_k: int = 3):

    # 메모리가 아예 없으면 검색 불가
    count = collection.count()
    if count == 0:
        print("저장된 메모리가 없습니다")
        return []

    # ChromaDB 검색 (유사도 거리값 포함)
    chroma_results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "distances"]
    )

    chroma_docs = chroma_results["documents"][0]
    distances = chroma_results["distances"][0]

    print(f"가장 유사한 문서 거리값: {min(distances):.2f}")

    # 유사도가 너무 낮으면 관련 기억 없다고 판단
    if min(distances) > SIMILARITY_THRESHOLD:
        print("저장된 메모리에 관련 내용이 없습니다")
        return []

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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (role, content) VALUES (?, ?)",
        (role, content)
    )
    conn.commit()
    conn.close()

def run_pipeline(user_input: str):
    print(f"\n사용자: {user_input}")

    related_memories = rrf_search(user_input)

    if related_memories:
        context = "\n".join(related_memories)
        print(f"\n관련 기억 찾음:\n{context}")
        prompt = f"관련 정보:\n{context}\n\n질문: {user_input}"
    else:
        print("\n관련 기억 없음 - 기본 응답 모드")
        prompt = user_input

    save_conversation("user", user_input)
    print(f"\n대화 저장 완료")
    print(f"최종 프롬프트:\n{prompt}")

    return prompt

if __name__ == "__main__":
    print("=== 유사도 기반 검색 테스트 ===")

    print("\n[ 테스트 1 - 관련 있는 질문 ]")
    run_pipeline("오늘 회의 몇시야?")

    print("\n[ 테스트 2 - 관련 없는 질문 ]")
    run_pipeline("오늘 날씨 어때?")