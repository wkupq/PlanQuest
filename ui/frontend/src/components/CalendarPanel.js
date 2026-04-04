import React, { useState } from 'react';

export default function CalendarPanel({ onClose }) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState([
    { date: '2025-03-30', title: '과제하기', time: '14:36' },
    { date: '2025-03-31', title: '공부하기', time: '15:00' },
  ]);
  const [newEvent, setNewEvent] = useState({ title: '', time: '' });

  const getDaysInMonth = (date) => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date) => {
    return new Date(date.getFullYear(), date.getMonth(), 1).getDay();
  };

  const monthNames = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  const days = [];
  const firstDay = getFirstDayOfMonth(currentDate);
  const daysInMonth = getDaysInMonth(currentDate);

  for (let i = 0; i < firstDay; i++) {
    days.push(null);
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i);
  }

  const handleAddEvent = () => {
    if (!newEvent.title.trim() || !newEvent.time) return;
    const today = new Date().toISOString().split('T')[0];
    setEvents([...events, { date: today, title: newEvent.title, time: newEvent.time }]);
    setNewEvent({ title: '', time: '' });
  };

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1));
  };

  const todayEvents = events.filter((e) => {
    const today = new Date().toISOString().split('T')[0];
    return e.date === today;
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">📅 캘린더</div>

        {/* 월 네비게이션 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <button
            onClick={prevMonth}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '18px',
              cursor: 'pointer',
              color: '#5D3A1A',
            }}
          >
            ◀
          </button>
          <span style={{ fontSize: '16px', fontWeight: '600', color: '#5D3A1A' }}>
            {currentDate.getFullYear()}년 {monthNames[currentDate.getMonth()]}
          </span>
          <button
            onClick={nextMonth}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '18px',
              cursor: 'pointer',
              color: '#5D3A1A',
            }}
          >
            ▶
          </button>
        </div>

        {/* 요일 헤더 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px', marginBottom: '8px' }}>
          {dayNames.map((day) => (
            <div
              key={day}
              style={{
                textAlign: 'center',
                fontSize: '12px',
                fontWeight: '600',
                color: '#8B6914',
                padding: '6px 0',
              }}
            >
              {day}
            </div>
          ))}
        </div>

        {/* 날짜 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px', marginBottom: '16px' }}>
          {days.map((day, i) => (
            <div
              key={i}
              style={{
                aspectRatio: '1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '8px',
                background: day ? '#FFF8F0' : 'transparent',
                color: '#5D3A1A',
                fontSize: '13px',
                fontWeight: '500',
                border: day ? '1px solid #E8D5B8' : 'none',
              }}
            >
              {day}
            </div>
          ))}
        </div>

        {/* 오늘의 일정 */}
        <div style={{ background: '#F5E6D3', borderRadius: '10px', padding: '12px', marginBottom: '12px' }}>
          <div style={{ fontSize: '13px', fontWeight: '600', color: '#5D3A1A', marginBottom: '8px' }}>
            오늘의 일정
          </div>
          {todayEvents.length === 0 ? (
            <div style={{ fontSize: '12px', color: '#B8956A' }}>일정이 없습니다</div>
          ) : (
            todayEvents.map((e, i) => (
              <div key={i} style={{ fontSize: '12px', color: '#5D3A1A', marginBottom: '4px' }}>
                ⏰ {e.time} - {e.title}
              </div>
            ))
          )}
        </div>

        {/* 일정 추가 */}
        <div className="form-group">
          <label>새로운 일정 추가</label>
          <input
            className="form-input"
            placeholder="일정 제목"
            value={newEvent.title}
            onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
          />
          <input
            className="form-input"
            type="time"
            value={newEvent.time}
            onChange={(e) => setNewEvent({ ...newEvent, time: e.target.value })}
            style={{ marginTop: '8px' }}
          />
          <button className="submit-btn" onClick={handleAddEvent} style={{ marginTop: '8px' }}>
            추가
          </button>
        </div>

        <button className="cancel-btn" onClick={onClose}>닫기</button>
      </div>
    </div>
  );
}
