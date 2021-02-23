#!/usr/bin/env python3

from simple_automation import run_inventory, Inventory, GpgVault
from tasks import TaskZsh, TaskTrackPortage, TaskTrackInstalledPackages

class MySite(Inventory):
    # -------- Register Tasks --------
    tasks = [TaskZsh, TaskTrackPortage, TaskTrackInstalledPackages]

    def register_vaults(self):
        # -------- Load vault --------
        self.vault = self.manager.add_vault(GpgVault, file="myvault.gpg", recipient="your_keyid_or_mail")

    def register_globals(self):
        # -------- Set global variables --------
        self.manager.copy("tracking.repo_url", self.vault)

    def register_inventory(self):
        # -------- Define Groups --------
        desktops = self.manager.add_group("desktops")

        # -------- Define Hosts --------
        my_laptop = self.manager.add_host("my_laptop", ssh_host="root@localhost")
        my_laptop.add_group(desktops)

    def run(self, context):
        context.run_task(TaskZsh)
        context.run_task(TaskTrackPortage)
        context.run_task(TaskTrackInstalledPackages)

# -------- Run the inventory --------
if __name__ == "__main__":
    run_inventory(MySite)
