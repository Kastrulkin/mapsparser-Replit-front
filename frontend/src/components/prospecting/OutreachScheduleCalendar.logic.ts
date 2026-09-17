
export type OutreachScheduleTouch = {
  id?: string;
  sequence_index?: number;
  channel?: string;
  scheduled_at?: string | null;
  day_offset?: number;
  subject?: string | null;
  text?: string | null;
  generated_text?: string | null;
  approved_text?: string | null;
  status?: string | null;
};

export const defaultOutreachStartValue = (baseDate = new Date()) => {
  const result = new Date(baseDate);
  result.setSeconds(0, 0);
  if (result.getHours() >= 19) {
    result.setDate(result.getDate() + 1);
    result.setHours(10, 0, 0, 0);
  } else {
    result.setMinutes(result.getMinutes() < 30 ? 30 : 0);
    if (result.getMinutes() === 0) result.setHours(result.getHours() + 1);
  }
  const year = result.getFullYear();
  const month = `${result.getMonth() + 1}`.padStart(2, '0');
  const day = `${result.getDate()}`.padStart(2, '0');
  const hours = `${result.getHours()}`.padStart(2, '0');
  const minutes = `${result.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

export const outreachStartIso = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
};

export const buildProjectedOutreachTouches = (
  channels: string[],
  days: number[],
  startValue: string,
  sourceTouches: OutreachScheduleTouch[] = [],
) => {
  const start = new Date(startValue);
  if (Number.isNaN(start.getTime())) return [];
  return channels.map((channel, index) => {
    const scheduledAt = new Date(start);
    scheduledAt.setDate(start.getDate() + Math.max(0, Number(days[index] || 0)));
    const source = sourceTouches[index] || {};
    return {
      ...source,
      id: source.id || `projected-${index}`,
      sequence_index: index,
      channel,
      day_offset: Math.max(0, Number(days[index] || 0)),
      scheduled_at: scheduledAt.toISOString(),
      status: source.status || 'draft',
    };
  });
};
