from differ import TrafficAllocation, describe, Change
import json
from unittest import TestCase
from optimizely.optimizely import Optimizely


class TrafficAllocationTest(TestCase):
    def setUp(self):
        with open('data/experiment-enabled/1.json', 'r') as f:
            self.opt = Optimizely(f.read())
        self.ta = TrafficAllocation(self.opt)


    def summarize_key(self, k):
        e = self.opt.config.get_experiment_from_key(k)
        return self.ta.summarize(e.id)

    def test_works_wacky(self):
        self.assertEqual({
            'a': 50, 'b': 50, 'not bucketed': 9900
        }, self.summarize_key('dan-testing-notifications'))

    def test_fails_not_running(self):
        self.assertRaises(ValueError, self.ta.summarize, 999999)

    def test_works_5050(self):
        self.assertEqual(
            { 'control': 5000, 'upsell-refined': 5000 },
            self.summarize_key('grow-261-billing-modal-in-list-import-0818'))


class DatafileDifferTest(TestCase):
    maxDiff = 10000

    def diff(self, name):
        with open('data/%s/0.json' % name, 'r') as before, \
             open('data/%s/1.json' % name, 'r') as after:
            return describe(json.loads(before.read()), json.loads(after.read()))

    def test_experiment_enabled(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` enabled. '
            '0.5% a, 0.5% b, 99% not bucketed.',
            self.diff('experiment-enabled'))

    def test_experiment_rampup(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` traffic increased '
            'from 1% to 10%. Currently: 5% a, 5% b, 90% not bucketed.',
            self.diff('traffic-allocation-increase'))

    def test_experiment_rampdown(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` traffic decreased '
            'from 10% to 5%. Currently: 2.5% a, 2.5% b, 95% not bucketed.',
            self.diff('traffic-allocation-decrease'))

    def test_variation_weight_change(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` variation weighting changed. '
            'Was: 2.5% a, 2.5% b, 95% not bucketed; currently: 5% a, 95% not bucketed.',
            self.diff('variation-percent-change'))

    def test_experiment_removed(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` paused.',
            self.diff('experiment-removed'))

    def test_variation_added(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` variation weighting changed. '
            'Was: 2.5% a, 2.5% b, 95% not bucketed; '
            'currently: 1.67% a, 1.67% b, 1.67% c, 94.99% not bucketed.',
            self.diff('variation-added'))

    def test_description_modified(self):
        self.assertIsNone(self.diff('experiment-description-modified'))

    def test_experiment_renamed(self):
        self.assertEqual(
            'Experiment `dan-testing-notifications` renamed to '
            '`dan-testing-notifications-foo`.',
            self.diff('experiment-renamed'))

    def test_event_added(self):
        self.assertIsNone(self.diff('event-added-no-experiments'))

    def test_event_live(self):
        self.assertEqual(
            'Event `dan-test-temp` added to active experiments. Tracking '
            'calls will now send curls.',
            self.diff('event-live'))

    def test_event_dead(self):
        self.assertEqual(
            'Event `dan-test-temp` removed from all active experiments. Tracking '
            'calls are now not sending curls.\n'
            'Experiment `dan-testing-notifications` paused.',
            self.diff('event-dead'))

    def test_event_renamed(self):
        self.assertEqual(
            'Event `dan-test-temp` renamed to `dan-test-temp-foo` (may '
            'affect track calls).\n'
            'Experiment `dan-testing-notifications` enabled. 1.67% a, 1.67% b, '
            '1.67% c, 94.99% not bucketed.',
            self.diff('event-renamed'))


class ChangeTest(TestCase):
    def test_hashing(self):
        s = { Change('foo'), Change('foo') }
        self.assertEqual(s, { Change('foo') })

    def test_str(self):
        self.assertEqual('foo', str(Change('foo')))
