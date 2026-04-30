import re
from pathlib import Path

rules_dir = Path("src/ranking_msc/rules")

ic_rules = [
    ("r021.py", "po", "PO_DOMAIN", "5 dígitos e existir na tabela do PCASP", "f\"PO '{xx_valor}' inválido para conta '{conta}': esperado 5 dígitos ou valor ausente na tabela.\""),
    ("r022.py", "fp", "FP_DOMAIN", "1 ou 2", "f\"FP '{xx_valor}' inválido para conta '{conta}': esperado '1' (Financeiro) ou '2' (Permanente).\""),
    ("r023.py", "dc", "DC_DOMAIN", "1", "f\"DC '{xx_valor}' inválido para conta '{conta}': esperado '1' (não compõe DC).\""),
    ("r025.py", "co", "codigos_validos_co", "Código-raiz CO existente na tabela", "f\"CO '{xx_val}' inválido para conta '{conta}': código-raiz '{xx_val[1:]}' não encontrado na tabela CO 2026.\""),
    ("r026.py", "nr", "NR_DOMAIN", "Código de NR existente no domínio", "f\"NR '{xx_val}' inválido para conta '{conta}': código não encontrado no domínio válido.\""),
    ("r027.py", "nd", "ND_DOMAIN", "Código de ND existente no domínio", "f\"ND '{xx_val}' inválido para conta '{conta}': código não encontrado no domínio válido.\""),
    ("r028.py", "fs", "FS_DOMAIN", "Código FS existente no domínio", "f\"FS '{xx_val}' inválido para conta '{conta}': código '{xx_val}' não encontrado na tabela Funcional.\"")
]

for fname, col, domain, val_esp, desc_fstring in ic_rules:
    path = rules_dir / fname
    if not path.exists(): continue
    content = path.read_text()
    if "iterrows" not in content: continue

    # For rules that do xx_val = row[col].zfill(4), etc., they might be slightly different.
    # Let's just print the exact iterrows block for each to build the patch.
    start = content.find("        issues: list[dict[str, object]] = []")
    if start == -1:
        start = content.find(f"        for _, row in df_com_{col}.drop_duplicates().iterrows():")
    
    end = content.find("        if issues:")
    if start != -1 and end != -1:
        block = content[start:end]
        print(f"=== {fname} ===")
        print(block)
