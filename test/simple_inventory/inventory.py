hosts = [dict(url="host1", groups=["desktops", "desktops", "desktops"]),
         dict(url="host2", groups=["desktops", "somehosts"]),
         dict(url="host3", groups=["only34", "desktops"]),
         dict(url="host4", groups=["only34", "somehosts"]),
        "host5"]
groups = ["desktops",
          dict(name="somehosts", after=["desktops"]),
          dict(name="only34", after=["all"], before=["desktops"]),
          ]
