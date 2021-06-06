from simple_automation.vault import load_vault

name = "localhost"
groups = ["desktops"]

ssh_host = "root@localhost"

install_sshd = True

vault = load_vault(f"vaults/{name}.py")
xyz = vault.afea
