"""
Plan-Quest - Ollama Manager
Ollama 자동 시작/종료 + 미설치 감지 모듈

기능:
  1. Ollama 설치 여부 확인
  2. Ollama 서버 자동 시작 (serve)
  3. 모델 다운로드 여부 확인 + 자동 pull
  4. Graceful 종료 시 Ollama 프로세스 정리
"""

import subprocess
import shutil
import time
import sys
import os
import signal
import platform
import urllib.request
import json
import logging

logger = logging.getLogger("ollama_manager")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[OllamaManager] %(message)s"))
logger.addHandler(handler)

# ─── 설정 ───
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
DEFAULT_MODEL = "llama3.2:latest"
STARTUP_TIMEOUT = 30  # Ollama 시작 대기 시간 (초)

# 내부 상태
_ollama_process = None


class OllamaStatus:
    """Ollama 상태 정보"""
    def __init__(self):
        self.installed = False
        self.running = False
        self.model_available = False
        self.model_name = DEFAULT_MODEL
        self.error = None


def is_ollama_installed() -> bool:
    """Ollama가 설치되어 있는지 확인"""
    return shutil.which("ollama") is not None


def is_ollama_running() -> bool:
    """Ollama 서버가 실행 중인지 확인"""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_models() -> list:
    """설치된 모델 목록 조회"""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def is_model_available(model: str = DEFAULT_MODEL) -> bool:
    """특정 모델이 다운로드되어 있는지 확인"""
    models = get_available_models()
    # 정확히 일치하거나 태그 없이 일치
    base_name = model.split(":")[0]
    for m in models:
        if m == model or m.startswith(base_name):
            return True
    return False


def start_ollama_server() -> bool:
    """Ollama 서버를 백그라운드로 시작"""
    global _ollama_process

    if is_ollama_running():
        logger.info("✅ Ollama 서버가 이미 실행 중입니다.")
        return True

    if not is_ollama_installed():
        logger.error("❌ Ollama가 설치되어 있지 않습니다.")
        return False

    logger.info("🚀 Ollama 서버를 시작합니다...")

    try:
        # 운영체제에 따라 프로세스 생성 방식 분기
        if platform.system() == "Windows":
            _ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            _ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # 서버 시작 대기
        for i in range(STARTUP_TIMEOUT):
            time.sleep(1)
            if is_ollama_running():
                logger.info(f"✅ Ollama 서버 시작 완료 ({i+1}초)")
                return True

        logger.error(f"⏰ Ollama 서버 시작 시간 초과 ({STARTUP_TIMEOUT}초)")
        return False

    except Exception as e:
        logger.error(f"❌ Ollama 서버 시작 실패: {e}")
        return False


def pull_model(model: str = DEFAULT_MODEL) -> bool:
    """모델을 다운로드 (ollama pull)"""
    if is_model_available(model):
        logger.info(f"✅ 모델 '{model}'이 이미 존재합니다.")
        return True

    logger.info(f"📥 모델 '{model}' 다운로드 시작...")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=600,  # 10분 타임아웃
        )
        if result.returncode == 0:
            logger.info(f"✅ 모델 '{model}' 다운로드 완료")
            return True
        else:
            logger.error(f"❌ 모델 다운로드 실패: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("⏰ 모델 다운로드 시간 초과 (10분)")
        return False
    except Exception as e:
        logger.error(f"❌ 모델 다운로드 오류: {e}")
        return False


def stop_ollama_server():
    """Ollama 서버 종료"""
    global _ollama_process

    if _ollama_process is not None:
        logger.info("🛑 Ollama 서버를 종료합니다...")
        try:
            _ollama_process.terminate()
            _ollama_process.wait(timeout=10)
            logger.info("✅ Ollama 서버 종료 완료")
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ 정상 종료 실패, 강제 종료...")
            _ollama_process.kill()
            _ollama_process.wait()
            logger.info("✅ Ollama 서버 강제 종료 완료")
        finally:
            _ollama_process = None
    else:
        logger.info("ℹ️ 관리 중인 Ollama 프로세스가 없습니다.")


def get_full_status() -> OllamaStatus:
    """Ollama 전체 상태 확인"""
    status = OllamaStatus()
    status.installed = is_ollama_installed()
    status.running = is_ollama_running()
    if status.running:
        status.model_available = is_model_available(DEFAULT_MODEL)
    return status


def auto_setup(model: str = DEFAULT_MODEL) -> OllamaStatus:
    """
    자동 설정: 설치 확인 → 서버 시작 → 모델 확인
    더블클릭 실행 흐름에서 사용
    """
    status = OllamaStatus()

    # 1. 설치 확인
    status.installed = is_ollama_installed()
    if not status.installed:
        status.error = "OLLAMA_NOT_INSTALLED"
        logger.error("❌ Ollama가 설치되어 있지 않습니다. https://ollama.ai 에서 설치하세요.")
        return status

    # 2. 서버 시작
    started = start_ollama_server()
    status.running = started
    if not started:
        status.error = "OLLAMA_START_FAILED"
        return status

    # 3. 모델 확인 및 다운로드
    status.model_available = is_model_available(model)
    if not status.model_available:
        logger.info(f"모델 '{model}'이 없습니다. 다운로드를 시도합니다...")
        pulled = pull_model(model)
        status.model_available = pulled
        if not pulled:
            status.error = "MODEL_PULL_FAILED"

    status.model_name = model
    return status


# ─── CLI로 직접 실행 시 ───
if __name__ == "__main__":
    print("=" * 50)
    print("  Plan-Quest Ollama Manager")
    print("=" * 50)

    status = auto_setup()

    print(f"\n📋 상태:")
    print(f"  설치됨: {'✅' if status.installed else '❌'}")
    print(f"  실행 중: {'✅' if status.running else '❌'}")
    print(f"  모델 준비: {'✅' if status.model_available else '❌'}")
    if status.error:
        print(f"  오류: {status.error}")

    if status.running and status.model_available:
        print(f"\n🎉 준비 완료! 모델: {status.model_name}")
        print("Ctrl+C로 종료할 수 있습니다.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n종료 중...")
            stop_ollama_server()
