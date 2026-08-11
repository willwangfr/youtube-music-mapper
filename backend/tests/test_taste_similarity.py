import pytest

from taste_similarity import rarity_weighted_overlap, calculate_similarity

META = {
    "Coldplay": {"listeners": 9_251_718, "tags": ["pop"]},
    "Obscure Act": {"listeners": 3_000, "tags": ["dubstep"]},
}


def test_sharing_an_obscure_artist_scores_higher_than_a_famous_one():
    # Both people own both artists' worth of listening; they differ only in
    # WHICH one they have in common. Identical libraries would both score 1.0
    # regardless of weight, so the rarity effect is only visible on a partial
    # overlap.
    me = {"Coldplay": 1, "Obscure Act": 1}
    shares_the_famous_one = rarity_weighted_overlap(me, {"Coldplay": 1}, META)
    shares_the_obscure_one = rarity_weighted_overlap(me, {"Obscure Act": 1}, META)
    assert shares_the_obscure_one > shares_the_famous_one


def test_identical_libraries_score_one_whatever_the_rarity():
    # Weight cancels when min == max, so rarity cannot move this.
    for artist in ("Coldplay", "Obscure Act"):
        assert rarity_weighted_overlap({artist: 1}, {artist: 1}, META) == 1.0


def test_identical_libraries_score_one():
    assert rarity_weighted_overlap(
        {"Coldplay": 2, "Obscure Act": 1}, {"Coldplay": 2, "Obscure Act": 1}, META
    ) == pytest.approx(1.0)


def test_disjoint_libraries_score_zero():
    assert rarity_weighted_overlap({"Coldplay": 1}, {"Obscure Act": 1}, META) == 0.0


def test_empty_libraries_score_one():
    assert rarity_weighted_overlap({}, {}, META) == 1.0


def test_unknown_artists_still_contribute():
    # No metadata must not silently drop an artist from the comparison.
    assert rarity_weighted_overlap({"Ghost": 1}, {"Ghost": 1}, {}) == pytest.approx(1.0)


def test_non_artists_get_neutral_weight_not_a_rarity_bonus():
    # Same listener count (169) as each other, so any score difference below
    # comes only from is_non_artist, not from artist_obscurity.
    meta = {
        "Real Obscure Artist": {"listeners": 169, "tags": ["dubstep"]},
        "Lost Lands Music Festival": {"listeners": 169, "tags": []},
    }
    me = {"Real Obscure Artist": 1, "Lost Lands Music Festival": 1}
    shares_the_real_artist = rarity_weighted_overlap(me, {"Real Obscure Artist": 1}, meta)
    shares_the_channel = rarity_weighted_overlap(me, {"Lost Lands Music Festival": 1}, meta)
    # A repost channel must not get the same rarity bonus a genuinely obscure
    # artist gets just because its "listener" count is also low.
    assert shares_the_real_artist > shares_the_channel


def test_calculate_similarity_without_meta_matches_previous_behaviour():
    p1 = {"liked_songs": [{"title": "a", "artists": [{"name": "Coldplay"}]}]}
    p2 = {"liked_songs": [{"title": "b", "artists": [{"name": "Coldplay"}]}]}
    assert calculate_similarity(p1, p2)["overall"] == pytest.approx(100.0)


def test_calculate_similarity_accepts_artist_meta():
    p1 = {"liked_songs": [{"title": "a", "artists": [{"name": "Obscure Act"}]}]}
    p2 = {"liked_songs": [{"title": "b", "artists": [{"name": "Obscure Act"}]}]}
    result = calculate_similarity(p1, p2, artist_meta=META)
    assert 0.0 <= result["overall"] <= 100.0
