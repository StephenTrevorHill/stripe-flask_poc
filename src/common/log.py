import json, sys

def log(**fields):
    print(json.dumps(fields), file=sys.stdout, flush=True)
