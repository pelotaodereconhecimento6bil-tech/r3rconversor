import re
from pathlib import Path

import pandas as pd
import pdfplumber

from utils import limpar_km
from core.normalizador import normalizar_texto_coluna


def _valor_unidas_para_float(valor):
    texto = str(valor or "").strip()

    if not texto or texto == "-" or "#VALOR" in texto.upper():
        return None

    texto = texto.replace("R$", "").strip()

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(".", "")

    texto = re.sub(r"[^\d\.-]", "", texto)

    if not texto or texto in {"-", "."}:
        return None

    try:
        return float(texto)
    except Exception:
        return None


def _normalizar_linha_unidas(linha):
    linha = str(linha or "").strip()
    linha = re.sub(r"\s+", " ", linha)

    # Padrão: PADRÃO
    linha = re.sub(
        r"(\d{5,6})\s+PADRÃO\s+(\d{2}/\d{2})",
        r"\1 PADRÃO \2",
        linha,
        flags=re.IGNORECASE,
    )

    # Corrige KM invadindo cor: 9P1re6t8o9 -> 91689 Preto
    linha = re.sub(
        r"(\d)P(\d)re(\d+)t?o(\d)",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)} Preto",
        linha,
        flags=re.IGNORECASE,
    )

    # Corrige KM invadindo Branco: 7B15ra9n5co -> 71595 Branco
    linha = re.sub(
        r"(\d+)B(\d*)ra(\d*)n(\d*)co",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)} Branco",
        linha,
        flags=re.IGNORECASE,
    )

    # Corrige KM invadindo Prata: 1P4r7a0t3a -> 14703 Prata
    linha = re.sub(
        r"(\d+)P(\d*)ra(\d*)t(\d*)a",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)} Prata",
        linha,
        flags=re.IGNORECASE,
    )

    # Corrige KM invadindo Cinza: 2C3in7z4a8 -> 23748 Cinza
    linha = re.sub(
        r"(\d+)C(\d*)in(\d*)z(\d*)a",
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)} Cinza",
        linha,
        flags=re.IGNORECASE,
    )

    # Corrige Azul com KM colado: 4PAzul N2a2v8a9r0ra -> 4P 22890 Azul
    linha = re.sub(
        r"(\b[24]P)Azul\s+N(\d+)a(\d+)v(\d+)a(\d+)r(\d*)ra",
        lambda m: f"{m.group(1)} {m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}{m.group(6)} Azul Navarra",
        linha,
        flags=re.IGNORECASE,
    )

    # Normaliza ano quebrado dentro de sólida/metálica/perolizada.
    linha = re.sub(
        r"S[óo]2li/d(\d)a",
        r"Sólida 2\1/",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"S[óo](\d{2})li/d(\d{2})a",
        r"Sólida \1/\2",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"S[óo](\d)l(\d)id/o(\d{2})",
        r"Sólida \1\2/\3",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"so(\d)l(\d)id/o(\d{2})",
        r"solido \1\2/\3",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"Me(\d{2})t(\d{2})ál/i(\d{2})ca(\d*)",
        r"Metálica \1/\3",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"M(\d{2})e/t(\d)á(\d)lica",
        r"Metálica \1/\2\3",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"Met(\d{2})áli/c(\d)a",
        r"Metálica \1/\2",
        linha,
        flags=re.IGNORECASE,
    )
    linha = re.sub(
        r"Met(\d{2})ál/ic(\d)a",
        r"Metálica \1/\2",
        linha,
        flags=re.IGNORECASE,
    )

    # Casos de ano em Sólida: Só2l3id/2a4 -> Sólida 23/24
    linha = re.sub(
        r"S[óo](\d)l(\d)id/(\d)a(\d)",
        r"Sólida \1\2/\3\4",
        linha,
        flags=re.IGNORECASE,
    )

    # NÃO INFORMADA colado com ano.
    linha = linha.replace("INFORMAD ", "INFORMADA ")
    linha = re.sub(
        r"(NÃO INFORMADA|NAO INFORMADA|NÃ?O INFORMAD[A]?)(\d{2}/\d{2})",
        r"NÃO INFORMADA \2",
        linha,
        flags=re.IGNORECASE,
    )

    # 4P62021 -> 4P 62021
    linha = re.sub(r"(\b[24]P)\s*(\d{5,6})\s+", r"\1 \2 ", linha)

        # 4PPra8t0a4 -> 4P Pra8t0a4
    linha = re.sub(
        r"(\b[12456]P)(?=[A-Za-zÁ-Úá-ú])",
        r"\1 ",
        linha,
        flags=re.IGNORECASE,
    )

    # R$ colado em metálicaR$ -> metálica R$
    linha = re.sub(r"(?<!\s)(R\$)", r" \1", linha)

    # Cor colada no ano.
    linha = re.sub(
        r"([A-Za-zÁ-Úá-ú]+)(\d{2}/\d{2})",
        r"\1 \2",
        linha,
    )

    # R$ colado após texto.
    linha = re.sub(r"(?<!\s)(R\$)", r" \1", linha)

    linha = re.sub(r"\s+", " ", linha).strip()
    return linha


def _extrair_ano_flexivel(texto):
    texto = str(texto or "")

    m = re.search(r"(\d{2})/(\d{2})", texto)
    if m:
        return int("20" + m.group(1)), int("20" + m.group(2)), m.start()

    for m in re.finditer(r"/", texto):
        antes = texto[max(0, m.start() - 20):m.start()]
        depois = texto[m.end():m.end() + 20]

        dig_antes = re.findall(r"\d", antes)
        dig_depois = re.findall(r"\d", depois)

        if len(dig_antes) >= 2 and len(dig_depois) >= 2:
            fab = int("20" + "".join(dig_antes[-2:]))
            mod = int("20" + "".join(dig_depois[:2]))
            return fab, mod, m.start()

    return None, None, None


def _extrair_km_flexivel(resto_pos_modelo, idx_ano):
    texto = str(resto_pos_modelo or "")
    trecho = texto[:idx_ano] if idx_ano is not None else texto

    # KM válido operacionalmente: 4 a 6 dígitos.
    # Se vier com 3 dígitos, considera inconsistente e retorna "-"
    m = re.search(r"\b\d{3,6}\b", trecho)
    if m:
        km_txt = m.group(0)
        if len(km_txt) <= 3:
            return "-"
        km = limpar_km(km_txt)
        return km if km is not None else "-"

    digitos = re.findall(r"\d", trecho)

    if len(digitos) < 4:
        return "-"

    if idx_ano is not None and len(digitos) >= 7:
        digitos_km = digitos[:-2]
    else:
        digitos_km = digitos

    if len(digitos_km) <= 3:
        return "-"

    km_txt = "".join(digitos_km[:6])
    km = limpar_km(km_txt)

    return km if km is not None else "-"


def _extrair_cor_flexivel(texto):
    t = str(texto or "").upper()

    if "NÃ" in t or "NAO" in t or "NÃO" in t or "INFORMAD" in t:
        return "NÃO INFORMADA"
    if "PADRÃO" in t or "PADRAO" in t:
        return "PADRÃO"
    if "BRAN" in t:
        return "BRANCO"
    if "PRET" in t:
        return "PRETO"
    if "PRAT" in t or "PRA" in t:
        return "PRATA"
    if "CINZ" in t:
        return "CINZA"
    if "AZUL" in t:
        return "AZUL"
    if "VERM" in t:
        return "VERMELHA"
    if "VERD" in t:
        return "VERDE"

    return ""


def _extrair_valores_tail(linha):
    valores_r = re.findall(
        r"R\$\s?-?[\d\.]+(?:,\d{2})?",
        linha,
        flags=re.IGNORECASE,
    )

    if len(valores_r) < 2:
        return None, None, "FIPE ou preço com desconto ausente"

    fipe = _valor_unidas_para_float(valores_r[0])
    preco_base = _valor_unidas_para_float(valores_r[1])

    if fipe is None:
        return None, None, "FIPE ausente ou inválida"

    if preco_base is None:
        return None, None, "Preço com desconto ausente ou inválido"

    return fipe, preco_base, None


def _falha(placa, motivo, linha):
    placa = placa or "Placa não identificada"
    return f"{placa} | {motivo} | {linha}"


def _parsear_linha_unidas(linha_bruta):
    linha = _normalizar_linha_unidas(linha_bruta)

    placa_match = re.search(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", linha)
    placa_debug = placa_match.group(0) if placa_match else ""

    if not linha:
        return None, _falha(placa_debug, "Linha vazia", linha_bruta)

    if "#VALOR" in linha.upper():
        return None, _falha(placa_debug, "FIPE/preço inválido (#VALOR)", linha_bruta)

    fipe, preco_base, erro_valor = _extrair_valores_tail(linha)

    if erro_valor:
        return None, _falha(placa_debug, erro_valor, linha_bruta)

    if fipe <= 0:
        return None, _falha(placa_debug, "FIPE zerada ou negativa", linha_bruta)

    m_inicio = re.match(
        r"^(RAC|FLEET)\s+([A-Z]{3}[0-9][A-Z0-9][0-9]{2})\s+(.+?)\s+R\$",
        linha,
        flags=re.IGNORECASE,
    )

    if not m_inicio:
        return None, _falha(placa_debug, "Estrutura inicial não reconhecida", linha_bruta)

    placa = m_inicio.group(2).upper().strip()
    corpo = m_inicio.group(3).strip()

    m_modelo = re.search(r"\b[12456]P\b|[12456]P(?=[A-Za-zÁ-Úá-ú])", corpo)

    if not m_modelo:
        return None, _falha(placa, "Modelo sem marcador 2P/4P/5P", linha_bruta)

    fim_modelo = m_modelo.end()
    modelo = corpo[:fim_modelo].strip()
    resto = corpo[fim_modelo:].strip()

    if not modelo:
        return None, _falha(placa, "Modelo ausente", linha_bruta)

    fab, mod, idx_ano = _extrair_ano_flexivel(resto)

    if fab is None or mod is None:
        return None, _falha(placa, "Ano não identificado", linha_bruta)

    km = _extrair_km_flexivel(resto, idx_ano)

    if km is None:
        km = "-"

    cor = _extrair_cor_flexivel(resto)

    if not cor:
        cor = "NÃO INFORMADA"

    return {
        "PLACA": placa,
        "MODELO": modelo,
        "FAB": fab,
        "MOD": mod,
        "KM": km,
        "COR": cor,
        "FIPE": fipe,
        "UF": "SP",
        "CIDADE": "",
        "PREÇO ORIGINAL": preco_base,
        "ORIGEM": "unidas",
    }, None


def montar_dataframe_unidas(caminho_pdf: Path):
    registros = []
    falhas = []
    unidas_detectada = False

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""

            if not texto:
                texto = pagina.extract_text(layout=True) or ""

            if not texto:
                continue

            texto_norm = normalizar_texto_coluna(texto)

            if (
                "tipo venda" in texto_norm
                and "valor fipe" in texto_norm
                and "desconto" in texto_norm
            ):
                unidas_detectada = True

            for linha in texto.split("\n"):
                linha = linha.strip()

                if not linha:
                    continue

                if not re.match(r"^(RAC|FLEET)\s+", linha, flags=re.IGNORECASE):
                    continue

                registro, erro = _parsear_linha_unidas(linha)

                if registro:
                    registros.append(registro)
                else:
                    falhas.append(erro or linha)

    if not unidas_detectada and not registros:
        return pd.DataFrame(), []

    return pd.DataFrame(registros), falhas