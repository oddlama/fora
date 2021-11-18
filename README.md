- declarative.

## Why

- Ansible uses yaml, which is not very well suited for more complex workflows and not easily readble and has many pitfalls.
  I know python, so no need for new DSL. Often very surprising things happen, which I don't like. Give me an API and I'm happy.
- Ansible is slow. This is fast. I want a serverless system that acts over ssh.
- Because I could.


## Features

Trivia
------

- All modules come after "all" by default.
- You can overwrite the all module to define global variables.
- Variable starting with _ are private to the module and won't be "inherited"
- Some variables are reserved (everything that directly belongs to a module as set in the meta, list of reserved variables is availabe e.g. in HostType)
- Scripts are instanciated for each execution
- fora_managed exists implicitly on the all group
