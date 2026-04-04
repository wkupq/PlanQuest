import React from 'react';
import { completeHabit, deleteHabit } from '../api';

export default function HabitPanel({ habits, onClose, onRefresh, showToast, showHeartAnim, onAddClick }) {

  const handleComplete = async (habit) => {
    if (habit.completed_today) return;
    try {
      const res = await completeHabit(habit.id);
      showHeartAnim(window.innerWidth / 2, window.innerHeight / 2, res.data.hearts_earned);
      showToast(res.data.message);
      onRefresh();
    } catch (err) {
      showToast(err.response?.data?.detail || '완료 처리 실패');
    }
  };

  const handleDelete = async (habit) => {
    if (!window.confirm(`'${habit.title}' 일정을 삭제할까요?`)) return;
    try {
      await deleteHabit(habit.id);
      showToast('일정 삭제 완료');
      onRefresh();
    } catch (err) {
      showToast('삭제 실패');
    }
  };

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">&#127793; 나의 일정</div>

        {habits.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px', color: '#B8956A' }}>
            아직 일정이 없어요.<br />일정을 추가하면 씨앗이 심어져요!
          </div>
        ) : (
          habits.map((h) => (
            <div className="habit-card" key={h.id}>
              <button
                className={`habit-check ${h.completed_today ? 'done' : ''}`}
                onClick={() => handleComplete(h)}
              >
                {h.completed_today ? '✓' : ''}
              </button>
              <div className="habit-info">
                <div className={`habit-title ${h.completed_today ? 'completed' : ''}`}>
                  {h.title}
                </div>
                <div className="habit-streak">
                  {h.repeat_days.map(d => dayNames[d]).join('·')}
                  {h.streak > 0 && ` · ${h.streak}일 연속`}
                </div>
              </div>
              <span className="habit-reward">&#10084; {h.hearts_reward}</span>
              <button className="habit-delete" onClick={() => handleDelete(h)}>&#128465;</button>
            </div>
          ))
        )}

        <button className="submit-btn" onClick={onAddClick} style={{ marginTop: '16px' }}>
          + 새 일정 추가
        </button>
        <button className="cancel-btn" onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}
