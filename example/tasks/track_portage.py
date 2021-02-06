from simple_automation import TrackedTask
from simple_automation.transactions import git
from simple_automation.transactions.basic import template, directory
from simple_automation.transactions.package import portage

from tasks.tracking import TrackedTask

class TaskTrackPortage(TrackedTask):
    identifier = "track portage"
    description = "Tracks portage settings for this system"
    tracking_paths = ["/etc/portage", "/var/lib/portage/world", "/var/lib/portage/world_sets"]
