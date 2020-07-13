import json

def quote(s):
    return json.dumps(s)

class ObjexExportAbort(Exception):
    def __init__(self, reason):
        self.reason = reason
