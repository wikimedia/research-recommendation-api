from recommendation.api.types.related_articles import candidate_finder
from recommendation.utils import configuration
import recommendation

EXPECTED = [('Q22686', 1.0), ('Q3752663', 0.8853468379287844), ('Q2462124', 0.861691557168689),
            ('Q432473', 0.8481581254555062), ('Q242351', 0.8379904779822078), ('Q868772', 0.8087311692249578),
            ('Q21070387', 0.7956811552934058), ('Q239411', 0.7829732882093489), ('Q736223', 0.7760532537216831),
            ('Q3731533', 0.7474319215265643), ('Q699872', 0.6474165168034756), ('Q2597050', 0.6352709659245916),
            ('Q12071552', 0.6273134513051442), ('Q6294', 0.6132842610738145), ('Q13628723', 0.5921917468920406),
            ('Q359442', 0.5868018793427279), ('Q29468', 0.5696888764253161), ('Q76', 0.5616138355609682),
            ('Q2036942', 0.5538574999463601), ('Q324546', 0.5466022935973467), ('Q17092708', 0.5438881700622109),
            ('Q69319', 0.5400609632856112), ('Q846330', 0.5337995502586717), ('Q44430', 0.5300078863669737),
            ('Q816459', 0.5156321533144876), ('Q4496', 0.515222705930191), ('Q29552', 0.5072461049596773)]


def test_embedding():
    candidate_finder.initialize_embedding(optimize=False)
    results = candidate_finder.get_embedding().most_similar('Q22686')
    for expected, actual in zip(EXPECTED, results):
        assert expected[0] == actual[0]
        assert isclose(expected[1], actual[1])


def test_configuration():
    assert recommendation.__name__ == configuration.get_config_value('related_articles', 'embedding_package')


# math.isclose was added in 3.5
# https://www.python.org/dev/peps/pep-0485/#proposed-implementation
def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
