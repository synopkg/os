#!/usr/bin/python3

import argparse
import datetime
import itertools
import json
from sqlalchemy import desc, or_
import sys

if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.HierarchyGenerator
    __package__ = 'dmt.HierarchyGenerator'

import dmt.db as db
import dmt.helpers as helpers
from dmt.BasePageGenerator import BasePageGenerator


OUTFILE='mirror-hierarchy.html'
RECENTCHANGE_HOURS=24

def powersetish(iterable):
    """return the powerset of iterable, from longest subset to smallest
    """
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s), -1, -1))

def iter_endcheck(iterable):
    """iterate over an iterable, and yield tuples of elements and if this is the last element
    """
    it = iter(iterable)
    prev = next(it)
    for val in it:
        yield prev, False
        prev = val
    yield prev, True


class HierarchyNode:
    def __init__(self, labels, parent):
        assert(isinstance(labels, tuple))
        self.names = []
        self.labels = labels
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)
            self.labelsdiff = set(labels) - set(parent.labels)
            #print("Parent is ", parent.labels, "and has children", (', '.join(str(x.labelsdiff) for x in parent.children)))
        else:
            self.labelsdiff = set(labels)

class HierarchyTree:
    def __init__(self):
        self.nodes_by_labels = {}

        root = HierarchyNode((), None)
        self.root = root
        root.parent = root
        self.nodes_by_labels[root.labels] = root

    def _find_position(self, labels):
        for s in powersetish(labels):
            if s in self.nodes_by_labels:
                return self.nodes_by_labels[s]
        raise Exception("We should have found at least the root by now.  (Was looking for "+str(labels)+")")

    def _add_node(self, name, labels):
        #print("Adding node", name)
        if labels in self.nodes_by_labels:
            node = self.nodes_by_labels[labels]
        else:
            parent = self._find_position(labels)
            assert(parent is not None)
            assert(parent.labels != labels)

            node = HierarchyNode(labels, parent)
            self.nodes_by_labels[labels] = node

        node.names.append(name)
        return node

    def add_nodes(self, tuples):
        #for name, labels in sorted(tuples, key=lambda t: [len(t[1])] + list(reversed(t[0].split('.')))):
        for name, labels in sorted(tuples, key=lambda t: len(t[1])):
            #print("Calling add_node for", name, "with lables", labels)
            n = self._add_node(name, labels)

    @staticmethod
    def _str_subtree(prefix, last, node):
        yield prefix+('+','\\')[last]+'-- '+str(node.labelsdiff)
        prefix = prefix+('|',' ')[last]+'  '

        for name in node.names:
            yield prefix+(' ','|')[len(node.children)>0] +'    + '+name
        for c, last in iter_endcheck(node.children):
            yield from HierarchyTree._str_subtree(prefix, last, c)

    def __str__(self):
        return "\n".join(self._str_subtree("", True, self.root))


    @staticmethod
    def nodelabeldomain_comparator(x):
        if len(x.labelsdiff) == 0: return None
        hostname = sorted(x.labelsdiff)[0]
        return helpers.hostname_comparator(hostname)

    @staticmethod
    def _table_subtree(node):
        #print(node.labels, "has children", (', '.join(str(x.labelsdiff) for x in node.children)))
        child_cells = list(itertools.chain.from_iterable(HierarchyTree._table_subtree(c) for c in sorted(node.children, key=HierarchyTree.nodelabeldomain_comparator)))
        number_terminals = sum(c['celltype'] == 'terminal' for c in child_cells)

        cell = { 'celltype': 'middle',
                 'entrytype': 'labels-only',
                 'labels': sorted(node.labelsdiff, key=helpers.hostname_comparator),
                 'width' : len(node.labelsdiff)
               }

        names = sorted(node.names)
        if len(node.labelsdiff) == 1:
            nodename = next(iter(node.labelsdiff)) # get the only element from the set
            if nodename in names:
                names.remove(nodename)
                cell['entrytype'] = 'site'
                cell['name'] = nodename
                cell['main'] = True
                cell['celltype'] = ['middle', 'terminal'][len(names) == 0 and number_terminals == 0]
        cell['height'] = max(len(names) + number_terminals, 1)
        yield cell

        for name in names:
            cell = { 'celltype': 'terminal',
                     'entrytype': 'site',
                     'name': name,
                     'main': False,
                     'height': 1,
                     'width' : 1,
                   }
            yield cell
        yield from child_cells

    def table(self):
        yield from self._table_subtree(self.root)


class MirrorHierarchy:
    def __init__(self, mirrors):
        self.mirrors = mirrors

        sitelabels = [(site, tuple(mirrors[site]['traces'])) for site in mirrors]

        self.tree = HierarchyTree()
        self.tree.add_nodes(sitelabels)
        #print(t)
        #for x in t.table():
        #    print(x)
    def get_cells(self):
        for c in self.tree.table():
            if c['entrytype'] == 'site':
                c['mirror'] = self.mirrors[c['name']]
            yield c

def get_traceset_changes(session, site_id, traces_last_change_cutoff):
    results = session.query(db.Traceset). \
              filter_by(site_id = site_id). \
              filter(db.Traceset.traceset.isnot(None)). \
              join(db.Checkrun). \
              filter(db.Checkrun.timestamp >= traces_last_change_cutoff). \
              order_by(db.Checkrun.timestamp)
    #cnt = len(list(itertools.groupby(x.traceset for x in results))) - 1
    it = iter(results)
    last_ts = None
    try:
        last_ts = next(it)
    except StopIteration:
        pass
    cnt = 0
    last_change = None
    for i in it:
        if last_ts.traceset != i.traceset:
            last_change = i.checkrun.timestamp
            cnt += 1
        last_ts = i

    res = { 'cnt': cnt,
            'last_change': last_change,
            'most_recent': last_ts.traceset if not last_ts is None else None,
          }
    return res

class Generator(BasePageGenerator):
    def __init__(self, outfile = OUTFILE, textonly = False, recent_hours = RECENTCHANGE_HOURS, **kwargs):
        super().__init__(**kwargs)
        self.outfile = outfile
        self.recent_hours = recent_hours
        self.textonly = textonly

    def run(self):
        now = datetime.datetime.now()
        traces_last_change_cutoff = now - datetime.timedelta(hours=self.recent_hours)
        ftpmastertrace = helpers.get_ftpmaster_trace(self.session)
        if ftpmastertrace is None: ftpmastertrace = now
        checkrun = self.session.query(db.Checkrun).order_by(desc(db.Checkrun.timestamp)).first()

        mirrors = {}
        results = self.session.query(db.Site, db.Traceset, db.Mastertrace). \
                  outerjoin(db.Traceset).\
                  filter(or_(db.Traceset.checkrun_id == None,
                             db.Traceset.checkrun_id == checkrun.id)).\
                  outerjoin(db.Mastertrace).\
                  filter(or_(db.Mastertrace.checkrun_id == None,
                             db.Mastertrace.checkrun_id == checkrun.id))
        for site, traceset, mastertrace in results:
            x = {}
            x['site'] = site.__dict__
            x['site']['trace_url'] = helpers.get_tracedir(x['site'])
            x['traces'] = []
            error = []
            x['mastertrace'] = { 'agegroup': 'unknown' }

            if not traceset is None:
                error.append(traceset.error)
            else:
                error.append("No traceset information")

            x['traceset_changes'] = get_traceset_changes(self.session, site.id, traces_last_change_cutoff)

            # use most recent traceset, ignoring the ones from the most recent run if there was an error
            x['traceset'] = x['traceset_changes']['most_recent']

            if not x['traceset'] is None:
                    traces = json.loads(x['traceset'])
                    if not isinstance(traces, list):
                        raise Exception("traces information for "+site+" is not a list")
                    if 'master' in traces: traces.remove('master')
                    x['traces'] = traces

            if not mastertrace is None:
                x['mastertrace'].update(mastertrace.__dict__)
                error.append(mastertrace.error)
            else:
                error.append("No mastertracefile information")

            x['error'] = "; ".join(filter(lambda x: x is not None, error))
            if x['error'] == "": x['error'] = None
            mirrors[site.name] = x
        hierarchy =  MirrorHierarchy(mirrors)

        if self.textonly:
            print(hierarchy.tree)
            #for x in hierarchy.get_cells():
            #    print(x)
        else:
            cells = list(hierarchy.get_cells())
            del cells[0]
            cells[-1]['last'] = True

            context = {
                'now': now,
                'last_run': checkrun.timestamp,
                'ftpmastertrace': ftpmastertrace,
                'hierarchy_table': cells,
                'recent_hours': self.recent_hours,
            }
            template = self.tmplenv.get_template('mirror-hierarchy.html')
            template.stream(context).dump(self.outfile, errors='strict')



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dburl', help='database', default=db.MirrorDB.DBURL)
    parser.add_argument('--templatedir', help='template directory', default='templates')
    parser.add_argument('--textonly', help='only write text to stdout', default=False, action='store_true')
    parser.add_argument('--recent-hours', help='flag mirrors that changed hierarchy within the last <x> hours', type=float, default=RECENTCHANGE_HOURS)
    parser.add_argument('--outfile', help='output-file', default=OUTFILE, type=argparse.FileType('w'))
    args = parser.parse_args()
    Generator(**args.__dict__).run()
