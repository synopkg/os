#!/usr/bin/python3

import argparse
import datetime
import json
import sys

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.StatusGenerator
    __package__ = 'dmt.StatusGenerator'

import dmt.db as db
import dmt.helpers as helpers

class Generator():
    def __init__(self, outfile, **kwargs):
        self.outfile = outfile
        self.template_name = 'mirror-status.html'

    def get_pages(self, dbh):
        return [self]

    def prepare(self, dbh):
        cur = dbh.cursor()

        now = datetime.datetime.now(datetime.timezone.utc)
        ftpmastertrace = helpers.get_ftpmaster_trace(cur)
        if ftpmastertrace is None: ftpmastertrace = now
        checkrun = helpers.get_latest_checkrun(cur)
        if checkrun is None: return

        cur.execute("""
            SELECT
                site.name,
                site.http_override_host,
                site.http_override_port,
                site.http_path,

                checkoverview.error AS checkoverview_error,
                checkoverview.age AS checkoverview_age,
                checkoverview.score AS checkoverview_score,
                checkoverview.aliases AS checkoverview_aliases,

                mastertrace.error AS mastertrace_error,
                mastertrace.trace_timestamp AS mastertrace_trace_timestamp,

                sitetrace.error AS sitetrace_error,
                sitetrace.trace_timestamp AS sitetrace_trace_timestamp,

                runs_per_day.runs_per_day

            FROM site JOIN
                checkoverview ON site.id = checkoverview.site_id LEFT OUTER JOIN
                mastertrace ON site.id = mastertrace.site_id LEFT OUTER JOIN
                sitetrace     ON site.id = sitetrace.site_id LEFT OUTER JOIN
                (
                 SELECT num_runs / days AS runs_per_day,
                        site_id
                 FROM (
                  SELECT COUNT(distinct trace_timestamp) AS num_runs,
                         EXTRACT(epoch from CURRENT_TIMESTAMP - MIN(checkrun.timestamp))/24/3600 AS days,
                         sitetrace.site_id
                  FROM sitetrace JOIN
                       checkrun ON sitetrace.checkrun_id = checkrun.id
                  WHERE checkrun.timestamp > CURRENT_TIMESTAMP - INTERVAL '2 week'
                  GROUP BY sitetrace.site_id) AS sub
                ) AS runs_per_day ON site.id = runs_per_day.site_id
            WHERE
                (checkoverview.checkrun_id = %(checkrun_id)s) AND
                (mastertrace  .checkrun_id = %(checkrun_id)s OR mastertrace.checkrun_id IS NULL) AND
                (sitetrace    .checkrun_id = %(checkrun_id)s OR sitetrace.checkrun_id IS NULL)
            """, {
                'checkrun_id': checkrun['id']
            })

        mirrors = []
        for row in cur.fetchall():
            row['site_trace_url'] = helpers.get_tracedir(row)
            aliases = json.loads(row['checkoverview_aliases']) if row['checkoverview_aliases'] is not None else {}
            row['aliases' ] = aliases
            row['bugs'] = helpers.get_bugs_for_mirror(row['name'])
            mirrors.append(row)

        mirrors.sort(key=lambda m: helpers.hostname_comparator(m['name']))
        context = {
            'mirrors': mirrors,
            'last_run': checkrun['timestamp'],
            'ftpmastertrace': ftpmastertrace,
            'now': now,
        }
        self.context = context

OUTFILE='mirror-status.html'

if __name__ == "__main__":
    from dmt.BasePageRenderer import BasePageRenderer

    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.RawDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--outfile', help='output-file', default=OUTFILE, type=argparse.FileType('w'))
    args = parser.parse_args()

    base = BasePageRenderer(**args.__dict__)
    dbh = db.RawDB(args.dburl)
    g = Generator(**args.__dict__)
    for x in g.get_pages(dbh):
        x.prepare(dbh)
        base.render(x)
