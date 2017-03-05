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
                traceset.traceset AS traceset_traceset

            FROM checkrun LEFT OUTER JOIN
                (SELECT * FROM mastertrace WHERE site_id = %(site_id)s) AS mastertrace ON checkrun.id = mastertrace.checkrun_id LEFT OUTER JOIN
                (SELECT * FROM sitetrace   WHERE site_id = %(site_id)s) AS sitetrace   ON checkrun.id = sitetrace.checkrun_id LEFT OUTER JOIN
                (SELECT * FROM traceset    WHERE site_id = %(site_id)s) AS traceset    ON checkrun.id = traceset.checkrun_id
            WHERE
                checkrun.timestamp >= %(check_age_cutoff)s
            ORDER BY
                checkrun.timestamp
            """, {
                'check_age_cutoff': check_age_cutoff,
                'site_id': self.site['id'],
            })

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
        for row in cur.fetchall():
            row['effective_mastertrace'] = {}
            if row['mastertrace_trace_timestamp'] is not None:
                if last_mastertrace != row['mastertrace_trace_timestamp']:
                    last_mastertrace = row['mastertrace_trace_timestamp']
                    # make sure we don't believe the very first master trace entry - it might be a mirrorrun in progress
                    if first_mastertrace: first_mastertrace = False
                    else:                 row['mastertrace_changed'] = True

            if row['sitetrace_trace_timestamp'] is not None:
                if row['sitetrace_trace_timestamp'] != mirror_version_tracker['sitetrace.trace_timestamp']:
                    mirror_version_tracker['sitetrace.trace_timestamp'] = row['sitetrace_trace_timestamp']
                    # make sure we don't believe the very first master trace entry - it might be a mirrorrun in progress
                    if first_sitetrace: first_sitetrace = False
                    else:
                        row['sitetrace_changed'] = True
                        if mirror_version_tracker['mastertrace.trace_timestamp'] != row['mastertrace_trace_timestamp']:
                            row['effective_mastertrace_changed'] = True

                        mirror_version_tracker['sitetrace.trace_timestamp']   = row['sitetrace_trace_timestamp']
                        mirror_version_tracker['mastertrace.trace_timestamp'] = row['mastertrace_trace_timestamp']

            # set the mastertrace after the last change of sitetrace (i.e. finished mirrorrun)
            if row['mastertrace_trace_timestamp'] is not None and \
               row['sitetrace_trace_timestamp'] is not None: # no errors
                row['effective_mastertrace_trace_timestamp'] = mirror_version_tracker['mastertrace.trace_timestamp']
            else:
                row['effective_mastertrace_trace_timestamp'] = None
            row['effective_mastertrace_lastseen_on_master'] = self.mastertraces_lastseen.get( row['effective_mastertrace_trace_timestamp'] )
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
