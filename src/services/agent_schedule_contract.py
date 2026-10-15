"""Shared schedule normalization for Operator and the existing automation editor."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ScheduleError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def apply_schedule(version, changes, *, business_timezone=None):
    previous = version.get('schedule') or {}
    schedule = dict(previous)
    for key in ('time', 'timezone', 'weekday', 'times', 'date'):
        if key in changes:
            schedule[key] = changes[key]
    if 'time' in changes and 'times' not in changes:
        schedule.pop('times', None)
        schedule.pop('date', None)
    if schedule.get('times') is not None:
        times = schedule['times']
        if not isinstance(times, list) or not 1 <= len(times) <= 2:
            raise ScheduleError('SCHEDULE_TIMES_INVALID', 'Укажите один или два запуска.')
        try:
            times = sorted(datetime.strptime(str(value), '%H:%M').strftime('%H:%M') for value in times)
            if len(set(times)) != len(times):
                raise ValueError()
            schedule['date'] = datetime.strptime(str(schedule.get('date') or ''), '%Y-%m-%d').date().isoformat()
        except ValueError:
            raise ScheduleError('SCHEDULE_TIMES_INVALID', 'Укажите дату ГГГГ-ММ-ДД и разные времена ЧЧ:ММ.')
        schedule['times'] = times
        schedule['time'] = times[0]
    schedule_time = schedule.get('time', '09:00')
    try:
        schedule['time'] = datetime.strptime(str(schedule_time), '%H:%M').strftime('%H:%M')
    except ValueError:
        raise ScheduleError('SCHEDULE_TIME_INVALID', 'Укажите время в формате ЧЧ:ММ.')
    zone_name = schedule.get('timezone') or business_timezone
    if not zone_name:
        raise ScheduleError('SCHEDULE_TIMEZONE_REQUIRED', 'Укажите часовой пояс бизнеса.')
    try:
        ZoneInfo(str(zone_name))
    except (ValueError, ZoneInfoNotFoundError):
        raise ScheduleError('SCHEDULE_TIMEZONE_INVALID', 'Укажите корректный часовой пояс.')
    schedule['timezone'] = str(zone_name)
    trigger = changes.get('trigger') or version.get('trigger') or 'schedule.daily'
    if trigger == 'manual.run':
        trigger = 'schedule.daily'
    if trigger not in {'schedule.daily', 'schedule.weekly'}:
        raise ScheduleError('SCHEDULE_TRIGGER_INVALID', 'Выберите ежедневный или еженедельный запуск.')
    if schedule.get('times') and trigger != 'schedule.daily':
        raise ScheduleError('SCHEDULE_TRIGGER_INVALID', 'Два ограниченных запуска задаются на одну дату.')
    if trigger == 'schedule.weekly':
        weekday = schedule.get('weekday')
        if not isinstance(weekday, int) or isinstance(weekday, bool) or not 0 <= weekday <= 6:
            raise ScheduleError('SCHEDULE_WEEKDAY_INVALID', 'Выберите день недели.')
    else:
        schedule.pop('weekday', None)
    return {**version, 'execution_mode': 'scheduled', 'trigger': trigger, 'schedule': schedule}


def describe_schedule(trigger, schedule):
    if schedule.get('times'):
        return f"{schedule['date']}, в {', '.join(schedule['times'])} ({schedule.get('timezone', 'пояс не указан')}); только указанная дата"
    if trigger == 'schedule.weekly':
        days = ('понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям')
        day = schedule.get('weekday')
        frequency = 'по ' + days[day] if isinstance(day, int) and 0 <= day < 7 else 'еженедельно'
    else:
        frequency = 'ежедневно'
    return f"{frequency}, {schedule.get('time', 'время не указано')} ({schedule.get('timezone', 'пояс не указан')})"


def next_bounded_run(schedule, now):
    validated = apply_schedule({'trigger': 'schedule.daily', 'schedule': schedule}, {})['schedule']
    zone = ZoneInfo(validated['timezone'])
    candidates = [datetime.fromisoformat(validated['date'] + 'T' + value).replace(tzinfo=zone)
                  for value in validated['times']]
    return next((candidate for candidate in candidates if candidate > now), None)
