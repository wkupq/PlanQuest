import React, { useEffect, useState } from "react";
import { harvestTree, deleteHabit } from "../api";
import { computeNextAlarm } from "../utils/timeUtils";
import "./TreeInfoModal.css";

const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];
const STAGE_NAMES = ["씨앗 🌰", "새싹 🌱", "어린나무 🌿", "큰나무 🌳"];


/**
 * 씨앗/나무 클릭 시 뜨는 정보 모달.
 *
 * Props:
 *   tree         : TreeResponse (id, habit_id, habit_title, repeat_days, times, ...)
 *   onClose      : 닫기 콜백
 *   onHarvested  : 수확 성공 시 콜백
 *   onDeleted    : 일정 삭제 성공 시 콜백
 *   showToast    : 토스트
 */
export default function TreeInfoModal({ tree, onClose, onHarvested, onDeleted, onMove, showToast }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [tick, setTick] = useState(0);

  // 1분마다 카운트다운 갱신
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  if (!tree) return null;

  const stage = Math.max(0, Math.min(3, tree.growth_stage || 0));
  const nextAlarm = computeNextAlarm(tree.times || [], tree.repeat_days || []);

  const handleHarvest = async () => {
    try {
      const res = await harvestTree(tree.id);
      showToast(res.data.message);
      onHarvested && onHarvested(res.data);
      onClose();
    } catch (err) {
      showToast(err.response?.data?.detail || "수확 실패");
    }
  };

  const handleDelete = async () => {
    try {
      await deleteHabit(tree.habit_id);
      showToast("🗑️ 일정 삭제됨");
      onDeleted && onDeleted();
      onClose();
    } catch (err) {
      showToast(err.response?.data?.detail || "삭제 실패");
    }
  };

  return (
    <div className="tree-modal-backdrop" onClick={onClose}>
      <div className="tree-modal" onClick={(e) => e.stopPropagation()}>
        <button className="tree-modal-close" onClick={onClose}>✕</button>

        <div className="tree-modal-header">
          <div className="tree-modal-title">{tree.habit_title}</div>
          <div className="tree-modal-stage">{STAGE_NAMES[stage]}</div>
        </div>

        <div className="tree-modal-body">
          <Row label="📅 반복 요일">
            {(tree.repeat_days || []).length > 0
              ? (tree.repeat_days || []).map((i) => DAY_NAMES[i]).join(" · ")
              : "(반복 없음)"}
          </Row>

          <Row label="⏰ 시간">
            {(tree.times || []).length > 0
              ? (tree.times || []).join(", ")
              : "(없음)"}
          </Row>

          {/* 다음 알람까지 카운트다운 */}
          {nextAlarm && (
            <div className="tree-modal-next">
              <div className="tree-modal-next-label">⏳ 다음 알람</div>
              <div className="tree-modal-next-when">{nextAlarm.dateText}</div>
              <div className="tree-modal-next-remain">{nextAlarm.remainText}</div>
            </div>
          )}

          <Row label="🔥 연속 달성">{tree.streak || 0}일</Row>
          <Row label="❤️ 회당 보상">하트 {tree.hearts_reward || 1}개</Row>

          {tree.completed_today && (
            <div className="tree-modal-badge">✅ 오늘 완료됨</div>
          )}
        </div>

        {/* 액션 버튼들 */}
        {tree.hearts_available > 0 && (
          <button className="tree-modal-harvest" onClick={handleHarvest}>
            ❤️ 하트 {tree.hearts_available}개 수확하기
          </button>
        )}

        {/* 이동 버튼 */}
        <button
          className="tree-modal-move"
          onClick={() => { onMove && onMove(tree); onClose(); }}
        >
          🔄 다른 칸으로 옮기기
        </button>

        {!confirmDelete ? (
          <button
            className="tree-modal-delete"
            onClick={() => setConfirmDelete(true)}
          >
            🗑️ 이 일정 삭제하기
          </button>
        ) : (
          <div className="tree-modal-confirm">
            <div className="tree-modal-confirm-text">
              정말 '{tree.habit_title}' 일정을 삭제할까요?
              <br /><span className="tree-modal-confirm-warn">씨앗/나무도 함께 사라집니다.</span>
            </div>
            <div className="tree-modal-confirm-buttons">
              <button className="tree-modal-confirm-cancel" onClick={() => setConfirmDelete(false)}>
                취소
              </button>
              <button className="tree-modal-confirm-yes" onClick={handleDelete}>
                삭제
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div className="tree-modal-row">
      <span className="tree-modal-row-label">{label}</span>
      <span className="tree-modal-row-value">{children}</span>
    </div>
  );
}
