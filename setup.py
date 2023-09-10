#!/usr/bin/env python3

from setuptools import setup

setup(
    name="nrrdnote",
    version="0.0.2",
    description="Terminal-based notes management for nerds.",
    author="Sean O'Connell",
    author_email="sean@sdoconnell.net",
    url="https://github.com/sdoconnell/nrrdnote",
    license="MIT",
    python_requires='>=3.8',
    packages=['nrrdnote'],
    install_requires=[
        'PyYAML>=5.4',
        'Rich>=10.2',
        'watchdog>=2.1',
        'python-dateutil>=2.8',
        'tzlocal>=2.1'
    ],
    include_package_data=True,
    entry_points={
        "console_scripts": "nrrdnote=nrrdnote.nrrdnote:main"
    },
    keywords='cli notes utility',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Topic :: Office/Business',
        'Topic :: Utilities'
    ]
)
