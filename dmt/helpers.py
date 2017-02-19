#!/usr/bin/python3

import urllib
from sqlalchemy import desc

if __name__ == '__main__' and __package__ is None:

    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.helpers
    __package__ = 'dmt.helpers'

import dmt.db as db


FTPMASTER = "ftp-master.debian.org"

def get_tracedir(site):
    baseurl = urllib.parse.urljoin("http://" + site['name'], site['http_path'])
    if not baseurl.endswith('/'): baseurl += '/'
    tracedir = urllib.parse.urljoin(baseurl, 'project/trace/')
    return tracedir

def get_ftpmaster_trace(session):
    ftpmastertraceq = session.query(db.Site, db.Mastertrace).filter_by(name = FTPMASTER). \
                      join(db.Mastertrace).filter(db.Mastertrace.trace_timestamp.isnot(None)). \
                      join(db.Checkrun). \
                      order_by(desc(db.Checkrun.timestamp)).first()
    if ftpmastertraceq is not None:
        return ftpmastertraceq[1].trace_timestamp
    else:
        return None
