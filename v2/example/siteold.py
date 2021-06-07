#!/usr/bin/env python3

from simple_automation import run_inventory, Inventory, GpgVault

from tasks.tracking import SetupTracking, TrackPortage, TrackInstalledPackages
from tasks.systemd import SetupSystemd
from tasks.zsh import SetupZsh

class Site(Inventory):
    # -------- Register Tasks --------
    tasks = [ SetupTracking
            , SetupSystemd
            , SetupZsh
            , TrackPortage
            , TrackInstalledPackages
            ]

    def register_vaults(self):
        # -------- Load vault --------
        self.vault = self.manager.add_vault(GpgVault, file="vault.gpg", recipient="680AA614E988DE3E84E0DEFA503F6C0684104B0A")

    def register_globals(self):
        # -------- Set global variables --------
        self.manager.set("tracking.home", "/var/lib/tracking")

        # -------- Copy variables from vault --------
        self.manager.copy("tracking.repo_url", self.vault)
        self.manager.set("tracking.id_ed25519", self.vault.get("botlama.id_ed25519"))
        self.manager.set("tracking.id_ed25519_pub", self.vault.get("botlama.id_ed25519_pub"))

    def register_inventory(self):
        # -------- Define Groups --------
        self.desktops = self.manager.add_group("desktops")
        self.servers = self.manager.add_group("servers")

        # -------- Define Hosts --------
        self.chef = self.manager.add_host("chef", ssh_host="root@localhost")
        self.chef.add_group(self.desktops)

        #self.cerev = self.manager.add_host("cerev", ssh_host="cerev.hosts.oddlama.org")
        #self.cerev.add_group(servers)

        #self.cato = self.manager.add_host("cato", ssh_host="cato.hosts.oddlama.org")
        #self.cato.add_group(servers)

    def run(self, context):
        context.run_task(SetupTracking)

        context.run_task(SetupSystemd)
        context.run_task(SetupZsh)

        context.run_task(TrackPortage)
        context.run_task(TrackInstalledPackages)

# -------- Run the inventory --------
if __name__ == "__main__":
    run_inventory(Site)
