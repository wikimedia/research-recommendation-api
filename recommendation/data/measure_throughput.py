import time

from recommendation.api.types.translation import translation
from recommendation.api.types.related_articles import related_articles, candidate_finder
from recommendation.api.external_data import fetcher


def measure_translation():
    seed_articles = fetcher.get_most_popular_articles('en')
    titles = [article['title'] for article in seed_articles]

    print('starting translation')

    start_time = time.time()

    for title in titles:
        print('.', end='', flush=True)
        translation.recommend('en', 'de', 'morelike', title, 24, include_pageviews=False)

    end_time = time.time()

    print()
    print('translation: Processed {} requests in {} seconds'.format(len(titles), end_time - start_time))


def measure_related_articles():
    candidate_finder.initialize_embedding()
    seed_articles = fetcher.get_most_popular_articles('en')
    titles = [article['title'] for article in seed_articles]

    print('starting related_articles')

    start_time = time.time()

    for title in titles:
        print('.', end='', flush=True)
        related_articles.recommend('en', title, 24)

    end_time = time.time()

    print()
    print('related_articles: Processed {} requests in {} seconds'.format(len(titles), end_time - start_time))


if __name__ == '__main__':
    measure_translation()
    measure_related_articles()
