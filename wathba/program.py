"""Demo schedule and completion derived from saved, trackable exercise sessions."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DOHA = ZoneInfo('Asia/Qatar')
DAYS = (0, 1, 3, 5)  # Monday, Tuesday, Thursday, Saturday; demonstration only.


def demo_program(sessions, target=5, now=None):
    now = (now or datetime.now(DOHA)).astimezone(DOHA)
    today = now.date()
    exercises = []
    for key, name in [('squat', 'Squats'), ('jump', 'Jump')]:
        records = [s for s in sessions if s.get('exercise', 'Squat').lower() == key]
        daily = [s for s in records if datetime.fromisoformat(s['created_at']).astimezone(DOHA).date() == today]
        reps = max((s['repetitions'] for s in daily if s.get('coverage', 0) >= 70), default=0)
        complete = reps >= target
        due = next(today + timedelta(days=i) for i in range(8)
                   if (today + timedelta(days=i)).weekday() in DAYS and (i > 0 or not complete))
        exercises.append({'id': key, 'name': name, 'target': target, 'completed': complete,
                          'repetitions_today': reps, 'next_due': due.isoformat(),
                          'last_session': records[0]['id'] if records else None})
    completed = sum(e['completed'] for e in exercises)
    return {'id': 'demo', 'name': 'Demo', 'times_per_week': 4,
            'schedule': ['Mon', 'Tue', 'Thu', 'Sat'], 'timezone': 'Asia/Qatar',
            'today': today.isoformat(), 'scheduled_today': today.weekday() in DAYS,
            'completed': completed, 'total': len(exercises), 'progress': completed * 50,
            'next_due': min(e['next_due'] for e in exercises), 'exercises': exercises,
            'note': 'Demonstration schedule. Exercise choice and frequency require your therapist’s approval.'}
