import re


def corrigir_espacos_colados(texto: str) -> str:
    texto = str(texto or "")

    # 2023/2023PRETO -> 2023/2023 PRETO
    texto = re.sub(
        r"((?:19|20)\d{2}/(?:19|20)\d{2})(?=[A-ZÁ-Ú])",
        r"\1 ",
        texto,
    )

    # 4PPRETO -> 4P PRETO
    texto = re.sub(
        r"(\b[12456]P)(?=[A-ZÁ-Ú])",
        r"\1 ",
        texto,
        flags=re.IGNORECASE,
    )

    # metálicaR$ -> metálica R$
    texto = re.sub(
        r"(?<!\s)(R\$)",
        r" \1",
        texto,
    )

    # textohttps:// -> texto https://
    texto = re.sub(
        r"(?<!\s)(https?://)",
        r" \1",
        texto,
    )

    return texto


def corrigir_anos_corrompidos(texto: str) -> str:
    texto = str(texto or "")

    substituicoes = {

        # MOVIDA
        r"ME2C0\.146P/((?:19|20)\d{2})":
            r"MEC.4P 2016/\1",

        r"ME2C0\.(\d{2})/((?:19|20)\d{2})":
            r"MEC. 20\1/\2",

        r"A2U0T2\.(\d)/((?:19|20)\d{2})":
            r"AUT. 202\1/\2",

        r"AU2T0\.(\d{2})/((?:19|20)\d{2})":
            r"AUT. 20\1/\2",

        r"220P(\d{2})/((?:19|20)\d{2})":
            r"2P 20\1/\2",

        r"PL2U0S(\d{2})/((?:19|20)\d{2})":
            r"PLUS 20\1/\2",

        r"\(VW PLAY2\)(\d{3}/(?:19|20)\d{2})":
            r"(VW PLAY) 2\1",

        r"\(HÍBRID20O2\)1/((?:19|20)\d{2})":
            r"(HÍBRIDO) 2021/\1",

        r"FLEX2\s*0A2U3T/2\.023":
            r"FLEX AUT. 2023/2023",
    }

    for padrao, substituicao in substituicoes.items():

        texto = re.sub(
            padrao,
            substituicao,
            texto,
            flags=re.IGNORECASE,
        )

    return texto


def corrigir_modelos_colados(texto: str) -> str:
    texto = str(texto or "")

    # MODELO2023/2024
    texto = re.sub(
        r"(?<=[A-ZÁ-Ú0-9\.\)])(?=(?:19|20)\d{2}/(?:19|20)\d{2})",
        " ",
        texto,
    )

    return texto


def corrigir_km_colado(texto: str) -> str:
    texto = str(texto or "")

    texto = re.sub(
        r"(?<=\d)(?=Não\b)",
        " ",
        texto,
        flags=re.IGNORECASE,
    )

    texto = re.sub(
        r"(?<=\d)(?=Sim\b)",
        " ",
        texto,
        flags=re.IGNORECASE,
    )

    return texto


def corrigir_ocr_automotivo(texto: str) -> str:
    texto = str(texto or "").strip()

    texto = corrigir_espacos_colados(texto)

    texto = corrigir_anos_corrompidos(texto)

    texto = corrigir_modelos_colados(texto)

    texto = corrigir_km_colado(texto)

    texto = re.sub(r"\s+", " ", texto).strip()

    return texto