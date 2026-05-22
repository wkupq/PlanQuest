import React from 'react';

export default function RoutinePanel({ habits, onClose }) {
  const today = new Date().getDay(); // 0=일, 1=월, ...
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  // 오늘 해야 할 일정만 필터링
  const todayHabits = habits.filter(h => h.repeat_days.includes(today));
  const completedCount = todayHabits.filter(h => h.completed_today).length;
  const totalCount = todayHabits.length;
  const percentage = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  // 전체 일정 통계
  const allCompleted = habits.filter(h => h.completed_today).length;
  const totalHabits = habits.length;

  // 최고 연속 기록
  const maxStreak = habits.reduce((max, h) => Math.max(max, h.streak || 0), 0);

  // 총 획득 가능 하트
  const totalHearts = habits.reduce((sum, h) => sum + (h.hearts_reward || 0), 0);
  const earnedHearts = habits.filter(h => h.completed_today).reduce((sum, h) => sum + (h.hearts_reward || 0), 0);

  // 원형 프로그레스 계산
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  // 달성률에 따른 색상
  const getColor = (pct) => {
    if (pct >= 80) return '#4CAF50';
    if (pct >= 50) return '#FF9800';
    if (pct > 0) return '#FF5722';
    return '#BDBDBD';
  };

  // 달성률에 따른 메시지
  const getMessage = (pct) => {
    if (pct === 100) return '완벽해요! 오늘의 모든 일정을 완료했어요! 🎉';
    if (pct >= 80) return '거의 다 했어요! 조금만 더 힘내세요! 💪';
    if (pct >= 50) return '절반 이상 완료! 잘 하고 있어요! 👍';
    if (pct > 0) return '좋은 시작이에요! 계속 진행해보세요! 🌱';
    return '오늘의 일정을 시작해보세요! ✨';
  };

  const progressColor = getColor(percentage);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">📊 오늘의 달성률</div>

        {/* 원형 프로그레스 바 */}
        <div className="routine-circle-wrapper">
          <svg width="180" height="180" viewBox="0 0 180 180">
            {/* 배경 원 */}
            <circle
              cx="90" cy="90" r={radius}
              fill="none"
              stroke="#E8D5B8"
              strokeWidth="12"
            />
            {/* 프로그레스 원 */}
            <circle
              cx="90" cy="90" r={radius}
              fill="none"
              stroke={progressColor}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              style={{
                transition: 'stroke-dashoffset 0.8s ease, stroke 0.5s ease',
                transform: 'rotate(-90deg)',
                transformOrigin: '90px 90px'
              }}
            />
          </svg>
          <div className="routine-circle-text">
            <span className="routine-percent" style={{ color: progressColor }}>{percentage}%</span>
            <span className="routine-fraction">{completedCount}/{totalCount}</span>
          </div>
        </div>

        {/* 응원 메시지 */}
        <div className="routine-message">
          {getMessage(percentage)}
        </div>

        {/* 통계 카드 */}
        <div className="routine-stats">
          <div className="routine-stat-card">
            <span className="routine-stat-icon">🔥</span>
            <span className="routine-stat-value">{maxStreak}일</span>
            <span className="routine-stat-label">최고 연속</span>
          </div>
          <div className="routine-stat-card">
            <span className="routine-stat-icon">❤️</span>
            <span className="routine-stat-value">{earnedHearts}/{totalHearts}</span>
            <span className="routine-stat-label">오늘 하트</span>
          </div>
          <div className="routine-stat-card">
            <span className="routine-stat-icon">📋</span>
            <span className="routine-stat-value">{allCompleted}/{totalHabits}</span>
            <span className="routine-stat-label">전체 완료</span>
          </div>
        </div>

        {/* 오늘의 일정 목록 */}
        <div className="routine-list-title">
          📅 오늘의 일정 ({dayNames[today]}요일)
        </div>

        {todayHabits.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '16px', color: '#B8956A', fontSize: '14px' }}>
            오늘은 예정된 일정이 없어요! 🎉
          </div>
        ) : (
          <div className="routine-list">
            {todayHabits.map((h) => (
              <div
                key={h.id}
                className={`routine-item ${h.completed_today ? 'routine-item-done' : ''}`}
              >
                <span className="routine-item-check">
                  {h.completed_today ? '✅' : '⬜'}
                </span>
                <span className="routine-item-title">{h.title}</span>
                <span className="routine-item-reward">❤️ {h.hearts_reward}</span>
                {h.streak > 0 && (
                  <span className="routine-item-streak">🔥{h.streak}</span>
                )}
              </div>
            ))}
          </div>
        )}

        <button className="cancel-btn" onClick={onClose} style={{ marginTop: '16px' }}>
          닫기
        </button>
      </div>
    </div>
  );
}
