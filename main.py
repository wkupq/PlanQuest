from langchain_community.llms import Ollama

# 1. Ollama 모델 연결
llm = Ollama(model="qwen2.5:7b")

# 2. 질문 전달
question = "안녕! 너는 이제부터 나의 AI 개인 비서야. 간단하게 자기소개해줄래?"

print("AI가 생각 중입니다... (첫 실행 시에는 10~30초 정도 걸릴 수 있습니다)\n")

# 3. 답변 출력
try:
    response = llm.invoke(question)
    print(f"비서의 답변: {response}")
except Exception as e:
    print(f"오류가 발생했습니다: {e}")