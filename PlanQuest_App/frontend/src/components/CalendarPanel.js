import React, { useState, useEffect, useCallback } from 'react';
import { getCalendarMonth, getCalendarDay } from '../api';
import './CalendarPanel.css';

const MONTH_NAMES = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토'];

// 완료 수에 따른 히트맵 색상 (5단계)
function heatColor(count) {
  if (!count) return null;       // 완료 없음 — 연한 베이지
  if (count === 1) return 'h1';
  if (count <= 2) return 'h2';
  if (count <= 4) return 'h3';
  if (count <= 6) return 'h4';
  return 'h5';
}

function ymd(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function CalendarPanel({ onClose }) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [monthData, setMonthData] = useState(null);    // { days: [], stats: {} }
  const [selectedDate, setSelectedDate] = useState(null);  // 'YYYY-MM-DD'
  const [dayData, setDayData] = useState(null);
  const [loading, setLoading] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth() + 1;

  // 월별 데이터 로드
  const loadMonth = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getCalendarMonth(year, month);
      setMonthData(res.data);
    } catch (err) {
      console.error('캘린더 로드 실패:', err);
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { loadMonth(); }, [loadMonth]);

  // 날짜 클릭 → 디테일 로드
  const handleDayClick = async (date) => {
    setSelectedDate(date);
    try {
      const res = await getCalendarDay(date);
      setDayData(res.data);
    } catch (err) {
      console.error('날짜 디테일 로드 실패:', err);
      setDayData(null);
    }
  };

  // 월 이동
  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 2, 1));  // month 는 1-base, Date 는 0-base
    setSelectedDate(null);
    setDayData(null);
  };
  const nextMonth = () => {
    setCurrentDate(new Date(year, month, 1));
    setSelectedDate(null);
    setDayData(null);
  };

  // 그리드 만들기
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const dayMap = {};
  if (monthData?.days) {
    for (const d of monthData.days) dayMap[d.date] = d;
  }

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push({ empty: true, key: `e-${i}` });
  for (let i = 1; i <= daysInMonth; i++) {
    const date = `${year}-${String(month).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
    cells.push({ day: i, date, info: dayMap[date], key: date });
  }

  const todayStr = ymd(new Date());

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="cal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="cal-close" onClick={onClose}>✕</button>
        <div className="cal-header">📅 캘린더</div>

        {/* 월 네비게이션 */}
        <div className="cal-nav">
          <button onClick={prevMonth}>◀</button>
          <span className="cal-month-label">{year}년 {MONTH_NAMES[month - 1]}</span>
          <button onClick={nextMonth}>▶</button>
        </div>

        {/* 통계 */}
        {monthData?.stats && (
          <div className="cal-stats">
            <Stat label="이번 달 달성" value={`${monthData.stats.completed_days}일`} />
            <Stat label="총 완료" value={`${monthData.stats.total_completions}건`} />
            <Stat label="🔥 연속" value={`${monthData.stats.current_streak}일`} highlight />
            <Stat label="❤️ 받은 하트" value={monthData.stats.total_hearts} />
          </div>
        )}

        {/* 요일 헤더 */}
        <div className="cal-grid cal-dow">
          {DAY_NAMES.map((d, i) => (
            <div key={d} className={`cal-dow-cell ${i === 0 ? 'sun' : ''} ${i === 6 ? 'sat' : ''}`}>
              {d}
            </div>
          ))}
        </div>

        {/* 날짜 그리드 (히트맵) */}
        <div className="cal-grid cal-days">
          {cells.map((c) =>
            c.empty ? (
              <div key={c.key} className="cal-day empty" />
            ) : (
              <button
                key={c.key}
                className={
                  'cal-day'
                  + (c.info ? ` ${heatColor(c.info.completions) || ''}` : '')
                  + (c.date === todayStr ? ' today' : '')
                  + (c.date === selectedDate ? ' selected' : '')
                }
                onClick={() => handleDayClick(c.date)}
              >
                <span className="cal-day-num">{c.day}</span>
                {c.info?.completions > 0 && (
                  <span className="cal-day-mark">{c.info.completions}</span>
                )}
                {c.info?.scheduled && c.info.completions === 0 && (
                  <span className="cal-day-dot">·</span>
                )}
              </button>
            )
          )}
        </div>

        {/* 히트맵 범례 */}
        <div className="cal-legend">
          <span>적음</span>
          <div className="cal-legend-cell" />
          <div className="cal-legend-cell h1" />
          <div className="cal-legend-cell h2" />
          <div className="cal-legend-cell h3" />
          <div className="cal-legend-cell h4" />
          <div className="cal-legend-cell h5" />
          <span>많음</span>
        </div>

        {/* 선택한 날짜 디