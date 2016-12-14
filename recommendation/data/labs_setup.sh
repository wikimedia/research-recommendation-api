#!/usr/bin/env bash

ETC_PATH='/etc/recommendation'
SRV_PATH='/srv/recommendation'
TMP_PATH='/tmp/recommendation'

apt-get update
apt-get install -y git nginx npm python3 python3-pip libpython3.4
pip3 install --upgrade pip

rm -rf ${TMP_PATH}
mkdir -p ${TMP_PATH}
mkdir -p ${SRV_PATH}/resources
mkdir -p ${SRV_PATH}/sock
mkdir -p ${ETC_PATH}

git clone https://gerrit.wikimedia.org/r/research/recommendation-api/wheels ${TMP_PATH}/wheels
git clone https://gerrit.wikimedia.org/r/research/recommendation-api ${TMP_PATH}/recommendation-api

pip install --use-wheel --no-deps ${TMP_PATH}/wheels/wheels/*.whl
pip install --no-deps ${TMP_PATH}/recommendation-api

ln -s /usr/bin/nodejs /usr/bin/node
cd ${TMP_PATH}
npm install bower
cd ${SRV_PATH}/resources
${TMP_PATH}/node_modules/bower/bin/bower install --allow-root ${TMP_PATH}/recommendation-api/recommendation/web/static/bower.json

chown -R www-data:www-data ${SRV_PATH}

cp ${TMP_PATH}/recommendation-api/recommendation/data/* ${ETC_PATH}
cp ${ETC_PATH}/recommendation.nginx /etc/nginx/sites-available/recommendation
ln -s /etc/nginx/sites-available/recommendation /etc/nginx/sites-enabled/
cp ${ETC_PATH}/recommendation.service /etc/systemd/system/multi-user.target.wants/
systemctl enable recommendation.service
systemctl daemon-reload

systemctl restart recommendation.service
systemctl restart nginx
