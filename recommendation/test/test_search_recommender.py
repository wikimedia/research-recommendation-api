from unittest.mock import patch

import pytest

from recommendation.api.translation.models import TranslationRecommendationRequest
from recommendation.recommenders.search_recommender import SearchRecommender


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "targetLanguage, lllangInput, langlinksOutput",
    [
        # lang and domain are the same
        ("fr", "fr", "fr"),
        # lang and domain are the same but langlinks as stored as be-x-old
        ("be-tarask", "be-x-old", "be-x-old"),
        # lang is nb, domain is no, langlinks are stored as no by MW maps it back to nb
        ("nb", "no", "nb"),
        # langlinks are stored with domain code
        ("bho", "bh", "bh"),
        # langlinks are stored with domain code
        ("lzh", "zh-classical", "zh-classical"),
    ],
)
async def test_recommend(targetLanguage, lllangInput, langlinksOutput):
    # Mock a valid API response
    with patch("recommendation.recommenders.search_recommender.get") as mock_get:
        mock_get.return_value = {
            "query": {
                "pages": [
                    # article absent in target language
                    {"title": "Page 1", "pageprops": {}, "langlinks": [], "index": 1},
                    # article present in target language
                    {"title": "Page 2", "pageprops": {}, "langlinks": [{"lang": langlinksOutput}], "index": 2},
                    # article absent in target language
                    {"title": "Page 3", "pageprops": {}, "langlinks": [], "index": 3},
                ]
            }
        }

        # Create a request model
        request_model = TranslationRecommendationRequest(
            source="en",
            target=targetLanguage,
            seed=None,
            topic="arts",
            country=None,
            count=10,
            rank_method="default",
            include_pageviews=False,
        )
        recommender = SearchRecommender(request_model)

        # Make sure the recommender accepts the request
        assert recommender.match() is True

        # Call the method
        response = await recommender.recommend()
        recommendations = response.recommendations
        # Assert mock 'get' function was called with the right lllang parameter
        assert mock_get.call_args[1]["params"]["lllang"] == lllangInput

        # Assert suggestions
        assert len(recommendations) == 2
        titles = [rec.title for rec in recommendations]
        assert "Page 1" in titles
        assert "Page 3" in titles
