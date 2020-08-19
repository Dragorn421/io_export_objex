import json

def quote(s):
    return json.dumps(s)

class ObjexExportAbort(Exception):
    def __init__(self, reason):
        self.reason = reason

def detect_zztag(log, name):
    if (name[0:2] == 'ZZ'
        or any(suspicious_string in name for suspicious_string in ('_ZZ', '#ZZ', '|ZZ'))
    ):
        log.warning('Found what may be an ancient ZZ-tag in name {}\n'
            'Those are not used at all anymore and will be ignored', name)

def get_addon_version():
    return addon_version
