import logging
from pkg_resources import resource_filename
import collections

import numpy as np
from sklearn.preprocessing import normalize

from recommendation.utils import configuration
from recommendation.api.external_data import wikidata
from recommendation.api.external_data import fetcher

log = logging.getLogger(__name__)

_embedding = None

Candidate = collections.namedtuple('Candidate', ['title', 'wikidata_id', 'url', 'score'])


def get_candidates(source, seed, count):
    """
    Candidate finder based on querying nearest neighbors
    from a semantic embedding of wikidata items
    """

    seed_title = resolve_seed(source, seed)
    seed_wikidata_item = wikidata.get_wikidata_items_from_titles(source, [seed_title])[0]
    nearest_neighbors = get_nearest_neighbors(seed_wikidata_item, count)

    ids_to_scores = {n[0]: n[1] for n in nearest_neighbors}

    # map resulting wikidata items back to articles
    results = wikidata.get_titles_from_wikidata_items(source, ids_to_scores.keys())

    return [Candidate(title=item.title,
                      wikidata_id=item.id,
                      url=item.url,
                      score=ids_to_scores[item.id]) for item in results][:count]


def resolve_seed(source, seed):
    seed_list = fetcher.wiki_search(source, seed, 1)
    if len(seed_list) == 0:
        log.info('Seed does not map to an article')
        return None
    return seed_list[0]


def get_nearest_neighbors(wikidata_item, count):
    nearest_neighbors = get_embedding().most_similar(wikidata_item.id, n=count)
    if len(nearest_neighbors) == 0:
        log.info('Seed Item is not in the embedding or no neighbors above t.')
    return nearest_neighbors


def get_embedding():
    global _embedding
    if _embedding is None:
        embedding_path = configuration.get_config_value('related_articles', 'embedding_path', fallback='')
        embedding_package = configuration.get_config_value('related_articles', 'embedding_package', fallback='')
        embedding_name = configuration.get_config_value('related_articles', 'embedding_name', fallback='')
        minimum_similarity = configuration.get_config_float('related_articles', 'minimum_similarity')
        _embedding = WikiEmbedding(embedding_path, embedding_package, embedding_name, minimum_similarity)
    return _embedding


class WikiEmbedding:
    def __init__(self, path, package, name, minimum_similarity):
        self.minimum_similarity = minimum_similarity

        self.w2idx = {}
        self.idx2w = []

        try:
            f = open(path, 'rb')
        except IOError:
            f = open(resource_filename(package, name), 'rb')

        with f:
            m, n = next(f).decode('utf8').strip().split(' ')
            self.E = np.zeros((int(m), int(n)))

            for i, l in enumerate(f):
                l = l.decode('utf8').strip().split(' ')
                w = l[0]
                self.E[i] = np.array(l[1:])
                self.w2idx[w] = i
                self.idx2w.append(w)

        self.E = normalize(self.E)
        self.idx2w = np.array(self.idx2w)

    def most_similar(self, word, n):
        """
        Find the top-N most similar words to w, based on cosine similarity.
        As a speed optimization, only consider neighbors with a similarity
        above min_similarity
        """
        if word not in self.w2idx:
            return []

        word_vector = self.E[self.w2idx[word]]
        scores = self.E.dot(word_vector)
        # only consider neighbors above threshold
        min_idxs = np.where(scores > self.minimum_similarity)
        ranking = np.argsort(-scores[min_idxs])[:n]
        nn_ws = self.idx2w[min_idxs][ranking]
        nn_scores = scores[min_idxs][ranking]
        return list(zip(nn_ws.tolist(), nn_scores.tolist()))
