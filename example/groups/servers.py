print("this is group", name)
onlyservers = "servers"
partially_overwritten = "servers"
overwritten = "servers"
from fora import group as this
this.mergedict["servers"] = "set by servers"
