import re


def demicrosoft(fn):
    fn = re.sub(r"[^0-9a-zA-Z -]+", "", fn)  # Remove unwanted characters
    fn = fn.replace(" ", "-")  # Replace spaces with hyphens
    fn = re.sub(r"-{2,}", "-", fn)  # Replace multiple hyphens with a single one
    fn = fn.strip("-")  # Remove leading/trailing hyphens
    return fn
