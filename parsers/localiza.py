import re
from pathlib import Path

import pandas as pd
import pdfplumber

from utils import limpar_km

from core.constantes import UF_REGEX
from core.normalizador import (
    inferir_cidade_por_nome_arquivo,
    limpar_cidade,
    limpar_cor_tabela_pdf,
    normalizar_cidade_sem_endereco,
    normalizar_linha,
    normalizar_texto_coluna,
    valor_localiza_para_float,
)
from core.validacoes import validar_e_corrigir_registro


def _parsear_linha_localiza_ipva(linha_bruta: str, cidade_padrao: str = "SÃO PAULO"):
    linha = normalizar_linha(str(linha_bruta or ""))

    if not linha:
        return None

    m_placa = re.match(
        r"^(?P<placa>[A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+(?P<resto>.+)$",
        linha,
    )

    if not m_placa:
        return None

    placa = m_placa.group("placa").upper().strip()
    resto = m_placa.group("resto").strip()

    m_primeiro_valor = re.search(
        r"\bR\$\s*(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\b",
        resto,
        flags=re.I,
    )

    if not m_primeiro_valor:
        return None

    esquerda = resto[:m_primeiro_valor.start()].strip()
    direita = resto[m_primeiro_valor.start():].strip()

    tokens = esquerda.split()

    idx_fab = None

    for i in range(len(tokens) - 2):
        if (
            re.fullmatch(r"20\d{2}|19\d{2}", tokens[i])
            and re.fullmatch(r"20\d{2}|19\d{2}", tokens[i + 1])
        ):
            km_teste = limpar_km(tokens[i + 2])

            if km_teste is not None:
                idx_fab = i
                break

    if idx_fab is None:
        return None

    modelo = " ".join(tokens[:idx_fab]).strip()
    fab = int(tokens[idx_fab])
    mod = int(tokens[idx_fab + 1])
    km = limpar_km(tokens[idx_fab + 2])
    cor = limpar_cor_tabela_pdf(" ".join(tokens[idx_fab + 3:]))

    if not modelo or km is None or not cor:
        return None

    padrao_moeda = re.compile(
        r"R\$\s*(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)|Sem FIPE",
        flags=re.I,
    )

    moedas = list(padrao_moeda.finditer(direita))

    if len(moedas) < 4:
        return None

    fipe = valor_localiza_para_float(moedas[0].group())
    preco_base = valor_localiza_para_float(moedas[-1].group())

    if fipe is None or preco_base is None:
        return None

    registro = {
        "PLACA": placa,
        "MODELO": modelo,
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor,
        "FIPE": fipe,
        "UF": "SP",
        "CIDADE": cidade_padrao,
        "PREÇO ORIGINAL": preco_base,
    }

    return validar_e_corrigir_registro(registro)


def montar_dataframe_localiza_ipva(caminho_pdf: Path):
    registros = []
    falhas = []

    layout_ipva_detectado = False
    cidade_padrao = inferir_cidade_por_nome_arquivo(caminho_pdf)

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                continue

            texto_norm = normalizar_texto_coluna(texto)

            if "ganho ipva" in texto_norm and "preco cliente" in texto_norm:
                layout_ipva_detectado = True

            for linha in texto.split("\n"):
                linha = linha.strip()

                if not linha:
                    continue

                if not re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", linha):
                    continue

                reg = _parsear_linha_localiza_ipva(
                    linha,
                    cidade_padrao=cidade_padrao,
                )

                if reg:
                    registros.append(reg)
                else:
                    falhas.append(linha)

    if not layout_ipva_detectado:
        return pd.DataFrame(), []

    return pd.DataFrame(registros), falhas


def _parsear_linha_localiza_original(linha_bruta: str):
    linha = normalizar_linha(str(linha_bruta or ""))

    if not linha:
        return None

    m_placa = re.match(
        r"^(?P<placa>[A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+(?P<resto>.+)$",
        linha,
    )

    if not m_placa:
        return None

    placa = m_placa.group("placa").upper().strip()
    resto = m_placa.group("resto").strip()

    m_preco_inicio = re.search(
        r"\bR\$\s*(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\b",
        resto,
        flags=re.I,
    )

    if not m_preco_inicio:
        return None

    esquerda = resto[:m_preco_inicio.start()].strip()
    direita = resto[m_preco_inicio.start():].strip()

    tokens = esquerda.split()

    idx_fab = None

    for i in range(len(tokens) - 2):
        if (
            re.fullmatch(r"20\d{2}|19\d{2}", tokens[i])
            and re.fullmatch(r"20\d{2}|19\d{2}", tokens[i + 1])
        ):
            km_teste = limpar_km(tokens[i + 2])

            if km_teste is not None:
                idx_fab = i
                break

    if idx_fab is None:
        return None

    modelo = " ".join(tokens[:idx_fab]).strip()
    fab = int(tokens[idx_fab])
    mod = int(tokens[idx_fab + 1])
    km = limpar_km(tokens[idx_fab + 2])
    cor = limpar_cor_tabela_pdf(" ".join(tokens[idx_fab + 3:]))

    if not modelo or not cor or km is None:
        return None

    padrao_moeda_localiza = re.compile(
        r"R\$\s*(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)|Sem FIPE",
        flags=re.I,
    )

    moedas = list(padrao_moeda_localiza.finditer(direita))

    if len(moedas) < 3:
        return None

    preco_base = valor_localiza_para_float(moedas[0].group())
    fipe = valor_localiza_para_float(moedas[2].group())

    if preco_base is None or fipe is None:
        return None

    m_margem = re.search(
        r"(?:-?\d{1,3},\d{1,2}%|Sem FIPE)\s+"
        r"(?P<uf>" + UF_REGEX + r")\s+"
        r"(?P<local>.+)$",
        direita,
        flags=re.I,
    )

    if not m_margem:
        return None

    uf = m_margem.group("uf").upper().strip()
    local = m_margem.group("local").strip()

    cidade = normalizar_cidade_sem_endereco(local)

    if not cidade:
        cidade = limpar_cidade(local)

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
    }

    return validar_e_corrigir_registro(registro)


def montar_dataframe_localiza_original(caminho_pdf: Path):
    registros = []
    falhas = []

    cabecalho_localiza_detectado = False

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                continue

            texto_norm = normalizar_texto_coluna(texto)

            if (
                "localiza seminovos atacado" in texto_norm
                and "orcamento" in texto_norm
                and "endereco" in texto_norm
            ):
                cabecalho_localiza_detectado = True

            for linha in texto.split("\n"):
                linha = linha.strip()

                if not linha:
                    continue

                if not re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", linha):
                    continue

                reg = _parsear_linha_localiza_original(linha)

                if reg:
                    registros.append(reg)
                else:
                    falhas.append(linha)

    if not cabecalho_localiza_detectado and not registros:
        return pd.DataFrame(), []

    return pd.DataFrame(registros), falhas


def montar_dataframe_localiza(caminho_pdf: Path):
    df_ipva, falhas_ipva = montar_dataframe_localiza_ipva(caminho_pdf)

    total_ipva = len(df_ipva) + len(falhas_ipva)
    taxa_ipva = (len(df_ipva) / total_ipva) if total_ipva else 0

    if len(df_ipva) > 0 and taxa_ipva >= 0.70:
        return df_ipva, falhas_ipva, "localiza_ipva", {
            "PREÇO CLIENTE",
            "FIPE",
            "GANHO IPVA",
        }

    df_original, falhas_original = montar_dataframe_localiza_original(caminho_pdf)

    total_original = len(df_original) + len(falhas_original)
    taxa_original = (len(df_original) / total_original) if total_original else 0

    if len(df_original) > 0 and taxa_original >= 0.70:
        return df_original, falhas_original, "localiza_original", {
            "PREÇO",
            "FIPE",
            "CIDADE",
            "ENDEREÇO",
        }

    return pd.DataFrame(), [], "localiza_nao_detectada", set()