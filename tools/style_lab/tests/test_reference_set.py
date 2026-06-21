from tools.style_lab.reference_set import (
    CORE_SAMPLE_IDS,
    EXTENDED_SAMPLE_IDS,
    build_reference_samples,
)


def test_core_and_extended_counts_match_approved_contract():
    assert len(CORE_SAMPLE_IDS) == 19
    assert len(EXTENDED_SAMPLE_IDS) == 26


def test_sample_ids_are_gt_three_digit_format():
    all_ids = CORE_SAMPLE_IDS + EXTENDED_SAMPLE_IDS

    assert all(sample_id.startswith("GT_") for sample_id in all_ids)
    assert all(len(sample_id) == 6 for sample_id in all_ids)
    assert all(sample_id[3:].isdigit() for sample_id in all_ids)


def test_core_and_extended_sets_do_not_overlap():
    assert set(CORE_SAMPLE_IDS).isdisjoint(set(EXTENDED_SAMPLE_IDS))


def test_build_reference_samples_assigns_tiers_roles_and_filenames():
    samples = build_reference_samples()

    assert len(samples) == 45
    assert samples[0].sample_id == "GT_024"
    assert samples[0].tier == "core"
    assert samples[0].filename == "GT_024.png"
    assert samples[0].role
    assert samples[-1].tier == "extended"
    assert samples[-1].filename == f"{samples[-1].sample_id}.png"
