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


from artist_meta import resolve_genre


def test_curated_map_wins():
    entry = {"listeners": 900000, "tags": ["pop"]}
    assert resolve_genre("Seven Lions", entry, {"Seven Lions": "Melodic Bass"}) == "Melodic Bass"


def test_trusted_tags_are_used_when_curated_is_silent():
    entry = {"listeners": 900000, "tags": ["dubstep", "electronic"]}
    assert resolve_genre("Someone", entry, {}) == "Dubstep/Bass"


def test_untrusted_tags_fall_through_to_other():
    # 4981 listeners is below the trust threshold.
    entry = {"listeners": 4981, "tags": ["dubstep"]}
    assert resolve_genre("DubstepGutter", entry, {}) == "Other"


def test_unmappable_tags_fall_through_to_other():
    entry = {"listeners": 900000, "tags": ["seen live", "favourites"]}
    assert resolve_genre("Someone", entry, {}) == "Other"


def test_first_mappable_tag_wins():
    entry = {"listeners": 900000, "tags": ["seen live", "k-pop", "pop"]}
    assert resolve_genre("Someone", entry, {}) == "K-Pop"


def test_curated_alias_maps_into_the_vocabulary():
    from taste_profile import GENRE_VOCABULARY
    resolved = resolve_genre("X", {"listeners": 9, "tags": []}, {"X": "Rock/Metal"})
    assert resolved == "Rock"
    assert resolved in GENRE_VOCABULARY


def test_unknown_curated_label_falls_through_to_other():
    assert resolve_genre("X", {"listeners": 9, "tags": []}, {"X": "Zzz Not A Genre"}) == "Other"


def test_unknown_curated_label_still_lets_tags_win():
    entry = {"listeners": 900000, "tags": ["dubstep"]}
    assert resolve_genre("X", entry, {"X": "Zzz Not A Genre"}) == "Dubstep/Bass"


def test_every_curated_alias_target_is_in_the_vocabulary():
    from artist_meta import CURATED_ALIASES
    from taste_profile import GENRE_VOCABULARY
    assert set(CURATED_ALIASES.values()) <= set(GENRE_VOCABULARY)


def test_every_tag_mapping_target_is_in_the_vocabulary():
    # resolve_genre returns TAG_TO_GENRE values unvalidated, unlike the
    # CURATED_ALIASES path above — this is the same shape of bug that guard
    # was written for, just on the other lookup table.
    from artist_meta import TAG_TO_GENRE
    from taste_profile import GENRE_VOCABULARY
    assert set(TAG_TO_GENRE.values()) <= set(GENRE_VOCABULARY)
