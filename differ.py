from cached_property import cached_property
from collections import defaultdict
from itertools import chain
import io
import json
from operator import itemgetter
from optimizely.optimizely import Optimizely # derp


def pct(v):
    return ('%.2f' % (v / 100,)).rstrip('0').rstrip('.') + '%'


def event_id_map(opt):
    return { ev['id']: ev for ev in opt.config.events }


class TrafficAllocation(object):
    def __init__(self, optimizely):
        self.optimizely = optimizely

    def summarize(self, experiment_id):
        conf = self.optimizely.config
        e = conf.get_experiment_from_id(experiment_id)

        if not e:
            raise ValueError('Experiment is not running in this config')

        vals = defaultdict(int)
        vals['not bucketed'] = 100 * 100
        end = 0
        for alloc in e.trafficAllocation:
            vid = alloc['entityId']
            if len(vid):
                v = conf.get_variation_from_id(e.key, vid)
                amount = alloc['endOfRange'] - end
                vals[v.key] += amount
                vals['not bucketed'] -= amount

            end = alloc['endOfRange']

        return { k: v for k, v in vals.items() if v > 0 }


class Change(object):
    def __init__(self, description):
        self.description = description

    def __eq__(self, other):
        return other.description == self.description

    def __hash__(self):
        return hash(self.description)

    def __str__(self):
        return self.description


class DatafileDiffer(object):
    def __init__(self, old, current):
        self.old = old
        self.current = current

        self.current_opt = Optimizely(json.dumps(self.current))
        self.old_opt = Optimizely(json.dumps(self.old))

    @property
    def old_experiments(self):
        return self.old_opt.config.experiments

    @property
    def current_experiments(self):
        return self.current_opt.config.experiments

    @cached_property
    def retained_experiment_ids(self):
        return ({ e['id'] for e in self.current_experiments } &
                { e['id'] for e in self.old_experiments })

    def describe(self):
        return '\n'.join(sorted({ str(c) for c in self.generate_changes() })) or None

    def generate_changes(self):
        return chain(*(generator() for generator in (
            self.detect_experiments_added,
            self.detect_experiments_removed,
            self.detect_experiments_renamed,
            self.detect_traffic_changes,
            self.detect_event_live,
            self.detect_event_dead,
            self.detect_event_renamed,
        )))

    def detect_experiments_added(self):
        new_ids = ({ e['id'] for e in self.current_experiments } -
                   { e['id'] for e in self.old_experiments })

        for i in new_ids:
            e = self.current_opt.config.get_experiment_from_id(i)
            yield Change('Experiment `%s` enabled. %s.' % (
                e.key, self.summarize_traffic_allocation(e.id)))

    def detect_experiments_removed(self):
        missing_ids = ({ e['id'] for e in self.old_experiments } -
                       { e['id'] for e in self.current_experiments })

        for i in missing_ids:
            e = self.old_opt.config.get_experiment_from_id(i)
            yield Change('Experiment `%s` paused.' % e.key)

    def detect_experiments_renamed(self):
        for i in self.retained_experiment_ids:
            e0 = self.old_opt.config.get_experiment_from_id(i)
            e1 = self.current_opt.config.get_experiment_from_id(i)
            if e0.key != e1.key:
                yield Change('Experiment `%s` renamed to `%s`.' % (
                    e0.key, e1.key))

    def detect_traffic_changes(self):
        for i in self.retained_experiment_ids:
            c = self.traffic_change(i)
            if c:
                yield c

    def detect_event_live(self):
        for event_key in self.event_status_changes(self.old_opt, self.current_opt):
            yield Change('Event `%s` added to active experiments. Tracking '
                         'calls will now send curls.' % event_key)

    def detect_event_dead(self):
        for event_key in self.event_status_changes(self.current_opt, self.old_opt):
            yield Change('Event `%s` removed from all active experiments. Tracking '
                         'calls are now not sending curls.' % event_key)

    def event_status_changes(self, opt0, opt1):
        e0 = event_id_map(opt0)
        e1 = event_id_map(opt1)

        for eid, settings in e1.items():
            experiments1 = settings['experimentIds']
            if not len(experiments1):
                continue

            if eid not in e0:
                yield settings['key']
            else:
                experiments0 = e0[eid]['experimentIds']
                if not len(experiments0):
                    yield settings['key']

    def detect_event_renamed(self):
        e0 = event_id_map(self.old_opt)
        e1 = event_id_map(self.current_opt)
        for eid, settings in e1.items():
            if eid not in e0:
                continue

            oldkey = e0[eid]['key']
            if oldkey != settings['key']:
                yield Change(
                    'Event `%s` renamed to `%s` (may affect track calls).' % (
                        oldkey, settings['key']))

    def traffic_change(self, experiment_id):
        e = self.current_opt.config.get_experiment_from_id(experiment_id)

        prev_alloc = TrafficAllocation(self.old_opt).summarize(e.id)
        curr_alloc = TrafficAllocation(self.current_opt).summarize(e.id)

        if prev_alloc == curr_alloc:
            return None

        curr_traffic = 100 * 100 - curr_alloc.get('not bucketed', 0)
        prev_traffic = 100 * 100 - prev_alloc.get('not bucketed', 0)

        # Sometimes adding/removing variations results in slight rebalancing
        # of the traffic allocation. Ignore this when it's very small.
        epsilon = 10

        if curr_traffic - prev_traffic > epsilon:
            return Change('Experiment `%s` traffic increased from %s to %s. '
                          'Currently: %s.' % (
                              e.key, pct(prev_traffic), pct(curr_traffic),
                              self.summarize_traffic_allocation(e.id)))
        elif curr_traffic - prev_traffic < -epsilon:
            return Change('Experiment `%s` traffic decreased from %s to %s. '
                          'Currently: %s.' % (
                              e.key, pct(prev_traffic), pct(curr_traffic),
                              self.summarize_traffic_allocation(e.id)))

        return Change('Experiment `%s` variation weighting changed. '
                      'Was: %s; currently: %s.' % (
                          e.key,
                          self.summarize_traffic_allocation(e.id, self.old_opt),
                          self.summarize_traffic_allocation(e.id)))

    def summarize_traffic_allocation(self, experiment_id, optimizely=None):
        alloc = TrafficAllocation(optimizely or self.current_opt)
        s = alloc.summarize(experiment_id)

        nb = None
        if 'not bucketed' in s:
            nb = s['not bucketed']
            del s['not bucketed']

        items = ['%s %s' % (pct(p), k)
                 for k, p in sorted(s.items(), key=itemgetter(0))]

        if nb:
            items.append('%s not bucketed' % pct(nb))

        return ', '.join(items)


def describe(old_datafile, current_datafile):
    return DatafileDiffer(old_datafile, current_datafile).describe()
