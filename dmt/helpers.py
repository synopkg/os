#!/usr/bin/python3

import urllib


if __name__ == '__main__' and __package__ is None:
    from pathlib import Path
    top = Path(__file__).resolve().parents[1]
    sys.path.append(str(top))
    import dmt.helpers
    __package__ = 'dmt.helpers'

def get_tracedir(site):
    baseurl = urllib.parse.urljoin("http://" + site['name'], site['http_path'])
    if not baseurl.endswith('/'): baseurl += '/'
    tracedir = urllib.parse.urljoin(baseurl, 'project/trace/')
    return tracedir

