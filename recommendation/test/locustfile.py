from locust import HttpUser, between, task

# Tests for the recommendation endpoint
tests = [
    ("en", "fr", 3, "Apple"),
    ("fr", "en", 3, "Tour_Eiffel"),
    ("it", "en", 3, "Ravenna"),
    ("es", "en", 3, "Madrid"),
    ("de", "en", 3, "Kölner_Dom"),
    ("nl", "en", 3, "Delfts_blauw"),
    ("ja", "en", 3, "伏見稲荷大社"),
    ("zh", "en", 3, "大熊猫"),
    ("ru", "en", 3, "Московский_Кремль"),
    ("cs", "en", 3, "Martina_Navrátilová"),
    ("fi", "en", 3, "Muumilaakson_tarinoita"),
    ("lt", "en", 3, "Vilnius"),
    ("lv", "en", 3, "Kristaps_Porziņģis"),
    ("et", "en", 3, "Naisekandmine"),
    ("tr", "en", 3, "Lokum"),
    ("ro", "en", 3, "Țara_Românească"),
    ("kk", "en", 3, "Қазақ_тілі"),
]


class RecommendationAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def translation_recommendation_morelike(self):
        for test in tests:
            (source, target, count, seed) = test
            self.client.get(
                f"/api/v1/translation?source={source}&target={target}&count={count}&seed={seed}&algorithm=morelike"
            )

    @task
    def translation_recommendation_mostpopular(self):
        for test in tests:
            (source, target, count, seed) = test
            self.client.get(f"/api/v1/translation?source={source}&target={target}&count={count}&algorithm=mostpopular")

    @task
    def translation_recommendation_morelike_pageviews(self):
        for test in tests:
            (source, target, count, seed) = test
            self.client.get(
                f"/api/v1/translation?source={source}&target={target}&count={count}&seed={seed}&algorithm=morelike&include_pageviews=true"
            )
