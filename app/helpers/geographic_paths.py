"""Fill GeographicNode.path with the URL each place has today.

Part of the location migration (LOCATION_MIGRATION.md, step 1): every node
built from a legacy Country/AreaOne/AreaTwo/Locality row keeps that row's
public URL exactly, "_" gaps included.
"""

from collections import defaultdict

from app.models import GeographicNode, db


def backfill_node_paths(apply=False):
    """Set path on nodes that don't have one. Returns a report dict.

    Nothing is written unless apply=True, and nothing is written at all if
    two nodes would get the same path.
    """
    nodes = GeographicNode.query.filter(GeographicNode.path.is_(None)).all()
    taken = {path for (path,) in db.session.query(GeographicNode.path).filter(GeographicNode.path.isnot(None))}

    planned = {}
    no_legacy_url = []
    by_path = defaultdict(list)
    for node in nodes:
        url = node.get_legacy_url()
        if not url or not url.startswith("/loc/"):
            no_legacy_url.append(node.id)
            continue
        planned[node.id] = url
        by_path[url].append(node.id)

    duplicates = {path: ids for path, ids in by_path.items() if len(ids) > 1 or path in taken}

    if apply and not duplicates:
        for node in nodes:
            if node.id in planned:
                node.path = planned[node.id]
        db.session.commit()

    return {
        "nodes_without_path": len(nodes),
        "planned": len(planned),
        "applied": bool(apply and not duplicates),
        "no_legacy_url": no_legacy_url,
        "duplicate_paths": duplicates,
    }
