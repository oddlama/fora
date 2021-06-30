#!/bin/bash
pylint simple_automation --disable=C0301,C0103,R0902,R0903,R0913,R0914
mypy simple_automation
