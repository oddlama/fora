from simple_automation import TrackedTask
from simple_automation.transactions import git
from simple_automation.transactions.basic import template, directory, save_output
from simple_automation.transactions.package import portage

from tasks.tracking import TrackedTask

class TaskTrackPortage(TrackedTask):
    identifier = "track_portage"
    description = "Tracks portage settings"
    tracking_paths = ["/etc/portage", "/var/lib/portage/world", "/var/lib/portage/world_sets"]

class TaskTrackInstalledPackages(TrackedTask):
    identifier = "track_installed_packages"
    description = "Tracks all installed packages"
    tracking_paths = ["/var/lib/root/installed_packages"]

    def run(self, context):
        save_output(context, command=["qlist", "-CIv"],
                    dst="/var/lib/root/installed_packages",
                    desc="Query installed packages")
