import time

from recommendation.api.types.translation import translation
from recommendation.api.types.related_articles import related_articles, candidate_finder
from recommendation.api.external_data import fetcher


def measure_translation():
    seed_articles = fetcher.get_most_popular_articles("en")
    titles = [article["title"] for article in seed_articles]

    print("starting translation")

    start_time = time.time()

    for title in titles:
        print(".", end="", flush=True)
        translation.recommend(
            "en", "de", "morelike", title, 24, include_pageviews=False
        )

    end_time = time.time()

    print()
    print(
        f"translation: Processed {len(titles)} requests in {end_time - start_time} seconds"
    )


def measure_related_articles():
    candidate_finder.initialize_embedding()
    seed_articles = fetcher.get_most_popular_articles("en")
    titles = [article["title"] for article in seed_articles]

    print("starting related_articles")

    start_time = time.time()

    for title in titles:
        print(".", end="", flush=True)
        related_articles.recommend("en", title, 24)

    end_time = time.time()

    print()
    print(
        f"related_articles: Processed {len(titles)} requests in {end_time - start_time} seconds"
    )


if __name__ == "__main__":
    measure_translation()
    measure_related_articles()
