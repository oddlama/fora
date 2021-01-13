from simple_automation import Task
from simple_automation.actions import Template


class TaskZsh(Task):
    track = ["/etc/zsh"]

    def run(self):
        pass
