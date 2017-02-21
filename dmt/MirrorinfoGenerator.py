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
    def __init__(self, site, history_hours=HISTORY_HOURS, outfile = OUTFILE, **kwargs):
        super().__init__(**kwargs)
        self.outfile = outfile
        self.site = site
        self.history_hours = history_hours

    def run(self):
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
                  order_by(desc(db.Checkrun.timestamp))
        checks = []
        for checkrun, traceset, mastertrace, sitetrace in results:
            x = {}
            x['checkrun'] = checkrun.__dict__
            if not traceset is None:
                x['traceset'] = traceset.__dict__
            if not mastertrace is None:
                x['mastertrace'] = mastertrace.__dict__
            if not sitetrace is None:
                x['sitetrace'] = sitetrace.__dict__
            checks.append(x)

        context = {
            'now': now,
            'site': self.site.__dict__,
            'checks': checks,
        }
        context['site']['base_url'] = helpers.get_baseurl(context['site'])
        context['site']['trace_url'] = helpers.get_tracedir(context['site'])
        template = self.tmplenv.get_template('mirror-report.html')
        template.stream(context).dump(self.outfile, errors='strict')




class Generator(BasePageGenerator):
    def __init__(self, outfile = OUTFILE, **kwargs):
        super().__init__(**kwargs)
        self.outfile = outfile

    def run(self):
        outdir = self.outfile
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

        results = self.session.query(db.Site)
        for site in results:
            of = os.path.join(outdir, site.name + '.html')
            i = MirrorReport(base = self, outfile=of, site = site)
            i.run()

