#!/bin/sh

set -u

WEBSITE_DIR=/var/tmp/website
export PYTHONPATH=$WEBSITE_DIR/lib/python2.4/site-packages/:$PYTHONPATH

mkdir -p $WEBSITE_DIR
cd $WEBSITE_DIR

standard_setup ()
{
    # $1 = source URL
    # $2 = untarred directory
    curl $1 | tar zxv && cd $2 && python setup.py install --prefix=/var/tmp/website
    cd $WEBSITE_DIR
}

curl http://mulletron.uwcs.co.uk/django.tar | tar xv
curl http://mulletron.uwcs.co.uk/python26.tar | tar xv
standard_setup http://pypi.python.org/packages/source/M/Markdown/markdown-1.7.tar.gz markdown-1.7
wget http://docutils.sourceforge.net/docutils-snapshot.tgz && tar zxvf docutils-snapshot.tgz && cd docutils && python setup.py install --prefix=/var/tmp/website
cd $WEBSITE_DIR

