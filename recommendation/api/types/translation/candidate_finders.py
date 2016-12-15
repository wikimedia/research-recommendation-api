import datetime
import logging
import random

from recommendation.api.external_data import fetcher
from recommendation.api.types.translation.utils import Article
from recommendation.utils import configuration

log = logging.getLogger(__name__)


class CandidateFinder:
    """
    CandidateFinder interface
    """

    def get_candidates(self, s, seed, n):
        """
        get list candidate source language articles
        using seed (optional)
        """
        return []


class PageviewCandidateFinder(CandidateFinder):
    """
    Utility Class for getting a list of the most
    popular articles in a source  Wikipedia.
    """

    def query_pageviews(self, s):
        """
        Query pageview API and parse results
        """
        days = configuration.get_config_int('popular_pageviews', 'days')
        date_format = configuration.get_config_value('popular_pageviews', 'date_format')
        query = configuration.get_config_value('popular_pageviews', 'query')
        date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime(date_format)
        query = query.format(source=s, date=date)
        try:
            data = fetcher.get(query)
        except ValueError:
            return []

        article_pv_tuples = []

        try:
            for d in data['items'][0]['articles']:
                article_pv_tuples.append((d['article'], d['views']))
        except:
            log.info('Could not get most popular articles for %s from pageview API. Try using a seed article.', s)

        return article_pv_tuples

    def get_candidates(self, s, seed, n):
        """
        Wrap top articles in a list of Article objects
        """
        articles = []
        article_pv_tuples = sorted(self.query_pageviews(s), key=lambda x: random.random())

        for i, t in enumerate(article_pv_tuples):
            a = Article(t[0])
            a.rank = i
            articles.append(a)

        return articles[:n]


class MorelikeCandidateFinder(CandidateFinder):
    """
    Utility class for getting articles that are similar to
    a given seed article in a source Wikipedia via "morelike"
    search
    """

    def get_morelike_candidates(self, s, query, n):
        """
        Perform a "morelike" search via the Mediawiki search API.
        First map the query to an article via standard search,
        and then get a list of related articles via morelike search
        """
        seed_list = fetcher.wiki_search(s, query, 1)

        if len(seed_list) == 0:
            log.info('Seed does not map to an article')
            return []

        seed = seed_list[0]
        if seed != query:
            log.info('Query: %s  Article: %s', query, seed)
        results = fetcher.wiki_search(s, seed, n, morelike=True)
        if results:
            results.insert(0, seed)
            log.info('Successful Morelike Search')
            return results
        else:
            log.info('Failed Morelike Search. Reverting to standard search')
            return fetcher.wiki_search(s, query, n)

    def get_candidates(self, s, seed, n):
        """
        Wrap morelike search results into a list of articles
        """
        results = self.get_morelike_candidates(s, seed, n)

        articles = []

        for i, title in enumerate(results):
            a = Article(title)
            a.rank = i
            articles.append(a)

        return articles[:n]


class RelatedArticleFinder(CandidateFinder):
    def get_candidates(self, s, seed, n):
        results = fetcher.get_related_articles(s, seed)
        if len(results) == 0:
            log.info('Failed related_articles search. Reverting to morelike. Source: %s Seed: %s', s, seed)
            return MorelikeCandidateFinder().get_candidates(s, seed, n)

        articles = []
        for item in results:
            a = Article(item['title'])
            a.wikidata_id = item['wikidata_id']
            a.rank = 1.0 - item['score']
            articles.append(a)

        return articles[:n]
