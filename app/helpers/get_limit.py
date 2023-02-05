def get_limit(limit, default=100):
    if limit == 'none':
        limit = None
    else:
        limit = limit if limit else default
    return limit
