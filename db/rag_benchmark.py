import time
import chromadb
import pickle
from config_loader import get_bm25_path

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memory")

def tokenize(text):
    return text.split()

def load_bm25():
    with open(get_bm25_path(), "rb") as f:
        return pickle.load(f)

def benchmark_chromadb(query: str, runs: int = 10):
    """ChromaDB 검색 속도 측정"""
    times = []
    for _ in range(runs):
        start = time.time()
        collection.query(query_texts=[query], n_results=3)
        end = time.time()
        times.append(end - start)

    avg = sum(times) / len(times)
    print(f"ChromaDB 평균 응답시간: {avg:.3f}초 ({runs}회 평균)")
    return avg

def benchmark_bm25(query: str, runs: int = 10):
    """BM25 검색 속도 측정"""
    data = load_bm25()
    times = []
    for _ in range(runs):
        start = time.time()
        scores = data["bm25"].get_scores(tokenize(query))
        scores.argmax()
        end = time.time()
        times.append(end - start)

    avg = sum(times) / len(times)
    print(f"BM25 평균 응답시간: {avg:.3f}초 ({runs}회 평균)")
    return avg

def benchmark_pipeline(query: str, runs: int = 10):
    """전체 RAG 파이프라인 속도 측정"""
    from pipeline import rrf_search
    times = []
    for _ in range(runs):
        start = time.time()
        rrf_search(query)
        end = time.time()
        times.append(end - start)

    avg = sum(times) / len(times)
    print(f"전체 파이프라인 평균 응답시간: {avg:.3f}초 ({runs}회 평균)")
    return avg

if __name__ == "__main__":
    query = "회의 일정"
    print("=== RAG 성능 측정 ===\n")

    chroma_avg = benchmark_chromadb(query)
    bm25_avg = benchmark_bm25(query)
    pipeline_avg = benchmark_pipeline(query)

    print(f"\n=== 성능 요약 ===")
    print(f"ChromaDB:        {chroma_avg:.3f}초")
    print(f"BM25:            {bm25_avg:.3f}초")
    print(f"전체 파이프라인:  {pipeline_avg:.3f}초")

    if pipeline_avg > 3.0:
        print("\n응답시간 3초 초과 - 최적화 필요")
    else:
        print("\n응답시간 3초 이내 - 정상")