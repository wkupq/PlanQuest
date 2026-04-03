"""
data_formatter.py — LoRA 학습 데이터 전처리·포맷 변환기
=========================================================
data_collector.py 가 내보낸 Alpaca/ShareGPT JSON을 받아
Unsloth / HuggingFace SFTTrainer 가 바로 사용할 수 있는
포맷으로 정제·분할·검증합니다.

기능:
  1. 텍스트 정제 (HTML, 제어문자, 과도한 공백 제거)
  2. Alpaca ↔ ShareGPT 상호 변환
  3. train / validation 분할 (stratified by source)
  4. 토큰 길이 기반 필터링 (max_tokens 초과 샘플 제거)
  5. 중복 제거 (질문 해시 기반)
  6. 데이터셋 통계 리포트

사용법:
    fmt = DataFormatter(max_tokens=2048)
    result = fmt.process(
        input_path="lora_data/exports/alpaca_20260403.json",
        output_dir="lora_data/processed/",
        val_ratio=0.1,
    )
    print(result)
"""

from __future__ import annotations

import hashlib  # SHA-256 사용 (MD5 사용 금지)
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
DEFAULT_MAX_TOKENS = 2048   # 토큰 길이 상한 (근사: 글자 수 ÷ 1.5)
DEFAULT_VAL_RATIO = 0.1     # 검증 셋 비율
MIN_SAMPLES_WARN = 100      # 이 수 미만이면 경고

ALPACA_REQUIRED_KEYS = {"instruction", "output"}
SHAREGPT_REQUIRED_KEYS = {"conversations"}


# ---------------------------------------------------------------------------
# 텍스트 클리너
# ---------------------------------------------------------------------------
class TextCleaner:
    """원시 텍스트 정제 유틸리티."""

    # 제거할 제어문자 (줄바꿈·탭 제외)
    _CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    _MULTI_NL = re.compile(r"\n{3,}")
    _MULTI_SP = re.compile(r" {2,}")

    @classmethod
    def clean(cls, text: str) -> str:
        if not isinstance(text, str):
            return ""
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        # 유니코드 정규화 (NFC)
        text = unicodedata.normalize("NFC", text)
        # 제어문자 제거
        text = cls._CTRL_RE.sub("", text)
        # 탭 → 공백
        text = text.replace("\t", " ")
        # 과도한 줄바꿈/공백 정리
        text = cls._MULTI_NL.sub("\n\n", text)
        text = cls._MULTI_SP.sub(" ", text)
        return text.strip()


# ---------------------------------------------------------------------------
# 처리 결과 데이터 클래스
# ---------------------------------------------------------------------------
@dataclass
class ProcessResult:
    train_path: Path
    val_path: Path
    train_count: int
    val_count: int
    removed_too_long: int
    removed_duplicate: int
    removed_invalid: int
    source_dist: dict

    def __str__(self) -> str:
        total_in = (
            self.train_count
            + self.val_count
            + self.removed_too_long
            + self.removed_duplicate
            + self.removed_invalid
        )
        lines = [
            "=" * 50,
            " DataFormatter 처리 결과",
            "=" * 50,
            f"  입력 샘플 수      : {total_in}",
            f"  → train           : {self.train_count}",
            f"  → val             : {self.val_count}",
            f"  제거 (너무 김)    : {self.removed_too_long}",
            f"  제거 (중복)       : {self.removed_duplicate}",
            f"  제거 (형식 오류)  : {self.removed_invalid}",
            f"  소스 분포         : {self.source_dist}",
            f"  train 저장        : {self.train_path}",
            f"  val   저장        : {self.val_path}",
        ]
        if self.train_count < MIN_SAMPLES_WARN:
            lines.append(
                f"\n  ⚠️  학습 샘플이 {self.train_count}건으로 부족합니다 "
                f"(권장: {MIN_SAMPLES_WARN}건 이상)"
            )
        lines.append("=" * 50)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DataFormatter
# ---------------------------------------------------------------------------
class DataFormatter:
    """
    LoRA 학습 데이터 전처리 파이프라인.

    Parameters
    ----------
    max_tokens : int
        샘플당 최대 토큰 수 (근사값: len(text) / 1.5).
        초과 샘플은 자동 제거.
    fmt : "alpaca" | "sharegpt"
        출력 포맷. 입력 포맷을 자동 감지하여 변환.
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        fmt: Literal["alpaca", "sharegpt"] = "alpaca",
    ):
        self.max_tokens = max_tokens
        self.output_fmt = fmt
        self._cleaner = TextCleaner()

    # -----------------------------------------------------------------------
    # 메인 파이프라인
    # -----------------------------------------------------------------------
    def process(
        self,
        input_path: Path | str,
        output_dir: Path | str | None = None,
        val_ratio: float = DEFAULT_VAL_RATIO,
    ) -> ProcessResult:
        """
        입력 JSON → 정제 → 필터링 → 분할 → 저장.

        Parameters
        ----------
        input_path : JSON 파일 경로 (Alpaca 또는 ShareGPT)
        output_dir : 출력 디렉토리 (None이면 입력과 같은 폴더)
        val_ratio  : 검증 셋 비율 (0.0~0.5)
        """
        input_path = Path(input_path)
        if output_dir is None:
            output_dir = input_path.parent
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. 로드 + 포맷 감지
        raw = self._load(input_path)
        detected_fmt = self._detect_format(raw)
        print(f"[DataFormatter] 입력 {len(raw)}건 / 감지 포맷: {detected_fmt}")

        # 2. 정규화 (모두 내부 공통 포맷으로)
        normalized = self._normalize(raw, detected_fmt)

        # 3. 정제 + 필터링
        cleaned, removed_invalid, removed_long, removed_dup = (
            self._clean_and_filter(normalized)
        )
        print(
            f"[DataFormatter] 정제 후 {len(cleaned)}건 "
            f"(invalid={removed_invalid}, 너무김={removed_long}, 중복={removed_dup})"
        )

        # 4. train/val 분할
        train, val = self._split(cleaned, val_ratio)

        # 5. 출력 포맷 변환
        train_out = [self._to_output_fmt(s) for s in train]
        val_out = [self._to_output_fmt(s) for s in val]

        # 6. 저장
        stem = input_path.stem
        train_path = output_dir / f"{stem}_train.json"
        val_path = output_dir / f"{stem}_val.json"
        self._save(train_out, train_path)
        self._save(val_out, val_path)

        # 7. 소스 분포
        source_dist = dict(
            Counter(s.get("_source", "unknown") for s in cleaned)
        )

        return ProcessResult(
            train_path=train_path,
            val_path=val_path,
            train_count=len(train),
            val_count=len(val),
            removed_too_long=removed_long,
            removed_duplicate=removed_dup,
            removed_invalid=removed_invalid,
            source_dist=source_dist,
        )

    # -----------------------------------------------------------------------
    # 포맷 변환 (공개)
    # -----------------------------------------------------------------------
    def alpaca_to_sharegpt(
        self, samples: list[dict], system: str | None = None
    ) -> list[dict]:
        """Alpaca 포맷 → ShareGPT 포맷 변환."""
        out = []
        for s in samples:
            human = s.get("instruction", "")
            if s.get("input"):
                human = f"{human}\n\n{s['input']}"
            out.append({
                "system": system or s.get("system", ""),
                "conversations": [
                    {"from": "human", "value": human},
                    {"from": "gpt",   "value": s.get("output", "")},
                ],
            })
        return out

    def sharegpt_to_alpaca(self, samples: list[dict]) -> list[dict]:
        """ShareGPT 포맷 → Alpaca 포맷 변환 (첫 번째 턴만 사용)."""
        out = []
        for s in samples:
            convs = s.get("conversations", [])
            human = next(
                (c["value"] for c in convs if c.get("from") == "human"), ""
            )
            gpt = next(
                (c["value"] for c in convs if c.get("from") == "gpt"), ""
            )
            out.append({
                "instruction": human,
                "input": "",
                "output": gpt,
                "system": s.get("system", ""),
            })
        return out

    # -----------------------------------------------------------------------
    # 내부 메서드
    # -----------------------------------------------------------------------
    @staticmethod
    def _load(path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8")
        # JSONL 처리
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)

    @staticmethod
    def _save(data: list[dict], path: Path) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _detect_format(samples: list[dict]) -> Literal["alpaca", "sharegpt"]:
        if not samples:
            return "alpaca"
        first = samples[0]
        if "conversations" in first:
            return "sharegpt"
        return "alpaca"

    def _normalize(
        self,
        samples: list[dict],
        fmt: Literal["alpaca", "sharegpt"],
    ) -> list[dict]:
        """내부 공통 포맷: {question, answer, system, _source} 로 통일."""
        result = []
        for s in samples:
            if fmt == "alpaca":
                q = s.get("instruction", "")
                if s.get("input"):
                    q = f"{q}\n\n{s['input']}"
                result.append({
                    "question": q,
                    "answer": s.get("output", ""),
                    "system": s.get("system", ""),
                    "_source": s.get("_source", "unknown"),
                })
            else:  # sharegpt
                convs = s.get("conversations", [])
                human = next(
                    (c["value"] for c in convs if c.get("from") == "human"), ""
                )
                gpt = next(
                    (c["value"] for c in convs if c.get("from") == "gpt"), ""
                )
                result.append({
                    "question": human,
                    "answer": gpt,
                    "system": s.get("system", ""),
                    "_source": s.get("_source", "unknown"),
                })
        return result

    def _clean_and_filter(
        self, samples: list[dict]
    ) -> tuple[list[dict], int, int, int]:
        """정제 + 필터링. (cleaned, invalid, too_long, duplicate) 반환."""
        cleaned = []
        removed_invalid = 0
        removed_long = 0
        removed_dup = 0
        seen_hashes: set[str] = set()

        for s in samples:
            q = self._cleaner.clean(s.get("question", ""))
            a = self._cleaner.clean(s.get("answer", ""))

            # 형식 오류
            if not q or not a:
                removed_invalid += 1
                continue

            # 토큰 길이 초과 (근사: 글자수 / 1.5)
            total_chars = len(q) + len(a)
            if total_chars / 1.5 > self.max_tokens:
                removed_long += 1
                continue

            # 중복 (질문 해시 기반) — SHA-256 사용 (MD5는 보안 취약)
            q_hash = hashlib.sha256(q.encode()).hexdigest()
            if q_hash in seen_hashes:
                removed_dup += 1
                continue
            seen_hashes.add(q_hash)

            cleaned.append({**s, "question": q, "answer": a})

        return cleaned, removed_invalid, removed_long, removed_dup

    @staticmethod
    def _split(
        samples: list[dict], val_ratio: float
    ) -> tuple[list[dict], list[dict]]:
        """
        소스(source) 비율을 유지하면서 train/val 분할.
        (stratified split)
        """
        if val_ratio <= 0:
            return samples, []

        # 소스별 그룹핑
        by_source: dict[str, list[dict]] = defaultdict(list)
        for s in samples:
            by_source[s.get("_source", "unknown")].append(s)

        train, val = [], []
        for group in by_source.values():
            if len(group) == 1:
                # 샘플이 1개뿐이면 무조건 train으로
                train.extend(group)
                continue
            n_val = max(1, int(len(group) * val_ratio))
            # 뒤에서 n_val개를 val로 (시간 순 정렬 유지)
            val.extend(group[-n_val:])
            train.extend(group[:-n_val])

        return train, val

    def _to_output_fmt(self, s: dict) -> dict:
        """내부 포맷 → 출력 포맷 변환."""
        if self.output_fmt == "alpaca":
            return {
                "instruction": s["question"],
                "input": "",
                "output": s["answer"],
                "system": s.get("system", ""),
            }
        else:  # sharegpt
            return {
                "system": s.get("system", ""),
                "conversations": [
                    {"from": "human", "value": s["question"]},
                    {"from": "gpt",   "value": s["answer"]},
                ],
            }


# ---------------------------------------------------------------------------
# 단독 실행 테스트
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile

    # --- 테스트용 Alpaca 데이터 생성 ---
    test_samples = [
        {
            "instruction": "오늘 미팅 일정 알려줘",
            "input": "",
            "output": (
                "오늘 오후 2시에 팀 스탠드업 미팅, "
                "오후 4시에 클라이언트 데모 발표가 예정되어 있습니다. "
                "미팅 15분 전에 알림을 보내드릴게요."
            ),
            "system": "당신은 AI 개인 비서입니다.",
            "_source": "calendar",
        },
        {
            "instruction": "이번 주 처리 못 한 이메일 정리해줘",
            "input": "",
            "output": (
                "이번 주 미처리 이메일 3건입니다.\n"
                "1. [중요] 계약서 검토 요청 — 법무팀, 화요일\n"
                "2. [일반] 세미나 참가 신청 마감 안내 — 금요일까지\n"
                "3. [참조] 월간 리포트 공유 — 기획팀\n"
                "우선순위 순으로 처리하시길 권장드립니다."
            ),
            "system": "당신은 AI 개인 비서입니다.",
            "_source": "email",
        },
        {
            "instruction": "Python에서 리스트 컴프리헨션 사용법 알려줘",
            "input": "",
            "output": (
                "리스트 컴프리헨션은 [표현식 for 변수 in 반복가능객체 if 조건] 형태입니다.\n"
                "예시: squares = [x**2 for x in range(10) if x % 2 == 0]\n"
                "일반 for 루프 대비 간결하고 빠릅니다."
            ),
            "system": "당신은 AI 개인 비서입니다.",
            "_source": "chat",
        },
        {
            "instruction": "x" * 3000,  # 너무 긴 질문 → 필터링
            "input": "",
            "output": "y" * 3000,
            "system": "",
            "_source": "chat",
        },
        {
            "instruction": "오늘 미팅 일정 알려줘",  # 중복 → 필터링
            "input": "",
            "output": "중복 답변입니다.",
            "system": "",
            "_source": "calendar",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test_alpaca.json"
        input_path.write_text(
            json.dumps(test_samples, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        fmt = DataFormatter(max_tokens=2048, fmt="alpaca")
        result = fmt.process(
            input_path=input_path,
            output_dir=Path(tmpdir) / "processed",
            val_ratio=0.2,
        )
        print(result)

        # ShareGPT 변환 테스트
        fmt_sg = DataFormatter(max_tokens=2048, fmt="sharegpt")
        result_sg = fmt_sg.process(
            input_path=input_path,
            output_dir=Path(tmpdir) / "sharegpt_out",
            val_ratio=0.2,
        )
        train_data = json.loads(result_sg.train_path.read_text(encoding="utf-8"))
        assert "conversations" in train_data[0], "ShareGPT 변환 실패"
        print("ShareGPT 변환 확인 ✅")
        print("\n✅ DataFormatter 모든 테스트 통과")
