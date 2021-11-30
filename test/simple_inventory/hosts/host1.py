import fora.host as this

this.add_group("desktops")
this.add_groups(["desktops"])
overwrite_host = "host1"

try:
    this.add_group("_invalid_")
except ValueError as e:
    if not "invalid group" in str(e):
        raise

try:
    this.add_groups(["_invalid_"])
except ValueError as e:
    if not "invalid group" in str(e):
        raise

assert this.name() == "host1"
