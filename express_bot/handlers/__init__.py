from pybotx import HandlerCollector

from . import commands, text

__all__ = ["register_handlers"]


def register_handlers(collector: HandlerCollector) -> None:
    commands.register(collector)
    text.register(collector)