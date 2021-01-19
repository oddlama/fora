from simple_automation import Task
from simple_automation.actions import git
from simple_automation.actions.basic import template, create_dir
from simple_automation.actions.package import portage


class TaskZsh(Task):
    identifier = "zsh"
    track = ["/etc/zsh"]

    def set_defaults(self, manager):
        manager.set(f"tasks.{self.identifier}.install", True)

    def run(self, context):
        # Set defaults
        context.defaults(dir_mode=0o755, file_mode=0o644, owner="root", group="root")
        context.umask(0o022)

        # Install zsh
        portage.package(context, name="app-shells/zsh", state="present")

        # Clone or update plugin repositories
        git.clone(context,
                  url="https://github.com/romkatv/powerlevel10k",
                  dst="/usr/share/zsh/repos/romkatv/powerlevel10k",
                  update=True, depth=1)
        git.clone(context,
                  url="https://github.com/Aloxaf/fzf-tab",
                  dst="/usr/share/zsh/repos/Aloxaf/fzf-tab",
                  update=True)
        git.clone(context,
                  url="https://github.com/zdharma/fast-syntax-highlighting",
                  dst="/usr/share/zsh/repos/zdharma/fast-syntax-highlighting",
                  update=True)

        # Copy configuration
        create_dir(context, path="/etc/zsh")
        template(context, src="zsh/zshrc.j2", dst="/etc/zsh/zshrc")
        template(context, src="zsh/zprofile.j2", dst="/etc/zsh/zprofile")
