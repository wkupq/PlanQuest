"""
lora_evaluator.py — LoRA 어댑터 학습 전후 성능 평가
=====================================================
베이스 모델과 LoRA 파인튜닝 모델의 응답 품질을 비교합니다.

평가 지표:
  - BLEU-4          : 번역/생성 정확도
  - ROUGE-L         : 참조 답변과의 최장 공통 부분열
  - 응답 길이        : 적정 길이 여부
  - 품질 점수        : QualityEvaluator 기반 규칙 점수

실행 방법:
    # 기본 평가 (val 셋 사용)
    python lora_evaluator.py \
        --adapter  lora_data/adapter/final_adapter \
        --val-data lora_data/processed/alpaca_val.json

    # 직접 질문으로 빠른 비교
    python lora_evaluator.py \
        --adapter lora_data/adapter/final_adapter \
        --questions "오늘 일정 알려줘" "내일 뭐해야 해?"
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── 의존성 선택적 임포트 ──────────────────────────────────────

def _try_import_nltk():
    try:
        import nltk
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)
        return nltk
    except ImportError:
        return None

def _try_import_rouge():
    try:
        from rouge_score import rouge_scorer
        return rouge_scorer
    except ImportError:
        return None


# ── BLEU 계산 ────────────────────────────────────────────────

def bleu4(reference: str, hypothesis: str) -> float:
    """BLEU-4 점수 계산. nltk 없으면 0 반환."""
    nltk = _try_import_nltk()
    if not nltk:
        logger.warning("nltk 미설치 — BLEU 계산 건너뜀 (pip install nltk)")
        return 0.0
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    ref_tokens  = list(reference)   # 한국어는 문자 단위 토크나이징
    hyp_tokens  = list(hypothesis)
    smoothie    = SmoothingFunction().method4
    return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothie)


# ── ROUGE-L 계산 ─────────────────────────────────────────────

def rouge_l(reference: str, hypothesis: str) -> float:
    """ROUGE-L F1 점수 계산. rouge_score 없으면 LCS 직접 계산."""
    rouge_scorer = _try_import_rouge()
    if rouge_scorer:
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
        scores = scorer.score(reference, hypothesis)
        return scores["rougeL"].fmeasure

    # 폴백: LCS 기반 직접 계산
    def lcs_len(a: str, b: str) -> int:
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(2)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i-1] == b[j-1]:
                    dp[i % 2][j] = dp[(i-1) % 2][j-1] + 1
                else:
                    dp[i % 2][j] = max(dp[(i-1) % 2][j], dp[i % 2][j-1])
        return dp[m % 2][n]

    lcs = lcs_len(reference, hypothesis)
    if not reference or not hypothesis:
        return 0.0
    precision = lcs / len(hypothesis)
    recall    = lcs / len(reference)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ── 품질 점수 ────────────────────────────────────────────────

def quality_score(question: str, answer: str) -> float:
    """QualityEvaluator 기반 품질 점수."""
    try:
        from data_collector import QualityEvaluator
        return QualityEvaluator().score(question, answer)
    except Exception:
        return 0.0


# ── Ollama 추론 (베이스 모델) ─────────────────────────────────

def ollama_infer(question: str, model: str = "qwen2.5:14b") -> str:
    """Ollama API로 베이스 모델 추론."""
    try:
        import requests
        resp = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": model,
                "prompt": question,
                "stream": False,
                "options": {"num_predict": 512, "temperature": 0.7},
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.error("Ollama 추론 실패: %s", e)
        return ""


# ── LoRA 어댑터 추론 ─────────────────────────────────────────

def lora_infer(question: str, adapter_path: str | Path, max_new_tokens: int = 512) -> str:
    """
    저장된 LoRA 어댑터로 추론.
    transformers + peft 필요.
    """
    adapter_path = Path(adapter_path)
    if not adapter_path.exists():
        raise FileNotFoundError(f"어댑터 경로 없음: {adapter_path}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        adapter_cfg = json.loads((adapter_path / "adapter_config.json").read_text())
        base_model_name = adapter_cfg.get("base_model_name_or_path", "Qwen/Qwen2.5-7B-Instruct")

        logger.info("베이스 모델 로드: %s", base_model_name)
        tokenizer = AutoTokenizer.from_pretrained(
            str(adapter_path), trust_remote_code=True
        )
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.float16,
        )
        model = PeftModel.from_pretrained(base_model, str(adapter_path))
        model.eval()

        # 프롬프트 구성
        prompt = f"### Instruction:\n{question}\n\n### Response:\n"
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        return tokenizer.decode(generated, skip_special_tokens=True).strip()

    except ImportError as e:
        logger.error("LoRA 추론 의존성 미설치: %s (pip install transformers peft torch)", e)
        return ""
    except Exception as e:
        logger.error("LoRA 추론 실패: %s", e)
        return ""


# ── 단일 샘플 평가 ────────────────────────────────────────────

def evaluate_single(
    question: str,
    reference: str,
    hypothesis: str,
) -> dict:
    """질문 하나에 대한 평가 지표 반환."""
    return {
        "bleu4":    round(bleu4(reference, hypothesis), 4),
        "rouge_l":  round(rouge_l(reference, hypothesis), 4),
        "quality":  round(quality_score(question, hypothesis), 4),
        "ans_len":  len(hypothesis),
        "ref_len":  len(reference),
    }


# ── 전체 평가 ─────────────────────────────────────────────────

def evaluate_dataset(
    val_data: list[dict],
    adapter_path: str | Path,
    base_model: str = "qwen2.5:14b",
    max_samples: int = 50,
) -> dict:
    """
    val_data(Alpaca 포맷)에 대해 베이스 vs LoRA 비교 평가.
    max_samples: 평가할 최대 샘플 수 (시간 절약)
    """
    samples = val_data[:max_samples]
    total = len(samples)
    logger.info("평가 시작 — %d개 샘플", total)

    base_scores: list[dict] = []
    lora_scores: list[dict] = []

    for i, sample in enumerate(samples, 1):
        question  = sample.get("instruction", "")
        reference = sample.get("output", "")
        if not question or not reference:
            continue

        logger.info("[%d/%d] 평가 중: %s...", i, total, question[:30])

        # 베이스 모델 응답
        base_ans = ollama_infer(question, model=base_model)
        if base_ans:
            base_scores.append(evaluate_single(question, reference, base_ans))

        # LoRA 어댑터 응답
        lora_ans = lora_infer(question, adapter_path)
        if lora_ans:
            lora_scores.append(evaluate_single(question, reference, lora_ans))

    def avg(scores: list[dict], key: str) -> float:
        vals = [s[key] for s in scores if key in s]
        return round(statistics.mean(vals), 4) if vals else 0.0

    result = {
        "n_evaluated": total,
        "base_model": {
            "bleu4":   avg(base_scores, "bleu4"),
            "rouge_l": avg(base_scores, "rouge_l"),
            "quality": avg(base_scores, "quality"),
            "avg_len": avg(base_scores, "ans_len"),
        },
        "lora_model": {
            "bleu4":   avg(lora_scores, "bleu4"),
            "rouge_l": avg(lora_scores, "rouge_l"),
            "quality": avg(lora_scores, "quality"),
            "avg_len": avg(lora_scores, "ans_len"),
        },
    }

    # 개선율 계산
    for metric in ["bleu4", "rouge_l", "quality"]:
        base_val = result["base_model"][metric]
        lora_val = result["lora_model"][metric]
        if base_val > 0:
            improvement = round((lora_val - base_val) / base_val * 100, 1)
        else:
            improvement = 0.0
        result[f"{metric}_improvement_pct"] = improvement

    return result


def print_report(result: dict) -> None:
    """평가 결과를 표 형태로 출력."""
    print("\n" + "═" * 55)
    print("  LoRA 파인튜닝 평가 보고서")
    print("═" * 55)
    print(f"  평가 샘플 수: {result['n_evaluated']}개\n")

    header = f"  {'지표':<12} {'베이스':>10} {'LoRA':>10} {'개선율':>10}"
    print(header)
    print("  " + "-" * 45)

    for metric, label in [("bleu4", "BLEU-4"), ("rouge_l", "ROUGE-L"), ("quality", "품질점수")]:
        base = result["base_model"][metric]
        lora = result["lora_model"][metric]
        imp  = result.get(f"{metric}_improvement_pct", 0)
        sign = "+" if imp >= 0 else ""
        print(f"  {label:<12} {base:>10.4f} {lora:>10.4f} {sign}{imp:>8.1f}%")

    print("  " + "-" * 45)
    base_len = result["base_model"]["avg_len"]
    lora_len = result["lora_model"]["avg_len"]
    print(f"  {'평균 답변 길이':<12} {base_len:>10.0f} {lora_len:>10.0f}")
    print("═" * 55 + "\n")

    # 종합 판정
    q_imp = result.get("quality_improvement_pct", 0)
    if q_imp > 5:
        print(f"  ✅ 파인튜닝 효과 있음 (품질 +{q_imp:.1f}%)")
    elif q_imp > 0:
        print(f"  ⚠️  미미한 개선 (+{q_imp:.1f}%). 데이터 추가 수집 권장")
    else:
        print(f"  ❌ 성능 저하 ({q_imp:.1f}%). 하이퍼파라미터 재조정 필요")
    print()


# ── 빠른 비교 (직접 질문 입력) ────────────────────────────────

def quick_compare(questions: list[str], adapter_path: str | Path, base_model: str) -> None:
    """질문 목록으로 베이스 vs LoRA 빠른 비교."""
    print("\n" + "═" * 55)
    print("  베이스 모델 vs LoRA 빠른 비교")
    print("═" * 55)

    for q in questions:
        print(f"\n질문: {q}")
        print("─" * 40)

        base_ans = ollama_infer(q, model=base_model)
        lora_ans = lora_infer(q, adapter_path)

        print(f"[베이스]\n{base_ans or '(응답 없음)'}\n")
        print(f"[LoRA  ]\n{lora_ans or '(응답 없음)'}\n")

        if base_ans and lora_ans:
            q_base = quality_score(q, base_ans)
            q_lora = quality_score(q, lora_ans)
            print(f"품질 점수 — 베이스: {q_base:.3f} | LoRA: {q_lora:.3f}")
        print("─" * 40)


# ── CLI ───────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LoRA 파인튜닝 평가")
    p.add_argument("--adapter",    required=True,
                   help="LoRA 어댑터 경로 (lora_data/adapter/final_adapter)")
    p.add_argument("--val-data",   default=None,
                   help="평가용 Alpaca JSON 경로 (기본: lora_data/processed/alpaca_val.json)")
    p.add_argument("--base-model", default="qwen2.5:14b",
                   help="베이스 Ollama 모델명 (기본: qwen2.5:14b)")
    p.add_argument("--max-samples", type=int, default=50,
                   help="평가할 최대 샘플 수 (기본: 50)")
    p.add_argument("--questions",  nargs="+", default=None,
                   help="빠른 비교용 직접 질문 목록")
    p.add_argument("--output",     default=None,
                   help="평가 결과 JSON 저장 경로 (선택)")
    return p


if __name__ == "__main__":
    args = _build_parser().parse_args()

    if args.questions:
        # 빠른 비교 모드
        quick_compare(args.questions, args.adapter, args.base_model)
    else:
        # val 데이터셋 평가 모드
        val_path = Path(args.val_data) if args.val_data else \
                   Path(__file__).parent / "lora_data/processed/alpaca_val.json"

        if not val_path.exists():
            print(f"[오류] val 데이터 없음: {val_path}")
            print("python data_pipeline.py 를 먼저 실행하세요.")
            raise SystemExit(1)

        val_data = json.loads(val_path.read_text(encoding="utf-8"))
        result = evaluate_dataset(
            val_data=val_data,
            adapter_path=args.adapter,
            base_model=args.base_model,
            max_samples=args.max_samples,
        )
        print_report(result)

        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"결과 저장: {out}")
