import re

from core.constantes import UFS_BRASIL
from core.normalizador import (
    limpar_cor_tabela_pdf,
    limpar_modelo_sem_invasao,
    normalizar_cidade_sem_endereco,
)


def validar_e_corrigir_registro(registro):
    if not registro:
        return None

    placa = str(registro.get("PLACA", "") or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        return None

    registro["PLACA"] = placa

    registro["MODELO"] = limpar_modelo_sem_invasao(registro.get("MODELO", ""))

    if not registro["MODELO"]:
        return None

    registro["CIDADE"] = normalizar_cidade_sem_endereco(registro.get("CIDADE", ""))

    if not registro["CIDADE"]:
        registro["CIDADE"] = "SÃO PAULO"

    uf = str(registro.get("UF", "") or "").upper().strip()

    if uf and uf not in UFS_BRASIL:
        uf = "SP"

    if not uf and registro["CIDADE"]:
        uf = "SP"

    registro["UF"] = uf

    if registro.get("FIPE") is None or registro.get("PREÇO ORIGINAL") is None:
        return None

    try:
        fipe = float(registro["FIPE"])
        preco = float(registro["PREÇO ORIGINAL"])

        if fipe <= 0 or preco <= 0:
            return None

    except Exception:
        return None

    try:
        fab = int(registro.get("FAB"))
        mod = int(registro.get("MOD"))
        km = int(registro.get("KM"))

    except Exception:
        return None

    if not (1900 <= fab <= 2100 and 1900 <= mod <= 2100):
        return None

    if km < 0 or km > 999999:
        return None

    registro["FAB"] = fab
    registro["MOD"] = mod
    registro["KM"] = km
    registro["COR"] = limpar_cor_tabela_pdf(registro.get("COR", ""))

    for campo_texto in ["MODELO", "COR", "CIDADE"]:
        texto_campo = str(registro.get(campo_texto, "") or "").upper()

        if "R$" in texto_campo or re.search(r"\d{1,3},\d{1,2}%", texto_campo):
            return None

    if not registro["COR"] or len(str(registro["COR"]).strip()) < 3:
        return None

    return registro