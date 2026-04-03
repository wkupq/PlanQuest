"""
setup_model.py — 사양 감지 + Qwen2.5 자동 선택 + Ollama pull
실행: python setup_model.py
"""

import platform
import subprocess
import sys
import json
import os

# ── 의존 패키지 체크 ──────────────────────────────────────────
def _require(pkg: str, import_name: str | None = None) -> None:
    name = import_name or pkg
    try:
        __import__(name)
    except ImportError:
        print(f"[setup] '{pkg}' 패키지 설치 중...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
            stdout=subprocess.DEVNULL,
        )

_require("psutil")
_require("py-cpuinfo", "cpuinfo")

import psutil          # noqa: E402
import cpuinfo         # noqa: E402

# ── 1. 사양 감지 ──────────────────────────────────────────────

def detect_ram_gb() -> float:
    """전체 시스템 RAM (GB)"""
    return psutil.virtual_memory().total / (1024 ** 3)


def detect_gpu_vram_gb() -> tuple[str, float]:
    """
    GPU 이름과 VRAM(GB) 반환.
    감지 불가 시 ("CPU-only", 0.0) 반환.
    우선순위: nvidia-smi → Metal (Apple) → 추정 불가
    """
    # NVIDIA
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip().splitlines()[0]
        name, vram_mb = out.split(",")
        return name.strip(), float(vram_mb.strip()) / 1024
    except Exception:
        pass

    # Apple Silicon (Metal) — psutil로 통합 메모리 추정
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            result = subprocess.check_output(
                ["system_profiler", "SPHardwareDataType"],
                text=True, stderr=subprocess.DEVNULL
            )
            for line in result.splitlines():
                if "Memory:" in line:
                    parts = line.split()
                    # "Memory: 16 GB" 형태
                    for i, p in enumerate(parts):
                        if p == "GB" and i > 0:
                            return "Apple Silicon (unified)", float(parts[i - 1])
        except Exception:
            pass
        # 시스템 RAM을 통합 메모리로 간주
        return "Apple Silicon (unified)", detect_ram_gb()

    # AMD / Intel Arc → rocm-smi / intel_gpu_top 시도
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            stderr=subprocess.DEVNULL, text=True
        )
        data = json.loads(out)
        # rocm-smi JSON 구조: {card0: {"VRAM Total Memory (B)": "..."}}
        for card_data in data.values():
            vram_b = int(card_data.get("VRAM Total Memory (B)", 0))
            if vram_b > 0:
                return "AMD GPU", vram_b / (1024 ** 3)
    except Exception:
        pass

    return "CPU-only", 0.0


def detect_cpu_info() -> dict:
    """CPU 이름, 코어 수, 아키텍처"""
    info = cpuinfo.get_cpu_info()
    return {
        "brand": info.get("brand_raw", "Unknown CPU"),
        "arch":  info.get("arch", platform.machine()),
        "cores": psutil.cpu_count(logical=False) or 1,
        "threads": psutil.cpu_count(logical=True) or 1,
    }


def gather_specs() -> dict:
    print("─" * 50)
    print("  시스템 사양 감지 중...")
    print("─" * 50)

    ram  = detect_ram_gb()
    gpu_name, vram = detect_gpu_vram_gb()
    cpu  = detect_cpu_info()
    os_  = f"{platform.system()} {platform.release()}"

    specs = {
        "os":       os_,
        "cpu":      cpu,
        "ram_gb":   round(ram, 1),
        "gpu_name": gpu_name,
        "vram_gb":  round(vram, 1),
    }

    print(f"  OS       : {os_}")
    print(f"  CPU      : {cpu['brand']} ({cpu['cores']}C/{cpu['threads']}T)")
    print(f"  RAM      : {specs['ram_gb']} GB")
    print(f"  GPU      : {gpu_name}")
    print(f"  VRAM     : {specs['vram_gb']} GB")
    print("─" * 50)

    return specs


# ── 2. Qwen2.5 모델 자동 선택 ────────────────────────────────

# (모델 이름, 최소 VRAM GB, 최소 RAM GB, 설명)
_MODEL_TABLE: list[tuple[str, float, float, str]] = [
    ("qwen2.5:32b",  22.0, 32.0, "최고 품질 — 고사양 전용"),
    ("qwen2.5:14b",  10.0, 16.0, "고품질 — 중상급 사양 권장"),
    ("qwen2.5:7b",    5.5,  8.0, "균형 — 대부분의 사양에서 동작"),
    ("qwen2.5:3b",    2.5,  6.0, "경량 — 저사양 fallback"),
    ("qwen2.5:1.5b",  1.5,  4.0, "초경량 — 최소 사양 fallback"),
]


def select_model(specs: dict) -> str:
    """
    사양에 맞는 최적 Qwen2.5 모델 반환.

    선택 기준:
    - GPU 있음  → VRAM 기준으로 최대 모델 선택
    - CPU-only  → RAM 기준으로 최대 모델 선택 (RAM의 60% 이하)
    """
    vram = specs["vram_gb"]
    ram  = specs["ram_gb"]
    gpu  = specs["gpu_name"]

    print("  모델 선택 로직 실행...")

    if gpu != "CPU-only":
        # GPU 모드: VRAM 기준
        for model, min_vram, _, desc in _MODEL_TABLE:
            if vram >= min_vram:
                reason = f"VRAM {vram}GB ≥ {min_vram}GB (GPU 모드)"
                _print_selection(model, desc, reason)
                return model
    else:
        # CPU 모드: RAM의 60% 사용 가정 (OS·앱 여유분 확보)
        usable_ram = ram * 0.60
        for model, _, min_ram, desc in _MODEL_TABLE:
            if usable_ram >= min_ram:
                reason = f"RAM {ram}GB × 60% = {usable_ram:.1f}GB ≥ {min_ram}GB (CPU 모드)"
                _print_selection(model, desc, reason)
                return model

    # 최후 fallback
    model, _, _, desc = _MODEL_TABLE[-1]
    _print_selection(model, desc, "최소 사양 fallback")
    return model


def _print_selection(model: str, desc: str, reason: str) -> None:
    print(f"\n  ✅ 선택된 모델 : {model}")
    print(f"     설명        : {desc}")
    print(f"     선택 근거   : {reason}\n")


# ── 3. Ollama pull ────────────────────────────────────────────

def check_ollama() -> bool:
    """ollama CLI 설치 여부 확인"""
    try:
        subprocess.check_output(["ollama", "--version"],
                                 stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def model_already_pulled(model: str) -> bool:
    """이미 pull된 모델인지 확인"""
    try:
        out = subprocess.check_output(
            ["ollama", "list"], stderr=subprocess.DEVNULL, text=True
        )
        # 모델명의 태그 앞부분만 비교 (예: qwen2.5:7b)
        base = model.split(":")[0]
        tag  = model.split(":")[1] if ":" in model else "latest"
        for line in out.splitlines():
            if base in line and tag in line:
                return True
    except Exception:
        pass
    return False


def pull_model(model: str) -> bool:
    """ollama pull 실행, 성공 여부 반환"""
    print(f"  Ollama pull 시작: {model}")
    print("  (모델 크기에 따라 수 분 ~ 수십 분 소요될 수 있습니다)\n")
    try:
        # 실시간 출력을 위해 Popen 사용
        proc = subprocess.Popen(
            ["ollama", "pull", model],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        print("  [오류] ollama 명령을 찾을 수 없습니다.")
        return False


def save_model_config(model: str) -> None:
    """선택된 모델명을 config 파일에 기록"""
    config_path = os.path.join(os.path.dirname(__file__), "model_config.txt")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(model)
    print(f"\n  모델 설정 저장됨: {config_path}")


# ── 4. 메인 ─────────────────────────────────────────────────

def main() -> None:
    print("\n" + "═" * 50)
    print("   PlanQuest — Ollama 모델 자동 설정")
    print("═" * 50 + "\n")

    # 1) Ollama 설치 확인
    if not check_ollama():
        print("[오류] Ollama가 설치되어 있지 않습니다.")
        print("  → https://ollama.com/download 에서 설치 후 다시 실행하세요.\n")
        sys.exit(1)
    print("  ✅ Ollama 설치 확인 완료\n")

    # 2) 사양 감지
    specs = gather_specs()

    # 3) 모델 선택
    model = select_model(specs)

    # 4) 이미 있는 모델이면 스킵
    if model_already_pulled(model):
        print(f"  ✅ '{model}' 이미 설치되어 있습니다. pull 생략.\n")
    else:
        # 5) pull
        success = pull_model(model)
        if not success:
            print(f"\n  [오류] '{model}' pull 실패. 네트워크 상태를 확인하세요.")
            sys.exit(1)
        print(f"\n  ✅ '{model}' pull 완료!")

    # 6) 설정 저장
    save_model_config(model)

    print("\n" + "═" * 50)
    print(f"   설정 완료! 사용 모델: {model}")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()
