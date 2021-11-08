#!/bin/bash
pylint simple_automation --ignore=tunnel_dispatcher_minified.py --disable=C0301,C0103,R0902,R0903,R0913,R0914,duplicate-code"${1:+,}$1"
mypy simple_automation
