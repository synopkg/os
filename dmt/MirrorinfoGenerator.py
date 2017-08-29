#!/usr/bin/python3

import argparse
import datetime
import itertools
import json
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

OUTFILE='mirror-info'
HISTORY_HOURS=24*7


class MirrorReport():
    def __init__(self, site, mastertraces_lastseen, history_hours=HISTORY_HOURS, outfile = OUTFILE, **kwargs):
        self.outfile = outfile
        self.site = site
        self.history_hours = history_hours
        self.mastertraces_lastseen = mastertraces_lastseen
        self.template_name = 'mirror-report.html'

    def prepare(self, dbh):
        cur = dbh.cursor()

        now = datetime.datetime.now()
        check_age_cutoff = now - datetime.timedelta(hours=self.history_hours)

        cur.execute("""
            SELECT
                checkrun.timestamp as checkrun_timestamp,

                mastertrace.id AS mastertrace_id,
                mastertrace.error AS mastertrace_error,
                mastertrace.trace_timestamp AS mastertrace_trace_timestamp,

                sitetrace.id AS sitetrace_id,
                sitetrace.error AS sitetrace_error,
                sitetrace.trace_timestamp AS sitetrace_trace_timestamp,

                traceset.id AS traceset_id,
                traceset.error AS traceset_error,
                traceset.traceset AS traceset_traceset,

                checkoverview.id AS checkoverview_id,
                checkoverview.error AS checkoverview_error,
                checkoverview.version AS checkoverview_version,
                checkoverview.age AS checkoverview_age

            FROM checkrun LEFT OUTER JOIN
                (SELECT * FROM mastertrace   WHERE site_id = %(site_id)s) AS mastertrace   ON checkrun.id = mastertrace.checkrun_id LEFT OUTER JOIN
                (SELECT * FROM sitetrace     WHERE site_id = %(site_id)s) AS sitetrace     ON checkrun.id = sitetrace.checkrun_id LEFT OUTER JOIN
                (SELECT * FROM traceset      WHERE site_id = %(site_id)s) AS traceset      ON checkrun.id = traceset.checkrun_id LEFT OUTER JOIN
                (SELECT * FROM checkoverview WHERE site_id = %(site_id)s) AS checkoverview ON checkrun.id = checkoverview.checkrun_id
            WHERE
                checkrun.timestamp >= %(check_age_cutoff)s
            ORDER BY
                checkrun.timestamp
            """, {
                'check_age_cutoff': check_age_cutoff,
                'site_id': self.site['id'],
            })

        track_items = ['mastertrace_trace_timestamp', 'sitetrace_trace_timestamp', 'checkoverview_version']
        prev = {x: None for x in track_items}
        checks = []
        for row in cur.fetchall():
            for x in track_items:
                if row[x] is not None:
                    if prev[x] is not None and prev[x] != row[x]:
                        row[x+'_changed'] = True
                    prev[x] = row[x]
            checks.append(row)

        context = {
            'now': now,
            'checks': reversed(checks),
        }
        context['site'] = {
            'name'     : self.site['name'],
            'base_url' : helpers.get_baseurl(self.site),
            'trace_url': helpers.get_tracedir(self.site),
        }

        self.context = context



class Generator():
    def __init__(self, outfile = OUTFILE, **kwargs):
        self.outfile = outfile

    def get_pages(self, dbh):
        outdir = self.outfile
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

        cur = dbh.cursor()
        mastertraces_lastseen = helpers.get_ftpmaster_traces_lastseen(cur)

        cur.execute("""
            SELECT
                site.id,
                site.name,
                site.http_override_host,
                site.http_override_port,
                site.http_path
            FROM site
            """)
        for site in cur.fetchall():
            of = os.path.join(outdir, site['name'] + '.html')
            i = MirrorReport(base = self, outfile=of, site = site, mastertraces_lastseen = mastertraces_lastseen)
            yield i


if __name__ == "__main__":
    from dmt.BasePageRenderer import BasePageRenderer

    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.MirrorDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--outfile', help='output-dir', default=OUTFILE)
    args = parser.parse_args()

    base = BasePageRenderer(**args.__dict__)
    dbh = db.RawDB(args.dburl)
    g = Generator(**args.__dict__)
    for x in g.get_pages(dbh):
        x.prepare(dbh)
        base.render(x)
