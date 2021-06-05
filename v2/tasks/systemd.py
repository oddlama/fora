from simple_automation.transactions import git
from simple_automation.transactions.basic import template, directory

from tasks.tracking import TrackedTask

class SetupSystemd(TrackedTask):
    identifier = "systemd"
    description = "Configures systemd"
    tracking_paths = ["/etc/systemd"]

    def run(self, context):
        with context.defaults(dir_mode=0o755, file_mode=0o644):
            # TODO
            #if len(context.vars.get('system.network_device_names')) > 0:
            #    template(context, src="templates/systemd/10-persistent-net.rules.j2", dst="/etc/udev/rules.d/10-persistent-net.rules")

            template(context, src="templates/systemd/coredump.conf.j2",  dst="/etc/systemd/coredump.conf",  mode=0o640, group='systemd-coredump')
            template(context, src="templates/systemd/journald.conf.j2",  dst="/etc/systemd/journald.conf",  mode=0o640, group='systemd-journal')
            template(context, src="templates/systemd/logind.conf.j2",    dst="/etc/systemd/logind.conf")
            template(context, src="templates/systemd/networkd.conf.j2",  dst="/etc/systemd/networkd.conf",  mode=0o640, group='systemd-network')
            template(context, src="templates/systemd/resolved.conf.j2",  dst="/etc/systemd/resolved.conf",  mode=0o640, group='systemd-resolve')
            template(context, src="templates/systemd/sleep.conf.j2",     dst="/etc/systemd/sleep.conf")
            template(context, src="templates/systemd/system.conf.j2",    dst="/etc/systemd/system.conf")
            template(context, src="templates/systemd/timesyncd.conf.j2", dst="/etc/systemd/timesyncd.conf", mode=0o640, group='systemd-timesync')
            template(context, src="templates/systemd/user.conf.j2",      dst="/etc/systemd/user.conf")

        systemd.timezone(context, timezone="{{ system.timezone }}")
        systemd.hwclock(context, type="utc")
        systemd.keymap(context, keymap="{{ system.keymap }}")
        systemd.locale(context, locale="{{ system.locale }}")
        systemd.ntp(context, enable=True)
