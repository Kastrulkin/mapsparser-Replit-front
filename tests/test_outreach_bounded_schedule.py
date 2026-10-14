from datetime import datetime,timezone
import pytest
from services.agent_schedule_contract import apply_schedule,ScheduleError,describe_schedule
from services.agent_trigger_runtime import _schedule_context


def bounded():
    return apply_schedule({}, {'times':['11:15','11:00'],'date':'2026-10-14','timezone':'Europe/Moscow'})


def test_two_real_native_slots_have_distinct_existing_dedupe_keys_and_expire():
    version=bounded();version['schedule_json']=version['schedule']
    first=_schedule_context({},version,datetime(2026,10,14,8,1,tzinfo=timezone.utc))
    second=_schedule_context({},version,datetime(2026,10,14,8,16,tzinfo=timezone.utc))
    assert first['due'] and second['due']
    assert first['schedule_time']=='11:00' and second['schedule_time']=='11:15'
    assert first['schedule_date']==second['schedule_date']=='2026-10-14'
    assert not _schedule_context({},version,datetime(2026,10,15,8,1,tzinfo=timezone.utc))['due']
    assert 'только указанная дата' in describe_schedule(version['trigger'],version['schedule'])


@pytest.mark.parametrize('change',[{'times':['11:00','11:00']},{'times':['11:00','11:15','11:30']},{'date':''},{'times':['25:00']},{'trigger':'schedule.weekly','weekday':2}])
def test_invalid_or_unbounded_two_run_schedule_cannot_be_activated(change):
    with pytest.raises(ScheduleError):apply_schedule({}, {'times':['11:00','11:15'],'date':'2026-10-14','timezone':'Europe/Moscow',**change})


def test_regular_daily_edit_does_not_keep_old_hidden_two_slots():
    updated=apply_schedule(bounded(),{'time':'13:00'})
    assert updated['schedule']['time']=='13:00'
    assert 'times' not in updated['schedule'] and 'date' not in updated['schedule']


def test_next_slot_display_uses_second_time_and_never_invents_tomorrow():
    from services.agent_schedule_contract import next_bounded_run
    schedule=bounded()['schedule']
    assert next_bounded_run(schedule,datetime(2026,10,14,8,1,tzinfo=timezone.utc)).strftime('%H:%M')=='11:15'
    assert next_bounded_run(schedule,datetime(2026,10,14,8,16,tzinfo=timezone.utc)) is None
    assert next_bounded_run(schedule,datetime(2026,10,15,8,0,tzinfo=timezone.utc)) is None
