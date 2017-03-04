#!/usr/bin/python3

import argparse
import datetime
import itertools
import json
from sqlalchemy import desc, or_
import sys
import os

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.HierarchyGenerator
    __package__ = 'dmt.HierarchyGenerator'

import dmt.db as db
import dmt.helpers as helpers
from dmt.BasePageGenerator import BasePageGenerator

OUTFILE='mirror-info'
HISTORY_HOURS=24*7


class MirrorReport(BasePageGenerator):
    def __init__(self, site, mastertraces_lastseen, history_hours=HISTORY_HOURS, outfile = OUTFILE, **kwargs):
        super().__init__(**kwargs)
        self.outfile = outfile
        self.site = site
        self.history_hours = history_hours
        self.mastertraces_lastseen = mastertraces_lastseen
        self.template = self.tmplenv.get_template('mirror-report.html')

    def prepare(self):
        now = datetime.datetime.now()
        check_age_cutoff = now - datetime.timedelta(hours=self.history_hours)

        results = self.session.query(db.Checkrun, db.Traceset, db.Mastertrace, db.Sitetrace). \
                  filter(db.Checkrun.timestamp >= check_age_cutoff). \
                  outerjoin(db.Traceset). \
                  filter_by(site_id = self.site.id). \
                  outerjoin(db.Mastertrace). \
                  filter_by(site_id = self.site.id). \
                  outerjoin(db.Sitetrace). \
                  filter_by(site_id = self.site.id). \
                  order_by(db.Checkrun.timestamp)
        checks = []
        # we try to determine the "version" a mirror is running
        # from its master-tracefile.  As the master-tracefile might
        # update during a mirrorun, we only believe it when a mirror
        # run is finished (which we determine from the site-tracefile
        # being updated.
        mirror_version_tracker = {
            'sitetrace.trace_timestamp': None,
            'mastertrace.trace_timestamp': None
        }
        first_sitetrace = True

        first_mastertrace = None
        last_mastertrace = None
        for checkrun, traceset, mastertrace, sitetrace in results:
            x = {}
            x['effective_mastertrace'] = {}
            x['checkrun'] = checkrun.__dict__
            if not traceset is None:
                x['traceset'] = traceset.__dict__
            if not mastertrace is None:
                x['mastertrace'] = mastertrace.__dict__

                if mastertrace.trace_timestamp is not None:
                    if last_mastertrace != mastertrace.trace_timestamp:
                        last_mastertrace = mastertrace.trace_timestamp
                        if first_mastertrace:
                            first_mastertrace = False
                        else:
                            x['mastertrace']['changed'] = True

            if not sitetrace is None:
                x['sitetrace'] = sitetrace.__dict__
                if sitetrace.trace_timestamp is not None:
                    if sitetrace.trace_timestamp != mirror_version_tracker['sitetrace.trace_timestamp']:
                        mirror_version_tracker['sitetrace.trace_timestamp'] = sitetrace.trace_timestamp
                        if first_sitetrace:
                            # make sure we don't believe the very first master trace entry -
                            # it might be a mirrorrun in progress
                            first_sitetrace = False
                        else:
                            x['sitetrace']['changed'] = True
                            if mirror_version_tracker['mastertrace.trace_timestamp'] != mastertrace.trace_timestamp:
                                x['effective_mastertrace']['changed'] = True

                            mirror_version_tracker['sitetrace.trace_timestamp'] = sitetrace.trace_timestamp
                            mirror_version_tracker['mastertrace.trace_timestamp'] = mastertrace.trace_timestamp if mastertrace is not None else None

            # set the mastertrace after the last change of sitetrace (i.e. finished mirrorrun)
            if sitetrace   is not None and sitetrace  .trace_timestamp is not None and \
               mastertrace is not None and mastertrace.trace_timestamp is not None: # no errors
                x['effective_mastertrace']['trace_timestamp'] = mirror_version_tracker['mastertrace.trace_timestamp']
                if x['effective_mastertrace']['trace_timestamp'] is not None and \
                   x['effective_mastertrace']['trace_timestamp'] in self.mastertraces_lastseen:
                    x['effective_mastertrace']['lastseen_on_master'] = self.mastertraces_lastseen[ x['effective_mastertrace']['trace_timestamp'] ]
                else:
                    x['effective_mastertrace']['lastseen_on_master'] = None
            checks.append(x)

        context = {
            'now': now,
            'site': self.site.__dict__,
            'checks': reversed(checks),
        }
        context['site']['base_url'] = helpers.get_baseurl(context['site'])
        context['site']['trace_url'] = helpers.get_tracedir(context['site'])

        self.context = context



class Generator(BasePageGenerator):
    def __init__(self, outfile = OUTFILE, **kwargs):
        super().__init__(**kwargs)
        self.outfile = outfile

    def prepare(self):
        outdir = self.outfile
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

        mastertraces_lastseen = helpers.get_ftpmaster_traces_lastseen(self.session)

        results = self.session.query(db.Site)
        for site in results:
            of = os.path.join(outdir, site.name + '.html')
            i = MirrorReport(base = self, outfile=of, site = site, mastertraces_lastseen = mastertraces_lastseen)
            i.prepare()
            yield i


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.MirrorDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--outfile', help='output-dir', default=OUTFILE)
    args = parser.parse_args()
    g = Generator(**args.__dict__)
    for x in g.prepare(): x.render()
