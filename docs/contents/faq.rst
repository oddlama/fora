Frequently Asked Questions
==========================

.. contents::
    :local:

Only show what changes would be applied to the remote systems
-------------------------------------------------------------

Use the ``--pretend`` command line parameter.

Only run on some of the defined hosts
-------------------------------------

Use the ``--hosts`` command line parameter.

Errors when trying to track files
---------------------------------

Have you made sure that your tracking repository already has a commit?
This is necessary because only then there will be a tracked branch when
checking it out initially. If you delete the repository on your remote
host, it will be checked out again the next time.

Change ssh port / parameters for a host
---------------------------------------

You can customize the ssh connection options with :meth:`set_ssh_port() <simple_automation.host.Host.set_ssh_port>` and :meth:`set_ssh_opts() <simple_automation.host.Host.set_ssh_opts>`.

.. code-block:: python

    def register_inventory(self):
        my_host = self.manager.add_host("my_host", ssh_host="root@localhost")
        my_host.set_ssh_port(2222)
        my_host.set_ssh_opts(["-J", "jumphost@example.com"])
