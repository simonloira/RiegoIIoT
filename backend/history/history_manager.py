from backend.history.activation_history import HistorySaver

type HistorySave = HistorySaver

history_handler: HistorySaver | None = None


def get_history_saver() -> HistorySaver:
    assert history_handler is not None, "No se inicializó el historial"
    return history_handler
