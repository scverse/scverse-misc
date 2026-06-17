from scverse_misc import deprecated_arg, Deprecation


@deprecated_arg("b", Deprecation("0.3.1", "Use function `bar()` instead."))
def foo(a: int, b: str) -> None:
    """Frobnicates its arguments.

    Args:
        a: The frobnicator.
        b: The frobnicatee.
    """
