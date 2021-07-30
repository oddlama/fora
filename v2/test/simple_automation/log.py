class ConnectionLogger:
    def __init__(self, host, connector):
        self.host = host
        self.connector = connector

    def init(self):
        print(f"[[32m>[m] Establishing connection to {self.host.name} via {self.connector.name}")

    def established(self):
        print(f"[[32m>[m] Connection to {self.host.name} established")

    def closed(self):
        print(f"[[32m>[m] Connection to {self.host.name} closed")

    def failed(self, msg):
        print(f"[[32m>[m] Connection to {self.host.name} failed: {msg}")

class Logger:
    def __init__(self):
        self.connections = {}

    def new_connection(self, host, connector):
        cl = ConnectionLogger(host, connector)
        self.connections[host] = cl
        return cl
