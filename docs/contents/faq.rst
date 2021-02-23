Frequently Asked Questions
==========================

.. contents::
    :local:

Only show what changes would be applied to the remote systems
-------------------------------------------------------------

Use the ``--pretend`` command line parameter.

Errors when trying to track files
---------------------------------

Have you made sure that your tracking repository already has a commit?
This is necessary because only then there will be a tracked branch when
checking it out initially. If you delete the repository on your remote
host, it will be checked out again the next time.
