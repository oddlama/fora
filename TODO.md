- better command output logging support
- automatic transaction diff output (e.g. template())
- automatic infrastructure to dot

- diff output on verbose mode
- easy instanciatable transaction templates. i.e. some transactions as a new transaction. shows differently and can have a name i dunno.
- move away from wierd jinja global variables and encourage python variable use. jinja2 can access those too

- Make failing transactions more readable
- A way to better create group executed task
- Easier task dispatching
- Way to merge variables
- Jinja2 filters
- Refine architecture page
- Include comprehensive example
- Step by step guide, simplify or merge others.

* transactions.basic.user
* transactions.basic.group
* transactions.systemd

new transaction tutorial

Building your own transaction
-----------------------------

You can encapsulate functionality by writing your own transactions If you want to extend

.. hint::

    We strongly recommend looking at the implementation for some of the basic
    builtin transactions. You might be able to reuse some of the already implemented
    convenience functions to query remote state.
