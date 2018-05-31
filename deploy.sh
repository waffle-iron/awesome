#! /bin/bash
declare WEB_ROOT=/srv/awesome/www
rm -rf $WEB_ROOT
cp -R  /var/lib/jenkins/jobs/awesome/workspace/www $WEB_ROOT
chown -R root:root $WEB_ROOT
supervisorctl restart awesome: