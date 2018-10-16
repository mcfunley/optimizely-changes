from hashlib import sha1
import hmac
from google.cloud import storage
import json
from main import webhook_post, webhook_secrets, datafile_gcs_path, \
    latest_datafile_gcs_path, gcs_bucket
import os
import requests
from unittest import TestCase
from unittest.mock import Mock, patch
from werkzeug.exceptions import BadRequest


def sign(data, signature_number=0):
    s = webhook_secrets()[signature_number].encode('utf-8')
    return 'sha1=' + hmac.new(s, msg=data, digestmod=sha1).hexdigest()


@patch.object(os, 'getenv', {
    'OPTIMIZELY_WEBHOOK_SECRET': 'foo, bar'
}.get)
class WebhookHandlerTest(TestCase):
    def test_no_signature(self):
        request = Mock(headers={})
        self.assertRaises(BadRequest, webhook_post, request)

    def test_bad_signature(self):
        request = Mock(
            get_data=Mock(return_value='adsf'.encode('utf-8')),
            headers={'X-Hub-Signature': 'xxx'})
        self.assertRaises(BadRequest, webhook_post, request)

    def test_unrecognized_event(self):
        d = { 'event': 'foo' }
        data = json.dumps(d).encode('utf-8')
        request = Mock(
            get_data=Mock(return_value=data),
            json=d,
            headers={'X-Hub-Signature': sign(data)})
        self.assertEqual('unhandled event', webhook_post(request))

    def test_alternate_secret(self):
        d = { 'event': 'foo' }
        data = json.dumps(d).encode('utf-8')
        request = Mock(
            get_data=Mock(return_value=data),
            json=d,
            headers={'X-Hub-Signature': sign(data, 1)})
        self.assertEqual('unhandled event', webhook_post(request))


@patch.object(os, 'getenv', {
    'OPTIMIZELY_WEBHOOK_SECRET': 'foo, bar'
}.get)
class WebhookSecretsTest(TestCase):
    def test_works(self):
        self.assertEqual(['foo', 'bar'], webhook_secrets())


class DatafilePathsTest(TestCase):
    def test_works(self):
        payload = {
            'timestamp': 1539053286,
            'project_id': 10847551550,
            'data': {
                'cdn_url': 'https://cdn.optimizely.com/datafiles/BJwszDYczj8GsM3wAqR3tu.json',
                'environment': 'Production',
                'origin_url': 'https://optimizely.s3.amazonaws.com/datafiles/BJwszDYczj8GsM3wAqR3tu.json',
                'revision': 459
            },
            'event': 'project.datafile_updated'
        }
        self.assertEqual(
            'datafile/10847551550/1539053286/BJwszDYczj8GsM3wAqR3tu.json',
            datafile_gcs_path(payload))

    def test_latest_works(self):
        payload = {
            'timestamp': 1539053286,
            'project_id': 10847551550,
            'data': {
                'cdn_url': 'https://cdn.optimizely.com/datafiles/BJwszDYczj8GsM3wAqR3tu.json',
                'environment': 'Production',
                'origin_url': 'https://optimizely.s3.amazonaws.com/datafiles/BJwszDYczj8GsM3wAqR3tu.json',
                'revision': 459
            },
            'event': 'project.datafile_updated'
        }
        self.assertEqual(
            'datafile/10847551550/_latest/datafile.json',
            latest_datafile_gcs_path(payload))


@patch.object(requests, 'post', Mock())
@patch.object(os, 'getenv', {
    'OPTIMIZELY_WEBHOOK_SECRET': 'foo, bar',
    'SLACK_URL': 'slack url',
}.get)
class SnippetUpdateTest(TestCase):
    payload = {
        'timestamp': 1539625752,
        'project_id': 8896740779,
        'data': {'cdn_url': 'https://cdn.optimizely.com/js/8896740779.js',
                 'origin_url': 'https://optimizely.s3.amazonaws.com/js/8896740779.js',
                 'revision': 1157},
        'event': 'project.snippet_updated'
    }

    def test_works(self):
        data = json.dumps(self.payload).encode('utf-8')
        request = Mock(
            get_data=Mock(return_value=data),
            json=self.payload,
            headers={'X-Hub-Signature': sign(data)})
        webhook_post(request)
        requests.post.assert_called_once_with('slack url', json={
            'username': 'Optimizely',
            'icon_url': 'https://app.optimizely.com/static/img/favicon-32x32.png',
            'text': ("WebX javascript updated. Sorry, that's all I know :grimacing:. "
                     "For details view the <https://app.optimizely.com/v2/projects/"
                     "8896740779/change_history|changelog>."),
        })


mock_gcs = Mock()

@patch.object(storage, 'Client', Mock(return_value=mock_gcs))
@patch.object(os, 'getenv', {
    'GCS_BUCKET_NAME': 'xxx'
}.get)
class GCSBucketTest(TestCase):
    def test_works(self):
        b = Mock()
        mock_gcs.get_bucket.return_value = b
        self.assertEqual(b, gcs_bucket())
        mock_gcs.get_bucket.assert_called_once_with('xxx')
