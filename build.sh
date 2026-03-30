#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py makemigrations website
python manage.py collectstatic --noinput
python manage.py migrate    