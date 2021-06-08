from simple_automation import host_id
from simple_automation.vault import load_vault

ssh_host = "root@localhost"
groups = ["desktops"]

vault = load_vault(f"vaults/{host_id}.py")
#TODO xyz = vault.afea
