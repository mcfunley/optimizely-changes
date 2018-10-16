## Development

Running `python main.py` runs a test webserver, which can be used to test changes using a testing proxy such as [ngrok](https://ngrok.com/). Run ngrok, run the test server, and then configure a webhook to hit your public endpoint in the Optimizely admin interface.

You need to set several environment variables (you can use [direnv](https://direnv.net/) to manage these locally):

* `OPTIMIZELY_WEBHOOK_SECRET` - This can be a single webhook secret, or secrets from several projects separated by commas.
* `GCS_BUCKET_NAME` - Set to the name of a GCS bucket where datafiles will be archived.
* `GOOGLE_APPLICATION_CREDENTIALS` - Set to the path of a credentials file so that the Google API's used here can authenticte.
* `SLACK_URL` - set this to a Slack webhook url to receive notifications. (Or you can omit this, and just watch the logs.)

## Testing

To run the tests: `python -m unittest`
