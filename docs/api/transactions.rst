.. _api_transactions:

Transactions
============

Transactions are the main building blocks for tasks. You will use them to define what a task
should do on the remote host. Every transaction will print a short summary of the changes it made to the remote.
Below you will find a list of predefined transactions you can use.

Basic transactions
------------------

.. autosummary::
    simple_automation.transactions.basic.directory
    simple_automation.transactions.basic.directory_all
    simple_automation.transactions.basic.template
    simple_automation.transactions.basic.template_all
    simple_automation.transactions.basic.copy
    simple_automation.transactions.basic.copy_all
    simple_automation.transactions.basic.save_output

Git transactions
----------------

.. autosummary::
    simple_automation.transactions.git.checkout
    simple_automation.transactions.git.clone

Package transactions
--------------------

By default, there is rudimentary support for installing packages via ``apt``, ``pacman`` and ``portage``.

.. autosummary::
    simple_automation.transactions.package.apt.package
    simple_automation.transactions.package.pacman.package
    simple_automation.transactions.package.portage.package
