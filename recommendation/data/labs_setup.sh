#!/usr/bin/env bash

ETC_PATH='/etc/recommendation'
SRV_PATH='/srv/recommendation'
TMP_PATH='/tmp/recommendation'
LIB_PATH='/var/lib/recommendation'
LOG_PATH='/var/log/uwsgi'

apt-get update
apt-get install -y git nginx npm python3 python3-pip libpython3.7 python3-setuptools

rm -rf ${TMP_PATH}
mkdir -p ${TMP_PATH}
mkdir -p ${SRV_PATH}/resources
mkdir -p ${SRV_PATH}/sock
mkdir -p ${ETC_PATH}
mkdir -p ${LIB_PATH}
mkdir -p ${LOG_PATH}

git clone https://gerrit.wikimedia.org/r/research/recommendation-api/wheels ${TMP_PATH}/wheels
git clone https://gerrit.wikimedia.org/r/research/recommendation-api ${TMP_PATH}/recommendation-api

pip3 install --no-deps ${TMP_PATH}/wheels/wheels/*.whl
pip3 install --no-deps ${TMP_PATH}/recommendation-api

# ln -s /usr/bin/nodejs /usr/bin/node
cd ${TMP_PATH}
npm install bower
cd ${SRV_PATH}/resources
${TMP_PATH}/node_modules/bower/bin/bower install --allow-root ${TMP_PATH}/recommendation-api/recommendation/web/static/bower.json

echo 'Downloading data, hang on...'
cd ${TMP_PATH}
wget https://ndownloader.figshare.com/files/6401424
unzip 6401424
mv 2016-08-01_2016-08-31_wikidata_100 ${ETC_PATH}/mini_embedding

chown -R www-data:www-data ${ETC_PATH}
chown -R www-data:www-data ${SRV_PATH}
chown -R www-data:www-data ${LIB_PATH}
chown -R www-data:www-data ${LOG_PATH}

cp ${TMP_PATH}/recommendation-api/recommendation/data/* ${ETC_PATH}
cp ${ETC_PATH}/recommendation.nginx /etc/nginx/sites-available/recommendation
unlink /etc/nginx/sites-enabled/recommendation
ln -s /etc/nginx/sites-available/recommendation /etc/nginx/sites-enabled/
cp ${ETC_PATH}/recommendation.service /etc/systemd/system/
systemctl enable recommendation.service
systemctl daemon-reload

systemctl restart recommendation.service
systemctl restart nginx
