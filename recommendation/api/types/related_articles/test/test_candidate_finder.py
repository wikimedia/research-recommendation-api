from recommendation.api.types.related_articles import candidate_finder
from recommendation.utils import configuration
import recommendation


def test_embedding():
    expected = [('Q22686', 1.0), ('Q3752663', 0.88534683792878444), ('Q2462124', 0.86169155716868895),
                ('Q432473', 0.84815812545550617), ('Q242351', 0.83799047798220783), ('Q868772', 0.8087311692249578),
                ('Q21070387', 0.79568115529340577), ('Q239411', 0.78297328820934886), ('Q736223', 0.7760532537216831),
                ('Q3731533', 0.74743192152656435)]
    results = candidate_finder.get_embedding().most_similar('Q22686', len(expected))
    assert len(expected) == len(results)
    for expected, actual in zip(expected, results):
        assert expected[0] == actual[0]
        assert isclose(expected[1], actual[1])


def test_configuration():
    assert recommendation.__name__ == configuration.get_config_value('related_articles', 'embedding_package')


# math.isclose was added in 3.5
# https://www.python.org/dev/peps/pep-0485/#proposed-implementation
def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
