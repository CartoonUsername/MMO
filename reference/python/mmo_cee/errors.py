class CEEError(Exception):
    """Basisfehler der Character Evolution Engine."""


class RuleViolation(CEEError):
    """Ein Ereignis verstößt gegen die Spielregeln und wird nicht aufgezeichnet."""


class IntegrityError(CEEError):
    """Die Hash-Kette einer Charakterhistorie ist inkonsistent."""


class RulesVersionMismatch(CEEError):
    """Ein Ereignis wurde unter einer anderen Regelversion aufgezeichnet als die zum Replay geladene.

    Stilles Neuberechnen unter anderen Regeln würde den Zustand verfälschen; eine Migration
    zwischen Regelversionen ist eine bewusste Aktion (Roadmap: Snapshots/Migration).
    """
