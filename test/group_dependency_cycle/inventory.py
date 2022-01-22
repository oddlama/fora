hosts = ["local:dummy"]
groups = [dict(name="group1", before=["group2"]), dict(name="group2", before=["group1"])]
