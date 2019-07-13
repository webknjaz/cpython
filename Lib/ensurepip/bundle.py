"""Download Pip and setuptools dists for bundling."""

import sys

from ._bundler import _ensure_wheels_are_downloaded


if __name__ == '__main__':
    _ensure_wheels_are_downloaded(verbosity='-v' in sys.argv)
