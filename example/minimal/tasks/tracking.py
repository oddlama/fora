import simple_automation

# Derived task that specifies repository url and destination
class TrackedTask(simple_automation.TrackedTask):
    tracking_repo_url = "{{ tracking.repo_url }}"
    tracking_local_dst = "/var/lib/root/tracking"
