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
from dmt.BasePageGenerator import BasePageGenerator

class Generator(BasePageGenerator):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        assert('outfile' in kwargs)
        self.outfile = kwargs['outfile']

    def run(self):
        now = datetime.datetime.now()
        ftpmastertrace = helpers.get_ftpmaster_trace(self.session)
        if ftpmastertrace is None: ftpmastertrace = now
        checkrun = self.session.query(db.Checkrun).order_by(desc(db.Checkrun.timestamp)).first()

        mastertraces = self.session.query(db.Site, db.Mastertrace). \
                       outerjoin(db.Mastertrace).\
                       filter(or_(db.Mastertrace.checkrun_id == None,
                                  db.Mastertrace.checkrun_id == checkrun.id)).\
                       order_by(db.Site.name)
        mirrors = []
        for site, mastertrace in mastertraces:
            x = {}
            x['site'] = site.__dict__
            x['site']['trace_url'] = helpers.get_tracedir(x['site'])

            if not mastertrace is None:
                x['mastertrace'] = mastertrace.__dict__

                if x['mastertrace']['trace_timestamp'] is not None:
                    x['mastertrace']['agegroup'] = self._get_agegroup(ftpmastertrace - x['mastertrace']['trace_timestamp'])
                x['error'] = x['mastertrace']['error']
            else:
                x['error'] = "No mastertracefile result"

            mirrors.append(x)

        context = {
            'mirrors': mirrors,
            'last_run': checkrun.timestamp,
            'ftpmasterttrace': ftpmastertrace,
            'now': now,
        }
        template = self.tmplenv.get_template('mirror-status.html')
        template.stream(context).dump(self.outfile, errors='strict')

OUTFILE='mirror-status.html'

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.MirrorDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--outfile', help='output-file', default=OUTFILE, type=argparse.FileType('w'))
    args = parser.parse_args()
    Generator(**args.__dict__).run()
