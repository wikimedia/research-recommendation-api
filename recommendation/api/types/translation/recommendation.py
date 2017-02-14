class Recommendation:
    def __init__(self, title):
        self.title = title
        self.wikidata_id = None
        self.rank = None
        self.pageviews = None
        self.url = None
        self.sitelink_count = None

    def __dict__(self):
        return dict(title=self.title,
                    wikidata_id=self.wikidata_id,
                    rank=self.rank,
                    pageviews=self.pageviews,
                    url=self.url,
                    sitelink_count=self.sitelink_count)

    def incorporate_wikidata_item(self, item):
        self.wikidata_id = item.id
        self.url = item.url
        self.sitelink_count = item.sitelink_count
