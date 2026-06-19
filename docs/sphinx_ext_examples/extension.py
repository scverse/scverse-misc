from scverse_misc import make_register_namespace_decorator


class DummyClass:
    """Some class to extend."""


register_namespace = make_register_namespace_decorator(DummyClass, "dummy")
