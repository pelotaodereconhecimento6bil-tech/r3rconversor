import re
from pathlib import Path

import pandas as pd
import pdfplumber

from core.normalizador import limpar_cor_tabela_pdf, normalizar_texto_coluna
from core.validacoes import validar_e_corrigir_registro
from utils import limpar_km


CIDADES_UTILITARIOS = [
    "SAO BERNARDO DO CAMPO",
    "SÃO BERNARDO DO CAMPO",
    "SAO PAULO",
    "SÃO PAULO",
    "SANTO ANDRE",
    "SANTO ANDRÉ",
    "GUARULHOS",
    "SOROCABA",
    "CAMPINAS",
    "BARUERI",
    "OSASCO",
]


def _normalizar_cidade(valor: str) -> str:
    texto = str(valor or "").upper().strip()
    texto = re.sub(r"\s+", " ", texto)

    correcoes = {
        "SAO BERNARDO DO CAMPO": "SÃO BERNARDO DO CAMPO",
        "SAO PAULO": "SÃO PAULO",
        "SANTO ANDRE": "SANTO ANDRÉ",
    }

    return correcoes.get(texto, texto)


def _valor_para_float(valor):
    texto = str(valor or "").strip().upper()

    if not texto or texto in {"#N/D", "N/D", "-", "NONE", "NAN"}:
        return None

    texto = texto.replace("R$", "").strip()
    texto = re.sub(r"[^\d,\.\-]", "", texto)

    if not texto or texto in {"-", ".", ","}:
        return None

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(".", "")

    try:
        return float(texto)
    except Exception:
        return None


def _extrair_cidade_e_resto(texto: str):
    texto = str(texto or "").strip()
    texto = re.sub(r"\s+", " ", texto)
    texto_up = texto.upper()

    padroes_cidade = [
        "SAO BERNARDO DO CAMPO",
        "SÃO BERNARDO DO CAMPO",
        "SAO PAULO",
        "SÃO PAULO",
        "SANTO ANDRE",
        "SANTO ANDRÉ",
        "GUARULHOS",
        "SOROCABA",
        "CAMPINAS",
        "BARUERI",
        "OSASCO",
    ]

    for cidade in sorted(padroes_cidade, key=len, reverse=True):
        cidade_up = cidade.upper()

        if texto_up.startswith(cidade_up):
            resto = texto[len(cidade):].strip()
            return _normalizar_cidade(cidade), resto

    # Correção para cidade grudada com o modelo:
    # SAO BERNARDO DO CAMPOHB20 -> SAO BERNARDO DO CAMPO / HB20
    m = re.match(
        r"^(SAO|SÃO)\s+BERNARDO\s+DO\s+CAMPO(?P<resto>[A-Z0-9].*)$",
        texto_up,
    )
    if m:
        resto = texto[m.start("resto"):].strip()
        return "SÃO BERNARDO DO CAMPO", resto

    return "-", texto


def _limpar_laudo(valor: str) -> str:
    texto = str(valor or "").strip()

    if not texto or texto.upper() in {"#N/D", "N/D", "NAN", "NONE"}:
        return ""

    return texto


def _parsear_linha_utilitarios(linha_bruta: str):
    linha = str(linha_bruta or "").strip()
    linha = re.sub(r"\s+", " ", linha)

    if not linha or linha.startswith("# Classificação"):
        return None, None

    match_inicio = re.match(
        r"^(?P<placa>[A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+"
        r"(?P<loja>[A-Z0-9ÃÁÀÂÉÊÍÓÔÕÚÇ]+)\s+"
        r"(?P<resto>.+)$",
        linha,
        flags=re.I,
)

    if not match_inicio:
        return None, None

    placa = match_inicio.group("placa").upper().strip()
    resto = match_inicio.group("resto").strip()

    cidade, resto = _extrair_cidade_e_resto(resto)

    if not cidade:
        cidade = "-"

    match_anos = re.search(
        r"(?P<fab>20\d{2}|19\d{2})\s*"
        r"(?P<mod>20\d{2}|19\d{2})\s+"
        r"(?P<km>\d{1,6})\b",
        resto,
    )

    if not match_anos:
        resto_corrigido = re.sub(
            r"(?i)(autom[aá]tico)\s*(20\d{2})",
            r"\1 \2",
            resto,
    )

    # =====================================================
    # CORREÇÃO OCR AUTOMÁTICO + ANO
    # =====================================================

        resto_corrigido = re.sub(
            r"(?i)AUTOM[ÁA]?\s*2\s*T\s*0\s*I\s*2\s*C\s*(\d)\s*O",
            r"AUTOMÁTICO 202\1",
            resto_corrigido,
    )

        resto_corrigido = re.sub(
            r"(?i)AUTOM[ÁA]?2T0I2C(\d)O",
            r"AUTOMÁTICO 202\1",
            resto_corrigido,
    )

        resto_corrigido = re.sub(
            r"(?i)AUTOM[ÁA]TI2C0O(\d{2})",
            r"AUTOMÁTICO 20\1",
            resto_corrigido,
    )

        resto_corrigido = re.sub(
            r"(?i)AUTOM[ÁA]TIC2O(\d{3})",
            r"AUTOMÁTICO 2\1",
            resto_corrigido,
    )

    # =====================================================

        resto_corrigido = re.sub(
            r"(?<=\D)(20\d{2})(20\d{2})(?=\s+\d{1,6})",
            r"\1 \2",
            resto_corrigido,
    )

        match_anos = re.search(
            r"(?P<fab>20\d{2}|19\d{2})\s*"
            r"(?P<mod>20\d{2}|19\d{2})\s+"
            r"(?P<km>\d{1,6})\b",
            resto_corrigido,
        )

        if match_anos:
            resto = resto_corrigido

    

    if not match_anos:
        return None, f"{placa} | ano/km não identificado | {linha_bruta}"

    modelo = resto[:match_anos.start()].strip()

# =========================================================
# LIMPEZA FINAL DO MODELO
# =========================================================

# remove lixo OCR da loja
    modelo = re.sub(
        r"^(VCPBB|VCPSBABO|VCPSBÃBO|VCP[A-Z0-9ÃÁÀÂÉÊÍÓÔÕÚÇ]*)\s+",
        "",
        modelo,
        flags=re.I,
)

# remove cidade residual
    modelo = re.sub(
        r"^(SAO|SÃO)?\s*BERNARDO\s+DO\s+CAMPO\s*",
        "",
        modelo,
        flags=re.I,
)

# corrige cidade grudada no modelo
    modelo = re.sub(
        r"^(SAO|SÃO)?\s*BERNARDO\s+DO\s+CAMPO",
        "",
        modelo,
        flags=re.I,
)

# =========================================================
# CORREÇÕES OCR SEVERAS
# =========================================================

    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CAMP(?=HB20)",
        "",
        modelo,
        flags=re.I,
)

    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CAKAMNPGOOO\s+Z\.E",
        "KANGOO Z.E",
        modelo,
        flags=re.I,
)

    modelo = re.sub(
        r"^BERNARDO\s+DO\s+COAMNIPX[OA]\s+PLUS",
        "ONIX PLUS",
        modelo,
        flags=re.I,
)

    modelo = re.sub(
        r"^BERNARDO\s+DO\s+COANMIXP\s+POREMIER",
        "ONIX PREMIER",
        modelo,
        flags=re.I,
)

    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CPOAMLOP\s+O(?=COMFORTLINE)",
        "POLO ",
        modelo,
        flags=re.I,
)

    

    # TRACKER
    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CATMRPAOCKER\s+LT",
        "TRACKER LT",
        modelo,
        flags=re.I,
)

# T-CROSS
    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CTA-?CMRPOOSS\s+",
        "T-CROSS ",
        modelo,
        flags=re.I,
)

# HB20 grudado
    modelo = re.sub(
        r"^BERNARDO\s+DO\s+CAMPHOB20",
        "HB20",
        modelo,
        flags=re.I,
)

# COMPASS
    modelo = re.sub(
        r"^BERNARDOC\s+DOOM\s+CPAASMSP\s+LOONGITUDE",
        "COMPASS LONGITUDE",
        modelo,
        flags=re.I,
)

# ONIX PLUS PREMIER
    modelo = re.sub(
        r"^BERNARDO\s+DOON\s+CIXA\s+MPLPUOS\s+PREMIER\s+II",
        "ONIX PLUS PREMIER II",
        modelo,
        flags=re.I,
)

# PULSE AUDACE
    modelo = re.sub(
        r"^BERNARDO\s+DOP\s+UCALSMEP\s+AOUDACE",
        "PULSE AUDACE",
        modelo,
        flags=re.I,
)

# =========================================================

# limpa espaços duplicados
    modelo = re.sub(r"\s+", " ", modelo).strip()

# =========================================================

    fab = int(match_anos.group("fab"))
    mod = int(match_anos.group("mod"))
    km = limpar_km(match_anos.group("km"))

    restante = resto[match_anos.end():].strip()

    link_match = re.search(r"https?://\S+", restante)
    link_laudo = link_match.group(0).strip() if link_match else ""

    if link_laudo:
        restante = restante.replace(link_laudo, "").strip()

    match_final = re.search(
        r"(?P<cor>.+?)\s+"
        r"(?P<fipe>-?\d+(?:[.,]\d{2})?)\s+"
        r"(?P<margem>-?\d+(?:[.,]\d{2})?)\s+"
        r"(?P<preco>-?\d+(?:[.,]\d{2})?|#N/D)\s*"
        r"(?P<laudo>.*)$",
        restante,
        flags=re.I,
    )

    if not match_final:
        return None, f"{placa} | valores finais não identificados | {linha_bruta}"

    cor = limpar_cor_tabela_pdf(match_final.group("cor"))
    fipe = _valor_para_float(match_final.group("fipe"))
    preco_base = _valor_para_float(match_final.group("preco"))
    laudo = _limpar_laudo(match_final.group("laudo"))

    if preco_base is None:
        return None, f"{placa} | preço ausente ou inválido | {linha_bruta}"

    if fipe in (None, 0):
        fipe = preco_base



    # remove caracteres OCR quebrados no início
    modelo = modelo.strip(" -_/.")

# normaliza espaços finais
    modelo = re.sub(r"\s+", " ", modelo).strip()

# evita modelo vazio
    if not modelo or len(modelo) < 3:
        return None, f"{placa} | modelo inválido | {linha_bruta}"





    registro = {
        "PLACA": placa,
        "MODELO": modelo,
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor,
        "FIPE": fipe,
        "UF": "-" if cidade == "-" else "SP",
        "CIDADE": cidade,
        "PREÇO ORIGINAL": preco_base,
        "LAUDO CAUTELAR": laudo,
        "LINK LAUDO": link_laudo,
        "ORIGEM": "utilitarios",
    }

    registro_validado = validar_e_corrigir_registro(registro)

    if not registro_validado:
        return None, f"{placa} | registro reprovado na validação | {linha_bruta}"

    registro_validado["ORIGEM"] = "utilitarios"

    return registro_validado, None


def montar_dataframe_utilitarios(caminho_pdf: Path):
    registros = []
    falhas = []
    layout_detectado = False

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                texto = pagina.extract_text(layout=True) or ""

            if not texto:
                continue

            texto_norm = normalizar_texto_coluna(texto)

            if (
                "placa loja cidade modelo" in texto_norm
                and "fipe margem preco laudo link" in texto_norm
            ):
                layout_detectado = True

            for linha in texto.split("\n"):
                linha = linha.strip()

                if not linha:
                    continue

                if linha.upper().startswith("PLACA LOJA"):
                    continue

                if not re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\s+", linha):
                    continue

                registro, erro = _parsear_linha_utilitarios(linha)

                if registro:
                    registros.append(registro)
                elif erro:
                    falhas.append(erro)

    if not layout_detectado and not registros:
        return pd.DataFrame(), []

    return pd.DataFrame(registros), falhas
