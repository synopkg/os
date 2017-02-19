#!/usr/bin/python3

import dateutil.relativedelta
import datetime
import jinja2

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.BasePageGenerator
    __package__ = 'dmt.BasePageGenerator'

from dmt.DB import MirrorDB, MirrorCheckResult, GlobalInfo
from dmt.Masterlist import Masterlist
from dmt.Mirrors import Mirrors

def get_human_readable_age(ts, base):
    rd = dateutil.relativedelta.relativedelta(base, ts)
    attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds']
    elems = ['%d %s' % (getattr(rd, attr), getattr(rd, attr) > 1 and attr or attr[:-1]) for attr in attrs if getattr(rd, attr)]

    hr = ', '.join(elems[0:2])
    formattedts = ts.strftime('%Y-%m-%d %H:%M:%S')

    return (formattedts, hr)

def datetimeagefilter(ts, base):
    formattedts, hr = get_human_readable_age(ts, base)
    res = '<abbr title="%s">%s</abbr>'%(formattedts, hr)
    return res
def datetimeagenoabbrfilter(ts, base):
    formattedts, hr = get_human_readable_age(ts, base)
    res = '%s - %s'%(hr, formattedts)
    return res

def raise_helper(msg):
    raise Exception(msg)

class BasePageGenerator:
    MASTERLIST='Mirrors.masterlist'
    DBURL='postgresql:///mirror-status'

    def __init__(self, args):
        self.args = args
        self.setup_db()
        self.setup_template_env()
        self.masterlist = Masterlist(args.masterlist).entries
        self.mirrors = Mirrors(self.masterlist)

    @staticmethod
    def make_argument_parser(outfile='out.html'):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--masterlist', help='Mirrors.masterlist file', default=BasePageGenerator.MASTERLIST)
        parser.add_argument('--dburl', help='database', default=BasePageGenerator.DBURL)
        parser.add_argument('--outfile', help='output-file', default=outfile, type=argparse.FileType('w'))
        parser.add_argument('--templatedir', help='template directory', default='templates')
        return parser

    def setup_template_env(self):
        self.tmplenv = jinja2.Environment(
            loader = jinja2.FileSystemLoader(self.args.templatedir),
            autoescape = True,
            undefined = jinja2.StrictUndefined
        )
        self.tmplenv.filters['datetimeage'] = datetimeagefilter
        self.tmplenv.filters['datetimeagenoabbr'] = datetimeagenoabbrfilter
        self.tmplenv.globals['raise'] = raise_helper

    def setup_db(self):
        self.db = MirrorDB(self.args.dburl)
        self.session = self.db.session()

    @staticmethod
    def _get_agegroup(delta):
        # our template defines 8 agegroups from OK(0) to okish(2) to warn(3) and Warn(4-5) to Error(6-7)
        if delta < datetime.timedelta(hours=6):
            return "0"
        elif delta < datetime.timedelta(hours=11):
            return "1"
        elif delta < datetime.timedelta(hours=16):
            return "2"
        elif delta < datetime.timedelta(hours=24):
            return "3"
        elif delta < datetime.timedelta(hours=36):
            return "4"
        elif delta < datetime.timedelta(hours=48):
            return "5"
        elif delta < datetime.timedelta(days=4):
            return "6"
        else:
            return "7"
