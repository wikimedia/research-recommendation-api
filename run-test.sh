#!/bin/bash
git init
git add .
tox -c "tox.ini"
