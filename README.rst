europe
======

|travis|

Toy Project


.. |travis| image:: https://travis-ci.org/zh0uquan/europe.svg?branch=master
           :target: https://travis-ci.org/zh0uquan/europe/
           :alt: "europe TravisCI build status"

PACKAGE TEST PHASE:

FOR EACH SUBPACKAGE:
    Also install them based on the tree

    RUN python setup.py install
    AND I NEED TO RELEASE --find-index?
    RUN pip-compile (dependencies) -> requirement.txt
    RUN pip install -r requirements.txt
    RUN pip-compile

    IN THE END, RUN PYTEST


REPO TEST PHASE:
    global compile -> detect
    run pytest
