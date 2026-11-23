"""Domain errors. The API maps each to a status code (api/handlers.py)."""


class NotFound(Exception):
    pass


class PlotTaken(Exception):
    """The plot already has an active booking for that season."""


class Invalid(Exception):
    pass
