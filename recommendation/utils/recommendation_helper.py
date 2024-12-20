import random

from recommendation.api.translation.models import (
    RankMethodEnum,
)


def sort_recommendations(recommendations, rank_method):
    if rank_method == RankMethodEnum.sitelinks:
        # Sort by langlinks count, from highest to lowest
        return sorted(recommendations, key=lambda x: x.langlinks_count, reverse=True)
    else:
        # shuffle recommendations
        return sorted(recommendations, key=lambda x: random.random())
