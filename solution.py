## Student Name: Mark Farid
## Student ID: 218994368

"""
Task A: Appointment Timeslot Recommender (Stub)

In this lab, you will design and implement an Appointment Slot Recommender using an LLM assistant
as your primary programming collaborator.

You are asked to implement a Python module that recommends available meeting slots within a
defined working window.

The system must:
  • Accept working hours (start and end time).
  • Accept a list of existing busy intervals.
  • Accept a required meeting duration.
  • Accept an optional buffer time between meetings.
  • Optionally restrict suggestions to a candidate time window.
  • Return chronologically ordered appointment slots that satisfy all constraints.

The system must ensure that:
  • Suggested slots fall within working hours.
  • Suggested slots do not overlap busy intervals.
  • Buffer time is respected when evaluating availability.
  • Output ordering is deterministic under identical inputs.

The module must preserve the following invariants:
  • Returned slots must be at least as long as the required duration.
  • No returned slot may violate buffer constraints.
  • The returned list must reflect the current system state.

The system must correctly handle non-trivial scenarios such as:
  • Adjacent busy intervals.
  • Very small gaps between meetings.
  • Buffers eliminating otherwise valid availability.
  • Overlapping or unsorted busy intervals.
  • A meeting duration longer than any available gap.
  • No availability within the working window.

Output:
  The output consists of the next N valid appointment suggestions in chronological order.
  Behavior must be deterministic under ties (if any).

See the lab handout for full requirements.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple


# ---------------- Data Models ----------------

@dataclass(frozen=True)
class TimeWindow:
    """
    A daily time window.
    Assumption (unless stated otherwise in handout): non-wrapping window where start < end.
    """
    start: time
    end: time


@dataclass(frozen=True)
class BusyInterval:
    """
    A busy interval on the given day.
    Invariant: start < end
    """
    start: time
    end: time


@dataclass(frozen=True)
class Slot:
    """
    A recommended appointment slot.

    start_time is a time-of-day within the working window.
    Deterministic ordering: sort by start_time ascending.
    """
    start_time: time


class InfeasibleSchedule(Exception):
    """Raised when no valid slots can be produced (if required by handout)."""
    pass

# helper functiosn:
IntervalDT = Tuple[datetime, datetime]


def _validate_time_window(name: str, w: TimeWindow) -> None:
    if w.start is None or w.end is None:
        raise ValueError(f"{name} start/end must not be None")
    if w.end <= w.start:
        raise ValueError(f"{name} must satisfy start < end (got {w.start} to {w.end})")


def _validate_busy_interval(b: BusyInterval) -> None:
    if b.start is None or b.end is None:
        raise ValueError("BusyInterval start/end must not be None")
    if b.end <= b.start:
        raise ValueError(f"BusyInterval must satisfy start < end (got {b.start} to {b.end})")


def _merge_intervals(intervals: List[IntervalDT]) -> List[IntervalDT]:
    """
    Merge overlapping or adjacent intervals using half-open semantics [start, end).
    Adjacent where cur_end == next_start are merged to simplify.
    """
    if not intervals:
        return []

    intervals_sorted = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: List[IntervalDT] = []
    cur_s, cur_e = intervals_sorted[0]

    for s, e in intervals_sorted[1:]:
        # overlap or adjacency => merge
        if cur_e >= s:
            if e > cur_e:
                cur_e = e
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e

    merged.append((cur_s, cur_e))
    return merged


def _clip_interval(iv: IntervalDT, start: datetime, end: datetime) -> Optional[IntervalDT]:
    s, e = iv
    if e <= start or s >= end:
        return None
    return (max(s, start), min(e, end))


def _append_slots_from_gap(
    gap_start: datetime,
    gap_end: datetime,
    duration: timedelta,
    n: int,
    out: List[Slot],
) -> None:
    """
    Generate back-to-back slots of length `duration` within [gap_start, gap_end).
    Append Slot(start_time) until out has n items or no more fit.
    """
    s = gap_start
    while s + duration <= gap_end and len(out) < n:
        out.append(Slot(start_time=s.time()))
        s = s + duration

# ---------------- Core Function ----------------

def suggest_slots(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta = timedelta(0),
    candidate_window: Optional[TimeWindow] = None
) -> List[Slot]:
    """
    Suggest up to the next n valid appointment slots (start times) for the given day.

    Args:
        day: the calendar day for which to suggest slots.
        working_hours: the allowed working window for meetings (start < end).
        busy_intervals: list of busy time intervals (may be overlapping / unsorted).
        duration: required meeting length (must be > 0).
        n: maximum number of slot suggestions to return (n >= 0).
        buffer: optional buffer time required between meetings (buffer >= 0).
        candidate_window: optional extra restriction on suggestions (must lie within this window too).

    Returns:
        A list of Slot objects, sorted by start_time ascending, deterministic under identical inputs.
        If no suitable time slots are available, return an empty list.

    Notes:
        - Suggested slots must fall within working_hours (and candidate_window if provided).
        - Suggested slots must not overlap busy_intervals, considering buffer time.
        - You are free to choose internal representation; inputs use time-of-day.
        - See lab handout for required slot granularity (e.g., 5-min/15-min steps), if any.
    """

    ##################################################################
    # TODO: Implement as per lab handout requirements and constraints.
    ##################################################################
    
    _validate_time_window("working_hours", working_hours)

    if candidate_window is not None:
        _validate_time_window("candidate_window", candidate_window)

    if duration is None or duration <= timedelta(0):
        raise ValueError("duration must be > 0")

    if buffer is None or buffer < timedelta(0):
        raise ValueError("buffer must be >= 0")

    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be an int >= 0")

    if n == 0:
        return []

    for b in busy_intervals:
        _validate_busy_interval(b)

    # ---- Compute effective allowed window (working ∩ candidate, if any) ----
    eff_start_t = working_hours.start
    eff_end_t = working_hours.end
    if candidate_window is not None:
        eff_start_t = max(eff_start_t, candidate_window.start)
        eff_end_t = min(eff_end_t, candidate_window.end)

    # If intersection is empty, no slots
    if eff_end_t <= eff_start_t:
        return []

    eff_start_dt = datetime.combine(day, eff_start_t)
    eff_end_dt = datetime.combine(day, eff_end_t)

    # ---- Expand busy intervals by buffer and convert to datetimes ----
    expanded_busy: List[IntervalDT] = []
    for b in busy_intervals:
        bs = datetime.combine(day, b.start) - buffer
        be = datetime.combine(day, b.end) + buffer
        expanded_busy.append((bs, be))

    # Merge overlaps/adjacency (robust to unsorted input)
    merged_busy = _merge_intervals(expanded_busy)

    # Clip busy intervals to effective window (ignore irrelevant parts)
    clipped: List[IntervalDT] = []
    for iv in merged_busy:
        clipped_iv = _clip_interval(iv, eff_start_dt, eff_end_dt)
        if clipped_iv is not None:
            clipped.append(clipped_iv)

    merged_busy = _merge_intervals(clipped)

    # ---- Find free gaps and emit up to n slots ----
    results: List[Slot] = []
    cursor = eff_start_dt

    for bs, be in merged_busy:
        if bs > cursor:
            # Free gap: [cursor, bs)
            _append_slots_from_gap(cursor, bs, duration, n, results)
            if len(results) >= n:
                return results
        cursor = max(cursor, be)

    # Tail gap: [cursor, eff_end_dt)
    if cursor < eff_end_dt and len(results) < n:
        _append_slots_from_gap(cursor, eff_end_dt, duration, n, results)

    return results
