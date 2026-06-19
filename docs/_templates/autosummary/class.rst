{{ fullname | escape | underline}}

.. currentmodule:: {{ module }}

.. add toctree option to make autodoc generate the pages

.. autoclass:: {{ objname }}

{% block attributes %}
{% for item in attributes %}
{% if loop.length != 1 %}
{% if loop.first %}
Attributes table
~~~~~~~~~~~~~~~~

.. autosummary::
{% endif %}
    ~{{ name }}.{{ item }}
{% endif %}
{%- endfor %}
{% endblock %}

{% block methods %}
{% for item in all_methods if item == '__call__' or not item.startswith('__') %}
{% if loop.length != 1 %}
{% if loop.first %}
Methods table
~~~~~~~~~~~~~

.. autosummary::
{% endif %}
    ~{{ name }}.{{ item }}
{% endif %}
{%- endfor %}
{% endblock %}

{% block attributes_documentation %}
{% for item in attributes %}
{% if loop.first %}
Attributes
~~~~~~~~~~
{% endif %}
.. autoattribute:: {{ [objname, item] | join(".") }}
{%- endfor %}
{% endblock %}

{% block methods_documentation %}
{% for item in all_methods if item == '__call__' or not item.startswith('__') %}
{% if loop.first %}
Methods
~~~~~~~
{% endif %}
.. automethod:: {{ [objname, item] | join(".") }}
{%- endfor %}
{% endblock %}
