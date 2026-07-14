from pathlib import Path

from forgeos.materials import load_all_packs, load_material_pack, default_materials_dir


def test_load_both_protopasta_packs():
    packs = load_all_packs(default_materials_dir())
    assert "protopasta_htpla" in packs
    assert "protopasta_htpla_cf" in packs
    ht = packs["protopasta_htpla"]
    cf = packs["protopasta_htpla_cf"]
    assert ht.abrasive is False
    assert cf.abrasive is True
    assert cf.nozzle_min_diameter_mm >= 0.5
    assert ht.max_volumetric_flow_mm3_s > cf.max_volumetric_flow_mm3_s
    assert ht.anneal.xy_scale > 1.0
    assert cf.recipe_for_part_class("drill_guide") == "max_accuracy"


def test_role_speeds_present():
    pack = load_material_pack(default_materials_dir() / "protopasta_htpla.yaml")
    for role in ("outer_wall", "infill", "travel", "first_layer"):
        assert role in pack.role_speeds_mm_s
        assert pack.role_speeds_mm_s[role] > 0
