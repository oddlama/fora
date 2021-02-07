from simple_automation.transactions import git
from simple_automation.transactions.basic import template, directory
from simple_automation.transactions.package import portage

from tasks.tracking import TrackedTask

class TaskZsh(TrackedTask):
    identifier = "zsh"
    description = "Installs zsh and a global zsh configuration"
    tracking_paths = ["/etc/zsh"]

    def run(self, context):
        # Set defaults
        context.defaults(user="root", umask=0o022, dir_mode=0o755, file_mode=0o644,
                         owner="root", group="root")

        # Install zsh
        portage.package(context, atom="app-shells/zsh", oneshot=True)

        # Clone or update plugin repositories
        git.checkout(context,
                  url="https://github.com/romkatv/powerlevel10k",
                  dst="/usr/share/zsh/repos/romkatv/powerlevel10k")
        git.checkout(context,
                  url="https://github.com/Aloxaf/fzf-tab",
                  dst="/usr/share/zsh/repos/Aloxaf/fzf-tab")
        git.checkout(context,
                  url="https://github.com/zdharma/fast-syntax-highlighting",
                  dst="/usr/share/zsh/repos/zdharma/fast-syntax-highlighting")

        # Copy configuration
        directory(context, path="/etc/zsh")
        template(context, src="templates/zsh/zshrc.j2", dst="/etc/zsh/zshrc")
        template(context, src="templates/zsh/zprofile.j2", dst="/etc/zsh/zprofile")
