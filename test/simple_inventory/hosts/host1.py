add_group("desktops")
add_groups(["desktops"])
overwrite_host = "host1"

try:
    add_group("_invalid_")
except ValueError as e:
    if not "invalid group" in str(e):
        raise

try:
    add_groups(["_invalid_"])
except ValueError as e:
    if not "invalid group" in str(e):
        raise

assert name == "host1"
