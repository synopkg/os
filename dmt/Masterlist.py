#!/usr/bin/python3

# Copyright 2016, 2017 Peter Palfrader
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Load a debian Mirrors.masterlist

import email

class MasterlistEntry:
    def __init__(self, lines):
        self.data = email.message_from_string('\n'.join(lines))
    def __str__(self):
        return self.data.__str__()
    def __getitem__(self, key):
        return self.data[key]
    def __contains__(self, key):
        return key in self.data

    @staticmethod
    def from_fh(fh):
        m = []
        for line in fh:
            line = line.strip()
            if line == "":
                if len(m) > 0: break
            else:
                m.append(line)

        if len(m) > 0: return MasterlistEntry(m)
        return None

class Masterlist:
    def __init__(self, fn):
        self.entries = self._load_entries(fn)

    def _load_entries(self, fn):
        entries = []
        with open(fn, encoding='utf-8') as masterlist:
            while True:
                e = MasterlistEntry.from_fh(masterlist)
                if e is None: break
                entries.append(e)
        return entries

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('masterlist', help='Mirrors.masterlist')
    args = parser.parse_args()

    masterlist = Masterlist(args.masterlist)
    for e in masterlist.entries:
        print('Site:', e['Site'])
        #e.fetch_traces()
