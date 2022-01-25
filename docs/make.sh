#!/bin/bash

rm -rf _build source
sphinx-apidoc -o source ../src/fora --separate
make dirhtml
