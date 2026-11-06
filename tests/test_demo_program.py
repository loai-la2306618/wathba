from datetime import datetime
from wathba.program import demo_program


def record(exercise, date='2026-11-05T21:30:00+00:00', reps=5, coverage=95):
    return {'id':exercise,'exercise':exercise,'created_at':date,'repetitions':reps,'coverage':coverage}


def test_daily_completion_and_next_due_use_doha_date():
    p=demo_program([record('Squat'),record('Jump',reps=4)],now=datetime.fromisoformat('2026-11-06T00:45:00+03:00'))
    assert p['completed']==1 and p['progress']==50
    assert p['exercises'][0]['completed']
    assert not p['exercises'][1]['completed']
    assert p['next_due']=='2026-11-07'
    assert len(p['schedule'])==p['times_per_week']==4


def test_completed_exercise_moves_to_next_slot_while_pending_stays_due():
    p=demo_program([record('Squat',date='2026-11-07T08:00:00+03:00')],now=datetime.fromisoformat('2026-11-07T10:00:00+03:00'))
    assert p['exercises'][0]['next_due']=='2026-11-09'
    assert p['exercises'][1]['next_due']=='2026-11-07'
    assert p['scheduled_today']


def test_yesterday_and_untrackable_recordings_do_not_complete_today():
    p=demo_program([record('Squat',date='2026-11-05T08:00:00+03:00'),record('Jump',coverage=30)],now=datetime.fromisoformat('2026-11-06T10:00:00+03:00'))
    assert p['completed']==0


def test_training_summary_counts_distinct_doha_days_weeks_and_months():
    from wathba.program import training_summary
    stamps = ['2026-10-30T10:00:00+03:00',  # Fri, week of Oct 26, October
              '2026-10-30T18:00:00+03:00',  # same day: one day, two sessions
              '2026-11-01T22:30:00+00:00',  # Mon Nov 2 in Doha (01:30) -> new week, November
              '2026-11-05T09:00:00+03:00',  # Thu, same week as Nov 2
              '2026-11-06T09:00:00+03:00']
    result = training_summary([{'created_at': t} for t in stamps])
    assert result == {'sessions': 5, 'days': 4, 'weeks': 2, 'months': 2, 'first': '2026-10-30', 'last': '2026-11-06'}
    assert training_summary([])['days'] == 0
