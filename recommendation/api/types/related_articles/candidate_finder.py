import logging
from pkg_resources import resource_filename
import collections
import time
import io
import itertools
import os

import numpy as np
import swiftclient
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
        try:
            start_of_chunk = next(nearest_neighbors_iter)
        except StopIteration:
            break
        chunk = itertools.chain((start_of_chunk,), itertools.islice(nearest_neighbors_iter, 499))
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
    embedding_client = configuration.get_config_value('related_articles', 'embedding_client', fallback='local_file_system')
    embedding_path = configuration.get_config_value('related_articles', 'embedding_path', fallback='')
    embedding_package = configuration.get_config_value('related_articles', 'embedding_package', fallback='')
    embedding_name = configuration.get_config_value('related_articles', 'embedding_name', fallback='')
    optimized_embedding_path = configuration.get_config_value('related_articles', 'optimized_embedding_path')
    minimum_similarity = configuration.get_config_float('related_articles', 'minimum_similarity')
    _embedding = WikiEmbedding(minimum_similarity)
    _embedding.initialize(embedding_client, embedding_path, embedding_package, embedding_name, optimize, optimized_embedding_path)


def get_embedding():
    global _embedding
    if _embedding is None:
        initialize_embedding()
    return _embedding


class WikiEmbedding:
    """
    This class fetches a raw embedding then optimizes
    and saves it within the given path.
    """

    def __init__(self, minimum_similarity):
        self.minimum_similarity = minimum_similarity
        self.idx2w = []
        self.wikidata_ids = []
        self.embedding = []

    def initialize(self, client, path, package, name, optimize, optimized_path):
        log.info('starting to load embedding')
        t1 = time.time()

        if optimize:
            if not self.load_optimized_embedding(optimized_path):
                self.load_embedding(client, path, package, name)
                self.save_optimized_embedding(optimized_path)
        else:
            self.load_embedding(client, path, package, name)

        t2 = time.time()
        log.info('embedding loaded in %f seconds', t2 - t1)

    def load_preprocessed_embedding(self):
        """
        For the instance hosted on LiftWing/k8s, the app fetches and uses
        float32 preprocessed numpy arrays from Swift for optimal memory usage
        (see T339890#9162780).

        Because of T342084 and T288198#9037109 we opted not to store
        the heavy preprocessed files within the docker image.
        """

        # Get swift environment variables set by helm
        swift_authurl = os.environ.get('SWIFT_AUTHURL')
        swift_user = os.environ.get('SWIFT_USER')
        swift_key = os.environ.get('SWIFT_SECRET_KEY')
        swift_container = os.environ.get('SWIFT_CONTAINER')
        swift_wikidata_ids_path = os.environ.get('SWIFT_WIKIDATA_IDS_PATH')
        swift_decoded_lines_float32_path = os.environ.get('SWIFT_DECODED_LINES_FLOAT32_PATH')

        if None in (swift_authurl, swift_user, swift_key, swift_container,
                    swift_wikidata_ids_path, swift_decoded_lines_float32_path):
            required_swift_env_vars = ['SWIFT_AUTHURL', 'SWIFT_USER', 'SWIFT_SECRET_KEY',
                                      'SWIFT_CONTAINER', 'SWIFT_WIKIDATA_IDS_PATH',
                                      'SWIFT_DECODED_LINES_FLOAT32_PATH']
            error_msg = 'One or more Swift environment variables is missing,\
            \nplease check whether all variables below are set in helm:\
            \n' + ', '.join(required_swift_env_vars)
            raise RuntimeError(error_msg)

        try:
            # Create a connection to Swift
            conn = swiftclient.Connection(authurl=swift_authurl,
                                          user=swift_user, key=swift_key)
            # Get the wikidata_ids swift object
            wikidata_ids_swift_object = conn.get_object(swift_container,
                                                        swift_wikidata_ids_path)
            # Get the decoded_lines_float32 swift object
            decoded_lines_float32_swift_object = conn.get_object(swift_container,
                                                                 swift_decoded_lines_float32_path)
        except swiftclient.exceptions.ClientException as e:
            log.exception('Failed to get objects from Swift')
            raise RuntimeError(f'Failed to get objects from Swift: {e}')

        log.info('initialize wikidata_ids array')
        wikidata_ids_numpy_binary = wikidata_ids_swift_object[1]
        wikidata_ids_numpy_array = np.load(wikidata_ids_numpy_binary)
        self.wikidata_ids = wikidata_ids_numpy_array
        log.info('wikidata_ids array initialized')

        log.info('initialize decoded_lines array')
        decoded_lines_float32_numpy_binary = decoded_lines_float32_swift_object[1]
        decoded_lines_float32_numpy_array = np.load(decoded_lines_float32_numpy_binary)
        embedding = decoded_lines_float32_numpy_array
        log.info('decoded_lines array initialized')

        return embedding

    def process_raw_embedding(self, path, package, name):
        """
        For the instance hosted on wmflabs, the app fetches the embedding
        from the local application directory and processes it in-memory.
        """

        try:
            f = open(path, 'r', encoding='utf-8')
        except FileNotFoundError:
            try:
                f = open(resource_filename(package, name), 'r', encoding='utf-8')
            except FileNotFoundError as e:
                log.exception('Embedding file not found')
                raise FileNotFoundError(f'Embedding file not found: {path}, {resource_filename(package, name)}') from e

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
        embedding = np.array(decoded_lines)
        del decoded_lines
        log.info('array initialized')

        return embedding

    def load_embedding(self, client, path, package, name):
        if client != 'swift':
            # process embedding fetched from local application directory used on wmflabs
            self.embedding = self.process_raw_embedding(path, package, name)
        else:
            # load preprocessed embedding files from Swift used on LiftWing/k8s
            self.embedding = self.load_preprocessed_embedding()

        log.info('normalizing embedding')
        self.embedding = normalize(self.embedding)
        log.info('embedding normalized')

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
