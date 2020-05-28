#!/bin/bash
read pkg v < <(poetry version)
initfn=${pkg}/__init__.py
cat >${initfn} <<EOIP
"""$pkg"""
__version__ = "$v"
EOIP
git add ${initfn}
