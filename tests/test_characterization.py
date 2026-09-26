from collections import Counter

from adaptive_lad.drift.characterization import jensen_shannon_divergence


def test_js_divergence_identity_and_symmetry() -> None:
    left = Counter({"A": 8, "B": 2})
    right = Counter({"A": 2, "B": 8})
    assert jensen_shannon_divergence(left, left) == 0.0
    assert jensen_shannon_divergence(left, right) == jensen_shannon_divergence(right, left)
    assert 0 < jensen_shannon_divergence(left, right) <= 1


def test_js_divergence_disjoint_is_one() -> None:
    assert jensen_shannon_divergence(Counter({"A": 1}), Counter({"B": 1})) == 1.0
