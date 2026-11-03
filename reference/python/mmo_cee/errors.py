class CEEError(Exception):
    """Basisfehler der Character Evolution Engine."""


class RuleViolation(CEEError):
    """Ein Ereignis verstößt gegen die Spielregeln und wird nicht aufgezeichnet."""


class IntegrityError(CEEError):
    """Die Hash-Kette einer Charakterhistorie ist inkonsistent."""
