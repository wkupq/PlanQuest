import chromadb

# ChromaDB 로컬 저장소 초기화
client = chromadb.PersistentClient(path="./chroma_db")

# 컬렉션 생성 (없으면 새로 만들고, 있으면 가져옴)
collection = client.get_or_create_collection(name="memory")

# 벡터 1개 저장
collection.add(
    documents=["오늘 오전 9시에 팀 회의가 있다"],
    ids=["mem_001"]
)
print("벡터 저장 성공")

# 저장한 벡터 조회
results = collection.query(
    query_texts=["회의 일정"],
    n_results=1
)
print("조회 결과:", results["documents"][0][0])