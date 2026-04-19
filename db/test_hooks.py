from memory import save_memory, init_memory_tables

if __name__ == "__main__":
    init_memory_tables()

    print("=== 퀘스트 훅 테스트 ===\n")

    print("[ 대화 저장 테스트 ]")
    save_memory("conversation", "오늘 회의 있어?")

    print("\n[ 이메일 저장 테스트 ]")
    save_memory("email", "클라이언트 메일 도착")

    print("\n[ 일정 저장 테스트 ]")
    save_memory("calendar", "내일 오전 10시 미팅")