import re
from pathlib import Path

import pandas as pd
import pdfplumber


CORES = [
    "BRANCO",
    "PRETO",
    "PRATA",
    "CINZA",
    "AZUL",
    "VERMELHO",
    "VERMELHA",
    "VERDE",
    "BEGE",
    "MARROM",
    "AMARELO",
]


def _limpar_numero(valor):
    texto = str(valor or "").strip()

    if not texto:
        return None

    texto = texto.replace("R$", "").strip()

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(".", "")

    texto = re.sub(r"[^\d\.-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return None


def _extrair_placa(linha):
    m = re.search(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", linha)
    return m.group(0) if m else None


def _extrair_ano(linha):
    m = re.search(r"(20\d{2})[\/\-](20\d{2})", linha)

    if m:
        return int(m.group(1)), int(m.group(2))

    m2 = re.search(r"(\d{2})\/(\d{2})", linha)

    if m2:
        return int("20" + m2.group(1)), int("20" + m2.group(2))

    return None, None


def _extrair_cor(linha):
    texto = str(linha).upper()

    for cor in CORES:
        if cor in texto:
            return cor

    return "NÃO INFORMADA"


def _extrair_km(linha):
    kms = re.findall(r"\b\d{4,6}\b", linha)

    if not kms:
        return "-"

    try:
        return int(kms[0])
    except Exception:
        return "-"


def _extrair_valores(linha):
    valores = re.findall(
        r"R?\$?\s?[\d\.]+(?:,\d{2})?",
        linha,
        flags=re.IGNORECASE,
    )

    numeros = []

    for v in valores:
        n = _limpar_numero(v)

        if n and n > 1000:
            numeros.append(n)

    if len(numeros) < 2:
        return None, None

    return numeros[0], numeros[1]


def _extrair_modelo(linha, placa):
    texto = linha

    texto = re.sub(r"^(RAC|FLEET)", "", texto, flags=re.IGNORECASE)

    if placa:
        texto = texto.replace(placa, "")

    texto = re.sub(r"20\d{2}[\/\-]20\d{2}.*", "", texto)

    texto = re.sub(r"\d{2}\/\d{2}.*", "", texto)

    texto = re.sub(r"\s+", " ", texto).strip()

    return texto[:80]


def _falha(placa, motivo):
    return f"{placa or 'SEM_PLACA'} | {motivo}"


def _parsear_linha_generica(linha):
    linha = str(linha or "").strip()

    if not linha:
        return None, None

    placa = _extrair_placa(linha)

    if not placa:
        return None, None

    fab, mod = _extrair_ano(linha)

    if not fab or not mod:
        return None, _falha(placa, "ANO NÃO IDENTIFICADO")

    fipe, preco = _extrair_valores(linha)

    if not fipe:
        return None, _falha(placa, "FIPE NÃO IDENTIFICADA")

    if not preco:
        return None, _falha(placa, "PREÇO NÃO IDENTIFICADO")

    modelo = _extrair_modelo(linha, placa)

    km = _extrair_km(linha)

    cor = _extrair_cor(linha)

    return {
        "PLACA": placa,
        "MODELO": modelo,
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor,
        "FIPE": fipe,
        "UF": "",
        "CIDADE": "",
        "PREÇO ORIGINAL": preco,
        "ORIGEM": "generico",
    }, None


def montar_dataframe_generico(caminho_pdf: Path):
    registros = []
    falhas = []

    with pdfplumber.open(caminho_pdf) as pdf:

        for pagina in pdf.pages:

            texto = pagina.extract_text() or ""

            if not texto:
                continue

            linhas = texto.split("\n")

            for linha in linhas:

                registro, erro = _parsear_linha_generica(linha)

                if registro:
                    registros.append(registro)

                elif erro:
                    falhas.append(erro)

    return pd.DataFrame(registros), falhas