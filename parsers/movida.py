import re
from pathlib import Path

from core.recuperacao_ocr import corrigir_ocr_automotivo

import pandas as pd
import pdfplumber

from utils import limpar_km
from core.normalizador import normalizar_texto_coluna


UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def valor_movida_para_float(valor):
    texto = str(valor or "").strip()

    if not texto or texto == "-":
        return None

    texto = texto.replace("R$", "")
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")
    texto = re.sub(r"[^\d\.-]", "", texto)

    if not texto or texto in {"-", "."}:
        return None

    try:
        return float(texto)
    except Exception:
        return None


def limpar_cor_movida(valor):
    texto = str(valor or "").upper().strip()
    texto = re.sub(r"[^A-ZÁ-ÚÇ ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return " ".join(texto.split()[:2])


def extrair_uf_movida(tokens):
    texto = " ".join(str(t or "") for t in tokens).upper()

    if "INTERMODALSP" in texto or " SP " in f" {texto} ":
        return "SP"

    tokens_limpos = [
        re.sub(r"[^A-Z]", "", str(t).upper())
        for t in tokens
    ]

    for token in tokens_limpos:
        if token in UFS:
            return token

    return "SP"


def separar_registros_por_placa(texto):
    texto = str(texto or "")
    texto = re.sub(r"\s+", " ", texto).strip()

    padrao_placa = r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}"
    matches = list(re.finditer(rf"\b{padrao_placa}\b", texto))

    registros = []

    for i, match in enumerate(matches):
        inicio = match.start()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        trecho = texto[inicio:fim].strip()

        if trecho:
            registros.append(trecho)

    return registros


def normalizar_linha_movida(linha):
    linha = str(linha or "").strip()

    linha = linha.replace("Nãpdo", "Não")
    linha = linha.replace("NÃPDO", "Não")

    linha = corrigir_ocr_automotivo(linha)

    return linha


def parsear_linha_movida(linha_bruta):
    linha = normalizar_linha_movida(linha_bruta)

    if not linha:
        return None

    link_match = re.search(r"https?://\S+", linha)
    link_laudo = link_match.group(0).strip() if link_match else ""

    if link_laudo:
        linha = linha.replace(link_laudo, "").strip()

    tokens = linha.split()

    if len(tokens) < 12:
        return None

    placa = tokens[0].upper().strip()

    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        return None

    idx_ano = None

    for i, token in enumerate(tokens):
        if re.fullmatch(r"(?:19|20)\d{2}/(?:19|20)\d{2}", token):
            idx_ano = i
            break

    if idx_ano is None:
        return None

    modelo = " ".join(tokens[1:idx_ano]).strip()

    if not modelo:
        return None

    fab_txt, mod_txt = tokens[idx_ano].split("/")
    fab = int(fab_txt)
    mod = int(mod_txt)

    if idx_ano + 2 >= len(tokens):
        return None

    cor = limpar_cor_movida(tokens[idx_ano + 1])

    km_token = tokens[idx_ano + 2]
    km_token = re.sub(r"(?i)não|sim", "", km_token)
    km = limpar_km(km_token)

    if not cor or km is None:
        return None

    idx_atacado = None

    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].upper() == "ATACADO":
            idx_atacado = i
            break

    if idx_atacado is None or idx_atacado < 4:
        return None

    fipe = valor_movida_para_float(tokens[idx_atacado - 4])
    preco_base = valor_movida_para_float(tokens[idx_atacado - 3])

    if fipe is None or preco_base is None:
        return None

    laudo = ""

    if idx_atacado + 1 < len(tokens):
        candidato = tokens[idx_atacado + 1].upper().strip()

        if candidato in {"A", "R", "AR"}:
            laudo = candidato

    uf = extrair_uf_movida(tokens[:idx_atacado])

    return {
        "PLACA": placa,
        "MODELO": modelo,
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor,
        "FIPE": fipe,
        "UF": uf,
        "CIDADE": "",
        "PREÇO ORIGINAL": preco_base,
        "LAUDO CAUTELAR": laudo,
        "LINK LAUDO": link_laudo,
        "ORIGEM": "movida",
    }


def montar_dataframe_movida(caminho_pdf: Path):
    registros = []
    falhas = []
    textos_paginas = []
    movida_detectada = False

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                texto = pagina.extract_text(layout=True) or ""

            if not texto:
                continue

            textos_paginas.append(texto)

            texto_norm = normalizar_texto_coluna(texto)

            if "atacado" in texto_norm and "laudo" in texto_norm and "fipe" in texto_norm:
                movida_detectada = True

    if not movida_detectada:
        return pd.DataFrame(), []

    texto_total = "\n".join(textos_paginas)
    trechos = separar_registros_por_placa(texto_total)

    for trecho in trechos:
        registro = parsear_linha_movida(trecho)

        if registro:
            registros.append(registro)
        else:
            falhas.append(trecho)

    return pd.DataFrame(registros), falhas