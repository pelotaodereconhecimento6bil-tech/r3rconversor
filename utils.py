import math
import re
import unicodedata
from typing import Mapping, Optional

PADRAO_PLACA = re.compile(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}")
PADRAO_MOEDA = re.compile(r"-?R\$\s?(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)|Sem FIPE", re.I)
PADRAO_PERCENTUAL = re.compile(r"-?\d{1,2},\d%|Sem FIPE", re.I)
PADRAO_CABECALHO_TABELA = re.compile(
    r"\b(?:PLACA|MODELO|FAB|MOD|KM|COR|FIPE|UF|CIDADE|PREÇO|PRECO|DIST|MARGEM)\b",
    re.I,
)
PADRAO_UF = re.compile(r"^[A-Z]{2}$")


def remover_acentos(texto: str) -> str:
    if texto is None:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto_base(texto: str) -> str:
    texto = remover_acentos(texto).lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_texto_coluna(texto: str) -> str:
    return normalizar_texto_base(texto)


def limpar_valor_monetario(texto):
    if texto is None:
        return None

    texto = str(texto).strip()
    if not texto:
        return None

    texto_upper = texto.upper()
    if texto_upper in {"R$ -", "-", "SEM FIPE", "R$ SEM FIPE", "NAN"}:
        return None
    if "SEM FIPE" in texto_upper:
        return None

    negativo = texto.startswith("-")
    if negativo:
        texto = texto[1:].strip()

    texto = texto.replace("R$", "").strip()
    texto = re.sub(r"\s+", "", texto)

    if not texto or texto == "-" or texto.lower() == "nan":
        return None

    texto = texto.replace(".", "").replace(",", ".")

    try:
        valor = float(texto)
        if math.isnan(valor):
            return None
        return -valor if negativo else valor
    except ValueError:
        return None


def limpar_km(texto):
    if texto is None:
        return None

    texto = str(texto).strip()
    if not texto or texto.lower() == "nan":
        return None

    texto = texto.replace(".", "").replace(",", "").strip()

    try:
        return int(texto)
    except ValueError:
        return None


def calcular_preco_final(preco, percentual=4):
    if preco is None:
        return None
    return preco * (1 + percentual / 100)


def calcular_dist_fipe_final(fipe, preco_final):
    if fipe is None or preco_final is None:
        return None
    return fipe - preco_final


def calcular_margem_final(dist_fipe_final, fipe):
    if fipe in (None, 0) or dist_fipe_final is None:
        return None
    return dist_fipe_final / fipe


def formatar_moeda_br(valor):
    if valor is None:
        return ""
    try:
        if math.isnan(valor):
            return ""
    except TypeError:
        pass

    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def formatar_percentual_br(valor):
    if valor is None:
        return ""
    try:
        if math.isnan(valor):
            return ""
    except TypeError:
        pass

    return f"{valor * 100:.2f}%".replace(".", ",")


def eh_placa(token: str) -> bool:
    if token is None:
        return False
    token = str(token).strip().upper()
    return bool(re.fullmatch(PADRAO_PLACA, token))


def normalizar_linha_pdf(linha: str) -> str:
    linha = str(linha).strip()

    linha = re.sub(r"R\$(?=\d)", "R$ ", linha)
    linha = re.sub(r"-R\$(?=\d)", "-R$ ", linha)
    linha = re.sub(r"(?<=\d)\s+\.\s*(?=\d{3}\b)", ".", linha)
    linha = re.sub(r"R\$\s*(\d)\s+(?=\d{1,2}\.\d{3}\b)", r"R$ \1", linha)
    linha = re.sub(r"-R\$\s*(\d)\s+(?=\d{1,2}\.\d{3}\b)", r"-R$ \1", linha)
    linha = re.sub(r"(%)(?=[A-ZÁ-Ú])", r"% ", linha)
    linha = re.sub(r"(\d{1,3}(?:\.\d{3})+|\d{4,})(?=[A-ZÁ-Ú])", r"\1 ", linha)
    linha = re.sub(r"\s+", " ", linha).strip()
    return linha


def cortar_texto_antes_de_ruido(texto: Optional[str]) -> str:
    if not texto:
        return ""

    texto = str(texto).strip()
    texto = normalizar_linha_pdf(texto)

    padroes = [
        r"\bR\$\b",
        r"\bSEM FIPE\b",
        r"\bPLACA\b",
        r"\bMODELO\b",
        r"\bFAB\b",
        r"\bMOD\b",
        r"\bKM\b",
        r"\bCOR\b",
        r"\bFIPE\b",
        r"\bUF\b",
        r"\bCIDADE\b",
        r"\bPREÇO\b",
        r"\bPRECO\b",
        r"\bDIST\b",
        r"\bMARGEM\b",
        r"\b" + PADRAO_PLACA.pattern + r"\b",
        r"\b\d{1,2},\d%\b",
    ]

    menor_indice = None
    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.I)
        if m:
            if menor_indice is None or m.start() < menor_indice:
                menor_indice = m.start()

    if menor_indice is not None:
        texto = texto[:menor_indice].strip()

    texto = re.sub(r"\s+", " ", texto).strip(" -,/;")
    return texto


def limpar_cor(texto: Optional[str]) -> str:
    texto = cortar_texto_antes_de_ruido(texto)
    texto = re.sub(r"\b\d{4}\b.*$", "", texto).strip()
    return texto


def limpar_cidade(local: str) -> str:
    texto = cortar_texto_antes_de_ruido(local)
    texto_norm = normalizar_texto_base(texto)

    if not texto_norm:
        return ""

    mapa_cidades = {
        "paulo": "SÃO PAULO",
        "sao paulo": "SÃO PAULO",
        "campo": "SÃO BERNARDO DO CAMPO",
        "sao bernardo do campo": "SÃO BERNARDO DO CAMPO",
        "campinas": "CAMPINAS",
        "andre": "SANTO ANDRÉ",
        "santo andre": "SANTO ANDRÉ",
        "preto": "SÃO JOSÉ DO RIO PRETO",
        "sao jose do rio preto": "SÃO JOSÉ DO RIO PRETO",
        "sorocaba": "SOROCABA",
        "bauru": "BAURU",
        "marilia": "MARÍLIA",
        "prudente": "PRESIDENTE PRUDENTE",
        "presidente prudente": "PRESIDENTE PRUDENTE",
        "vicente": "SÃO VICENTE",
        "sao vicente": "SÃO VICENTE",
        "osasco": "OSASCO",
        "araraquara": "ARARAQUARA",
        "barueri": "BARUERI",
        "piracicaba": "PIRACICABA",
    }

    if texto_norm in mapa_cidades:
        return mapa_cidades[texto_norm]

    if "sao bernardo" in texto_norm:
        return "SÃO BERNARDO DO CAMPO"
    if "santo andre" in texto_norm:
        return "SANTO ANDRÉ"
    if "campinas" in texto_norm:
        return "CAMPINAS"
    if texto_norm == "sao paulo" or " sao paulo" in f" {texto_norm} ":
        return "SÃO PAULO"

    return str(texto).strip().title()


def texto_tem_contaminacao(texto: Optional[str]) -> bool:
    if texto is None:
        return False
    texto = str(texto)
    if not texto.strip():
        return False
    return bool(PADRAO_MOEDA.search(texto) or PADRAO_PERCENTUAL.search(texto) or PADRAO_CABECALHO_TABELA.search(texto) or PADRAO_PLACA.search(texto))


def registro_extraido_valido(registro: Optional[Mapping]) -> bool:
    if not registro:
        return False

    placa = str(registro.get("PLACA", "") or "").upper().strip()
    if not eh_placa(placa):
        return False

    for campo in ("FAB", "MOD", "KM"):
        valor = registro.get(campo)
        if valor is None:
            return False
        try:
            int(valor)
        except (TypeError, ValueError):
            return False

    uf = str(registro.get("UF", "") or "").upper().strip()
    if uf and not PADRAO_UF.fullmatch(uf):
        return False

    preco_original = registro.get("PREÇO ORIGINAL")
    if preco_original is None:
        return False

    for campo in ("MODELO", "COR", "CIDADE"):
        valor = str(registro.get(campo, "") or "").strip()
        if not valor:
            return False
        if texto_tem_contaminacao(valor):
            return False

    return True


def sanitizar_dataframe_saida(df):
    df = df.copy()

    if "PLACA" in df.columns:
        df["PLACA"] = df["PLACA"].astype(str).str.upper().str.extract(f"({PADRAO_PLACA.pattern})", expand=False)

    if "COR" in df.columns:
        df["COR"] = df["COR"].fillna("").apply(limpar_cor)

    if "CIDADE" in df.columns:
        df["CIDADE"] = df["CIDADE"].fillna("").apply(limpar_cidade)

    if "UF" in df.columns:
        df["UF"] = (
            df["UF"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.extract(r"([A-Z]{2})", expand=False)
            .fillna("")
        )

    return df
