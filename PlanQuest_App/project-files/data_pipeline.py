"""
data_pipeline.py — LoRA 학습 데이터 파이프라인
================================================
DataCollector DB → 품질 필터 → train/val 분할 → Alpaca JSON 내보내기
lora_trainer.py 에 바로 연결되는 전처리 파이프라인.

실행 방법:
    python data_pipeline.py                     # 기본 실행
    python data_pipeline.py --min-quality 0.6   # 품질 기준 상향
    python data_pipeline.py --val-ratio 0.15    # 검증 비율 조정
    python data_pipeline.py --stats             # 수집 현황만 출력
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── 기본 경로 ─────────────────────────────────────────────────
_BASE_DIR   = Path(__file__).parent
LORA_DIR    = _BASE_DIR / "lora_data"
PROCESSED   = LORA_DIR / "processed"
DB_PATH     = LORA_DIR / "interactions.db"

# ── 기본 하이퍼파라미터 ────────────────────────────────────────
DEFAULT_MIN_QUALITY = 0.5   # 최소 품질 점수
DEFAULT_VAL_RATIO   = 0.1   # 검증셋 비율 (10%)
MIN_SAMPLES_WARN    = 100   # 샘플 수 부족 경고 기준
TARGET_SAMPLES      = 500   # 목표 샘플 수


# ── DB 헬퍼 ───────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """interactions.db 연결 반환. DB 없으면 오류 메시지 출력."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"interactions.db 가 없습니다: {DB_PATH}\n"
            "RAGChain을 통해 대화를 먼저 쌓아야 합니다."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_stats() -> dict:
    """수집 현황 요약 반환."""
    try:
        with _get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM interactions WHERE is_approved=1"
            ).fetchone()[0]
            by_quality = conn.execute(
                """SELECT
                       CASE
                           WHEN quality_score >= 0.7 THEN 'high (≥0.7)'
                           WHEN quality_score >= 0.5 THEN 'mid (0.5~0.7)'
                           ELSE 'low (<0.5)'
                       END as tier,
                       COUNT(*) as cnt
                   FROM interactions
                   GROUP BY tier"""
            ).fetchall()
            by_source = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM interactions GROUP BY source"
            ).fetchall()
    except FileNotFoundError as e:
        return {"error": str(e)}

    return {
        "total": total,
        "approved": approved,
        "target": TARGET_SAMPLES,
        "progress_pct": round(total / TARGET_SAMPLES * 100, 1),
        "by_quality": {r["tier"]: r["cnt"] for r in by_quality},
        "by_source": {r["source"]: r["cnt"] for r in by_source},
    }


def print_stats() -> None:
    """수집 현황을 콘솔에 출력."""
    stats = get_stats()
    if "error" in stats:
        print(f"[오류] {stats['error']}")
        return

    print("\n" + "═" * 50)
    print("  LoRA 학습 데이터 수집 현황")
    print("═" * 50)
    print(f"  전체 대화 수  : {stats['total']:,}개")
    print(f"  수동 검수 완료: {stats['approved']:,}개")
    print(f"  목표 달성률   : {stats['progress_pct']}% ({stats['total']}/{TARGET_SAMPLES})")
    print()
    print("  [품질 분포]")
    for tier, cnt in stats["by_quality"].items():
        print(f"    {tier}: {cnt}개")
    print()
    print("  [출처 분포]")
    for src, cnt in stats["by_source"].items():
        print(f"    {src}: {cnt}개")
    print("═" * 50 + "\n")

    if stats["total"] < MIN_SAMPLES_WARN:
        print(f"⚠️  샘플이 {MIN_SAMPLES_WARN}개 미만입니다. 더 많은 대화가 필요합니다.")


# ── 데이터 로드 & 필터 ────────────────────────────────────────

def load_filtered_rows(
    min_quality: float = DEFAULT_MIN_QUALITY,
    approved_only: bool = False,
) -> list[dict]:
    """DB에서 품질 필터 적용 후 행 반환."""
    with _get_conn() as conn:
        query = "SELECT * FROM interactions WHERE quality_score >= ?"
        params: list = [min_quality]
        if approved_only:
            query += " AND is_approved=1"
        query += " ORDER BY quality_score DESC, created_at ASC"
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


# ── train / val 분할 ──────────────────────────────────────────

def split_train_val(
    rows: list[dict],
    val_ratio: float = DEFAULT_VAL_RATIO,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """
    행 목록을 train / val 로 분할.
    - 출처(source) 비율을 유지하는 stratified split
    - val_ratio=0 이면 val 없음
    """
    if val_ratio <= 0:
        return rows, []

    random.seed(seed)

    # 출처별 그룹화
    groups: dict[str, list[dict]] = {}
    for row in rows:
        src = row.get("source", "chat")
        groups.setdefault(src, []).append(row)

    train_rows: list[dict] = []
    val_rows:   list[dict] = []

    for src, group in groups.items():
        random.shuffle(group)
        n_val = max(1, int(len(group) * val_ratio)) if len(group) > 5 else 0
        val_rows.extend(group[:n_val])
        train_rows.extend(group[n_val:])

    # 최종 셔플
    random.shuffle(train_rows)
    random.shuffle(val_rows)

    return train_rows, val_rows


# ── Alpaca 변환 ───────────────────────────────────────────────

def rows_to_alpaca(rows: list[dict], include_context: bool = True) -> list[dict]:
    """DB 행 목록 → Alpaca 포맷 리스트"""
    samples = []
    for row in rows:
        inp = ""
        if include_context and row.get("context_used"):
            inp = f"[참고 문서]\n{row['context_used']}"
        samples.append({
            "instruction": row["question"],
            "input": inp,
            "output": row["answer"],
            "system": row.get("system_prompt") or "당신은 사용자의 개인 AI 스케줄러 비서입니다.",
        })
    return samples


def save_json(data: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("저장 완료: %s (%d개)", path, len(data))


# ── 메인 파이프라인 ───────────────────────────────────────────

def run_pipeline(
    min_quality: float = DEFAULT_MIN_QUALITY,
    val_ratio: float = DEFAULT_VAL_RATIO,
    approved_only: bool = False,
    include_context: bool = True,
    fmt: Literal["alpaca", "sharegpt"] = "alpaca",
    output_dir: Path | None = None,
    seed: int = 42,
) -> dict:
    """
    전체 파이프라인 실행.
    반환값: {"train": Path, "val": Path|None, "n_train": int, "n_val": int}
    """
    out_dir = output_dir or PROCESSED
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 데이터 로드
    logger.info("DB 로드 중 (min_quality=%.2f, approved_only=%s)", min_quality, approved_only)
    rows = load_filtered_rows(min_quality=min_quality, approved_only=approved_only)
    logger.info("필터 후 %d개 행", len(rows))

    if not rows:
        logger.warning("사용 가능한 데이터가 없습니다. 대화를 더 쌓아주세요.")
        return {"train": None, "val": None, "n_train": 0, "n_val": 0}

    if len(rows) < MIN_SAMPLES_WARN:
        logger.warning("샘플 수 부족 (%d개). 목표: %d개", len(rows), TARGET_SAMPLES)

    # 2. train/val 분할
    train_rows, val_rows = split_train_val(rows, val_ratio=val_ratio, seed=seed)
    logger.info("train=%d, val=%d", len(train_rows), len(val_rows))

    # 3. 포맷 변환 & 저장
    train_samples = rows_to_alpaca(train_rows, include_context=include_context)
    val_samples   = rows_to_alpaca(val_rows,   include_context=include_context)

    train_path = out_dir / "alpaca_train.json"
    val_path   = out_dir / "alpaca_val.json" if val_rows else None

    save_json(train_samples, train_path)
    if val_path:
        save_json(val_samples, val_path)

    # 4. 요약 출력
    print("\n" + "─" * 45)
    print("  파이프라인 완료")
    print(f"  train: {len(train_samples)}개 → {train_path}")
    if val_path:
        print(f"  val:   {len(val_samples)}개  → {val_path}")
    print("─" * 45)
    print("\n  다음 단계: lora_trainer.py 실행")
    print(f"  python lora_trainer.py --train {train_path}", end="")
    if val_path:
        print(f" \\\n      --val {val_path}", end="")
    print("\n")

    return {
        "train": train_path,
        "val": val_path,
        "n_train": len(train_samples),
        "n_val": len(val_samples),
    }


# ── 팀원 데이터 병합 ─────────────────────────────────────────

def merge_alpaca_files(
    input_files: list[Path],
    output_path: Path,
    dedup: bool = True,
    min_quality: float = 0.0,
    seed: int = 42,
) -> int:
    """
    여러 팀원의 Alpaca JSON 파일을 하나로 병합.

    - dedup: instruction+output 기준 중복 제거
    - min_quality: 파일에 quality_score 필드가 있으면 필터 적용
    - 병합 후 셔플해서 저장

    반환값: 최종 샘플 수
    """
    all_samples: list[dict] = []
    seen: set[str] = set()

    for f in input_files:
        f = Path(f)
        if not f.exists():
            logger.warning("파일 없음, 건너뜀: %s", f)
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("파일 읽기 실패 (%s): %s", f, e)
            continue

        added = 0
        for sample in data:
            # 필수 필드 확인
            if not sample.get("instruction") or not sample.get("output"):
                continue

            # 품질 필터 (quality_score 필드가 있는 경우)
            if min_quality > 0 and "quality_score" in sample:
                if sample["quality_score"] < min_quality:
                    continue

            # 중복 제거
            if dedup:
                key = f"{sample['instruction'].strip()}|{sample['output'][:50].strip()}"
                if key in seen:
                    continue
                seen.add(key)

            all_samples.append(sample)
            added += 1

        logger.info("%s: %d개 로드 (추가 %d개)", f.name, len(data), added)

    if not all_samples:
        logger.warning("병합할 데이터가 없습니다.")
        return 0

    # 셔플
    random.seed(seed)
    random.shuffle(all_samples)

    save_json(all_samples, output_path)

    print("\n" + "─" * 45)
    print(f"  병합 완료: {len(all_samples)}개")
    print(f"  저장: {output_path}")
    print(f"  중복 제거: {dedup}")
    print("─" * 45 + "\n")

    return len(all_samples)


def merge_and_split(
    input_files: list[Path],
    output_dir: Path | None = None,
    val_ratio: float = DEFAULT_VAL_RATIO,
    dedup: bool = True,
    seed: int = 42,
) -> dict:
    """
    팀원 파일 병합 → train/val 분할 → 저장.
    lora_trainer.py에 바로 사용 가능한 형태로 출력.

    반환값: {"train": Path, "val": Path, "n_train": int, "n_val": int}
    """
    out_dir = output_dir or PROCESSED
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 병합
    merged_path = out_dir / "_merged_temp.json"
    total = merge_alpaca_files(input_files, merged_path, dedup=dedup, seed=seed)

    if total == 0:
        return {"train": None, "val": None, "n_train": 0, "n_val": 0}

    # 2. 로드 후 train/val 분할
    merged = json.loads(merged_path.read_text(encoding="utf-8"))

    # dict → row 형태로 변환 (split_train_val 호환)
    rows = [
        {
            "question":      s.get("instruction", ""),
            "answer":        s.get("output", ""),
            "context_used":  s.get("input", ""),
            "system_prompt": s.get("system", ""),
            "source":        s.get("source", "chat"),
        }
        for s in merged
    ]

    train_rows, val_rows = split_train_val(rows, val_ratio=val_ratio, seed=seed)

    train_samples = rows_to_alpaca(train_rows, include_context=True)
    val_samples   = rows_to_alpaca(val_rows,   include_context=True)

    train_path = out_dir / "alpaca_train.json"
    val_path   = out_dir / "alpaca_val.json"

    save_json(train_samples, train_path)
    save_json(val_samples,   val_path)

    # 임시 파일 정리
    merged_path.unlink(missing_ok=True)

    print(f"\n  train: {len(train_samples)}개 → {train_path}")
    print(f"  val:   {len(val_samples)}개  → {val_path}")
    print(f"\n  다음: python lora_trainer.py --train {train_path} --val {val_path}\n")

    return {
        "train": train_path,
        "val":   val_path,
        "n_train": len(train_samples),
        "n_val":   len(val_samples),
    }


# ── CLI ───────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LoRA 학습 데이터 파이프라인")
    sub = p.add_subparsers(dest="cmd")

    # ── 기본 실행 (내 DB → Alpaca JSON)
    exp = sub.add_parser("export", help="내 DB를 Alpaca JSON으로 내보내기 (기본)")
    exp.add_argument("--min-quality", type=float, default=DEFAULT_MIN_QUALITY)
    exp.add_argument("--val-ratio",   type=float, default=DEFAULT_VAL_RATIO)
    exp.add_argument("--approved-only", action="store_true")
    exp.add_argument("--no-context",  action="store_true")
    exp.add_argument("--output-dir",  type=Path, default=None)
    exp.add_argument("--seed",        type=int, default=42)

    # ── 수집 현황
    sub.add_parser("stats", help="수집 현황 출력")

    # ── 팀원 파일 병합
    mrg = sub.add_parser("merge", help="팀원 Alpaca JSON 파일 병합")
    mrg.add_argument("files", nargs="+", type=Path,
                     help="병합할 Alpaca JSON 파일 목록")
    mrg.add_argument("--output-dir", type=Path, default=None)
    mrg.add_argument("--val-ratio",  type=float, default=DEFAULT_VAL_RATIO)
    mrg.add_argument("--no-dedup",   action="store_true", help="중복 제거 비활성화")
    mrg.add_argument("--seed",       type=int, default=42)

    return p


if __name__ == "__main__":
    parser = _build_parser()
    args = parser.parse_args()

    # 서브커맨드 없으면 기본 export 실행
    if args.cmd is None or args.cmd == "export":
        print_stats()
        run_pipeline(
            min_quality=getattr(args, "min_quality", DEFAULT_MIN_QUALITY),
            val_ratio=getattr(args, "val_ratio", DEFAULT_VAL_RATIO),
            approved_only=getattr(args, "approved_only", False),
            include_context=not getattr(args, "no_context", False),
            output_dir=getattr(args, "output_dir", None),
            seed=getattr(args, "seed", 42),
        )

    elif args.cmd == "stats":
        print_stats()

    elif args.cmd == "merge":
        merge_and_split(
            input_files=args.files,
            output_dir=args.output_dir,
            val_ratio=args.val_ratio,
            dedup=not args.no_dedup,
            seed=args.seed,
        )
