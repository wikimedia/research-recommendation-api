#!/usr/bin/env bash

ETC_PATH='/etc/recommendation'
SRV_PATH='/srv/recommendation'
TMP_PATH='/tmp/recommendation'
LIB_PATH='/var/lib/recommendation'
LOG_PATH='/var/log/uwsgi'

echo "Updating the system..."
apt-get update
apt-get install -y git nginx npm python3 python3-pip libpython3.7 python3-setuptools python3-wheel

echo "Setting up paths..."
rm -rf ${TMP_PATH}
mkdir -p ${TMP_PATH}
mkdir -p ${SRV_PATH}/resources
mkdir -p ${SRV_PATH}/sock
mkdir -p ${ETC_PATH}
mkdir -p ${LIB_PATH}
mkdir -p ${LOG_PATH}

echo "Cloing repositories..."
git clone https://gerrit.wikimedia.org/r/research/recommendation-api/wheels ${TMP_PATH}/wheels
git clone https://gerrit.wikimedia.org/r/research/recommendation-api ${TMP_PATH}/recommendation-api

echo "Making wheel files..."
cd ${TMP_PATH}/wheels
rm -rf wheels/*.whl
make

echo "Installing repositories..."
pip3 install --no-deps ${TMP_PATH}/wheels/wheels/*.whl
pip3 install --no-deps ${TMP_PATH}/recommendation-api

echo "Installing front-end resources..."
# ln -s /usr/bin/nodejs /usr/bin/node
cd ${TMP_PATH}
npm install bower
cd ${SRV_PATH}/resources
${TMP_PATH}/node_modules/bower/bin/bower install --allow-root ${TMP_PATH}/recommendation-api/recommendation/web/static/bower.json

# Enable these lines if you're setting the related_articles endpoint
# echo 'Downloading mini embeddings, hang on...'
# cd ${TMP_PATH}
# wget https://ndownloader.figshare.com/files/6401424
# unzip 6401424
# mv 2016-08-01_2016-08-31_wikidata_100 ${ETC_PATH}/mini_embedding

echo "Setting up ownership..."
chown -R www-data:www-data ${ETC_PATH}
chown -R www-data:www-data ${SRV_PATH}
chown -R www-data:www-data ${LIB_PATH}
chown -R www-data:www-data ${LOG_PATH}

echo "Copying configuration files..."
cp ${TMP_PATH}/recommendation-api/recommendation/data/* ${ETC_PATH}
# Disable this line when setting up the related_articles endpoint
sed -i '/related_articles = True/c\related_articles = False' ${ETC_PATH}/recommendation.ini
cp ${ETC_PATH}/recommendation.nginx /etc/nginx/sites-available/recommendation
if [[ -f "/etc/nginx/sites-enabled/recommendation" ]]; then
    unlink /etc/nginx/sites-enabled/recommendation
fi
ln -s /etc/nginx/sites-available/recommendation /etc/nginx/sites-enabled/
cp ${ETC_PATH}/recommendation.service /etc/systemd/system/

echo "Enabling and starting services..."
systemctl enable recommendation.service
systemctl daemon-reload

systemctl restart recommendation.service
systemctl restart nginx
