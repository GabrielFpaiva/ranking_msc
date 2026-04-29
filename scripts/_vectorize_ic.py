import re
from pathlib import Path

rules_dir = Path("src/ranking_msc/rules")

def refactor_r025():
    path = rules_dir / "r025.py"
    if not path.exists(): return
    content = path.read_text()
    if "iterrows" not in content: return

    old = """        issues: list[dict[str, object]] = []

        for _, row in df_com_co.drop_duplicates().iterrows():
            co_raw = str(row["co"]).strip()
            co_val = co_raw.zfill(4)
            conta = str(row["conta_contabil"])

            if len(co_raw) != 4:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"CO '{co_val}' inválido para conta '{conta}': "
                        "deve ter exatamente 4 dígitos."
                    ),
                    "valor_esperado": "4 dígitos",
                    "valor_encontrado": co_val,
                    "competencia": context.competencia,
                })
                continue

            if co_val not in codigos_validos_co:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"CO '{co_val}' não encontrado na tabela CO 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "Código CO existente na tabela",
                    "valor_encontrado": co_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R025: %d pendência(s) de CO inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)"""

    new = """        df_unica = df_com_co.drop_duplicates(subset=["conta_contabil", "co"]).copy()
        df_unica["co_raw"] = df_unica["co"].astype(str).str.strip()
        df_unica["co_val"] = df_unica["co_raw"].str.zfill(4)

        mask_len = df_unica["co_raw"].str.len() != 4
        mask_tabela = (~mask_len) & (~df_unica["co_val"].isin(codigos_validos_co))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "CO '" + viol["co_val"] + "' inválido para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 4 dígitos.",
                "valor_esperado": "4 dígitos",
                "valor_encontrado": viol["co_val"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "CO '" + viol["co_val"] + "' não encontrado na tabela CO 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "Código CO existente na tabela",
                "valor_encontrado": viol["co_val"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R025: %d pendência(s) de CO inválido. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])"""
    
    path.write_text(content.replace(old, new))
    print("Patched R025")

def refactor_r026():
    path = rules_dir / "r026.py"
    if not path.exists(): return
    content = path.read_text()
    if "iterrows" not in content: return

    old = """        issues: list[dict[str, object]] = []

        for _, row in df_com_nr.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            nr_raw = str(row["nr"]).strip()
            nr_val = nr_raw.zfill(8)

            if len(nr_raw) != 8:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"NR '{nr_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 8 dígitos."
                    ),
                    "valor_esperado": "8 dígitos",
                    "valor_encontrado": nr_raw,
                    "competencia": context.competencia,
                })
                continue

            if not nr_raw.isdigit():
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"NR '{nr_raw}' inválida para conta '{conta}': "
                        "deve conter apenas dígitos (0–9)."
                    ),
                    "valor_esperado": "apenas dígitos (0-9)",
                    "valor_encontrado": nr_raw,
                    "competencia": context.competencia,
                })
                continue

            if nr_val not in codigos_validos:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"NR '{nr_val}' não encontrada na tabela NR 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "código em tabela_nr.csv",
                    "valor_encontrado": nr_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R026: %d pendência(s) de NR inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)"""
    new = """        df_unica = df_com_nr.drop_duplicates(subset=["conta_contabil", "nr"]).copy()
        df_unica["nr_raw"] = df_unica["nr"].astype(str).str.strip()
        df_unica["nr_val"] = df_unica["nr_raw"].str.zfill(8)

        mask_len = df_unica["nr_raw"].str.len() != 8
        mask_digit = (~mask_len) & (~df_unica["nr_raw"].str.isdigit())
        mask_tabela = (~mask_len) & (~mask_digit) & (~df_unica["nr_val"].isin(codigos_validos))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 8 dígitos.",
                "valor_esperado": "8 dígitos",
                "valor_encontrado": viol["nr_raw"],
                "competencia": context.competencia,
            }))

        if mask_digit.any():
            viol = df_unica[mask_digit]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve conter apenas dígitos (0–9).",
                "valor_esperado": "apenas dígitos (0-9)",
                "valor_encontrado": viol["nr_raw"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "NR '" + viol["nr_val"] + "' não encontrada na tabela NR 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "código em tabela_nr.csv",
                "valor_encontrado": viol["nr_val"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R026: %d pendência(s) de NR inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])"""
    path.write_text(content.replace(old, new))
    print("Patched R026")

def refactor_r027():
    path = rules_dir / "r027.py"
    if not path.exists(): return
    content = path.read_text()
    if "iterrows" not in content: return

    old = """        issues: list[dict[str, object]] = []

        for _, row in df_com_nd.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            nd_raw = str(row["nd"]).strip()
            nd_val = nd_raw.zfill(8)

            if len(nd_raw) != 8:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"ND '{nd_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 8 dígitos."
                    ),
                    "valor_esperado": "8 dígitos",
                    "valor_encontrado": nd_raw,
                    "competencia": context.competencia,
                })
                continue

            if not nd_raw.isdigit():
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"ND '{nd_raw}' inválida para conta '{conta}': "
                        "deve conter apenas dígitos (0–9)."
                    ),
                    "valor_esperado": "apenas dígitos (0-9)",
                    "valor_encontrado": nd_raw,
                    "competencia": context.competencia,
                })
                continue

            if nd_val not in codigos_validos:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"ND '{nd_val}' não encontrada na tabela ND 2026 "
                        f"para conta '{conta}'."
                    ),
                    "valor_esperado": "código em tabela_nd.csv",
                    "valor_encontrado": nd_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R027: %d pendência(s) de ND inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)"""
    new = """        df_unica = df_com_nd.drop_duplicates(subset=["conta_contabil", "nd"]).copy()
        df_unica["nd_raw"] = df_unica["nd"].astype(str).str.strip()
        df_unica["nd_val"] = df_unica["nd_raw"].str.zfill(8)

        mask_len = df_unica["nd_raw"].str.len() != 8
        mask_digit = (~mask_len) & (~df_unica["nd_raw"].str.isdigit())
        mask_tabela = (~mask_len) & (~mask_digit) & (~df_unica["nd_val"].isin(codigos_validos))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "ND '" + viol["nd_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 8 dígitos.",
                "valor_esperado": "8 dígitos",
                "valor_encontrado": viol["nd_raw"],
                "competencia": context.competencia,
            }))

        if mask_digit.any():
            viol = df_unica[mask_digit]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "ND '" + viol["nd_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve conter apenas dígitos (0–9).",
                "valor_esperado": "apenas dígitos (0-9)",
                "valor_encontrado": viol["nd_raw"],
                "competencia": context.competencia,
            }))

        if mask_tabela.any():
            viol = df_unica[mask_tabela]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "ND '" + viol["nd_val"] + "' não encontrada na tabela ND 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "código em tabela_nd.csv",
                "valor_encontrado": viol["nd_val"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R027: %d pendência(s) de ND inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])"""
    path.write_text(content.replace(old, new))
    print("Patched R027")

def refactor_r028():
    path = rules_dir / "r028.py"
    if not path.exists(): return
    content = path.read_text()
    if "iterrows" not in content: return

    old = """        issues: list[dict[str, object]] = []

        for _, row in df_com_fs.drop_duplicates().iterrows():
            conta = str(row["conta_contabil"])
            fs_raw = str(row["fs"]).strip()
            fs_val = fs_raw.zfill(5)

            if len(fs_raw) != 5:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_raw}' inválida para conta '{conta}': "
                        "deve ter exatamente 5 dígitos."
                    ),
                    "valor_esperado": "5 dígitos",
                    "valor_encontrado": fs_raw,
                    "competencia": context.competencia,
                })
                continue

            funcao = fs_val[:2]
            subfuncao = fs_val[2:]

            if funcao not in funcoes_validas:
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_val}': função '{funcao}' não encontrada "
                        f"na tabela FS 2026 para conta '{conta}'."
                    ),
                    "valor_esperado": "função em tabela_fs.csv",
                    "valor_encontrado": funcao,
                    "competencia": context.competencia,
                })
                continue

            if subfuncao not in subfuncoes_validas:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"FS '{fs_val}': subfunção '{subfuncao}' não encontrada "
                        f"na tabela FS 2026 para conta '{conta}'."
                    ),
                    "valor_esperado": "subfunção em tabela_fs.csv",
                    "valor_encontrado": subfuncao,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R028: %d pendência(s) de FS inválida. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)"""
    new = """        df_unica = df_com_fs.drop_duplicates(subset=["conta_contabil", "fs"]).copy()
        df_unica["fs_raw"] = df_unica["fs"].astype(str).str.strip()
        df_unica["fs_val"] = df_unica["fs_raw"].str.zfill(5)
        df_unica["funcao"] = df_unica["fs_val"].str[:2]
        df_unica["subfuncao"] = df_unica["fs_val"].str[2:]

        mask_len = df_unica["fs_raw"].str.len() != 5
        mask_funcao = (~mask_len) & (~df_unica["funcao"].isin(funcoes_validas))
        mask_subfuncao = (~mask_len) & (~mask_funcao) & (~df_unica["subfuncao"].isin(subfuncoes_validas))

        dfs_issues = []

        if mask_len.any():
            viol = df_unica[mask_len]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FS '" + viol["fs_raw"] + "' inválida para conta '" + viol["conta_contabil"].astype(str) + "': deve ter exatamente 5 dígitos.",
                "valor_esperado": "5 dígitos",
                "valor_encontrado": viol["fs_raw"],
                "competencia": context.competencia,
            }))

        if mask_funcao.any():
            viol = df_unica[mask_funcao]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FS '" + viol["fs_val"] + "': função '" + viol["funcao"] + "' não encontrada na tabela FS 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "função em tabela_fs.csv",
                "valor_encontrado": viol["funcao"],
                "competencia": context.competencia,
            }))

        if mask_subfuncao.any():
            viol = df_unica[mask_subfuncao]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "FS '" + viol["fs_val"] + "': subfunção '" + viol["subfuncao"] + "' não encontrada na tabela FS 2026 para conta '" + viol["conta_contabil"].astype(str) + "'.",
                "valor_esperado": "subfunção em tabela_fs.csv",
                "valor_encontrado": viol["subfuncao"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R028: %d pendência(s) de FS inválida. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])"""
    path.write_text(content.replace(old, new))
    print("Patched R028")

def refactor_r029():
    path = rules_dir / "r029.py"
    if not path.exists(): return
    content = path.read_text()
    if "iterrows" not in content: return

    old = """        issues: list[dict[str, object]] = []

        for _, row in df_com_ai.iterrows():
            ai_val = row["ai"]
            conta = str(row["conta_contabil"])

            # Validação 1 — formato: exatamente 4 dígitos numéricos
            if len(ai_val) != 4 or not ai_val.isdigit():
                issues.append({
                    "severidade": "ERRO",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' fora do formato: "
                        f"esperado exatamente 4 dígitos numéricos, "
                        f"encontrado '{ai_val}'. Conta: {conta}."
                    ),
                    "valor_esperado": "4 dígitos numéricos (ex: '2023')",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })
                continue  # formato errado → não verifica plausibilidade

            # Validação 2 — plausibilidade: 2000 <= ano <= ano_competencia
            ano = int(ai_val)
            if ano < 2000 or ano > ano_competencia:
                issues.append({
                    "severidade": "ALERTA",
                    "conta_contabil": conta,
                    "descricao": (
                        f"AI '{ai_val}' implausível: "
                        f"esperado ano entre 2000 e {ano_competencia}, "
                        f"encontrado {ano}."
                    ),
                    "valor_esperado": f"2000 ≤ ano ≤ {ano_competencia}",
                    "valor_encontrado": ai_val,
                    "competencia": context.competencia,
                })

        if issues:
            logger.warning(
                "R029: %d pendência(s) de AI inválido. competência=%s",
                len(issues),
                context.competencia,
                extra=_extra,
            )

        return self.build_issues(issues)"""
    new = """        df_unica = df_com_ai.copy()
        mask_formato = (df_unica["ai"].str.len() != 4) | (~df_unica["ai"].str.isdigit())
        
        # Safe cast for valid years
        df_validos = df_unica[~mask_formato].copy()
        df_validos["ano"] = pd.to_numeric(df_validos["ai"], errors='coerce').fillna(0).astype(int)
        mask_plausivel = (df_validos["ano"] < 2000) | (df_validos["ano"] > ano_competencia)
        
        dfs_issues = []

        if mask_formato.any():
            viol = df_unica[mask_formato]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ERRO",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "AI '" + viol["ai"] + "' fora do formato: esperado exatamente 4 dígitos numéricos, encontrado '" + viol["ai"] + "'. Conta: " + viol["conta_contabil"].astype(str) + ".",
                "valor_esperado": "4 dígitos numéricos (ex: '2023')",
                "valor_encontrado": viol["ai"],
                "competencia": context.competencia,
            }))

        if mask_plausivel.any():
            viol = df_validos[mask_plausivel]
            dfs_issues.append(pd.DataFrame({
                "severidade": "ALERTA",
                "conta_contabil": viol["conta_contabil"].astype(str),
                "descricao": "AI '" + viol["ai"] + "' implausível: esperado ano entre 2000 e " + str(ano_competencia) + ", encontrado " + viol["ano"].astype(str) + ".",
                "valor_esperado": "2000 ≤ ano ≤ " + str(ano_competencia),
                "valor_encontrado": viol["ai"],
                "competencia": context.competencia,
            }))

        if dfs_issues:
            issues_df = pd.concat(dfs_issues, ignore_index=True)
            logger.warning(
                "R029: %d pendência(s) de AI inválido. competência=%s",
                len(issues_df),
                context.competencia,
                extra=_extra,
            )
            return self.build_issues(issues_df.to_dict("records"))

        return self.build_issues([])"""
    path.write_text(content.replace(old, new))
    print("Patched R029")

refactor_r025()
refactor_r026()
refactor_r027()
refactor_r028()
refactor_r029()
