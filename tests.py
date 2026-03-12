import pytest
from datetime import date, datetime, time, timedelta

# Update import path to match your project structure:
from solution import TimeWindow, BusyInterval, Slot, suggest_slots, get_last_reason, REASON_NO_GAP


# ---------- Helpers ----------

def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def in_window(win: TimeWindow, t: time) -> bool:
    return win.start <= t < win.end


def assert_slots_basic_constraints(
    slots,
    day,
    working_hours,
    busy_intervals,
    duration,
    n,
    buffer,
    candidate_window,
):
    # Return type / length
    assert isinstance(slots, list)
    assert len(slots) <= n

    # Deterministic ordering: start_time ascending
    assert slots == sorted(slots, key=lambda s: s.start_time)

    # Each slot start must be within working_hours and candidate_window (if any)
    for s in slots:
        assert in_window(working_hours, s.start_time)
        if candidate_window is not None:
            assert in_window(candidate_window, s.start_time)

    # Each slot must fit fully inside working_hours and candidate_window
    for s in slots:
        start_dt = combine(day, s.start_time)
        end_dt = start_dt + duration

        wh_end = combine(day, working_hours.end)
        assert end_dt <= wh_end

        if candidate_window is not None:
            cw_end = combine(day, candidate_window.end)
            assert end_dt <= cw_end

    # No overlap with busy intervals, considering buffer:
    # busy interval is expanded to [start-buffer, end+buffer)
    for s in slots:
        slot_start = combine(day, s.start_time)
        slot_end = slot_start + duration

        for b in busy_intervals:
            b_start = combine(day, b.start) - buffer
            b_end = combine(day, b.end) + buffer
            assert not overlaps(slot_start, slot_end, b_start, b_end)


# ---------- Tests ----------
# Covers C3, C8, C9, AC3, AC7, AC8
def test_a1_no_busy_simple_slots():
    """
    Like original "single med exact times": here, no busy events.
    Expect earliest slots within working hours (we only assert constraints + non-empty).
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = []
    duration = timedelta(minutes=30)

    out = suggest_slots(
        day=day,
        working_hours=working,
        busy_intervals=busy,
        duration=duration,
        n=3,
        buffer=timedelta(0),
        candidate_window=None
    )

    assert_slots_basic_constraints(out, day, working, busy, duration, 3, timedelta(0), None)
    # Should at least return 1 slot if implementation uses a reasonable slot step
    assert len(out) > 0
    # Earliest slot should be at or after working start
    assert out[0].start_time >= time(9, 0)

# Covers C1, C5, AC1
def test_a2_deterministic_same_inputs_same_outputs():
    """
    Like original tie/determinism check: same inputs must return identical outputs.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [
        BusyInterval(time(10, 0), time(10, 30)),
        BusyInterval(time(13, 0), time(14, 0)),
    ]
    duration = timedelta(minutes=30)
    buffer = timedelta(minutes=0)

    out1 = suggest_slots(day, working, busy, duration, n=10, buffer=buffer, candidate_window=None)
    out2 = suggest_slots(day, working, busy, duration, n=10, buffer=buffer, candidate_window=None)

    assert [s.start_time for s in out1] == [s.start_time for s in out2]
    assert_slots_basic_constraints(out1, day, working, busy, duration, 10, buffer, None)

# Covers C4, AC4, EC2, EC3
def test_a3_overlapping_and_unsorted_busy_intervals_handled():
    """
    Busy intervals may be unsorted/overlapping; suggestions must still avoid conflicts.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [
        BusyInterval(time(10, 30), time(11, 0)),
        BusyInterval(time(10, 0), time(10, 45)),   # overlaps with above
        BusyInterval(time(9, 30), time(9, 45)),    # unsorted relative order
    ]
    duration = timedelta(minutes=15)

    out = suggest_slots(day, working, busy, duration, n=8, buffer=timedelta(0), candidate_window=None)
    assert_slots_basic_constraints(out, day, working, busy, duration, 8, timedelta(0), None)

# Covers C8, AC7
def test_a4_candidate_window_respected():
    """
    Like original allowed_window respected: here we add an extra candidate window restriction.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    candidate = TimeWindow(time(13, 0), time(15, 0))
    busy = []
    duration = timedelta(minutes=30)

    out = suggest_slots(day, working, busy, duration, n=5, buffer=timedelta(0), candidate_window=candidate)
    assert_slots_basic_constraints(out, day, working, busy, duration, 5, timedelta(0), candidate)

    # Every slot must start within candidate window
    assert all(candidate.start <= s.start_time < candidate.end for s in out)

# Covers C9, AC8
def test_a5_buffer_eliminates_small_gaps():
    """
    Like original rate-limit constraint: here buffer is the key extra constraint.
    With buffer, some slots that would otherwise fit should be invalid.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(11, 0))
    # Two busy intervals leaving a 20-minute gap between them
    busy = [
        BusyInterval(time(9, 30), time(9, 50)),
        BusyInterval(time(10, 10), time(10, 30)),
    ]
    duration = timedelta(minutes=20)

    # Without buffer: the gap 9:50–10:10 is exactly 20 minutes -> potentially valid
    out_no_buffer = suggest_slots(day, working, busy, duration, n=10, buffer=timedelta(0), candidate_window=None)
    assert_slots_basic_constraints(out_no_buffer, day, working, busy, duration, 10, timedelta(0), None)

    # With 5-min buffer: effective busy expands, gap shrinks -> should reduce or remove those slots
    buf = timedelta(minutes=5)
    out_with_buffer = suggest_slots(day, working, busy, duration, n=10, buffer=buf, candidate_window=None)
    assert_slots_basic_constraints(out_with_buffer, day, working, busy, duration, 10, buf, None)

    # Buffer should not increase number of available slots (monotonicity)
    assert len(out_with_buffer) <= len(out_no_buffer)


#################################################################################
# Add your own additional tests here to cover more cases and edge cases as needed.
#################################################################################

# Covers C6, AC5, EC1
# No availability returns empty edge case
def test_a6():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(10, 0))
    busy = [BusyInterval(time(9, 0), time(10, 0))]
    duration = timedelta(minutes=15)
    out = suggest_slots(day, working, busy, duration, n=5, buffer=timedelta(0), candidate_window=None)
    assert out == []

# Covers C10, AC9
# Exact slots meaning should'nt be busy back to back
def test_a7():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    out = suggest_slots(day, working, [], timedelta(minutes=60), n=10)
    assert [s.start_time for s in out] == [time(9, 0), time(10, 0), time(11, 0)]

# Covers C2, C9, AC2, AC8
# Skip single busy interval
def test_a8():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [BusyInterval(time(10, 0), time(11, 0))]
    out = suggest_slots(day, working, busy, timedelta(minutes=30), n=10)
    assert [s.start_time for s in out] == [time(9, 0), time(9, 30), time(11, 0), time(11, 30)]

# Covers C4, AC4, EC2
# Merge overlapping busy
def test_a9():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(13, 0))
    busy = [BusyInterval(time(11, 0), time(12, 0)), BusyInterval(time(10, 0), time(11, 30))]
    out = suggest_slots(day, working, busy, timedelta(minutes=30), n=10)
    assert [s.start_time for s in out] == [time(9, 0), time(9, 30), time(12, 0), time(12, 30)]

# Covers C8, AC7
# Exact candidate window intersection
def test_a10():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    candidate = TimeWindow(time(13, 0), time(15, 0))
    out = suggest_slots(day, working, [], timedelta(minutes=60), n=10, candidate_window=candidate)
    assert [s.start_time for s in out] == [time(13, 0), time(14, 0)]

# Covers C9, AC8
# Buffer expands busy and removes slots
def test_a11():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [BusyInterval(time(10, 0), time(11, 0))]
    out = suggest_slots(day, working, busy, timedelta(minutes=30), n=10, buffer=timedelta(minutes=30))
    assert [s.start_time for s in out] == [time(9, 0), time(11, 30)]

# Covers C11, AC10
# No gap when empty
def test_a12():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(10, 0))
    busy = [BusyInterval(time(9, 0), time(10, 0))]
    out = suggest_slots(day, working, busy, timedelta(minutes=15), n=5, buffer=timedelta(0), candidate_window=None)
    assert out == []
    assert get_last_reason() == REASON_NO_GAP

# Covers C11, AC10
# Candidate window empty
def test_a13():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    candidate = TimeWindow(time(13, 0), time(13, 0))
    with pytest.raises(ValueError):
        suggest_slots(day, working, [], timedelta(minutes=30), n=5, buffer=timedelta(0), candidate_window=candidate)

# Covers C2, C4, AC2, AC4, EC4
# Adjacent busy intervals
def test_a14():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [
        BusyInterval(time(10, 0), time(10, 30)),
        BusyInterval(time(10, 30), time(11, 0)),
    ]
    out = suggest_slots(day, working, busy, timedelta(minutes=30), n=10, buffer=timedelta(0), candidate_window=None)
    assert [s.start_time for s in out] == [time(9, 0), time(9, 30), time(11, 0), time(11, 30)]

# Covers C3, AC3
# n=0 returns empty list
def test_a15():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    busy = []
    out = suggest_slots(day, working, busy, timedelta(minutes=30), n=0, buffer=timedelta(0), candidate_window=None)
    assert out == []

# Covers C8, AC7
# The slot must completely fit before the window ends
def test_a16():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(10, 30))
    busy = [BusyInterval(time(9, 0), time(10, 0))]
    out = suggest_slots(day, working, busy, timedelta(minutes=60), n=10, buffer=timedelta(0), candidate_window=None)
    assert out == []

# Covers C4, AC4
# Reordering the busy intervals doesnt change the output
def test_a17():
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(13, 0))
    duration = timedelta(minutes=30)
    busy1 = [
        BusyInterval(time(10, 0), time(11, 0)),
        BusyInterval(time(12, 0), time(12, 30)),
        BusyInterval(time(9, 30), time(9, 45)),
    ]
    busy2 = [
        BusyInterval(time(12, 0), time(12, 30)),
        BusyInterval(time(9, 30), time(9, 45)),
        BusyInterval(time(10, 0), time(11, 0)),
    ]
    out1 = suggest_slots(day, working, busy1, duration, n=20, buffer=timedelta(0), candidate_window=None)
    out2 = suggest_slots(day, working, busy2, duration, n=20, buffer=timedelta(0), candidate_window=None)
    assert [s.start_time for s in out1] == [s.start_time for s in out2]