> [!IMPORTANT]
> ### Deprecation Notice
> The GapFinder tool will be deprecated between July 1 and 15 2024. For detailed background information, please refer to the [Phabricator task T367549](https://phabricator.wikimedia.org/T367549).
> #### API Migration
> For tools utilizing the API, please migrate to the LiftWing endpoint. Documentation for the LiftWing API can be found [here](https://api.wikimedia.org/wiki/Lift_Wing_API/Reference/Get_content_translation_recommendation).
> An example of such a migration can be seen in this [diff on the Spanish Wikipedia](https://es.wikipedia.org/w/index.php?title=MediaWiki:Gadget-WikiProject.js&diff=prev&oldid=160820835).
> #### UI Alternative
> For the user interface, please use the [Content Translation tool](https://www.mediawiki.org/wiki/Content_translation#Try_the_tool).


# Content Translation Recommendation API

Given a source and target wiki, the API provides source articles missing in the target.

## API Parameters
* **URL**
  * https://api.wikimedia.org/service/lw/recommendation/v1/api
* **URL Params**
  * **Required:**
    * `source or s=[string]` source wiki project language code (e.g. `en`)
    * `target or t=[string]` target wiki project language code (e.g. `fr`)
  * **Optional:**
    * `n=[int]` number of recommendations to fetch (default `12`)
    * `article=[string]` seed article for personalized recommendations. Can be a list of
      seeds separated by `|`
    * `pageviews=[true|false]` whether to include pageview counts in the response (default `true`)
    * `search=[wiki|morelike]` which search algorithm to use (default `morelike`)

## Sample Call:

https://api.wikimedia.org/service/lw/recommendation/v1/api?s=en&t=fr&n=3&article=Apple

```
[
  {
    "pageviews": 58,
    "title": "Pomological_Watercolor_Collection",
    "wikidata_id": "Q23134015",
    "rank": 497
  },
  {
    "pageviews": 50,
    "title": "Nurse_grafting",
    "wikidata_id": "Q24897497",
    "rank": 495
  },
  {
    "pageviews": 74,
    "title": "Cadra_calidella",
    "wikidata_id": "Q5016600",
    "rank": 493
  }
]
```

## Running the API
Make sure you are using at least Python 3.4.

There is a `wsgi` file provided at `recommendation/data/recommendation.wsgi`. This can be run
using a tool like `uwsgi` as follows:
```
# Inside a virtualenv and in the root directory of the repo
pip install -e .
pip install uwsgi
uwsgi --http :5000 --wsgi-file recommendation/data/recommendation.wsgi --venv my-venv
```
If you get an error with Werkzeug, try `pip install Werkzeug==0.16.0`
until https://github.com/noirbizarre/flask-restplus/issues/777 is resolved.

Then navigate here to see the UI:
```
http://localhost:5000/
```

To check out the API, go to:
```
http://localhost:5000/api?s=en&t=fr&n=3&article=Apple
```

You should get a similar response to the **Sample Call** above
