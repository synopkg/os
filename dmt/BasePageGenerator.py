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

import dmt.db as db

def get_human_readable_age(ts, base):
    assert(ts is not None)
    assert(base is not None)

    if base < ts:
        rounding_skew = datetime.timedelta(seconds = 30)
    elif base > ts:
        rounding_skew = datetime.timedelta(seconds = -30)
    rd = dateutil.relativedelta.relativedelta(base, ts + rounding_skew)
    attrs = ['years', 'months', 'days', 'hours', 'minutes']
    elems = ['%d %s' % (getattr(rd, attr), getattr(rd, attr) > 1 and attr or attr[:-1]) for attr in attrs if getattr(rd, attr)]

    hr = ', '.join(elems[0:2])
    if hr == "": hr = "seconds"
    #hr += ' (%s)'%(rd,)
    formattedts = ts.strftime('%Y-%m-%d %H:%M:%S')

    return (formattedts, hr)

def datetimeagefilter(ts, base):
    formattedts, hr = get_human_readable_age(ts, base)
    res = '<abbr title="%s">%s</abbr>'%(formattedts, hr)
    return jinja2.Markup(res)

def datetimeagenoabbrfilter(ts, base):
    formattedts, hr = get_human_readable_age(ts, base)
    res = '%s - %s'%(hr, formattedts)
    return res


def agegroupclassfilter(ts, base):
    delta = base - ts
    # our template defines 8 agegroups from OK(0) to okish(2) to warn(3) and Warn(4-5) to Error(6-7)
    if delta < datetime.timedelta(hours=6):
        r = 'class="age0"'
    elif delta < datetime.timedelta(hours=11):
        r = 'class="age1"'
    elif delta < datetime.timedelta(hours=16):
        r = 'class="age2"'
    elif delta < datetime.timedelta(hours=24):
        r = 'class="age3"'
    elif delta < datetime.timedelta(hours=48):
        r = 'class="age4"'
    elif delta < datetime.timedelta(days=3):
        r = 'class="age5"'
    elif delta < datetime.timedelta(days=4):
        r = 'class="age6"'
    elif delta < datetime.timedelta(days=8):
        r = 'class="age7"'
    elif delta < datetime.timedelta(days=14):
        r = 'class="age8"'
    elif delta < datetime.timedelta(days=30):
        r = 'class="age9"'
    else:
        r = 'class="age10"'
    return jinja2.Markup(r)

def raise_helper(msg):
    raise Exception(msg)

class BasePageGenerator:
    def __init__(self, **kwargs):
        if 'base' in kwargs:
            self.tmplenv  = kwargs['base'].tmplenv
            self.dbh      = kwargs['base'].dbh
            self.session  = kwargs['base'].session
        else:
            assert('dburl' in kwargs)
            assert('templatedir' in kwargs)
            self.tmplenv = self.setup_template_env(kwargs['templatedir'])
            (self.dbh, self.session) = self.setup_db(kwargs['dburl'])


    @staticmethod
    def setup_template_env(templatedir):
        tmplenv = jinja2.Environment(
            loader = jinja2.FileSystemLoader(templatedir),
            autoescape = True,
            undefined = jinja2.StrictUndefined
        )
        tmplenv.filters['datetimeage'] = datetimeagefilter
        tmplenv.filters['datetimeagenoabbr'] = datetimeagenoabbrfilter
        tmplenv.filters['agegroupclass'] = agegroupclassfilter
        tmplenv.globals['raise'] = raise_helper
        return tmplenv

    @staticmethod
    def setup_db(dburl):
        dbh = db.MirrorDB(dburl)
        session = dbh.session()
        return (dbh, session)

