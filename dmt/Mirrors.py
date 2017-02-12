#!/usr/bin/python3

from collections import OrderedDict
import dateutil.parser
from multiprocessing.pool import ThreadPool as Pool
from bs4 import BeautifulSoup
import queue
import re
import socket
import sys
import threading
import urllib
import urllib.request

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.Mirrors
    __package__ = 'dmt.Mirrors'

from dmt.Masterlist import Masterlist

class MirrorFailureException(Exception):
    def __init__(self, e, msg):
        assert(not msg is None)
        self.message = str(msg)
        self.origin = e

class Mirror:
    TIMEOUT = 30
    ARCHIVES = ["Archive", "CDImage", "Debug", "Old", "Ports", "Security"]
    PROTOS = ["http", "rsync"]

    def __init__(self, entry, timeout=None):
        self.timeout = timeout if timeout is not None else self.TIMEOUT
        self.entry = entry
        self.site = entry['Site']

        if 'Includes' in entry:
            self.includes = set(entry['Includes'].split())
        else:
            self.includes = set()

        if 'Alias' in entry:
            self.alias = set(entry['Alias'])
        else:
            self.alias = set()

        self._learn_archives()

    @staticmethod
    def _filter_tracefilenames(tracefilenames):
        return filter(lambda x: not x.startswith('_') and
                                not x.endswith('-stage1'), tracefilenames)

    def supports(self, archive, service):
        return (archive+"-"+service) in self.entry

    def _learn_archives(self):
        self.archives = set()
        for a in self.ARCHIVES:
            for p in self.PROTOS:
                if self.supports(a, p):
                    self.archives.add(a)
                    continue
        if len(self.archives) == 0:
            print("Warning:", self.site, "no archives", file=sys.stderr)

    def get_tracedir(self, archive, service):
        if not self.supports(archive, service):
            return None
        if service == 'http':
            baseurl = urllib.parse.urljoin("http://" + self.site, self.entry['Archive-http'])
            if not baseurl.endswith('/'): baseurl += '/'
            tracedir = urllib.parse.urljoin(baseurl, 'project/trace/')
            return tracedir
        elif service == 'rsync':
            raise Exception("Not implemented yet")
        else:
            assert(False)

    def _fetch(self, service, url):
        if service == 'http':
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as response:
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
        elif service == 'rsync':
            raise Exception("Not implemented yet")
        else:
            assert(False)

    def fetch_master(self, archive, service):
        if not self.supports(archive, service):
            raise Exception("Mirror does not support archive/service")
        if service == 'http':
            traceurl = urllib.parse.urljoin(self.get_tracedir(archive, service), 'master')
            return self._fetch(service, traceurl)

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

        if re.fullmatch('[a-zA-Z0-9._-]*', link) and link != "":
            return link
        else:
            return None

    def list_tracefiles(self, archive, service):
        if not self.supports(archive, service):
            raise Exception("Mirror does not support archive/service")
        if service == 'http':
            tracedir = self.get_tracedir(archive, service)
            data = self._fetch(service, tracedir)

            soup = BeautifulSoup(data)
            links = soup.find_all('a')
            links = filter(lambda x: 'href' in x.attrs, links)
            links = map(lambda x: Mirror._clean_link(x.get('href'), tracedir), links)
            tracefiles = filter(lambda x: x is not None, links)
            tracefiles = self._filter_tracefilenames(tracefiles)
            return sorted(tracefiles)

    @staticmethod
    def parse_tracefile(contents):
        try:
            lines = contents.decode('utf-8').split('\n')
            first = lines.pop(0)
            ts = dateutil.parser.parse(first)
            return ts
        except:
            return None

    @staticmethod
    def check_round_robin(hostname, service):
        warnings = []

        try:
            resultset = socket.getaddrinfo(hostname, service, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            return ["Could not resolve hostname."]

        per_family = {}
        for family, _, _, _, sockaddr in resultset:
            addr = sockaddr[0]
            if family in per_family:
                per_family[family] = 1
            else:
                per_family[family] = 0

        if sum(per_family.values()) > 0:
            return ["site has multiple address record for one family"]
        else:
            return []

class Mirrors:
    MAX_FETCHERS = 32
    MAX_QUEUE_SIZE = MAX_FETCHERS*4

    def __init__(self, masterlist):
        # self.mirrors = {site: Mirror(masterlist[site]) for site in masterlist}
        self.mirrors = OrderedDict()
        for site in masterlist:
            self.mirrors[site] = Mirror(masterlist[site])
        self._cleanup()

    def _cleanup(self):
        pass
    # This code drops hosts that have Includes:, adding them as Alias to the include-target
    #    seen_in_includes = {}
    #    has_includes = OrderedDict()
    #    for site in self.mirrors:
    #        mirror = self.mirrors[site]
    #        if len(mirror.includes) == 0: continue
    #        has_includes[site] = True
    #
    #        broken_includes = []
    #        for i in mirror.includes:
    #            if not i in self.mirrors:
    #                print("Warning:", site, "includes unknown mirror", i, file=sys.stderr)
    #                broken_includes.append(i)
    #                continue
    #
    #            if not i in seen_in_includes: seen_in_includes[i] = 0
    #            seen_in_includes[i] += 1
    #        for i in broken_includes:
    #            mirror.includes.remove(i)
    #
    #    # Trickle includes down the tree
    #    made_progress = True
    #    while made_progress:
    #        made_progress = False
    #        remaining = OrderedDict()
    #        for site in has_includes:
    #            if seen_in_includes.get(site, 0) > 0:
    #                remaining[site] = True
    #                continue
    #            made_progress = True
    #
    #            mirror = self.mirrors[site]
    #            for i in mirror.includes:
    #                seen_in_includes[i] -= 1
    #                assert(seen_in_includes[i] >= 0)
    #                self.mirrors[i].alias.add(site)
    #            del self.mirrors[site]
    #        has_includes = remaining
    #
    #    remaining_cnt = sum(seen_in_includes.values())
    #    assert( (remaining_cnt == 0) == (len(has_includes) == 0) )
    #    if remaining_cnt > 0:
    #        print("Warning: Loops in include-hierarchy involving", ', '.join(remaining.keys()), file=sys.stderr)

    @staticmethod
    def _check_all_one_mirror(mirror, archive, service):
        result = {'mirror': mirror, 'warnings': []}
        try:
            tf = mirror.fetch_master(archive, service)
            traces = mirror.list_tracefiles(archive, service)
            result['trace-master-timestamp'] = Mirror.parse_tracefile(tf)

            if result['trace-master-timestamp']:
                result['success'] = True
                result['message'] = "Master tracefile is from " + result['trace-master-timestamp'].isoformat()
                result['traces'] = traces
            else:
                result['success'] = False
                result['message'] = "Invalid tracefile"

            result['warnings'] += Mirror.check_round_robin(mirror.site, service)
        except MirrorFailureException as e:
            result['success'] = False
            result['message'] = e.message
        return result

    @staticmethod
    def _check_all_launcher(result_queue, archive, service, mirrors):
        pool = Pool(processes=Mirrors.MAX_FETCHERS)
        for _, m in mirrors.items():
            if m.supports('Archive', 'http'):
                async_result = pool.apply_async(Mirrors._check_all_one_mirror, [m, archive, service])
                result_queue.put(async_result)
        result_queue.put(None)

    def check_all(self, archive, service):
        result_queue = queue.Queue(self.MAX_QUEUE_SIZE)
        t = threading.Thread(target=self._check_all_launcher, args=[result_queue, archive, service, self.mirrors], daemon=True)
        t.start()

        result = {}
        while True:
            element = result_queue.get()
            result_queue.task_done()

            if element is None: break
            res = element.get()
            yield res

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('masterlist', help='Mirrors.masterlist')
    args = parser.parse_args()

    masterlist = Masterlist(args.masterlist).entries
    mirrors = Mirrors(masterlist)

    #for _, m in mirrors.mirrors.items():
    #    print('**Site:', m.site, m.archives)
    #    if m.supports('Archive', 'http'):
    #        try:
    #            print(m.fetch_master('Archive', 'http'))
    #        except MirrorFailureException as e:
    #            print("Failed:", e.message)
    #    #e.fetch_traces()
    check_results = mirrors.check_all('Archive', 'http')
    for r in check_results:
        m = r['message']
        if len(r['warnings']) > 0:
            m += ' ' + ', '.join(r['warnings'])
        print('**Site', r['mirror'].site, ' - ', r['success'], m)
