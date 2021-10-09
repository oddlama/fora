class ConnectionLogger:
    def __init__(self, host, connector):
        self.host = host
        self.connector = connector

    def init(self):
        print(f"[[32m>[m] Establishing connection to {self.host.name} via {self.connector.schema}")

    def established(self):
        print(f"[[32m>[m] Connection to {self.host.name} established")

    def requested_close(self):
        print(f"[[32m>[m] Requesting to close connection to {self.host.name}")

    def closed(self):
        print(f"[[32m>[m] Connection to {self.host.name} closed")

    def failed(self, msg):
        print(f"[[32m>[m] Connection to {self.host.name} failed: {msg}")

    def error(self, msg):
        print(f"[[32m>[m] Connection error on {self.host.name}: {msg}")

class Logger:
    def __init__(self):
        self.connections = {}

    def new_connection(self, host, connector):
        cl = ConnectionLogger(host, connector)
        self.connections[host] = cl
        return cl

    def skip_host(self, host, msg):
        print(f"[ SKIP ] Skipping host {host.name}: {msg}")
