{{ fullname | escape | underline}}

.. currentmodule:: {{ module }}

.. auto{{ "decorator" if fullname | is_decorator else "function" }}:: {{ objname }}
