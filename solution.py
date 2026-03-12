## Student Name: Mark Farid
## Student ID: 218994368

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple


# ---------------- Data Models ----------------

@dataclass(frozen=True)
class TimeWindow:
    """
    A daily time window (non-wrapping): start < end.
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
    A recommended appointment slot (start time only).
    """
    start_time: time


class InfeasibleSchedule(Exception):
    """Raised when no valid slots can be produced (if required by handout)."""
    pass


# ---------------- Explanation / Reason Codes (C11) ----------------

# Fixed set of reasons (as required by C11/AC10)
REASON_NO_GAP = "NO_GAP"
REASON_BUFFER_BLOCKED = "BUFFER_BLOCKED"
REASON_CANDIDATE_WINDOW_EMPTY = "CANDIDATE_WINDOW_EMPTY"
REASON_INVALID_INPUT = "INVALID_INPUT"

_last_reason: Optional[str] = None


def get_last_reason() -> Optional[str]:
    """
    Returns the reason code for the most recent suggest_slots call
    *only when* that call returned [].
    Returns None if the last call returned non-empty results.
    """
    return _last_reason


def _set_reason(reason: Optional[str]) -> None:
    global _last_reason
    _last_reason = reason


# ---------------- Helper Functions ----------------

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
    Adjacent where cur_end == next_start are merged (covers EC4).
    """
    if not intervals:
        return []

    intervals_sorted = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: List[IntervalDT] = []
    cur_s, cur_e = intervals_sorted[0]

    for s, e in intervals_sorted[1:]:
        if cur_e >= s:  # overlap or adjacency
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


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    # Half-open overlap check [a_start, a_end) overlaps [b_start, b_end)
    return a_start < b_end and b_start < a_end


def _append_slots_from_gap(
    gap_start: datetime,
    gap_end: datetime,
    duration: timedelta,
    step: timedelta,
    n: int,
    out: List[Slot],
) -> None:
    """
    Generate slots in [gap_start, gap_end) such that each slot is [t, t+duration)
    and successive start times differ by exactly step (C10/AC9).
    """
    t = gap_start
    while t + duration <= gap_end and len(out) < n:
        out.append(Slot(start_time=t.time()))
        t = t + step


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
    Suggest up to the next n valid appointment slot start times for the given day.

    Key rules aligned to updated requirements:
    - C8/AC7: Each returned slot interval [s, s+duration) must fit fully within
      the effective allowed window (working ∩ candidate).
    - C9/AC8: Buffer expands busy intervals to [bs-buffer, be+buffer) (half-open).
    - C10/AC9: Slot starts are generated with a fixed step size S (here: S = duration).
    - C11/AC10: If returning [], an explanation reason code is made available via get_last_reason().
    """
    _set_reason(None)  # reset each call; set only if returning []

    # ---- Validate inputs ----
    try:
        _validate_time_window("working_hours", working_hours)

        if candidate_window is not None:
            _validate_time_window("candidate_window", candidate_window)

        if duration is None or duration <= timedelta(0):
            raise ValueError("duration must be > 0")

        if buffer is None or buffer < timedelta(0):
            raise ValueError("buffer must be >= 0")

        if not isinstance(n, int) or n < 0:
            raise ValueError("n must be an int >= 0")

        for b in busy_intervals:
            _validate_busy_interval(b)

    except ValueError:
        _set_reason(REASON_INVALID_INPUT)
        raise

    if n == 0:
        # Not “no availability”; just “asked for none”
        return []

    # ---- Compute effective allowed window (A6 / C8) ----
    eff_start_t = working_hours.start
    eff_end_t = working_hours.end

    if candidate_window is not None:
        eff_start_t = max(eff_start_t, candidate_window.start)
        eff_end_t = min(eff_end_t, candidate_window.end)

    if eff_end_t <= eff_start_t:
        _set_reason(REASON_CANDIDATE_WINDOW_EMPTY)
        return []

    eff_start_dt = datetime.combine(day, eff_start_t)
    eff_end_dt = datetime.combine(day, eff_end_t)

    # Fixed step size S (C10). Choose S = duration to match existing behavior/tests.
    step = duration

    # ---- Expand busy intervals by buffer (C9) and convert to datetimes ----
    expanded_busy: List[IntervalDT] = []
    for b in busy_intervals:
        bs = datetime.combine(day, b.start) - buffer
        be = datetime.combine(day, b.end) + buffer
        expanded_busy.append((bs, be))

    merged_busy = _merge_intervals(expanded_busy)

    # Clip to effective window
    clipped: List[IntervalDT] = []
    for iv in merged_busy:
        clipped_iv = _clip_interval(iv, eff_start_dt, eff_end_dt)
        if clipped_iv is not None:
            clipped.append(clipped_iv)

    merged_busy = _merge_intervals(clipped)

    # ---- Find free gaps and generate slots ----
    results: List[Slot] = []
    cursor = eff_start_dt

    for bs, be in merged_busy:
        if bs > cursor:
            _append_slots_from_gap(cursor, bs, duration, step, n, results)
            if len(results) >= n:
                return results
        cursor = max(cursor, be)

    if cursor < eff_end_dt and len(results) < n:
        _append_slots_from_gap(cursor, eff_end_dt, duration, step, n, results)

    if not results:
        # Choose reason code (C11) when output is empty
        # Distinguish BUFFER_BLOCKED vs NO_GAP:
        if buffer > timedelta(0):
            # Re-check feasibility without buffer:
            no_buffer_out = suggest_slots(
                day=day,
                working_hours=working_hours,
                busy_intervals=busy_intervals,
                duration=duration,
                n=1,
                buffer=timedelta(0),
                candidate_window=candidate_window
            )
            # Prevent last_reason from being overwritten by recursive call
            # (if no_buffer_out is non-empty, buffer eliminated it)
            if len(no_buffer_out) > 0:
                _set_reason(REASON_BUFFER_BLOCKED)
            else:
                _set_reason(REASON_NO_GAP)
        else:
            _set_reason(REASON_NO_GAP)

    return results