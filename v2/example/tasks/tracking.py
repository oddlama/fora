import simple_automation

from simple_automation.transactions.basic import template, directory, save_output, user
from simple_automation.transactions.package import portage

class SetupTracking(simple_automation.Task):
    identifier = "setup_tracking"
    description = "Sets up access to the tracking repository"

    def run(self, context):
        # Create tracking user
        user(context, name="tracking", home="{{ tracking.home }}")

        # Copy tracking ssh key
        with context.defaults(owner="tracking", group="tracking"):
            directory(context, path="{{ tracking.home }}/.ssh")
            template(context, content="{{ tracking.id_ed25519 }}", dst="{{ tracking.home }}/.ssh/id_ed25519")
            template(context, content="{{ tracking.id_ed25519_pub }}", dst="{{ tracking.home }}/.ssh/id_ed25519.pub")

# A base class for tracked tasks that specifies common
# meta settings about the tracking repository
class TrackedTask(simple_automation.TrackedTask):
    tracking_repo_url = "{{ tracking.repo_url }}"
    tracking_local_dst = "{{ tracking.home }}/repo"
    tracking_user = "tracking"
    tracking_group = "tracking"

class TrackPortage(TrackedTask):
    identifier = "track_portage"
    description = "Tracks portage settings"
    tracking_paths = ["/etc/portage", "/var/lib/portage/world", "/var/lib/portage/world_sets"]

class TrackInstalledPackages(TrackedTask):
    identifier = "track_installed_packages"
    description = "Tracks all installed packages"
    tracking_paths = ["{{ tracking.home }}/installed_packages"]

    def run(self, context):
        save_output(context, command=["qlist", "-CIv"],
                    dst="{{ tracking.home }}/installed_packages",
                    desc="Query installed packages")
