from collab_split import split_artist_name


def test_plain_name_is_returned_unchanged():
    assert split_artist_name("Seven Lions") == ["Seven Lions"]


def test_ampersand_splits():
    assert split_artist_name("Seven Lions & Brieanna Grace") == [
        "Seven Lions", "Brieanna Grace"
    ]


def test_comma_and_ampersand_splits():
    assert split_artist_name("ILLENIUM, Wooli, & Grabbitz") == [
        "ILLENIUM", "Wooli", "Grabbitz"
    ]


def test_feat_splits():
    assert split_artist_name("SLANDER feat. Julia Church") == [
        "SLANDER", "Julia Church"
    ]


def test_x_separator_splits():
    assert split_artist_name("ISOxo x Knock2") == ["ISOxo", "Knock2"]


def test_name_containing_x_is_not_split():
    # "ISOxo" has no surrounding spaces, so it must survive intact.
    assert split_artist_name("ISOxo") == ["ISOxo"]


def test_empty_components_are_dropped():
    assert split_artist_name("Dabin,  , Said The Sky") == ["Dabin", "Said The Sky"]
