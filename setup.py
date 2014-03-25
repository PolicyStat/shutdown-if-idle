#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages  # noqa

rel_file = lambda *args: os.path.join(
    os.path.dirname(
        os.path.abspath(__file__),
    ), *args)


def get_file(filename):
    with open(rel_file(filename)) as f:
        return f.read()


def get_description():
    return get_file('README.md')

setup(
    name="shutdown_if_idle",
    version="0.0.1",
    description="Shutdown machine if considered idle",
    author="Jason Ward",
    author_email="jason.louard.ward@gmail.com",
    url="http://github.com/PolicyStat/shutdown-if-idle/",
    platforms=["any"],
    license="BSD",
    packages=find_packages(),
    scripts=[],
    zip_safe=False,
    install_requires=[],
    cmdclass={},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: XML",
    ],
    long_description=get_description(),
    entry_points={
        'console_scripts': [
            'shutdown-if-idle = shutdown_if_no_usage:entry_point',
        ],
    },
)
