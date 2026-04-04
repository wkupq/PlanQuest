import React, { useState } from 'react';
import { createHabit } from '../api';

export default function HabitForm({ onClose, onRefresh, showToast }) {
  const [title, setTitle] = useState('');
  const [repeatDays, setRepeatDays] = useState([1, 2, 3, 4, 5]); // 기본 평일
  const [times, setTimes] = useState([]);
  const [newTime, setNewTime] = useState('');

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  const toggleDay = (day) => {
    setRepeatDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()
    );
  };

  const addTime = () => {
    if (newTime && !times.includes(newTime)) {
      setTimes([...times, newTime].sort());
      setNewTime('');
    }
  };

  const removeTime = (t) => {
    setTimes(times.filter((x) => x !== t));
  };

  const handleSubmit = async () => {
    if (!title.trim()) {
      showToast('일정 이름을 입력해주세요');
      return;
    }
    try {
      await createHabit({
        title: title.trim(),
        repeat_days: repeatDays,
        times,
        alarm_enabled: true,
        hearts_reward: 1,
      });
      showToast(`'${title}' 일정 추가! 씨앗을 심었어요 🌱`);
      onRefresh();
      onClose();
    } catch (err) {
      showToast('일정 추가 실패');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">&#127793; 새 일정 추가</div>

        <div className="form-group">
          <label>일정 이름</label>
          <input
            className="form-input"
            placeholder="예: 과제하기"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
          />
        </div>

        <div className="form-group">
          <label>주간 반복</label>
          <div className="day-selector">
            {dayNames.map((name, i) => (
              <button
                key={i}
                className={`day-btn ${repeatDays.includes(i) ? 'selected' : ''}`}
                onClick={() => toggleDay(i)}
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label>시간 반복</label>
          <div className="time-tags">
            <button className="add-time-btn" onClick={() => {
              const t = prompt('시간 입력 (예: 14:30)');
              if (t && /^\d{1,2}:\d{2}$/.test(t) && !times.includes(t)) {
                setTimes([...times, t].sort());
              }
            }}>+</button>
            {times.map((t) => (
              <span className="time-tag" key={t}>
                &#215; {t}
                <button onClick={() => removeTime(t)}>&#215;</button>
              </span>
            ))}
          </div>
        </div>

        <div style={{
          background: '#FFF8F0',
          borderRadius: '10px',
          padding: '12px',
          marginBottom: '12px',
          fontSize: '13px',
          color: '#8B6914',
          textAlign: 'center',
        }}>
          일정을 추가하면 맵에 <strong>씨앗</strong>이 심어져요!<br />
          일정 완료 시 나무가 자라고 <span style={{color: '#e74c3c'}}>&#10084; 하트</span>를 얻어요.
        </div>

        <button className="submit-btn" onClick={handleSubmit}>
          씨앗 심기 &#127793;
        </button>
        <button className="cancel-btn" onClick={onClose}>취소</button>
      </div>
    </div>
  );
}
