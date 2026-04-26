import re
from pathlib import Path

import pandas as pd
import pdfplumber

from utils import limpar_km, limpar_valor_monetario
from core.constantes import UFS_BRASIL
from core.normalizador import (
    normalizar_linha,
    normalizar_texto_coluna,
    corrigir_texto_celula_pdf,
    limpar_cor_tabela_pdf,
    limpar_cidade,
)
from core.validacoes import validar_e_corrigir_registro


CIDADES_CURTAS = {
    "PAULO": "SÃO PAULO",
    "SAO PAULO": "SÃO PAULO",
    "SÃO PAULO": "SÃO PAULO",
    "CAMPO": "SÃO BERNARDO DO CAMPO",
    "CAMPINAS": "CAMPINAS",
    "PRETO": "SÃO JOSÉ DO RIO PRETO",
    "RIBEIRAO PRETO": "RIBEIRÃO PRETO",
    "RIBEIRÃO PRETO": "RIBEIRÃO PRETO",
    "OSASCO": "OSASCO",
}


def _normalizar_token_cidade_final(valor: str) -> str:
    valor = str(valor or "").upper().strip().replace(",", "")
    valor = re.sub(r"\s+", " ", valor)

    if not valor:
        return ""

    if valor in CIDADES_CURTAS:
        return CIDADES_CURTAS[valor]

    if valor.endswith(" PAULO"):
        return "SÃO PAULO"

    if valor.endswith(" CAMPO"):
        return "SÃO BERNARDO DO CAMPO"

    if valor.endswith(" PRETO"):
        return "SÃO JOSÉ DO RIO PRETO"

    return limpar_cidade(valor)


def _extrair_uf_cidade_final(texto_local: str):
    texto = str(texto_local or "").strip()
    texto = re.sub(r"\s+", " ", texto).strip(" ,;-\t")

    if not texto:
        return "", ""

    tokens = texto.split()
    uf = ""

    if tokens and tokens[0].upper() in UFS_BRASIL:
        uf = tokens[0].upper()
        cidade_txt = " ".join(tokens[1:]).strip()
    else:
        cidade_txt = texto

    cidade = _normalizar_token_cidade_final(cidade_txt)

    if cidade and not uf:
        uf = "SP"

    return uf, cidade


def parsear_linha_tabela_final(linha_bruta: str):
    linha = normalizar_linha(linha_bruta)
    tokens = linha.split()

    if not tokens:
        return None

    placa = tokens[0].upper().strip()

    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        return None

    tokens_sem_placa = tokens[1:]

    idx_fab = None

    for i in range(len(tokens_sem_placa) - 1):
        if re.fullmatch(r"\d{4}", tokens_sem_placa[i]) and re.fullmatch(r"\d{4}", tokens_sem_placa[i + 1]):
            idx_fab = i
            break

    if idx_fab is None:
        return None

    modelo_tokens = tokens_sem_placa[:idx_fab]

    if not modelo_tokens:
        return None

    try:
        fab = int(tokens_sem_placa[idx_fab])
        mod = int(tokens_sem_placa[idx_fab + 1])
    except Exception:
        return None

    idx_km = idx_fab + 2

    if idx_km >= len(tokens_sem_placa):
        return None

    km = limpar_km(tokens_sem_placa[idx_km])

    if km is None:
        return None

    tail = " ".join(tokens_sem_placa[idx_km + 1:]).strip()

    if not tail:
        return None

    m_margem = re.search(r"(-?\d{1,3},\d{1,2}%)\s*$", tail)

    if not m_margem:
        return None

    tail_sem_margem = tail[:m_margem.start()].strip()

    padrao_valor = re.compile(r"(?:-?R\$\s*)?-?\d{1,3}(?:\.\d{3})*(?:,\d{2})")
    valores = list(padrao_valor.finditer(tail_sem_margem))

    if len(valores) < 3:
        return None

    m_fipe = valores[-3]
    m_preco_final = valores[-2]

    cor_txt = tail_sem_margem[:m_fipe.start()].strip()
    local_txt = tail_sem_margem[m_fipe.end():m_preco_final.start()].strip()

    if not cor_txt:
        return None

    fipe = limpar_valor_monetario(m_fipe.group())
    preco_final_informado = limpar_valor_monetario(m_preco_final.group())

    if fipe is None or preco_final_informado is None:
        return None

    uf, cidade = _extrair_uf_cidade_final(local_txt)

    return {
        "PLACA": placa,
        "MODELO": " ".join(modelo_tokens).strip(),
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor_txt.strip(),
        "FIPE": fipe,
        "UF": uf,
        "CIDADE": cidade,
        "PREÇO ORIGINAL": preco_final_informado,
        "PREÇO_FINAL_INFORMADO": preco_final_informado,
    }


def montar_dataframe_tabela_final(caminho_pdf: Path):
    linhas = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()

            if not texto:
                continue

            for linha in texto.split("\n"):
                linha = linha.strip()

                if not linha:
                    continue

                if linha.upper().startswith("PLACA "):
                    continue

                primeiro = linha.split()[0] if linha.split() else ""

                if re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", primeiro):
                    linhas.append(linha)

    registros = []
    falhas = []

    for linha in linhas:
        reg = parsear_linha_tabela_final(linha)

        if reg:
            registros.append(reg)
        else:
            falhas.append(linha)

    return pd.DataFrame(registros), falhas


def _normalizar_cabecalho_tabela_pdf(valor: str) -> str:
    texto = normalizar_texto_coluna(valor).upper()
    texto = texto.replace("PRECO", "PREÇO")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _extrair_ano_pdf_tabela(valor) -> int | None:
    digitos = "".join(re.findall(r"\d", str(valor or "")))

    for i in range(max(0, len(digitos) - 3)):
        candidato = digitos[i:i + 4]

        if re.fullmatch(r"(?:19|20)\d{2}", candidato):
            return int(candidato)

    return None


def _obter_valor_linha_tabela(row, idx, nome_coluna: str):
    pos = idx.get(nome_coluna)

    if pos is None or pos >= len(row):
        return ""

    return row[pos]


def _extrair_anos_e_km_de_texto_contaminado(texto: str):
    texto = corrigir_texto_celula_pdf(texto)
    digitos = "".join(re.findall(r"\d", texto))

    if len(digitos) < 8:
        return None, None, None

    candidatos = []

    for i in range(0, len(digitos) - 3):
        candidato = digitos[i:i + 4]

        if re.fullmatch(r"20\d{2}", candidato):
            candidatos.append((i, int(candidato)))

    if len(candidatos) < 2:
        return None, None, None

    (_, fab), (pos_mod, mod) = candidatos[0], candidatos[1]
    resto = digitos[pos_mod + 4:]

    km = None

    if resto and len(resto) >= 4:
        km = int(resto[-6:]) if len(resto) > 6 else int(resto)

    return fab, mod, km


def _corrigir_fab_mod_km_tabela_pdf(modelo, fab_raw, mod_raw, km_raw):
    modelo_txt = corrigir_texto_celula_pdf(modelo)
    fab_txt = corrigir_texto_celula_pdf(fab_raw)
    mod_txt = corrigir_texto_celula_pdf(mod_raw)
    km_txt = corrigir_texto_celula_pdf(km_raw)

    fab = _extrair_ano_pdf_tabela(fab_txt)
    mod = _extrair_ano_pdf_tabela(mod_txt)
    km = limpar_km(km_txt)

    if fab is None and mod is not None and km is not None:
        if fab_txt and not re.fullmatch(r"20\d{2}", fab_txt):
            modelo_txt = f"{modelo_txt} {fab_txt}".strip()

        return modelo_txt, mod, mod, km

    if fab is not None and mod is not None and km is not None:
        return modelo_txt, fab, mod, km

    combinado = " ".join([modelo_txt, fab_txt, mod_txt, km_txt])
    fab2, mod2, km2 = _extrair_anos_e_km_de_texto_contaminado(combinado)

    return (
        modelo_txt,
        fab if fab is not None else fab2,
        mod if mod is not None else mod2,
        km if km is not None else km2,
    )


def _normalizar_numero_monetario_br(texto: str):
    texto = str(texto or "").strip()

    if not texto:
        return None

    texto = texto.replace("R$", "").strip()
    texto = re.sub(r"\s+", "", texto)

    if not texto or texto in {"-", "+"}:
        return None

    negativo = texto.startswith("-")

    if negativo:
        texto = texto[1:].strip()

    if re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto):
        valor = float(texto.replace(".", "").replace(",", "."))
        return -valor if negativo else valor

    if re.fullmatch(r"\d{1,3}(?:\.\d{3})*", texto):
        valor = float(texto.replace(".", ""))
        return -valor if negativo else valor

    return limpar_valor_monetario(("-" if negativo else "") + texto)


def _extrair_valores_monetarios_pdf(valor):
    texto = corrigir_texto_celula_pdf(valor).upper()

    if not texto or "SEM FIPE" in texto:
        return []

    texto = texto.replace("−", "-")
    texto = re.sub(r"(?<=[A-ZÁ-Ú])R\$", " R$", texto)
    texto = re.sub(r"(?<=[A-ZÁ-Ú])-R\$", " -R$", texto)
    texto = re.sub(r"R\$(?=\d)", "R$ ", texto)
    texto = re.sub(r"-R\$(?=\d)", "-R$ ", texto)

    texto = re.sub(r"\b(\d)\s+(\d{1,3}\.\d{3},\d{2})\b", r"\1\2", texto)
    texto = re.sub(r"(-?)\s*(\d+)\s+\.\s*(\d{3},\d{2})", r"\1\2.\3", texto)
    texto = re.sub(r"R\$\s*(\d)\s+(\d{2})(?![\d,.])", r"R$ \1\2", texto)
    texto = re.sub(r"-\s+(\d)\s+\.\s*(\d{3},\d{2})", r"-\1.\2", texto)

    padrao_com_centavos = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")
    padrao_inteiro_com_rs = re.compile(r"-?R\$\s*(\d{1,3}(?:\.\d{3})*|\d{4,6})(?![,\d])")

    encontrados = []

    for m in padrao_com_centavos.finditer(texto):
        valor_float = _normalizar_numero_monetario_br(m.group())

        if valor_float is not None:
            encontrados.append((m.start(), valor_float))

    for m in padrao_inteiro_com_rs.finditer(texto):
        bruto = m.group().replace("R$", "").strip()
        valor_float = _normalizar_numero_monetario_br(bruto)

        if valor_float is not None:
            encontrados.append((m.start(), valor_float))

    encontrados.sort(key=lambda x: x[0])

    valores = []

    for _, v in encontrados:
        if not valores or abs(valores[-1] - v) > 0.009:
            valores.append(v)

    return valores


def _limpar_valor_monetario_tabela_pdf(valor):
    valores = _extrair_valores_monetarios_pdf(valor)

    if not valores:
        return None

    plausiveis = [v for v in valores if abs(v) >= 1000]

    if plausiveis:
        return plausiveis[-1]

    return valores[-1]


def montar_dataframe_tabela_pdf_extraida(caminho_pdf: Path):
    registros = []
    falhas = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            tabelas = pagina.extract_tables() or []

            for tabela in tabelas:
                if not tabela or len(tabela) < 2:
                    continue

                cabecalho = [_normalizar_cabecalho_tabela_pdf(c) for c in tabela[0]]

                if "PLACA" not in cabecalho or "PREÇO FINAL" not in cabecalho:
                    continue

                idx = {nome: pos for pos, nome in enumerate(cabecalho) if nome}

                colunas_minimas = {
                    "PLACA", "MODELO", "FAB", "MOD",
                    "KM", "COR", "FIPE", "CIDADE", "PREÇO FINAL"
                }

                if not colunas_minimas.issubset(set(idx)):
                    continue

                for row in tabela[1:]:
                    if not row:
                        continue

                    placa = str(_obter_valor_linha_tabela(row, idx, "PLACA") or "").strip().upper()

                    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
                        continue

                    try:
                        modelo_raw = _obter_valor_linha_tabela(row, idx, "MODELO")
                        fab_raw = _obter_valor_linha_tabela(row, idx, "FAB")
                        mod_raw = _obter_valor_linha_tabela(row, idx, "MOD")
                        km_raw = _obter_valor_linha_tabela(row, idx, "KM")

                        modelo, fab, mod, km = _corrigir_fab_mod_km_tabela_pdf(
                            modelo_raw,
                            fab_raw,
                            mod_raw,
                            km_raw,
                        )

                        cor = limpar_cor_tabela_pdf(_obter_valor_linha_tabela(row, idx, "COR"))
                        fipe = _limpar_valor_monetario_tabela_pdf(_obter_valor_linha_tabela(row, idx, "FIPE"))

                        uf = str(_obter_valor_linha_tabela(row, idx, "UF") or "").strip().upper()
                        cidade = _normalizar_token_cidade_final(_obter_valor_linha_tabela(row, idx, "CIDADE"))

                        if cidade and not uf:
                            uf = "SP"

                        preco_base = _limpar_valor_monetario_tabela_pdf(
                            _obter_valor_linha_tabela(row, idx, "PREÇO FINAL")
                        )

                        registro = {
                            "PLACA": placa,
                            "MODELO": modelo,
                            "FAB": fab,
                            "MOD": mod,
                            "KM": km,
                            "COR": cor,
                            "FIPE": fipe,
                            "UF": uf,
                            "CIDADE": cidade,
                            "PREÇO ORIGINAL": preco_base,
                            "PREÇO_FINAL_INFORMADO": preco_base,
                        }

                        campos_obrigatorios = [
                            registro["PLACA"],
                            registro["MODELO"],
                            registro["FAB"],
                            registro["MOD"],
                            registro["KM"],
                            registro["FIPE"],
                            registro["PREÇO ORIGINAL"],
                        ]

                        if any(v is None or v == "" for v in campos_obrigatorios):
                            falhas.append(str(row))
                            continue

                        registro_corrigido = validar_e_corrigir_registro(registro)

                        if registro_corrigido:
                            registros.append(registro_corrigido)
                        else:
                            falhas.append(str(row))

                    except Exception:
                        falhas.append(str(row))

    return pd.DataFrame(registros), falhas