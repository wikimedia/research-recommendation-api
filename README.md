> [!IMPORTANT]
> ### Deprecation Notice
> The GapFinder tool will be deprecated between July 1 and 15 2024. For detailed background information, please refer to the [Phabricator task T367549](https://phabricator.wikimedia.org/T367549).
> #### API Migration
> For tools utilizing the API, please migrate to the LiftWing endpoint. See the [documentation for the LiftWing API](https://www.mediawiki.org/w/index.php?api=lift-wing&title=Special%3ARestSandbox#/Countries%2C%20language%2C%20and%20translation/translation).
> #### UI Alternative
> For the user interface, please use the [Content Translation tool](https://www.mediawiki.org/wiki/Content_translation#Try_the_tool).

# Content Translation Recommendation API

Given a source and target wiki, the API provides source articles missing in the target.

## Sample Call

https://api.wikimedia.org/service/lw/recommendation/api/v1/translation?source=en&target=fr&count=3&seed=Apple

```json
{
  "recommendations": [
    {
      "title": "Nurse grafting",
      "pageviews": 0,
      "wikidata_id": "Q24897497",
      "rank": 449,
      "langlinks_count": 1,
      "size": 6238,
      "lead_section_size": null,
      "collection": null
    },
    {
      "title": "List of food origins",
      "pageviews": 0,
      "wikidata_id": "Q6620581",
      "rank": 361,
      "langlinks_count": 1,
      "size": 21210,
      "lead_section_size": null,
      "collection": null
    },
    {
      "title": "Apple genome",
      "pageviews": 0,
      "wikidata_id": "Q96372263",
      "rank": 474,
      "langlinks_count": 0,
      "size": 4448,
      "lead_section_size": null,
      "collection": null
    }
  ],
  "continue_offset": null,
  "continue_seed": null
}
```

## Running the API

Make sure you are using at least Python 3.10

Inside a virtualenv and in the root directory of the repo

```bash
pip install -e .
gunicorn
```

Then navigate here to see openapi spec: http://localhost:8080/docs

To check out the API, go to:
http://localhost:8080/api/v1/translation?source=en&target=fr&count=3&seed=Apple

You should get a similar response to the **Sample Call** above

## Running using Docker

Build the image first.

```bash
 docker build --target production --tag recommendation-api:latest -f .pipeline/blubber.yaml .
```

Then run:

```bash
docker run recommendation-api:latest
```

## Testing using Docker

Build the image first.

```bash
 docker build --target test --tag recommendation-api-test:latest -f .pipeline/blubber.yaml .
```

Then run:

```bash
docker run recommendation-api-test:latest
```

## Load Testing using Locust

To run load testing using Locust, run

```bash
locust -f recommendation/test/locustfile.py
```

Then navigate to <http://localhost:8089/> to run the tests. Provide number of users and API host to test.

## Environment Variables

All configuration variables defined on configuration.py can be overridden by setting the corresponding environment variable.

You may use a .env file or by setting the environment variables directly in shell.

Refer <https://docs.pydantic.dev/latest/concepts/pydantic_settings/> for more options
