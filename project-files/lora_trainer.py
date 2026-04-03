"""
lora_trainer.py — Unsloth LoRA 파인튜닝 스크립트
==================================================
Qwen2.5 모델에 LoRA 어댑터를 붙여 개인화 파인튜닝합니다.
Unsloth가 없는 환경에서도 HuggingFace PEFT로 폴백합니다.

실행 방법:
    # 기본 학습
    python lora_trainer.py --train lora_data/processed/alpaca_train.json

    # 전체 옵션
    python lora_trainer.py \
        --train lora_data/processed/alpaca_train.json \
        --val   lora_data/processed/alpaca_val.json \
        --model qwen2.5:7b \
        --output lora_data/adapter/ \
        --epochs 3 \
        --batch  4 \
        --lr     2e-4

의존성 (5주차 실제 학습 시 설치):
    pip install unsloth torch transformers datasets peft trl accelerate
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 설정 데이터 클래스
# ---------------------------------------------------------------------------
@dataclass
class LoRAConfig:
    """LoRA 학습 하이퍼파라미터."""

    # 모델
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    # revision: HuggingFace 모델 커밋 해시 고정 (supply-chain 공격 방지)
    # 실제 배포 시 반드시 특정 커밋 해시로 고정하세요.
    # 예) model_revision: str = "abc1234..."
    model_revision: str = "main"       # 개발 중 기본값; 5주차에 해시로 교체
    max_seq_length: int = 2048
    load_in_4bit: bool = True          # QLoRA (4-bit 양자화)

    # LoRA
    lora_r: int = 16                   # rank
    lora_alpha: int = 32               # scaling factor (보통 r*2)
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])

    # 학습
    num_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4  # 유효 배치 = batch * grad_accum
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    fp16: bool = False                 # GPU가 있을 때만 True
    bf16: bool = False                 # Ampere+ GPU에서 권장

    # 저장
    output_dir: str = "lora_data/adapter"
    save_steps: int = 50
    logging_steps: int = 10
    eval_steps: int = 50
    save_total_limit: int = 2          # 최신 2개 체크포인트만 유지

    # 데이터
    train_path: str = ""
    val_path: str = ""

    def __post_init__(self):
        # GPU 자동 감지 → fp16/bf16 설정
        try:
            import torch
            if torch.cuda.is_available():
                # Ampere(SM 8.0+) 이상이면 bf16, 아니면 fp16
                cap = torch.cuda.get_device_capability()
                if cap[0] >= 8:
                    self.bf16 = True
                else:
                    self.fp16 = True
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# 프롬프트 템플릿
# ---------------------------------------------------------------------------
ALPACA_PROMPT = """\
### System:
{system}

### Instruction:
{instruction}

### Input:
{input}

### Response:
{output}"""

ALPACA_PROMPT_NO_INPUT = """\
### System:
{system}

### Instruction:
{instruction}

### Response:
{output}"""

EOS_TOKEN = "<|endoftext|>"  # Qwen2.5 EOS


def format_alpaca_sample(sample: dict, eos_token: str = EOS_TOKEN) -> str:
    """Alpaca 샘플 → 학습용 프롬프트 문자열."""
    system = sample.get("system", "당신은 유능한 AI 개인 비서입니다.")
    instruction = sample.get("instruction", "")
    inp = sample.get("input", "")
    output = sample.get("output", "")

    if inp.strip():
        text = ALPACA_PROMPT.format(
            system=system,
            instruction=instruction,
            input=inp,
            output=output,
        )
    else:
        text = ALPACA_PROMPT_NO_INPUT.format(
            system=system,
            instruction=instruction,
            output=output,
        )
    return text + eos_token


# ---------------------------------------------------------------------------
# 데이터 로더
# ---------------------------------------------------------------------------
def load_dataset_from_json(path: str | Path):
    """JSON → HuggingFace Dataset 변환."""
    try:
        from datasets import Dataset
    except ImportError:
        raise ImportError("pip install datasets 가 필요합니다.")

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Dataset.from_list(data)


# ---------------------------------------------------------------------------
# Unsloth 학습기
# ---------------------------------------------------------------------------
class UnslothTrainer:
    """
    Unsloth 기반 LoRA 학습기.
    Unsloth 미설치 시 HuggingFace PEFT + TRL SFTTrainer로 폴백.
    """

    def __init__(self, config: LoRAConfig):
        self.config = config
        self._use_unsloth = self._check_unsloth()
        print(
            f"[LoRATrainer] 백엔드: "
            f"{'Unsloth' if self._use_unsloth else 'HuggingFace PEFT'}"
        )

    @staticmethod
    def _check_unsloth() -> bool:
        try:
            import unsloth as _unsloth_check  # noqa: F401 — 설치 여부 확인용
            del _unsloth_check
            return True
        except ImportError:
            return False

    # -----------------------------------------------------------------------
    # 모델 로드
    # -----------------------------------------------------------------------
    def load_model(self):
        """모델 + 토크나이저 로드 (Unsloth 우선)."""
        cfg = self.config

        if self._use_unsloth:
            from unsloth import FastLanguageModel  # noqa: F401 (Unsloth 환경에서만 임포트)
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=cfg.model_name,
                revision=cfg.model_revision,   # revision pinning (supply-chain 보안)
                max_seq_length=cfg.max_seq_length,
                dtype=None,
                load_in_4bit=cfg.load_in_4bit,
            )
            model = FastLanguageModel.get_peft_model(
                model,
                r=cfg.lora_r,
                target_modules=cfg.target_modules,
                lora_alpha=cfg.lora_alpha,
                lora_dropout=cfg.lora_dropout,
                bias="none",
                use_gradient_checkpointing="unsloth",
                random_state=42,
            )
        else:
            # PEFT 폴백
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch
            from peft import LoraConfig as PeftLoraConfig, get_peft_model, prepare_model_for_kbit_training

            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=cfg.load_in_4bit,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            ) if cfg.load_in_4bit else None

            model = AutoModelForCausalLM.from_pretrained(
                cfg.model_name,
                revision=cfg.model_revision,   # revision pinning (supply-chain 보안)
                quantization_config=quant_cfg,
                device_map="auto",
                trust_remote_code=True,
            )
            tokenizer = AutoTokenizer.from_pretrained(
                cfg.model_name,
                revision=cfg.model_revision,   # revision pinning
                trust_remote_code=True,
            )

            if cfg.load_in_4bit:
                model = prepare_model_for_kbit_training(model)

            peft_config = PeftLoraConfig(
                r=cfg.lora_r,
                lora_alpha=cfg.lora_alpha,
                target_modules=cfg.target_modules,
                lora_dropout=cfg.lora_dropout,
                bias="none",
                task_type="CAUSAL_LM",
            )
            model = get_peft_model(model, peft_config)

        tokenizer.pad_token = tokenizer.eos_token
        model.print_trainable_parameters()
        return model, tokenizer

    # -----------------------------------------------------------------------
    # 학습
    # -----------------------------------------------------------------------
    def train(self, model, tokenizer) -> None:
        """SFTTrainer로 학습 실행."""
        from trl import SFTTrainer
        from transformers import TrainingArguments

        cfg = self.config

        # 데이터셋 로드
        train_ds = load_dataset_from_json(cfg.train_path)
        val_ds = load_dataset_from_json(cfg.val_path) if cfg.val_path else None

        # 프롬프트 적용
        eos = tokenizer.eos_token or EOS_TOKEN
        train_ds = train_ds.map(
            lambda x: {"text": format_alpaca_sample(x, eos)},
            remove_columns=train_ds.column_names,
        )
        if val_ds:
            val_ds = val_ds.map(
                lambda x: {"text": format_alpaca_sample(x, eos)},
                remove_columns=val_ds.column_names,
            )

        training_args = TrainingArguments(
            output_dir=cfg.output_dir,
            num_train_epochs=cfg.num_epochs,
            per_device_train_batch_size=cfg.per_device_train_batch_size,
            gradient_accumulation_steps=cfg.gradient_accumulation_steps,
            learning_rate=cfg.learning_rate,
            warmup_ratio=cfg.warmup_ratio,
            weight_decay=cfg.weight_decay,
            lr_scheduler_type=cfg.lr_scheduler_type,
            fp16=cfg.fp16,
            bf16=cfg.bf16,
            logging_steps=cfg.logging_steps,
            save_steps=cfg.save_steps,
            eval_steps=cfg.eval_steps if val_ds else None,
            evaluation_strategy="steps" if val_ds else "no",
            save_total_limit=cfg.save_total_limit,
            load_best_model_at_end=bool(val_ds),
            report_to="none",             # wandb 비활성화
            seed=42,
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            dataset_text_field="text",
            max_seq_length=cfg.max_seq_length,
            dataset_num_proc=2,
            packing=True,              # 짧은 샘플 패킹 → 학습 효율 향상
            args=training_args,
        )

        print("[LoRATrainer] 학습 시작...")
        trainer.train()
        print("[LoRATrainer] 학습 완료.")

    # -----------------------------------------------------------------------
    # 어댑터 저장
    # -----------------------------------------------------------------------
    def save_adapter(self, model, tokenizer, output_dir: str | None = None) -> Path:
        """LoRA 어댑터만 저장 (전체 모델 저장 X → 용량 절약)."""
        save_path = Path(output_dir or self.config.output_dir) / "final_adapter"
        save_path.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(save_path)
        tokenizer.save_pretrained(save_path)
        print(f"[LoRATrainer] 어댑터 저장 완료: {save_path}")
        return save_path

    # -----------------------------------------------------------------------
    # 추론 테스트 (저장된 어댑터 로드)
    # -----------------------------------------------------------------------
    @staticmethod
    def test_inference(adapter_path: str | Path, question: str) -> str:
        """저장된 어댑터로 추론 테스트."""
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        adapter_path = Path(adapter_path)
        # 로컬 경로 로드: revision 파라미터 불필요 (로컬 파일이므로 B615 해당 없음)
        tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_path), trust_remote_code=True  # nosec B615
        )

        # 베이스 모델 이름 읽기
        adapter_config = json.loads(
            (adapter_path / "adapter_config.json").read_text()
        )
        base_model_name = adapter_config["base_model_name_or_path"]
        # 어댑터 config에 저장된 revision 사용 (없으면 "main")
        base_revision = adapter_config.get("revision", "main")

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            revision=base_revision,   # revision pinning
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        model = PeftModel.from_pretrained(base_model, adapter_path)
        model.eval()

        prompt = ALPACA_PROMPT_NO_INPUT.format(
            system="당신은 유능한 AI 개인 비서입니다.",
            instruction=question,
            output="",
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # 응답 부분만 추출
        if "### Response:" in result:
            result = result.split("### Response:")[-1].strip()
        return result


# ---------------------------------------------------------------------------
# 환경 체크 유틸리티
# ---------------------------------------------------------------------------
def check_environment() -> dict:
    """학습 환경 사전 점검."""
    report = {}

    # PyTorch
    try:
        import torch
        report["torch"] = torch.__version__
        report["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            report["gpu"] = torch.cuda.get_device_name(0)
            report["vram_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / 1e9, 1
            )
    except ImportError:
        report["torch"] = "not installed"

    # Unsloth
    try:
        import unsloth
        report["unsloth"] = unsloth.__version__
    except ImportError:
        report["unsloth"] = "not installed (PEFT 폴백 사용)"

    # Transformers
    try:
        import transformers
        report["transformers"] = transformers.__version__
    except ImportError:
        report["transformers"] = "not installed"

    # TRL
    try:
        import trl
        report["trl"] = trl.__version__
    except ImportError:
        report["trl"] = "not installed"

    return report


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qwen2.5 LoRA 파인튜닝 스크립트"
    )
    parser.add_argument("--train", required=True, help="학습 데이터 JSON 경로")
    parser.add_argument("--val", default="", help="검증 데이터 JSON 경로 (선택)")
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="HuggingFace 모델 이름 또는 로컬 경로",
    )
    parser.add_argument("--output", default="lora_data/adapter", help="저장 경로")
    parser.add_argument("--epochs", type=int, default=3, help="학습 에폭 수")
    parser.add_argument("--batch", type=int, default=4, help="배치 사이즈")
    parser.add_argument("--lr", type=float, default=2e-4, help="학습률")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--max-len", type=int, default=2048, help="최대 시퀀스 길이")
    parser.add_argument(
        "--check-env", action="store_true", help="환경 점검만 하고 종료"
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.check_env:
        env = check_environment()
        print("\n=== 학습 환경 점검 ===")
        for k, v in env.items():
            print(f"  {k}: {v}")
        return

    config = LoRAConfig(
        model_name=args.model,
        train_path=args.train,
        val_path=args.val,
        output_dir=args.output,
        num_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        learning_rate=args.lr,
        lora_r=args.lora_r,
        lora_alpha=args.lora_r * 2,
        max_seq_length=args.max_len,
    )

    trainer = UnslothTrainer(config)

    print("\n=== LoRA 학습 시작 ===")
    model, tokenizer = trainer.load_model()
    trainer.train(model, tokenizer)
    trainer.save_adapter(model, tokenizer)
    print("\n✅ 학습 완료!")


# ---------------------------------------------------------------------------
# 단독 실행 — 환경 점검 모드
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # CLI 인자 없이 실행 시 환경 점검
    if len(sys.argv) == 1:
        print("=== 학습 환경 점검 ===")
        env = check_environment()
        for k, v in env.items():
            print(f"  {k}: {v}")

        print("\n=== LoRA 설정 기본값 ===")
        cfg = LoRAConfig()
        for k, v in cfg.__dict__.items():
            print(f"  {k}: {v}")

        print("\n=== 프롬프트 포맷 예시 ===")
        sample = {
            "system": "당신은 AI 개인 비서입니다.",
            "instruction": "오늘 일정 알려줘",
            "input": "",
            "output": "오늘 오후 3시에 팀 미팅이 있습니다.",
        }
        print(format_alpaca_sample(sample, eos_token="<EOS>"))
        print("\n✅ 환경 점검 완료 (실제 학습은 GPU 환경에서 실행)")
    else:
        main()
