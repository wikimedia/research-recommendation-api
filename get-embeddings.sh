#!/bin/bash
set -eu -o pipefail
wget --quiet https://analytics.wikimedia.org/published/wmf-ml-models/recommendation-api/mini_embedding_compressed.zip
unzip mini_embedding_compressed.zip
mkdir ./recommendation/embeddings
mv 2016-08-01_2016-08-31_wikidata_100 recommendation/embeddings/mini_embedding