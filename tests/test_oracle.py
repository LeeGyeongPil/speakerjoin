"""AC-5: the fast sweep equals a brute-force oracle, and it is fast."""

import random
import time

import speakerjoin as sj
from speakerjoin.model import Segment, Transcript, Turn, Word


def oracle(turns, a, b):
    """Per-speaker overlap sum over ALL turns (sorted order); the first maximum wins."""
    sums = {}
    for t in sorted(turns, key=lambda t: (t.start, t.end, t.speaker)):
        ov = min(t.end, b) - max(t.start, a)
        if ov > 0:
            sums[t.speaker] = sums.get(t.speaker, 0.0) + ov
    best, best_value = None, 0.0
    for speaker, value in sums.items():
        if value > best_value:
            best, best_value = speaker, value
    return best


def random_case(rng):
    turns = []
    for _ in range(rng.randint(0, 7)):
        start = round(rng.uniform(0, 10), 2)
        turns.append(Turn(start, round(start + rng.uniform(0.05, 4), 2), rng.choice("ABC")))
    words = []
    for i in range(rng.randint(1, 12)):
        start = round(rng.uniform(0, 12), 2)
        words.append(Word(f"w{i}", start, round(start + rng.uniform(0.05, 1.5), 2)))
    return turns, words


def test_overlap_assignment_matches_brute_force_on_500_random_inputs():
    rng = random.Random(20261114)
    for case in range(500):
        turns, words = random_case(rng)
        seg = Segment(0.0, 14.0, "x", tuple(words))
        res = sj.merge(Transcript((seg,), "x"), sj.Diarization(tuple(turns), "x"))
        expected = [oracle(turns, w.start, w.end) for w in words]
        assert [w.speaker for w in res.words] == expected, f"case {case}"


def test_midpoint_with_a_single_speaker_matches_containment():
    rng = random.Random(7)
    for _ in range(200):
        turns, words = random_case(rng)
        seg = Segment(0.0, 14.0, "x", tuple(words))
        res = sj.merge(
            Transcript((seg,), "x"), sj.Diarization(tuple(turns), "x"), strategy="midpoint"
        )
        for w, got in zip(words, res.words, strict=True):
            mid = (w.start + w.end) / 2
            inside = {t.speaker for t in turns if t.start <= mid < t.end}
            if len(inside) == 1:
                assert got.speaker == next(iter(inside))
            elif not inside:
                assert got.speaker is None


def test_twenty_thousand_words_and_two_thousand_turns_merge_in_two_seconds():
    rng = random.Random(1)
    segments = []
    for s in range(1000):
        base = s * 2.0
        words = tuple(Word(f"w{s}_{i}", base + i * 0.1, base + i * 0.1 + 0.08) for i in range(20))
        segments.append(Segment(base, base + 2.0, "x", words))
    turns = tuple(
        Turn(t * 1.0 + rng.uniform(0, 0.3), t * 1.0 + 1.2, rng.choice(["A", "B", "C"]))
        for t in range(2000)
    )
    transcript = Transcript(tuple(segments), "x")
    diarization = sj.Diarization(turns, "x")
    started = time.perf_counter()
    res = sj.merge(transcript, diarization)
    elapsed = time.perf_counter() - started
    assert res.report.words_total == 20000
    assert elapsed < 2.0, f"merge took {elapsed:.2f}s"
