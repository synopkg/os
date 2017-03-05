#!/usr/bin/python3

import urllib
from sqlalchemy import desc
import sqlalchemy.orm.session
import psycopg2.extras

if __name__ == '__main__' and __package__ is None:

    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.helpers
    __package__ = 'dmt.helpers'

import dmt.db as db


FTPMASTER = "ftp-master.debian.org"

def get_baseurl(site):
    hn = site['name']
    if not site['http_override_host'] is None:
        hn = site['http_override_host']
    if not site['http_override_port'] is None:
        hn += ':%d'%(site['http_override_port'],)

    baseurl = urllib.parse.urljoin("http://" + hn, site['http_path'])
    if not baseurl.endswith('/'): baseurl += '/'
    return baseurl

def get_tracedir(site):
    baseurl = get_baseurl(site)
    tracedir = urllib.parse.urljoin(baseurl, 'project/trace/')
    return tracedir

def get_ftpmaster_trace(session):
    #if isinstance(session, db.RawDB):
    #    dbh = session
    #    cur = dbh.cursor()
    if isinstance(session, psycopg2.extras.RealDictCursor):
        cur = session
        cur.execute("""
            SELECT trace_timestamp
            FROM mastertrace JOIN
                site ON site.id = mastertrace.site_id JOIN
                checkrun ON checkrun.id = mastertrace.checkrun_id
            WHERE
                site.name = %(site_name)s AND
                trace_timestamp IS NOT NULL
            ORDER BY
                timestamp DESC
            LIMIT 1
            """, {
                'site_name': FTPMASTER,
            })
        res = cur.fetchone()
        if res is None: return None
        return res['trace_timestamp']

    else:
        assert(isinstance(session, sqlalchemy.orm.session.Session))
        ftpmastertraceq = session.query(db.Site, db.Mastertrace).filter_by(name = FTPMASTER). \
                          join(db.Mastertrace).filter(db.Mastertrace.trace_timestamp.isnot(None)). \
                          join(db.Checkrun). \
                          order_by(desc(db.Checkrun.timestamp)).first()
        if ftpmastertraceq is not None:
            return ftpmastertraceq[1].trace_timestamp
        else:
            return None

def get_latest_checkrun(cur):
    assert(isinstance(cur, psycopg2.extras.RealDictCursor))
    cur.execute("""
        SELECT id, timestamp
        FROM checkrun
        ORDER BY timestamp DESC
        LIMIT 1
        """)
    checkrun = cur.fetchone()
    return checkrun

def get_ftpmaster_traces_lastseen(session):
    """For each trace on ftp-master, report when it was last seen.
    """
    results = session.query(db.Mastertrace, db.Checkrun). \
              filter(db.Mastertrace.trace_timestamp.isnot(None)). \
              join(db.Site).filter_by(name = FTPMASTER). \
              join(db.Checkrun). \
              order_by(db.Checkrun.timestamp)
    trace_timestamp_lastseen = {}
    for mastertrace, checkrun in results:
        trace_timestamp_lastseen[mastertrace.trace_timestamp] = checkrun.timestamp
    return trace_timestamp_lastseen

def hostname_comparator(hostname):
    return list(reversed(hostname.split('.')))
