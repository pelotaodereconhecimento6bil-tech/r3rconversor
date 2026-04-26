COLUNAS_FINAIS = [
    "PLACA",
    "MODELO",
    "FAB",
    "MOD",
    "KM",
    "COR",
    "FIPE",
    "UF",
    "CIDADE",
    "PREÇO FINAL",
    "DIST FIPE FINAL",
    "MARGEM FINAL",
]

MONEY_PATTERN = r"(?:-?R\$\s?(?:-|\d{1,3}(?:\.\d{3})*(?:,\d{2})?)|Sem FIPE)"
PERCENT_PATTERN = r"(?:-?\d{1,2},\d%|Sem FIPE)"

UFS_BRASIL = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

UF_REGEX = "(?:" + "|".join(sorted(UFS_BRASIL)) + ")"

CORES_BASE_PDF = [
    "BRANCO", "BRANCA", "PRETO", "PRETA", "CINZA", "PRATA", "AZUL",
    "VERMELHO", "VERMELHA", "VERDE", "AMARELO", "AMARELA", "MARROM",
]

CORRECOES_COR_PDF = {
    "OCINZA": "CINZA",
    "OPRETO": "PRETO",
    "OBRANCO": "BRANCO",
    "OBRANCA": "BRANCA",
    "OPRATA": "PRATA",
    "OAZUL": "AZUL",
    "OVERMELHO": "VERMELHO",
    "OVERMELHA": "VERMELHA",
    "CPORETO": "PRETO",
    "CPRETO": "PRETO",
    "CPORATA": "PRATA",
    "CPRATA": "PRATA",
    "CBORANCO": "BRANCO",
    "CBRANCO": "BRANCO",
    "CBRANCA": "BRANCA",
    "CCOINZA": "CINZA",
    "CCINZA": "CINZA",
    "CPAZUL": "AZUL",
}

PALAVRAS_INVALIDAS_CIDADE = {
    "AVENIDA", "AV", "AV.", "RUA", "RODOVIA", "ROD", "ESTRADA",
    "SHOPPING", "LOJA", "MARGINAL", "PRAÇA", "PRACA", "ALAMEDA",
    "TRAVESSA", "KM", "Nº", "NO", "N", "D", "C&C", "C", "CC",
}

CIDADES_CONHECIDAS_PDF = {
    "OSASCO": "OSASCO",
    "CAMPINAS": "CAMPINAS",
    "RIBEIRAO PRETO": "RIBEIRÃO PRETO",
    "RIBEIRÃO PRETO": "RIBEIRÃO PRETO",
    "SAO PAULO": "SÃO PAULO",
    "SÃO PAULO": "SÃO PAULO",
    "SAO BERNARDO DO CAMPO": "SÃO BERNARDO DO CAMPO",
    "SÃO BERNARDO DO CAMPO": "SÃO BERNARDO DO CAMPO",
    "SANTO ANDRE": "SANTO ANDRÉ",
    "SANTO ANDRÉ": "SANTO ANDRÉ",
    "SOROCABA": "SOROCABA",
    "BAURU": "BAURU",
    "MARILIA": "MARÍLIA",
    "MARÍLIA": "MARÍLIA",
    "PRESIDENTE PRUDENTE": "PRESIDENTE PRUDENTE",
    "SAO VICENTE": "SÃO VICENTE",
    "SÃO VICENTE": "SÃO VICENTE",
    "SAO JOSE DO RIO PRETO": "SÃO JOSÉ DO RIO PRETO",
    "SÃO JOSÉ DO RIO PRETO": "SÃO JOSÉ DO RIO PRETO",
    "ARARAQUARA": "ARARAQUARA",
    "BARUERI": "BARUERI",
    "PIRACICABA": "PIRACICABA",
}