"""
ranking_msc.rules
~~~~~~~~~~~~~~~~~

Submódulo de regras de validação.

Cada regra fica em seu próprio arquivo (r082.py, r083.py…).
Ao criar uma regra nova, importe-a aqui para que o @register_rule
a registre automaticamente no RULE_REGISTRY.

Exemplo:
    from ranking_msc.rules.r082 import R082  # noqa: F401
"""

from ranking_msc.rules.r003 import R003  # noqa: F401
from ranking_msc.rules.r004 import R004  # noqa: F401
from ranking_msc.rules.r010 import R010  # noqa: F401
from ranking_msc.rules.r021 import R021  # noqa: F401
from ranking_msc.rules.r030 import R030  # noqa: F401
