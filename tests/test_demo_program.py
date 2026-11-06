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
