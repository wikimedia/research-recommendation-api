#!/usr/bin/env bash

ETC_PATH='/etc/recommendation'
SRV_PATH='/srv/recommendation'
TMP_PATH='/tmp/recommendation'

rm -rf ${TMP_PATH}
mkdir -p ${TMP_PATH}

git clone https://gerrit.wikimedia.org/r/research/recommendation-api ${TMP_PATH}/recommendation-api

pip install --no-deps ${TMP_PATH}/recommendation-api

#cp ${TMP_PATH}/recommendation-api/recommendation/data/* ${ETC_PATH}

systemctl restart recommendation.service
