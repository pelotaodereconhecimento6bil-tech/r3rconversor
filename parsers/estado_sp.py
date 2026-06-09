import re
from pathlib import Path

import pandas as pd
import pdfplumber

from utils import limpar_km
from core.normalizador import limpar_cidade, limpar_cor_tabela_pdf, normalizar_texto_coluna


CIDADES_ESTADO_SP = [
    "SÃO BERNARDO DO CAMPO",
    "SAO BERNARDO DO CAMPO",

    "SÃO JOSÉ DO RIO PRETO",
    "SAO JOSE DO RIO PRETO",

    "SÃO JOSÉ DOS CAMPOS",
    "SAO JOSE DOS CAMPOS",

    "SÃO PAULO",
    "SAO PAULO",

    "SÃO VICENTE",
    "SAO VICENTE",

    "SANTO ANDRÉ",
    "SANTO ANDRE",

    "PRESIDENTE PRUDENTE",
    "RIBEIRÃO PRETO",
    "RIBEIRAO PRETO",

    "PRAIA GRANDE",
    "MOGI MIRIM",
    "INDAIATUBA",
    "GUARULHOS",
    "PIRACICABA",
    "SOROCABA",
    "CAMPINAS",
    "JUNDIAÍ",
    "JUNDIAI",
    "ARARAQUARA",
    "MARÍLIA",
    "MARILIA",
    "OSASCO",
    "BARUERI",
    "BAURU",
    "ARARAS",
    "SUZANO",
]


def _valor_estado_sp(valor):
    texto = str(valor or "").strip()

    if texto in {"", "-", "R$ -", "#DIV/0!", "0"}:
        return None

    negativo = "(" in texto and ")" in texto

    texto = (
        texto.replace("R$", "")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )

    try:
        numero = float(texto)
        return -numero if negativo else numero
    except Exception:
        return None


def _normalizar_cidade_estado_sp(cidade):
    cidade = str(cidade or "").upper().strip()
    cidade = re.sub(r"\s+", " ", cidade)

    correcoes = {
        "SAO PAULO": "SÃO PAULO",
        "SAO BERNARDO DO CAMPO": "SÃO BERNARDO DO CAMPO",
        "SAO JOSE DOS CAMPOS": "SÃO JOSÉ DOS CAMPOS",
        "SAO JOSE DO RIO PRETO": "SÃO JOSÉ DO RIO PRETO",
        "RIBEIRAO PRETO": "RIBEIRÃO PRETO",
        "SANTO ANDRE": "SANTO ANDRÉ",
    }

    return correcoes.get(cidade, cidade)


def _separar_final_estado_sp(resto):
    resto = str(resto or "").strip()
    resto = re.sub(r"\s+", " ", resto)

    link = ""
    if "http" in resto:
        antes, depois = resto.split("http", 1)
        resto = antes.strip()
        link = "http" + depois.strip()

    laudo = ""

    for opcao in [
        "Aprovado com apontamento",
        "Não conforme",
        "Nao conforme",
        "Aprovado",
    ]:
        if resto.upper().endswith(opcao.upper()):
            laudo = opcao
            resto = resto[: -len(opcao)].strip()
            break

    resto = re.sub(r"\s+0\s+0$", "", resto).strip()
    resto = re.sub(r"\s+0$", "", resto).strip()

    cidade = ""
    endereco = resto
    resto_upper = resto.upper()

    melhor_match = None
    melhor_cidade = ""

    for cid in CIDADES_ESTADO_SP:
        cid_upper = cid.upper()
        padrao = rf"\b{re.escape(cid_upper)}\b"

        for match in re.finditer(padrao, resto_upper):
            if (
                melhor_match is None
                or match.start() > melhor_match.start()
                or (
                    match.start() == melhor_match.start()
                    and len(cid_upper) > len(melhor_cidade)
                )
            ):
                melhor_match = match
                melhor_cidade = cid

    if melhor_match:
        cidade = _normalizar_cidade_estado_sp(melhor_cidade)
        endereco = resto[: melhor_match.start()].strip()

    return endereco, cidade, laudo, link


def _agrupar_registros_estado_sp(texto):
    registros = []
    atual = ""

    for linha in texto.split("\n"):
        linha = re.sub(r"\s+", " ", str(linha or "").strip())

        if not linha:
            continue

        if linha.startswith("Placa LOJA MODELO"):
            continue

        if re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\s+", linha):
            if atual:
                registros.append(atual.strip())
            atual = linha
        else:
            if atual:
                atual += " " + linha

    if atual:
        registros.append(atual.strip())

    return registros


def _parsear_registro_estado_sp(linha):
    linha = re.sub(r"\s+", " ", str(linha or "").strip())

    padrao = re.compile(
        r"^(?P<placa>[A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+"
        r"(?P<loja>[A-Z0-9]+)\s+"
        r"(?P<modelo>.+?)\s+"
        r"(?P<fab>20\d{2}|19\d{2})\s+"
        r"(?P<mod>20\d{2}|19\d{2})\s+"
        r"(?P<km>[\d\.,]+)\s+"
        r"(?P<cor>.+?)\s+"
        r"(?P<fipe>R\$\s?(?:-|[\d\.,]+))\s+"
        r"(?P<margem_rs>R\$\s?(?:\([\d\.,]+\)|-|[\d\.,]+))\s+"
        r"(?P<margem_pct>(?:#DIV/0!|\d+%))\s+"
        r"(?P<preco>R\$\s?[\d\.,]+)\s+"
        r"(?P<resto>.+)$",
        re.IGNORECASE,
    )

    match = padrao.match(linha)

    if not match:
        return None

    endereco, cidade, laudo, link = _separar_final_estado_sp(match.group("resto"))

    return {
        "PLACA": match.group("placa").upper(),
        "MODELO": match.group("modelo").strip(),
        "FAB": int(match.group("fab")),
        "MOD": int(match.group("mod")),
        "KM": limpar_km(match.group("km")),
        "COR": limpar_cor_tabela_pdf(match.group("cor")),
        "FIPE": _valor_estado_sp(match.group("fipe")),
        "UF": "SP",
        "CIDADE": cidade if cidade else "",
        "PREÇO ORIGINAL": _valor_estado_sp(match.group("preco")),
        "LAUDO CAUTELAR": "" if laudo == "0" else laudo,
        "LINK LAUDO": "" if link == "0" else link,
        "ORIGEM": "estado_sp",
    }


def montar_dataframe_estado_sp(caminho_pdf: Path):
    registros = []
    falhas = []
    layout_detectado = False

    textos = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                texto = pagina.extract_text(layout=True) or ""

            if not texto:
                continue

            texto_norm = normalizar_texto_coluna(texto)

            if (
                "placa loja modelo ano fab ano mod" in texto_norm
                and "preco cliente" in texto_norm
                and "link do laudo" in texto_norm
            ):
                layout_detectado = True

            textos.append(texto)

    if not layout_detectado:
        return pd.DataFrame(), []

    texto_total = "\n".join(textos)
    linhas_registro = _agrupar_registros_estado_sp(texto_total)

    for linha in linhas_registro:
        registro = _parsear_registro_estado_sp(linha)

        if registro:
            registros.append(registro)
        else:
            falhas.append(linha)

    return pd.DataFrame(registros), falhas