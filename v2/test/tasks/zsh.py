#from simple_automation.transactions import git
#from simple_automation.transactions.basic import template, directory
#from simple_automation.transactions.package import portage

from simple_automation.task import this
this.description("")

from simple_automation import host, task
from simple_automation.operations import files, portage

with task.status("Install zsh"):
    # ...

with host.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
    # Copy configuration
    files.directory(name="", path="/etc/zsh")
    files.template(name="", src="templates/zsh/zshrc.j2", dst="/etc/zsh/zshrc")
    files.template(name="", src="templates/zsh/zprofile.j2", dst="/etc/zsh/zprofile")


print("loading task zsh.py")
description = "Installs zsh and a global zsh configuration"
tracking_paths = ["/etc/zsh"]

def run(host):
    #portage.package(atom="app-shells/zsh", oneshot=True)
    with host.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
        pass
    ## Install zsh
    #portage.package(context, atom="app-shells/zsh", oneshot=True)

    #with context.defaults(umask=0o022, dir_mode=0o755, file_mode=0o644):
    #    # Clone or update plugin repositories
    #    git.checkout(context,
    #                 url="https://github.com/romkatv/powerlevel10k",
    #                 dst="/usr/share/zsh/repos/romkatv/powerlevel10k")
    #    git.checkout(context,
    #                 url="https://github.com/Aloxaf/fzf-tab",
    #                 dst="/usr/share/zsh/repos/Aloxaf/fzf-tab")
    #    git.checkout(context,
    #                 url="https://github.com/zdharma/fast-syntax-highlighting",
    #                 dst="/usr/share/zsh/repos/zdharma/fast-syntax-highlighting")

    #    # Copy configuration
    #    directory(context, path="/etc/zsh")
    #    template(context, src="templates/zsh/zshrc.j2", dst="/etc/zsh/zshrc")
    #    template(context, src="templates/zsh/zprofile.j2", dst="/etc/zsh/zprofile")
