from recommendation.api.external_data import wikidata


def test_chunker(monkeypatch):
    params = {}
    parameter = "does not matter"
    values = [str(i) for i in range(50 * 10 + 1)]
    monkeypatch.setattr(wikidata, "query", lambda x: x[parameter].split("|"))
    items = wikidata.chunk_query_for_parameter(params, parameter, values)

    assert items == values
