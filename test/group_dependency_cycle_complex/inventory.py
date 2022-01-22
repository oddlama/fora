hosts = ["local:dummy"]
groups = [dict(name="group1", after=["group2"]),
          dict(name="group2", after=["group3"]),
          dict(name="group3", after=["group2"])]
