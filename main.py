import differ
from flask import abort
from google.cloud import storage
from hashlib import sha1
import hmac
import json
import logging
import os
import requests
from urllib.parse import urlparse


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s]: %(message)s')

logger = logging.getLogger('optimizely-changes')


def slack_url():
    return os.getenv('SLACK_URL')

def webhook_secrets():
    return [x.strip() for x in os.getenv('OPTIMIZELY_WEBHOOK_SECRET').split(',')]

def gcs_bucket():
    gcs = storage.Client()
    return gcs.get_bucket(os.getenv('GCS_BUCKET_NAME'))

def webhook_post(request):
    verify_request(request)

    event = request.json['event']
    if event == 'project.datafile_updated':
        datafile_updated(request.json)
        return 'ok'
    elif event == 'project.snippet_updated':
        snippet_updated(request.json)
        return 'ok'

    return 'unhandled event'


def verify_request(request):
    sig = request.headers.get('X-Hub-Signature')
    if not sig:
        abort(400)

    for secret in webhook_secrets():
        key = bytes(secret, 'utf-8')
        csig = 'sha1=' + hmac.new(
            key, msg=request.get_data(), digestmod=sha1).hexdigest()
        if csig == sig:
            return
    abort(400)


def snippet_updated(payload):
    changes = 'https://app.optimizely.com/v2/projects/%s/change_history' % payload['project_id']
    notify(
        'WebX javascript updated. Sorry, that\'s all I know :grimacing:. '
        'For details view the <%s|changelog>.' % changes)


def datafile_updated(payload):
    data = payload['data']
    if data['environment'] != 'Production':
        return

    # We get two webhook hits per change; only one includes the permalink
    # to the datafile. Only process the permalink payload.
    if '/datafiles/' not in data['cdn_url']:
        return

    old_datafile = load_latest_datafile(payload)
    current_datafile = save_datafile(payload)
    desc = differ.describe(old_datafile, current_datafile)
    if desc:
        notify(desc)


def notify(description):
    logger.info('Notifying for change: %s' % description)

    url = slack_url()
    if not url:
        return

    requests.post(url, json={
	    'username': 'Optimizely',
	    'icon_url': 'https://app.optimizely.com/static/img/favicon-32x32.png',
        'text': description,
    })


def load_latest_datafile(payload):
    bucket = gcs_bucket()

    latest_path = latest_datafile_gcs_path(payload)
    b = bucket.blob(latest_path)
    if not b.exists():
        logger.info('No existing latest datafile found')
        return None

    data = json.loads(b.download_as_string())
    logger.info('Loaded latest datafile from %s' % latest_path)
    return data


def save_datafile(payload):
    url = payload['data']['origin_url']
    response = requests.get(url)

    bucket = gcs_bucket()
    b = bucket.blob(datafile_gcs_path(payload))
    b.upload_from_string(response.text)
    logger.info('Wrote %s' % b.path)

    latest_path = latest_datafile_gcs_path(payload)
    bucket.copy_blob(b, bucket, latest_path)
    logger.info('Copied %s to %s' % (b.path, latest_path))

    return response.json()


def latest_datafile_gcs_path(payload):
    return 'datafile/%s/_latest/datafile.json' % payload['project_id']


def datafile_gcs_path(payload):
    filename = urlparse(payload['data']['origin_url']).path.split('/')[-1]
    return 'datafile/%s/%s/%s' % (
        payload['project_id'],
        payload['timestamp'],
        filename)


def test_server():
    from flask import Flask, request
    app = Flask('optimizely-changes')

    @app.route('/', methods=['POST'])
    def wrapper():
        return webhook_post(request)

    app.run(port=4000)


if __name__ == '__main__':
    test_server()
