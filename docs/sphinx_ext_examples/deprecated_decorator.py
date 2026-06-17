from scverse_misc import deprecated, Deprecation


@deprecated(Deprecation("0.3.1", "Use bar instead."))
def foo(a: int, b: str) -> None:
    """Frobnicates its arguments.

    Args:
        a: The frobnicator.
        b: The frobnicatee.
    """
