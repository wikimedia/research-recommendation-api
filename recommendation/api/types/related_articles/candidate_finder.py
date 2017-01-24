import logging
from pkg_resources import resource_filename
import collections
import time
import itertools

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
    seed_wikidata_items = wikidata.get_wikidata_items_from_titles(source, [seed_title])
    if not seed_wikidata_items:
        return []
    seed_wikidata_item = seed_wikidata_items[0]
    nearest_neighbors = get_nearest_neighbors(seed_wikidata_item)
    if len(nearest_neighbors) == 0:
        return []

    ids_to_scores = {n[0]: n[1] for n in nearest_neighbors}

    # map resulting wikidata items back to articles
    candidates = []
    nearest_neighbors_iter = iter(nearest_neighbors)
    while len(candidates) < count and nearest_neighbors_iter:
        chunk = itertools.islice(nearest_neighbors_iter, 500)
        results = wikidata.get_titles_from_wikidata_items(source, (n[0] for n in chunk))
        candidates += [Candidate(title=item.title,
                                 wikidata_id=item.id,
                                 url=item.url,
                                 score=ids_to_scores[item.id]) for item in results]

    candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

    return candidates[:count]


def resolve_seed(source, seed):
    seed_list = fetcher.wiki_search(source, seed, 1)
    if len(seed_list) == 0:
        log.info('Seed does not map to an article')
        return None
    return seed_list[0]


def get_nearest_neighbors(wikidata_item):
    nearest_neighbors = get_embedding().most_similar(wikidata_item.id)
    return nearest_neighbors


def initialize_embedding(optimize=True):
    global _embedding
    embedding_path = configuration.get_config_value('related_articles', 'embedding_path', fallback='')
    embedding_package = configuration.get_config_value('related_articles', 'embedding_package', fallback='')
    embedding_name = configuration.get_config_value('related_articles', 'embedding_name', fallback='')
    optimized_embedding_path = configuration.get_config_value('related_articles', 'optimized_embedding_path')
    minimum_similarity = configuration.get_config_float('related_articles', 'minimum_similarity')
    _embedding = WikiEmbedding(minimum_similarity)
    _embedding.initialize(embedding_path, embedding_package, embedding_name, optimize, optimized_embedding_path)


def get_embedding():
    global _embedding
    if _embedding is None:
        initialize_embedding()
    return _embedding


class WikiEmbedding:
    def __init__(self, minimum_similarity):
        self.minimum_similarity = minimum_similarity
        self.idx2w = []
        self.wikidata_ids = []
        self.embedding = []

    def initialize(self, path, package, name, optimize, optimized_path):
        log.info('starting to load embedding')
        t1 = time.time()

        if optimize:
            if not self.load_optimized_embedding(optimized_path):
                self.load_raw_embedding(path, package, name)
                self.save_optimized_embedding(optimized_path)
        else:
            self.load_raw_embedding(path, package, name)

        t2 = time.time()
        log.info('embedding loaded in %f seconds', t2 - t1)

    def load_raw_embedding(self, path, package, name):
        try:
            f = open(path, 'r', encoding='utf-8')
        except IOError:
            f = open(resource_filename(package, name), 'r', encoding='utf-8')

        line = f.readline()
        rows, columns = map(int, line.strip().split(' '))

        log.info('decoding file')
        decoded_lines = []
        i = 0
        for line in f:
            if i % int(rows / 20.0) == 0:
                log.info('{:.0%} decoded'.format(i / rows))
            i += 1
            wikidata_id, _, values = line.partition(' ')
            self.wikidata_ids.append(wikidata_id)
            decoded_lines.append(np.fromstring(values, dtype=float, sep=' ', count=columns))
        log.info('file decoded')

        log.info('building array')
        self.wikidata_ids = np.array(self.wikidata_ids)
        self.embedding = np.array(decoded_lines)
        del decoded_lines
        log.info('array initialized')

        log.info('normalizing')
        self.embedding = normalize(self.embedding)
        log.info('normalized')

    def load_optimized_embedding(self, path):
        try:
            infile = open(path, 'rb')
        except IOError:
            return False

        embedding = np.load(infile)
        self.embedding = embedding['embedding']
        self.wikidata_ids = embedding['wikidata_ids']
        return True

    def save_optimized_embedding(self, path):
        log.info('saving optimized embedding')
        outfile = open(path, 'wb')
        np.savez(outfile, embedding=self.embedding, wikidata_ids=self.wikidata_ids)
        log.info('optimized embedding saved at %s', path)

    def most_similar(self, word):
        """
        Find the most similar words to w, based on cosine similarity.
        As a speed optimization, only consider neighbors with a similarity
        above min_similarity
        """
        word_index_array = np.where(self.wikidata_ids == word)[0]
        if not word_index_array:
            return []
        word_index = word_index_array[0]

        word_vector = self.embedding[word_index]
        scores = self.embedding.dot(word_vector)
        # only consider neighbors above threshold
        min_idxs = np.where(scores > self.minimum_similarity)
        ranking = np.argsort(-scores[min_idxs])
        nn_ws = self.wikidata_ids[min_idxs][ranking]
        nn_scores = scores[min_idxs][ranking]
        return list(zip(nn_ws.tolist(), nn_scores.tolist()))
