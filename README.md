# simple_automation

An ansible-inspired infrastructure and configuration management tool, but with a focus on minimalism and simplicity.
Intended uses are small-scale machine administation, system configuration tracking, or even just dotfiles management.

The main features are:

* Simple, not complex.
* Minimal dependencies:
  - Uses jinja2 for templating
  - System command 'gpg' is used for gpg encrypted vaults.
  - pycryptodome is used (scrypt + AES-256-GCM) for symmetric vault encryption (not required if feature not used).
* Minimal. This library consists of just 1300 LoC.
* Supports encrypted variable storage.
* Executes commands over a single ssh connection (→ fast execution)
* Concicse, readable output (and optionally more verbose but still compact)
* Easily keep track of your system's state by automatically committing changed files to a git repository.
* Use python to write your configuration and don't be limited by a domain specific language.
* Uses a single ssh connection per host.

Drawbacks:

* Currently for simplicity there is no way to become a privileged user on a host.
  That means if you want to do things as root on a machine, you need an ssh connection for the root user.

## Minimal Example (Configure zsh)

...

## Minimal Example (Tracking only)

## Good to know

* Tasks have an implicit enabled variable
* Context defaults. Best practice: Always set them yourself.
  context.defaults(user="root", umask=0o077, dir_mode=0o700, file_mode=0o600,
                   owner="root", group="root")
* Writing your own transactions.
* Which transactions are already avaiable?
* Your tracking repo must already have a commit!
* Manage packages on hosts with different distributions
* Conditionals based on transaction results
* Using vault variables
* Check if host is in group: `if my_laptop in desktops:` or `if desktops in my_laptop.groups`.
* Only track a directory without doing anything else. Useful for externally modified directories,
  or even to use this just for system tracking.
* Variable inheritance order
* Special jinja2 variables (simple_automation_managed, context)
* Secrets: Don't put secrets where they are printed. Ideally only in templated files, then you are safe.
* host.set("var", "value") vs host.var = "value".
  You may also use custom python variables and object in templates. These
  have the advantage that they are not merged into the global variables
  dictionary. You can access them later in any templated string via {{ context.host.<var> }}.
* Defer variable definition to vault, by doing set("var", vault.get("var")) convenience funciton maybe? manager.defer("var", vault)
* Vault types: Keyfile, keyfile from ENV example, Symmetric key ask, symm from env, gpg unlock with keyid.
* Base directory is deduced from the location of the main started script. To override, use Manager ctor param
* Unlock multiple vaults with one key: getpass before, use key= param. Downside: will need to unlock every time not only when needed
