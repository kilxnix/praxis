from praxis.eval.scoring import structural_score, blank_scorecard, gate_report, RUBRIC_FIELDS

GOOD = {
    "nodes": [
        {"id": "n1", "type": "step", "label": "take order", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n2", "type": "actor", "label": "me", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n3", "type": "tool", "label": "notebook", "evidence": [{"quote": "in my notebook", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "n4", "type": "artifact", "label": "slip", "evidence": [{"quote": "a slip", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
    ],
    "edges": [
        {"id": "e1", "type": "performs", "source": "n2", "target": "n1", "evidence": [{"quote": "I take the order", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "e2", "type": "uses", "source": "n1", "target": "n3", "evidence": [{"quote": "in my notebook", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
        {"id": "e3", "type": "produces", "source": "n1", "target": "n4", "evidence": [{"quote": "a slip", "turn": 1}], "confidence": {"value": 0.5, "evidence_count": 1}},
    ],
}

def test_structural_score_on_good_model():
    s = structural_score(GOOD)
    assert s["connected"] and s["grounded"] and s["grain_ok"]
    assert s["coverage"] == 1.0

def test_blank_scorecard_has_human_fields():
    card = blank_scorecard("vague_baker")
    for f in RUBRIC_FIELDS:
        assert card["human"][f] is None

def test_gate_report_flags_auto_pass_majority():
    cards = [blank_scorecard("a"), blank_scorecard("b")]
    for c in cards:
        c["auto"] = structural_score(GOOD)
        c["auto"]["seconds"] = 30.0
    rep = gate_report(cards)
    assert rep["n"] == 2
    assert rep["auto_pass_rate"] == 1.0
    assert "AUTO-PASS" in rep["verdict_hint"]
