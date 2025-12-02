from recommendation.api.translation.models import (
    PageCollectionMetadata,
    SectionTranslationRecommendation,
    TranslationRecommendation,
)
from recommendation.recommenders.multiple_collection_recommender import MultipleCollectionRecommender


def test_reorder_collection_section_recommendations():
    # Collections from the docstring example
    collection1 = PageCollectionMetadata(name="Collection One")
    collection2 = PageCollectionMetadata(name="Collection Two")
    collection3 = PageCollectionMetadata(name="Collection Three")

    # Recommendations from the docstring example
    rec1 = SectionTranslationRecommendation(
        source_title="Article 1",
        target_title="Target",
        collection=collection1,
        source_sections=[],
        target_sections=[],
        present={},
        missing={},
    )
    rec2 = SectionTranslationRecommendation(
        source_title="Article 2",
        target_title="Target",
        collection=collection1,
        source_sections=[],
        target_sections=[],
        present={},
        missing={},
    )
    rec3 = SectionTranslationRecommendation(
        source_title="Article 3",
        target_title="Target",
        collection=collection2,
        source_sections=[],
        target_sections=[],
        present={},
        missing={},
    )
    rec4 = SectionTranslationRecommendation(
        source_title="Article 4",
        target_title="Target",
        collection=collection2,
        source_sections=[],
        target_sections=[],
        present={},
        missing={},
    )
    rec5 = SectionTranslationRecommendation(
        source_title="Article 5",
        target_title="Target",
        collection=collection3,
        source_sections=[],
        target_sections=[],
        present={},
        missing={},
    )

    test_recommendations = [rec1, rec2, rec3, rec4, rec5]

    # Act
    reordered = MultipleCollectionRecommender.reorder_page_collection_recommendations(test_recommendations)

    # Assert: expected order from the docstring
    assert reordered == [rec1, rec3, rec5, rec2, rec4]


def test_reorder_collection_article_recommendations():
    # Arrange: 3 collections
    collection1 = PageCollectionMetadata(name="Collection One")
    collection2 = PageCollectionMetadata(name="Collection Two")
    collection3 = PageCollectionMetadata(name="Collection Three")

    # Translation recommendations belonging to those collections
    rec1 = TranslationRecommendation(
        title="Article 1",
        wikidata_id="Q1",
        langlinks_count=10,
        size=1234,
        collection=collection1,
    )
    rec2 = TranslationRecommendation(
        title="Article 2",
        wikidata_id="Q2",
        langlinks_count=5,
        size=2345,
        collection=collection1,
    )
    rec3 = TranslationRecommendation(
        title="Article 3",
        wikidata_id="Q3",
        langlinks_count=8,
        size=3456,
        collection=collection2,
    )
    rec4 = TranslationRecommendation(
        title="Article 4",
        wikidata_id="Q4",
        langlinks_count=12,
        size=4567,
        collection=collection2,
    )
    rec5 = TranslationRecommendation(
        title="Article 5",
        wikidata_id="Q5",
        langlinks_count=3,
        size=5678,
        collection=collection3,
    )

    recommendations = [rec1, rec2, rec3, rec4, rec5]

    reordered = MultipleCollectionRecommender.reorder_page_collection_recommendations(recommendations)

    # Assert: round‑robin order, preserving order within each collection
    assert reordered == [rec1, rec3, rec5, rec2, rec4]
