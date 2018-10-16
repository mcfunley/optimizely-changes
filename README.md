# optimizely-changes

This is a [Google Cloud Function](https://cloud.google.com/functions/) that notices production-affecting Optimizely changes. This works for both full stack projects and web projects.

![Full stack notifications](docs/fs-notifications.png?raw=true)
![WebX notifications](docs/webx-notifications.png?raw=true)


## Configuration
There are four configuration steps for using this.

1. Create a GCS bucket for archived datafiles.
1. Set up the cloud function in your Google Cloud console.
1. Configure an Optimizely webhook (or webhooks) to hit the cloud function endpoint.
1. Configure a Slack webhook for the channel that will receive notifications.

### GCS Configuration

If you are using this for an [Optimizely Full Stack](https://www.optimizely.com/products/full-stack/) project, the datafiles are archived to a configurable [Google Cloud Storage](https://cloud.google.com/storage/) bucket. You can use an existing bucket or make one, e.g.

```
gsutil mb gs://example-optimizely-datafiles-example
```

### GCF Configuration
You need to create a cloud function pointing at the `webhook_post` function in this codebase. [See the Google documentation](https://cloud.google.com/functions/docs/quickstart-console) for how to do this.

You need to set several environment variables for the function. (You will not have all of these at first, you have to do the Optimizely and Slack steps first.)

* `GCS_BUCKET_NAME` - Set to the name of a GCS bucket (see above) where datafiles will be archived.
* `OPTIMIZELY_WEBHOOK_SECRET` - This can be a single webhook secret, or secrets from several projects separated by commas.
* `SLACK_URL` - set this to a Slack webhook url to receive notifications. (In development you can omit this, and just watch the logs.)

Note the endpoint url for the cloud function. You use this in the Optimizely step.

### Optimizely Configuration
See [Optimizely's documentation](https://help.optimizely.com/Set_Up_Optimizely/Set_up_a_webhook_for_a_Full_Stack_project_datafile) for setting up a webhook. Point this at the GCF endpoint you got above.

You need to take the webhook secret provided in this step and configure it as the cloud function's `OPTIMIZELY_WEBHOOK_SECRET` environment variable.

If you have more than one Optimizely project, you can use one instance of this cloud function to handle all of their webhooks. Comma separate the webhook secrets in the `OPTIMIZELY_WEBHOOK_SECRET` variable.

### Slack Configuration
You need to create a Slack webhook integration for the channel to receive notifications. [See the Slack docs](https://get.slack.help/hc/en-us/articles/115005265063-Incoming-WebHooks-for-Slack) for how to do do this. Set the cloud function's `SLACK_URL` to the value you get here.

## Development

You will need to set the environment variables above to develop locally. [Direnv](https://direnv.net/) is a handy way to manage this.

In development you should also set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable. Set this to the path of a credentials file so that the Google API's used here can authenticte.

Running `python main.py` runs a test webserver, which can be used to test the webhook endpoint using a testing proxy such as [ngrok](https://ngrok.com/). Run ngrok, run the test server, and then configure a webhook to hit your public endpoint in the Optimizely admin interface.

## Testing

To run the tests: `python -m unittest`
