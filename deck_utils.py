"""
Deck utilities for Alerte Fatigue addon.
Resolves deck family: parent deck, sub-decks, and inherited filtered decks.
"""
from .logger import log, log_error


def get_deck_family(col, did: int) -> set:
    """
    Given a deck ID, return the set of all related deck IDs:
    - The deck itself
    - If it's a filtered deck (dyn=1), its original deck + all children of that original deck
    - All children of the resolved main deck
    - The parent chain up to root

    Returns a set of deck IDs (ints).
    """
    try:
        family = set()
        root_did = _resolve_root(col, did)
        _collect_family(col, root_did, family)
        return family
    except Exception as e:
        log_error(f"DeckUtils: get_deck_family error: {e}")
        return {did}


def _resolve_root(col, did: int) -> int:
    """
    Resolve the 'real' (non-filtered) root deck for a given deck ID.
    - If the deck is filtered (dyn), resolve to its odid (original deck).
    - Then walk up to find the topmost real ancestor.
    """
    try:
        deck = col.decks.get(did)
        if deck is None:
            return did

        # If it's a filtered deck, use the original deck id
        if deck.get("dyn", 0) == 1:
            odid = 0
            try:
                odid = col.db.scalar("SELECT odid FROM cards WHERE did = ? AND odid != 0 LIMIT 1", did) or 0
            except Exception:
                pass
            if not odid and "terms" in deck and deck["terms"]:
                try:
                    import re
                    term = deck["terms"][0][0]
                    m = re.search(r'deck:\s*"([^"]+)"', term) or re.search(r'deck:([^\s]+)', term)
                    if m:
                        target_did = col.decks.id_for_name(m.group(1))
                        if target_did:
                            odid = target_did
                except Exception:
                    pass
            if odid:
                did = odid
                deck = col.decks.get(did)
                if deck is None:
                    return did

        # Walk up to find the topmost parent (excluding root '1')
        # We keep the immediate parent that is not the virtual root
        name = deck.get("name", "")
        parts = name.split("::")
        if len(parts) > 1:
            # Get parent name
            parent_name = "::".join(parts[:-1])
            parent = col.decks.by_name(parent_name)
            if parent:
                # Recurse to find topmost
                return _resolve_root(col, parent["id"])

        return did
    except Exception as e:
        log_error(f"DeckUtils: _resolve_root error: {e}")
        return did


def _collect_family(col, did: int, family: set):
    """
    Recursively collect did and all its children deck IDs.
    Also includes any filtered decks pointing to members of this family.
    """
    family.add(did)
    try:
        deck = col.decks.get(did)
        if deck is None:
            return
        deck_name = deck.get("name", "")

        # Collect all decks whose name starts with this deck's name + "::"
        all_decks = col.decks.all()
        for d in all_decks:
            d_name = d.get("name", "")
            d_id = d.get("id", 0)
            # Sub-deck
            if d_name.startswith(deck_name + "::") and d_id not in family:
                family.add(d_id)
            # Filtered deck pointing to a deck already in family
            if d.get("dyn", 0) == 1:
                f_odid = 0
                try:
                    f_odid = col.db.scalar("SELECT odid FROM cards WHERE did = ? AND odid != 0 LIMIT 1", d_id) or 0
                except Exception:
                    pass
                if not f_odid and "terms" in d and d["terms"]:
                    try:
                        import re
                        term = d["terms"][0][0]
                        m = re.search(r'deck:\s*"([^"]+)"', term) or re.search(r'deck:([^\s]+)', term)
                        if m:
                            target_did = col.decks.id_for_name(m.group(1))
                            if target_did:
                                f_odid = target_did
                    except Exception:
                        pass
                if f_odid in family and d_id not in family:
                    family.add(d_id)
    except Exception as e:
        log_error(f"DeckUtils: _collect_family error: {e}")


def get_deck_name(col, did: int) -> str:
    """Return the short (last component) name of a deck."""
    try:
        deck = col.decks.get(did)
        if deck:
            return deck.get("name", "").split("::")[-1]
    except Exception:
        pass
    return str(did)
