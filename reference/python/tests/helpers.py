from mmo_cee import CharacterService


def make_veteran(svc: CharacterService, cid: str, kind: str = "player", level_xp: int = 1000):
    """Level 4 per default; level_xp=160000 -> Stufe 41."""
    svc.create(cid, kind)
    svc.record(cid, "identity.xp_gained", {"amount": level_xp})


def attune(svc, cid, element, amount=100):
    svc.record(cid, "element.exposure", {"element": element, "amount": amount})
    svc.record(cid, "element.attuned", {"element": element})
