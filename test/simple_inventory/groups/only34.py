import fora.group as this

this.before("desktops")
this.before_all(["desktops"])
this.after("all")
this.after_all(["all"])

try:
    this.after("_invalid_")
except ValueError as e:
    if not "invalid group" in str(e):
        raise

try:
    this.before("_invalid_")
except ValueError as e:
    if not "invalid group" in str(e):
        raise

try:
    this.after("only34")
except ValueError as e:
    if not "dependency to self" in str(e):
        raise

assert this.name() == "only34"

overwrite_group = "only34"
