#!/usr/bin/python3

from collections import OrderedDict
import sys
import urllib
import urllib.request

from Masterlist import Masterlist

class MirrorFailureException(Exception):
    def __init__(self, e):
        self.message = e.reason
        self.origin = e

class Mirror:
    TIMEOUT = 5
    ARCHIVES = ["Archive", "CDImage", "Debug", "Old", "Ports", "Security"]
    PROTOS = ["http", "rsync"]

    def __init__(self, entry):
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

    def supports(self, archive, proto):
        return (archive+"-"+proto) in self.entry

    def _learn_archives(self):
        self.archives = set()
        for a in self.ARCHIVES:
            for p in self.PROTOS:
                if self.supports(a, p):
                    self.archives.add(a)
                    continue
        if len(self.archives) == 0:
            print("Warning:", self.site, "no archives", file=sys.stderr)

    def fetch_master(self, archive, proto):
        if not self.supports(archive, proto):
            raise Exception("Mirror does not support archive/proto")
        if proto == 'http':
            baseurl = urllib.parse.urljoin("http://" + self.site, self.entry['Archive-http'] + '/')
            traceurl = urllib.parse.urljoin(baseurl, 'project/trace/master')

            try:
                with urllib.request.urlopen(traceurl, timeout=self.TIMEOUT) as response:
                    data = response.read()
                    return data
            except urllib.error.URLError as e:
                raise MirrorFailureException(e)

        elif proto == 'rsync':
            raise Exception("Not implemented yet")
        else:
            assert(False)

class Mirrors:
    def __init__(self, masterlist):
        # self.mirrors = {site: Mirror(masterlist[site]) for site in masterlist}
        self.mirrors = OrderedDict()
        for site in masterlist:
            self.mirrors[site] = Mirror(masterlist[site])
        self._cleanup()

    def _cleanup(self):
        seen_in_includes = {}
        has_includes = OrderedDict()
        for site in self.mirrors:
            mirror = self.mirrors[site]
            if len(mirror.includes) == 0: continue
            has_includes[site] = True

            for i in mirror.includes:
                if not i in self.mirrors:
                    print("Warning:", site, "includes unknown mirror", i, file=sys.stderr)
                    mirror.includes.remove(i)

                if not i in seen_in_includes: seen_in_includes[i] = 0
                seen_in_includes[i] += 1

        # Trickle includes down the tree
        made_progress = True
        while made_progress:
            made_progress = False
            remaining = OrderedDict()
            for site in has_includes:
                if seen_in_includes.get(site, 0) > 0:
                    remaining[site] = True
                    continue
                made_progress = True

                mirror = self.mirrors[site]
                for i in mirror.includes:
                    seen_in_includes[i] -= 1
                    assert(seen_in_includes[i] >= 0)
                    self.mirrors[i].alias.add(site)
                del self.mirrors[site]
            has_includes = remaining

        remaining_cnt = sum(seen_in_includes.values())
        assert( (remaining_cnt == 0) == (len(has_includes) == 0) )
        if remaining_cnt > 0:
            print("Warning: Loops in include-hierarchy involving", ', '.join(remaining.keys()), file=sys.stderr)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('masterlist', help='Mirrors.masterlist')
    args = parser.parse_args()

    masterlist = Masterlist(args.masterlist).entries
    mirrors = Mirrors(masterlist)

    for _, m in mirrors.mirrors.items():
        print('**Site:', m.site, m.archives)
        if m.supports('Archive', 'http'):
            try:
                print(m.fetch_master('Archive', 'http'))
            except MirrorFailureException as e:
                print("Failed:", e.message)
        #e.fetch_traces()
