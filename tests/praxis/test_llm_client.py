from praxis.llm_client import OllamaClient

def test_parse_json_strips_code_fences_and_prose():
    raw = 'Sure!\n```json\n{"nodes": [{"label": "invoicing"}]}\n```\nHope that helps.'
    assert OllamaClient.parse_json(raw) == {"nodes": [{"label": "invoicing"}]}

def test_parse_json_returns_empty_dict_on_garbage():
    assert OllamaClient.parse_json("no json here at all") == {}
