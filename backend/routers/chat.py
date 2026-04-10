"""Plan-Quest - AI 채팅 라우터 (SSE 스트리밍)"""
import asyncio
import json
import httpx

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["채팅"])

# ─── Ollama 설정 ───
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2:latest"  # 사용할 모델 (필요시 변경)

SYSTEM_PROMPT = (
    "너는 Plan-Quest의 AI 비서야. "
    "사용자의 일정 관리, 습관 형성, 동기 부여를 도와줘. "
    "친절하고 격려하는 톤으로 답변해. "
    "한국어로 대화해."
)


class ChatRequest(BaseModel):
    message: str


def is_ollama_running() -> bool:
    """Ollama 서버가 실행 중인지 확인"""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


@router.get("/chat/health")
def chat_health():
    """Ollama 연결 상태 확인 (상세)"""
    from ollama_manager import get_full_status, DEFAULT_MODEL
    status = get_full_status()
    return {
        "ollama_installed": status.installed,
        "ollama_running": status.running,
        "model_available": status.model_available,
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
    }


@router.post("/chat/setup-ollama")
async def setup_ollama():
    """Ollama 자동 설정 (서버 시작 + 모델 다운로드)"""
    from ollama_manager import auto_setup
    status = auto_setup(OLLAMA_MODEL)
    return {
        "installed": status.installed,
        "running": status.running,
        "model_available": status.model_available,
        "error": status.error,
    }


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 스트리밍 채팅 엔드포인트 - 토큰 단위 출력"""

    async def event_generator():
        # Ollama가 실행 중이 아니면 폴백 응답
        if not is_ollama_running():
            fallback = (
                "⚠️ Ollama가 실행되고 있지 않습니다. "
                "Ollama를 설치하고 실행한 뒤 다시 시도해주세요.\n\n"
                "설치: https://ollama.ai\n"
                f"모델 다운로드: ollama pull {OLLAMA_MODEL}"
            )
            for char in fallback:
                yield f"data: {json.dumps({'token': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        # Ollama API로 스트리밍 요청
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": req.message},
                ],
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            done = data.get("done", False)

                            if token:
                                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                            if done:
                                yield f"data: {json.dumps({'done': True})}\n\n"
                                return
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            error_msg = "❌ Ollama 서버에 연결할 수 없습니다."
            yield f"data: {json.dumps({'token': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            error_msg = f"❌ 오류 발생: {str(e)}"
            yield f"data: {json.dumps({'token': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
