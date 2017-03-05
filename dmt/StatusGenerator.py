#!/usr/bin/python3

import argparse
import datetime
from sqlalchemy import desc, or_
import sys

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.StatusGenerator
    __package__ = 'dmt.StatusGenerator'

import dmt.db as db
import dmt.helpers as helpers

import dmt.db as db
import dmt.helpers as helpers

def get_last_successfull_sitetrace(session, site_id):
    result = session.query(db.Sitetrace). \
             filter_by(site_id = site_id). \
             filter(db.Sitetrace.error == None). \
             join(db.Checkrun). \
             order_by(desc(db.Checkrun.timestamp)). \
             limit(1).first()

    if result is not None:
        res = { 'trace_timestamp': result.trace_timestamp,
              }
    else:
        return None


class Generator():
    def __init__(self, outfile, **kwargs):
        self.outfile = outfile
        self.template_name = 'mirror-status.html'

    def prepare(self, dbsession):
        now = datetime.datetime.now(datetime.timezone.utc)
        ftpmastertrace = helpers.get_ftpmaster_trace(dbsession)
        if ftpmastertrace is None: ftpmastertrace = now
        checkrun = dbsession.query(db.Checkrun).order_by(desc(db.Checkrun.timestamp)).first()

        mastertraces = dbsession.query(db.Site, db.Mastertrace, db.Sitetrace). \
                       outerjoin(db.Mastertrace).\
                       filter(or_(db.Mastertrace.checkrun_id == None,
                                  db.Mastertrace.checkrun_id == checkrun.id)).\
                       outerjoin(db.Sitetrace).\
                       filter(or_(db.Sitetrace.checkrun_id == None,
                                  db.Sitetrace.checkrun_id == checkrun.id)).\
                       order_by(db.Site.name)
        mirrors = []
        for site, mastertrace, sitetrace in mastertraces:
            x = {}
            x['site'] = site.__dict__
            x['site']['trace_url'] = helpers.get_tracedir(x['site'])

            if not mastertrace is None:
                x['mastertrace'] = mastertrace.__dict__
                x['error'] = x['mastertrace']['error']
            else:
                x['error'] = "No mastertracefile result"

            mirrors.append(x)
            if not sitetrace is None:
                x['sitetrace'] = sitetrace.__dict__
            else:
                x['sitetrace']['trace_timestamp'] = None
                x['sitetrace']['error'] = "No sitetrace result"

            if x['sitetrace']['trace_timestamp'] is None:
                last_success = get_last_successfull_sitetrace(dbsession, site.id)
                if not last_success is None:
                    x['sitetrace'].update(last_success)

        mirrors.sort(key=lambda m: helpers.hostname_comparator(m['site']['name']))
        context = {
            'mirrors': mirrors,
            'last_run': checkrun.timestamp,
            'ftpmastertrace': ftpmastertrace,
            'now': now,
        }
        self.context = context
        return [self]

OUTFILE='mirror-status.html'

if __name__ == "__main__":
    from dmt.BasePageRenderer import BasePageRenderer

    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.MirrorDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--outfile', help='output-file', default=OUTFILE, type=argparse.FileType('w'))
    args = parser.parse_args()

    base = BasePageRenderer(**args.__dict__)
    dbsession = db.MirrorDB(args.dburl).session()
    g = Generator(**args.__dict__)
    for x in g.prepare(dbsession): base.render(x)
