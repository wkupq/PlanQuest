/**
 * 일정의 다음 알람까지 시간 계산.
 *
 * 백엔드 모델:
 *   times       = ["09:00", "18:00"]
 *   repeat_days = [0,1,2,3,4]  // 0=월 ... 6=일 (한국식)
 *
 * JS Date.getDay() 는 0=일 ... 6=토 라서 변환 필요.
 */

const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];

/**
 * @param {string[]} times       - ["09:00", "18:00"]
 * @param {number[]} repeatDays  - [0..6], 비어있으면 매일
 * @returns {{
 *   dateText: string,    // "오늘 18:30" / "내일 09:00" / "수 14:00"
 *   remainText: string,  // "5분 후" / "2시간 13분 후" / "1일 5시간 후" / "곧"
 *   shortText: string,   // 작은 배지용: "5분" / "2시간" / "1일" / "곧"
 *   msUntil: number,
 *   minutesUntil: number,
 * } | null}
 */
export function computeNextAlarm(times = [], repeatDays = []) {
  if (!times || times.length === 0) return null;
  const now = new Date();
  const candidates = [];

  for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
    const d = new Date(now);
    d.setDate(d.getDate() + dayOffset);

    const jsDow = d.getDay();          // 0=일 ... 6=토
    const krDow = (jsDow + 6) % 7;     // 0=월 ... 6=일
    if (repeatDays.length > 0 && !repeatDays.includes(krDow)) continue;

    for (const t of times) {
      const [hh, mm] = String(t).split(":").map(Number);
      if (Number.isNaN(hh) || Number.isNaN(mm)) continue;
      const cand = new Date(d);
      cand.setHours(hh, mm, 0, 0);
      if (cand > now) candidates.push(cand);
    }
  }

  if (!candidates.length) return null;
  candidates.sort((a, b) => a - b);
  const next = candidates[0];

  // 날짜 텍스트
  const sameDay = next.toDateString() === now.toDateString();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const isTomorrow = next.toDateString() === tomorrow.toDateString();
  const hh = String(next.getHours()).padStart(2, "0");
  const mm = String(next.getMinutes()).padStart(2, "0");
  const dayLabel = sameDay
    ? "오늘"
    : isTomorrow
    ? "내일"
    : DAY_NAMES[(next.getDay() + 6) % 7];
  const dateText = `${dayLabel} ${hh}:${mm}`;

  // 남은 시간 (분 단위 정밀도, 초 단위 X)
  const diffMs = next - now;
  const totalMin = Math.max(0, Math.floor(diffMs / 60000));
  const days = Math.floor(totalMin / 1440);
  const hours = Math.floor((totalMin % 1440) / 60);
  const minutes = totalMin % 60;

  // 길게 (모달용)
  let remainText;
  if (days > 0) remainText = `${days}일 ${hours}시간 후`;
  else if (hours > 0) remainText = `${hours}시간 ${minutes}분 후`;
  else if (minutes > 0) remainText = `${minutes}분 후`;
  else remainText = "곧";

  // 짧게 (배지용 — 가장 큰 단위만)
  let shortText;
  if (days > 0) shortText = `${days}일`;
  else if (hours > 0) shortText = minutes > 0 ? `${hours}시간 ${minutes}분` : `${hours}시간`;
  else if (minutes > 0) shortText = `${minutes}분`;
  else shortText = "곧";

  return {
    dateText,
    remainText,
    shortText,
    msUntil: diffMs,
    minutesUntil: totalMin,
  };
}
