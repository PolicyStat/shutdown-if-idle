#! /bin/sh

nosetests --verbose --with-doctest --with-coverage shutdown_if_no_usage.py $@ && find -name '*.py' | xargs flake8
