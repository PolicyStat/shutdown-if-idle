#! /bin/sh

nosetests --verbose --with-doctest --with-coverage --cover-package shutdown_if_idle $@ && find -name '*.py' | xargs flake8
