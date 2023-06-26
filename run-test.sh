#!/bin/bash
set -eu -o pipefail
python3 --version
pytest -W ignore::DeprecationWarning -W ignore::pytest.PytestCacheWarning