"""Explainable attendance calculations with explicit denominator semantics."""

from math import ceil, floor


COUNTED_STATUSES = frozenset({'PRESENT', 'ABSENT', 'LATE'})
ATTENDED_STATUSES = frozenset({'PRESENT', 'LATE'})


def _record_status(record):
    """Read explicit status while remaining compatible with legacy rows."""
    status = getattr(record, 'status', None)
    if status:
        return status
    return 'PRESENT' if getattr(record, 'is_present', False) else 'ABSENT'


def calculate_attendance(records, *, target=0.75):
    """Return bounded attendance metrics for an iterable of attendance rows.

    ``EXCUSED`` rows are reported but excluded from the scheduled-class
    denominator.  Legacy rows without a status use their ``is_present`` value.
    ``target`` is a fraction in the inclusive range 0..1.
    """
    if not 0 <= target <= 1:
        raise ValueError('target must be between 0 and 1')

    counts = {status: 0 for status in ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED')}
    for record in records:
        status = _record_status(record)
        if status not in counts:
            status = 'ABSENT'
        counts[status] += 1

    scheduled = sum(counts[status] for status in COUNTED_STATUSES)
    attended = sum(counts[status] for status in ATTENDED_STATUSES)
    percentage = round(attended / scheduled * 100, 2) if scheduled else 0.0

    if scheduled == 0 or target == 0 or attended / scheduled >= target:
        classes_needed = 0
    elif target == 1:
        classes_needed = scheduled - attended
    else:
        classes_needed = ceil((target * scheduled - attended) / (1 - target))

    # ``safe_missed`` is the number of additional absences possible while
    # retaining the target, assuming no further attended classes.
    if target == 0:
        safe_missed = None
    elif scheduled == 0:
        safe_missed = 0
    else:
        safe_missed = max(0, floor(attended / target - scheduled))

    return {
        **counts,
        'total_records': sum(counts.values()),
        'scheduled_classes': scheduled,
        'attended_classes': attended,
        'percentage': percentage,
        'target_percentage': round(target * 100, 2),
        'classes_needed': classes_needed,
        'safe_missed_classes': safe_missed,
    }
