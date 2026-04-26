import re
from pathlib import Path

import pandas as pd
import pdfplumber

from utils import (
    eh_placa,
    limpar_cidade,
    limpar_cor,
    limpar_km,
    limpar_valor_monetario,
    normalizar_linha_pdf,
    registro_extraido_valido,
)

MONEY_PATTERN = r"(?:-?R\$\s?(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)|Sem FIPE)"
PERCENT_PATTERN = r"(?:-?\d{1,2},\d%|Sem FIPE)"


def extrair_linhas_pdf_rigido(caminho_pdf: Path):
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

                if "LOCALIZA SEMINOVOS ATACADO" in linha:
                    continue
                if "Oferta disponível apenas" in linha:
                    continue
                if linha.startswith("Placa Modelo Fab Mod KM Cor Preço"):
                    continue

                primeiro = linha.split()[0] if linha.split() else ""
                if eh_placa(primeiro):
                    linhas.append(linha)

    return linhas


def separar_placa_e_resto(linha_bruta: str):
    match = re.match(
        r"^(?P<placa>[A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+(?P<resto>.+)$",
        linha_bruta.strip(),
    )
    if not match:
        return None, None

    return match.group("placa").strip(), match.group("resto").strip()


def parsear_inicio_sem_placa(resto_inicio: str):
    tokens = resto_inicio.split()

    if len(tokens) < 5:
        return None

    idx_fab = None
    for i in range(len(tokens) - 2):
        if re.fullmatch(r"\d{4}", tokens[i]) and re.fullmatch(r"\d{4}", tokens[i + 1]):
            idx_fab = i
            break

    if idx_fab is None:
        return None

    modelo_tokens = tokens[:idx_fab]
    fab = tokens[idx_fab]
    mod = tokens[idx_fab + 1]

    if idx_fab + 2 >= len(tokens):
        return None

    km = tokens[idx_fab + 2]
    cor_tokens = tokens[idx_fab + 3:]

    cor = limpar_cor(" ".join(cor_tokens).strip())

    if not modelo_tokens or not cor:
        return None

    return {
        "MODELO": " ".join(modelo_tokens).strip(),
        "FAB": int(fab),
        "MOD": int(mod),
        "KM": limpar_km(km),
        "COR": cor,
    }


def parsear_linha_rigida(linha_bruta: str):
    placa, resto_original = separar_placa_e_resto(linha_bruta)
    if not placa:
        return None

    resto = normalizar_linha_pdf(resto_original)

    padrao_final = re.compile(
        rf"(?P<preco>{MONEY_PATTERN})\s+"
        rf"(?P<orcamento>{MONEY_PATTERN})\s+"
        rf"(?P<fipe>{MONEY_PATTERN})\s+"
        rf"(?P<dist>{MONEY_PATTERN})\s+"
        rf"(?P<margem>{PERCENT_PATTERN})\s+"
        rf"(?P<uf>[A-Z]{{2}})\s+"
        rf"(?P<local>.+)$",
        re.IGNORECASE,
    )

    match_final = padrao_final.search(resto)
    if not match_final:
        return None

    inicio_sem_placa = resto[: match_final.start()].strip()
    parte_inicial = parsear_inicio_sem_placa(inicio_sem_placa)
    if not parte_inicial:
        return None

    reg = {
        "PLACA": placa,
        "MODELO": parte_inicial["MODELO"],
        "FAB": parte_inicial["FAB"],
        "MOD": parte_inicial["MOD"],
        "KM": parte_inicial["KM"],
        "COR": parte_inicial["COR"],
        "FIPE": limpar_valor_monetario(match_final.group("fipe")),
        "UF": match_final.group("uf"),
        "CIDADE": limpar_cidade(match_final.group("local").strip()),
        "PREÇO ORIGINAL": limpar_valor_monetario(match_final.group("preco")),
    }
    return reg if registro_extraido_valido(reg) else None


def montar_dataframe_rigido(caminho_pdf: Path):
    linhas = extrair_linhas_pdf_rigido(caminho_pdf)

    registros = []
    falhas = []

    for linha in linhas:
        reg = parsear_linha_rigida(linha)
        if reg:
            registros.append(reg)
        else:
            falhas.append(linha)

    return pd.DataFrame(registros), falhas
