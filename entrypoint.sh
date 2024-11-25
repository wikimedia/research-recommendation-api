#!/bin/bash

poetry install
poetry run update-cache
poetry run gunicorn