import re
from pathlib import Path

from utils import limpar_valor_monetario

from core.constantes import (
    CIDADES_CONHECIDAS_PDF,
    CORES_BASE_PDF,
    CORRECOES_COR_PDF,
    PALAVRAS_INVALIDAS_CIDADE,
    UFS_BRASIL,
)


def normalizar_linha(linha: str) -> str:
    linha = str(linha or "").strip()

    linha = re.sub(r"C/A\s*2R(?=\d{3}\b)", "C/AR 2", linha, flags=re.IGNORECASE)
    linha = re.sub(r"C/A(?=\d{4}\b)", "C/AR ", linha, flags=re.IGNORECASE)

    linha = re.sub(r"(?<=\s)(\d)\s+(\d{1,2}\.\d{3},\d{2})(?=\s|$)", r"\1\2", linha)

    linha = re.sub(r"(?<=[A-ZÁ-Ú])R\$", " R$", linha)
    linha = re.sub(r"(?<=[A-ZÁ-Ú])-R\$", " -R$", linha)

    linha = re.sub(r"R\$(?=\d)", "R$ ", linha)
    linha = re.sub(r"-R\$(?=\d)", "-R$ ", linha)

    linha = re.sub(r"(?<=[A-ZÁ-Ú/])(?=\d{4}\s+\d{4}\b)", " ", linha)

    linha = re.sub(r"(?<=\d)\s+\.\s*(?=\d{3}\b)", ".", linha)

    linha = re.sub(r"R\$\s*(\d)\s+(?=\d{1,2}\.\d{3}\b)", r"R$ \1", linha)
    linha = re.sub(r"-R\$\s*(\d)\s+(?=\d{1,2}\.\d{3}\b)", r"-R$ \1", linha)

    linha = re.sub(r"(%)(?=[A-ZÁ-Ú])", r"% ", linha)
    linha = re.sub(r"(\d{1,3}(?:\.\d{3})+|\d{4,})(?=[A-ZÁ-Ú])", r"\1 ", linha)

    linha = re.sub(r"\s+", " ", linha).strip()
    return linha


def normalizar_texto_coluna(texto: str) -> str:
    texto = str(texto or "").lower().strip()

    substituicoes = {
        "á": "a", "à": "a", "ã": "a", "â": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for k, v in substituicoes.items():
        texto = texto.replace(k, v)

    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def corrigir_texto_celula_pdf(valor) -> str:
    texto = str(valor or "").replace("\n", " ").strip()
    texto = re.sub(r"(?<=[A-ZÁ-Ú])R\$", " R$", texto)
    texto = re.sub(r"(?<=[A-ZÁ-Ú])-R\$", " -R$", texto)
    texto = re.sub(r"R\$(?=\d)", "R$ ", texto)
    texto = re.sub(r"-R\$(?=\d)", "-R$ ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def limpar_cor_tabela_pdf(valor) -> str:
    texto = corrigir_texto_celula_pdf(valor).upper().strip()

    if not texto:
        return ""

    if "R$" in texto:
        texto = texto.split("R$", 1)[0].strip()

    if "SEM FIPE" in texto:
        texto = texto.split("SEM FIPE", 1)[0].strip()

    texto_sem_espaco = texto.replace(" ", "")

    for ruim, bom in CORRECOES_COR_PDF.items():
        if texto_sem_espaco.startswith(ruim):
            texto = bom + " " + texto_sem_espaco[len(ruim):]
            break

    melhor_pos = None

    for cor in CORES_BASE_PDF:
        pos = texto.find(cor)
        if pos >= 0 and (melhor_pos is None or pos < melhor_pos):
            melhor_pos = pos

    if melhor_pos is not None:
        texto = texto[melhor_pos:]

    texto = re.sub(r"[^A-ZÁ-ÚÇ ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    palavras = texto.split()
    return " ".join(palavras[:2]).strip()


def limpar_cidade(local: str) -> str:
    texto = str(local or "").upper().strip()

    if "SAO BERNARDO" in texto or "SÃO BERNARDO" in texto or "CAMPO" in texto:
        return "SÃO BERNARDO DO CAMPO"

    if "CAMPINAS" in texto:
        return "CAMPINAS"

    if "RIBEIRAO" in texto or "RIBEIRÃO" in texto:
        return "RIBEIRÃO PRETO"

    if "ANDRE" in texto:
        return "SANTO ANDRÉ"

    if "PAULO" in texto:
        return "SÃO PAULO"

    return str(local or "").strip().title()


def normalizar_cidade_sem_endereco(valor: str) -> str:
    texto = str(valor or "").strip()
    texto = re.sub(r"\s+", " ", texto).strip(" ,;-")

    if not texto:
        return ""

    texto_up = texto.upper()

    if "CAMPINAS" in texto_up:
        return "CAMPINAS"

    if "RIBEIRAO" in texto_up or "RIBEIRÃO" in texto_up:
        return "RIBEIRÃO PRETO"

    if "OSASCO" in texto_up:
        return "OSASCO"

    if "SAO BERNARDO" in texto_up or "SÃO BERNARDO" in texto_up:
        return "SÃO BERNARDO DO CAMPO"

    for cidade_bruta, cidade_canonica in sorted(
        CIDADES_CONHECIDAS_PDF.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if texto_up == cidade_bruta or texto_up.startswith(cidade_bruta + " "):
            return cidade_canonica

    tokens = texto_up.split()
    cidade_tokens = []

    for token in tokens:
        token_limpo = token.strip(".,;:-")

        if token_limpo in PALAVRAS_INVALIDAS_CIDADE:
            break

        cidade_tokens.append(token_limpo)

    cidade = " ".join(cidade_tokens).strip()

    if not cidade:
        return ""

    if cidade in CIDADES_CONHECIDAS_PDF:
        return CIDADES_CONHECIDAS_PDF[cidade]

    return cidade.title()


def limpar_modelo_sem_invasao(valor: str) -> str:
    texto = corrigir_texto_celula_pdf(valor)
    texto = re.sub(r"\s+", " ", texto).strip()

    if not texto:
        return ""

    tokens = texto.split()

    remover_finais = set(UFS_BRASIL) | {
        "CAMPINAS", "OSASCO", "PAULO", "SOROCABA", "BAURU",
        "MARILIA", "MARÍLIA", "ARARAQUARA", "BARUERI",
        "PIRACICABA", "PRUDENTE", "VICENTE", "PRETO",
    }

    while tokens and tokens[-1].upper().strip(".,;:-") in remover_finais:
        tokens.pop()

    return " ".join(tokens).strip()


def valor_localiza_para_float(valor: str):
    texto = str(valor or "").strip()

    if not texto:
        return None

    texto_up = texto.upper()

    if "SEM FIPE" in texto_up or texto_up in {"R$ -", "-", "R$"}:
        return None

    texto = texto.replace("R$", "").strip()
    texto = re.sub(r"\s+", "", texto)

    if not texto or texto == "-":
        return None

    negativo = texto.startswith("-")

    if negativo:
        texto = texto[1:]

    if re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto):
        valor_float = float(texto.replace(".", "").replace(",", "."))

    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})*", texto):
        valor_float = float(texto.replace(".", ""))

    elif re.fullmatch(r"\d+", texto):
        valor_float = float(texto)

    else:
        return limpar_valor_monetario(("-" if negativo else "") + texto)

    return -valor_float if negativo else valor_float


def inferir_cidade_por_nome_arquivo(caminho_pdf: Path) -> str:
    nome = normalizar_texto_coluna(Path(caminho_pdf).stem).upper()

    if "RIBEIRAO" in nome or "RIBEIRÃO" in nome:
        return "RIBEIRÃO PRETO"

    if "CAMPINAS" in nome:
        return "CAMPINAS"

    if "OSASCO" in nome:
        return "OSASCO"

    if "SAO BERNARDO" in nome or "SÃO BERNARDO" in nome:
        return "SÃO BERNARDO DO CAMPO"

    if "SANTO ANDRE" in nome or "SANTO ANDRÉ" in nome:
        return "SANTO ANDRÉ"

    if "RAPOSO" in nome or "SAO PAULO" in nome or "SÃO PAULO" in nome:
        return "SÃO PAULO"

    return "SÃO PAULO"