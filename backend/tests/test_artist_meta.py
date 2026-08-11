from artist_meta import is_non_artist, trusted_tags


def test_low_listeners_and_no_tags_is_flagged():
    # "Lost Lands Music Festival": 169 listeners, no tags.
    assert is_non_artist({"listeners": 169, "tags": []}) is True


def test_low_listeners_with_tags_is_kept():
    # "RayRay": 2366 listeners but genuinely tagged.
    assert is_non_artist({"listeners": 2366, "tags": ["trap", "electronic"]}) is False


def test_high_listeners_with_no_tags_is_kept():
    assert is_non_artist({"listeners": 500000, "tags": []}) is False


def test_manual_override_wins():
    # "Brieanna Grace" is a real vocalist the heuristic would flag.
    entry = {"listeners": 295, "tags": [], "is_artist": True}
    assert is_non_artist(entry) is False


def test_manual_override_can_force_flag():
    entry = {"listeners": 900000, "tags": ["dubstep"], "is_artist": False}
    assert is_non_artist(entry) is True


def test_missing_listeners_is_flagged():
    assert is_non_artist({"tags": []}) is True


def test_tags_below_trust_threshold_are_discarded():
    # DubstepGutter is tagged "fried vegan eggs saladcore" at 4981 listeners.
    entry = {"listeners": 4981, "tags": ["fried vegan eggs saladcore", "dubstep"]}
    assert trusted_tags(entry) == []


def test_tags_above_trust_threshold_are_kept():
    entry = {"listeners": 530426, "tags": ["melodic dubstep", "electronic"]}
    assert trusted_tags(entry) == ["melodic dubstep", "electronic"]


def test_exactly_at_threshold_is_not_flagged():
    # The comparison is `<`, so 5000 itself is above the bar.
    assert is_non_artist({"listeners": 5000, "tags": []}) is False


def test_tags_exactly_at_trust_threshold_are_kept():
    entry = {"listeners": 5000, "tags": ["dubstep"]}
    assert trusted_tags(entry) == ["dubstep"]
