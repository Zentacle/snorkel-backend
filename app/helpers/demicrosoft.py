import re

def demicrosoft(fn):
    fn = re.sub("[^0-9a-zA-Z ]+", "", fn)
    for ch in [' ']:
        fn = fn.replace(ch,"-")
    return fn
