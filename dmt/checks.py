#!/usr/bin/python3

from collections import OrderedDict
#import dateutil.parser
import datetime
from bs4 import BeautifulSoup
import re
import socket
import sys
import urllib
import urllib.request


if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.checks
    __package__ = 'dmt.checks'

import dmt.db as db
import dmt.helpers as helpers

class MirrorFailureException(Exception):
    def __init__(self, e, msg):
        if msg is None:
            self.message = repr(e)
        else:
            self.message = str(msg)
        self.origin = e

class BaseCheck:
    TIMEOUT = 15

    def get_tracedir(self):
        return helpers.get_tracedir(self.site)

    @staticmethod
    def _fetch(url, request_headers={}):
        try:
            req = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(req, timeout=BaseCheck.TIMEOUT) as response:
                data = response.read()
                return data
        except socket.timeout as e:
            raise MirrorFailureException(e, 'timed out fetching '+url)
        except urllib.error.URLError as e:
            raise MirrorFailureException(e, e.reason)
        except OSError as e:
            raise MirrorFailureException(e, e.strerror)
        except Exception as e:
            raise MirrorFailureException(e, 'other exception: '+str(e))

    def __init__(self, site, checkrun_id):
        self.site      = site.__dict__
        self.result = {
            'site_id':     site.id,
            'checkrun_id': checkrun_id
        }

    def run(self):
        raise Exception("run called on abstractish base class")

    def store(self, session, checkrun_id):
        raise Exception("store called on abstractish base class")


class TracfileFetcher(BaseCheck):
    def __init__(self, site, checkrun_id, tracefilename, request_host=None):
        super().__init__(site, checkrun_id)
        self.tracefilename = tracefilename
        self.request_headers = {}
        if request_host is not None:
            self.request_headers['Host'] = request_host

    def parse_tracefile(self, rawcontents):
        try:
            decoded = rawcontents.decode('utf-8')
            self.result['full'] = decoded
            content = {}

            lines = decoded.split('\n')
            first = lines.pop(0)
            # ts = dateutil.parser.parse(first)
            for f in ('%a %b %d %H:%M:%S UTC %Y',
                      '%a %b %d %H:%M:%S GMT %Y'):
                try:
                    ts = datetime.datetime.strptime(first, f)
                    break
                except ValueError:
                    pass
            if ts is None:
                self.result['error'] = "Invalid tracefile"
            else:
                self.result['trace_timestamp'] = ts

            for line in lines:
                line = line.split(':', 1)
                if len(line) == 2:
                    key = line[0].lower()
                    value = line[1].lstrip()
                    content[key] = {'text': value}

            self.result['content'] = content
        except:
            self.result['error'] = "Invalid tracefile"

    def run(self):
        try:
            traceurl = urllib.parse.urljoin(self.get_tracedir(), self.tracefilename)
            rawtracefilecontents = self._fetch(traceurl, request_headers=self.request_headers)
            self.parse_tracefile(rawtracefilecontents)
        except MirrorFailureException as e:
            self.result['error'] = e.message

class MastertraceFetcher(TracfileFetcher):
    def __init__(self, site, checkrun_id):
        super().__init__(site, checkrun_id, 'master')

    def store(self, session, checkrun_id):
        i = db.Mastertrace(**self.result)
        session.add(i)

class SitetraceFetcher(TracfileFetcher):
    def __init__(self, site, checkrun_id):
        super().__init__(site, checkrun_id, site.name)

    def store(self, session, checkrun_id):
        i = db.Sitetrace(**self.result)
        session.add(i)

class SiteAliasFetcher(TracfileFetcher):
    def __init__(self, site, checkrun_id, sitealias):
        #self.sitealias = sitealias
        super().__init__(site, checkrun_id, 'master', request_host=sitealias.name)
        del self.result['site_id']
        self.result['sitealias_id'] = sitealias.id

    def store(self, session, checkrun_id):
        i = db.SiteAliasMastertrace(**self.result)
        session.add(i)

def siteAliasChecker_generator(site, checkrun_id):
    for alias in site.sitealiases:
        yield SiteAliasFetcher(site, checkrun_id, alias)

class TracesetFetcher(BaseCheck):
    def __init__(self, site, checkrun_id):
        super().__init__(site, checkrun_id)

    @staticmethod
    def _filter_tracefilenames(tracefilenames):
        return filter(lambda x: not x.startswith('_') and
                                # Used by ftpsync for stagged sync
                                not x.endswith('-stage1') and
                                # Used by ftpsync as temporary file
                                not x.endswith('.new'), tracefilenames)

    @staticmethod
    def _clean_link(link, tracedir):
        # some mirrors provide absolute links instead of relative ones,
        # so turn them all into full links, then try to get back relative ones no matter what.
        fulllink = urllib.parse.urljoin(tracedir, link)

        l1 = urllib.parse.urlparse(tracedir)
        l2 = urllib.parse.urlparse(fulllink)
        if l1.netloc != l2.netloc:
            return None

        if fulllink.startswith(tracedir):
            link = fulllink[len(tracedir):]

        if re.fullmatch('\.*', link):
            return None
        elif re.fullmatch('[a-zA-Z0-9._-]*', link):
            return link
        else:
            return None

    def list_tracefiles(self):
        tracedir = self.get_tracedir()
        data = self._fetch(tracedir)

        soup = BeautifulSoup(data, "html.parser")
        links = soup.find_all('a')
        links = filter(lambda x: 'href' in x.attrs, links)
        links = map(lambda x: self._clean_link(x.get('href'), tracedir), links)
        tracefiles = filter(lambda x: x is not None, links)
        tracefiles = self._filter_tracefilenames(tracefiles)
        return sorted(set(tracefiles))

    def run(self):
        try:
            traces = self.list_tracefiles()

            if len(traces) > 0:
                self.result['traceset'] = traces
            else:
                self.result['error'] = "No traces found"
        except MirrorFailureException as e:
            self.result['error'] = e.message

    def store(self, session, checkrun_id):
        i = db.Traceset(**self.result)
        session.add(i)
