"""Plan-Quest - AI 채팅 라우터 (ReAct Agent + SSE 스트리밍)"""
import asyncio
import json
import httpx
from io import StringIO
import sys

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent_core import get_agent

router = APIRouter(prefix="/api", tags=["채팅"])

# ─── Ollama 설정 ───
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:latest"  # Qwen2.5로 변경 (향상된 추론)

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
    """
    ReAct 에이전트 스트리밍 채팅 엔드포인트

    사용자 쿼리를 에이전트가 처리하고 스트리밍으로 응답합니다.
    에이전트는 필요한 도구를 자동으로 선택해서 실행합니다.
    """

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

        try:
            # ReAct 에이전트 실행
            agent = get_agent()
            if not agent:
                error_msg = "❌ AI 에이전트를 초기화할 수 없습니다."
                yield f"data: {json.dumps({'token': error_msg}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
                return

            # 에이전트 실행
            response = await agent.run(req.message)

            # 응답을 문자 단위로 스트리밍
            if response:
                for char in response:
                    yield f"data: {json.dumps({'token': char}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'done': True})}\n\n"

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


@router.get("/chat/tools")
async def get_available_tools():
    """사용 가능한 에이전트 도구 목록 조회"""
    agent = get_agent()
    if not agent:
        return {"error": "에이전트가 초기화되지 않았습니다."}

    tools_info = []
    for tool in agent.tools:
        tools_info.append({
            "name": tool.name,
            "description": tool.description
        })

    return {
        "available_tools": tools_info,
        "total_tools": len(tools_info),
        "model": OLLAMA_MODEL
    }
