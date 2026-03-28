"""
procurar_distvel.py — Módulo de Processamento de Distância e Velocidade

Responsável por organizar dados de distância percorrida e velocidade média
gerados pelo software Topscan (aba "Bin Measure"). Agrupa por dia em abas
separadas, soma Bin1 + Bin2, e calcula a distância em metros.
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.worksheet import Worksheet

# ─── Configuração de Logging ──────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────
TOPSCAN_HEADER_ROW = 6
SHEET_NAME = "Bin Measure"
MEASURE_COLUMN = "Measure"

# Eventos do Topscan para filtrar
EVENT_DISTANCE = "Mouse 1 Center Distance Traveled (apart 1.000000 second)"
EVENT_VELOCITY = "Mouse 1 Center Velocity Average (apart 1.000000 second)"

# Colunas de interesse após o merge
MERGE_KEYS = ["DAY", "ANIMAL"]
OUTPUT_COLUMNS = ["DAY", "ANIMAL", "Bin_Soma_dist", "Bin_Soma_vel"]

# Conversão de milímetros para metros
MM_TO_METERS_DIVISOR = 1000

# Renomeação de cabeçalhos para a planilha de saída
COLUMN_RENAMES = {
    "DAY": "Dia",
    "ANIMAL": "Animal",
    "Bin_Soma_dist": "Distância",
    "Bin_Soma_dist_blank": "Distância (metros)",
    "Bin_Soma_vel": "Velocidade",
}

# Formatação de largura das colunas Excel
COLUMN_WIDTHS = {
    "C": 14,   # Distância
    "D": 18,   # Distância (metros)
    "E": 14,   # Velocidade
}

# ─── Estilos do Excel ────────────────────────────────────────
CENTERED = Alignment(horizontal="center", vertical="center")
HEADER_FONT = Font(bold=True)
HEADER_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


# ─── Funções Auxiliares ───────────────────────────────────────

def _normalize_day_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza a coluna 'DAY': remove sufixo '.0', converte para inteiro,
    e descarta linhas com valores inválidos.
    """
    df["DAY"] = (
        df["DAY"]
        .astype(str)
        .str.replace(".0", "", regex=False)
    )
    df["DAY"] = pd.to_numeric(df["DAY"], errors="coerce")
    df = df.dropna(subset=["DAY"])
    return df


def _calculate_bin_sum(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula a soma de Bin1 + Bin2 (ou apenas Bin1 se Bin2 não existir).
    Valores não numéricos são tratados como 0.
    """
    df["Bin1"] = pd.to_numeric(df["Bin1"], errors="coerce").fillna(0)

    if "Bin2" in df.columns:
        df["Bin2"] = pd.to_numeric(df["Bin2"], errors="coerce").fillna(0)
        df["Bin_Soma"] = df["Bin1"] + df["Bin2"]
    else:
        df["Bin_Soma"] = df["Bin1"]

    return df


def _merge_distance_velocity(
    df: pd.DataFrame,
    day: int,
) -> pd.DataFrame:
    """
    Para um dia específico, filtra os eventos de distância e velocidade,
    faz o merge por (DAY, ANIMAL) e mantém apenas as colunas de interesse.

    Adiciona coluna de distância em metros (Bin_Soma / 1000).
    """
    distance_data = df[
        (df[MEASURE_COLUMN] == EVENT_DISTANCE) & (df["DAY"] == day)
    ]
    velocity_data = df[
        (df[MEASURE_COLUMN] == EVENT_VELOCITY) & (df["DAY"] == day)
    ]

    if distance_data.empty and velocity_data.empty:
        return pd.DataFrame()

    df_merged = pd.merge(
        distance_data,
        velocity_data,
        on=MERGE_KEYS,
        suffixes=("_dist", "_vel"),
    )

    # Mantém apenas as colunas que existem no merge
    available_columns = [col for col in OUTPUT_COLUMNS if col in df_merged.columns]
    df_merged = df_merged.reindex(columns=available_columns)

    # Calcula distância em metros
    if "Bin_Soma_dist" in df_merged.columns:
        insert_pos = df_merged.columns.get_loc("Bin_Soma_dist") + 1
        df_merged.insert(insert_pos, "Bin_Soma_dist_blank", "")
        df_merged["Bin_Soma_dist_blank"] = df_merged["Bin_Soma_dist"] / MM_TO_METERS_DIVISOR

    return df_merged


def _apply_worksheet_formatting(ws: Worksheet) -> None:
    """Aplica formatação visual profissional à planilha Excel."""
    # Larguras de colunas
    for col_letter, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    # Renomear cabeçalhos
    for cell in ws[1]:
        if cell.value in COLUMN_RENAMES:
            cell.value = COLUMN_RENAMES[cell.value]

    # Estilização de todas as células
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.alignment = CENTERED
            if cell.row == 1:
                cell.font = HEADER_FONT
                cell.border = HEADER_BORDER


def _get_or_create_sheet(workbook: Workbook, name: str) -> Worksheet:
    """Retorna a aba existente ou cria uma nova no workbook."""
    if name in workbook.sheetnames:
        return workbook[name]
    return workbook.create_sheet(title=name)


# ─── Função Principal (API Pública) ──────────────────────────

def organizar(
    caminho_arquivo: str,
    workbook: Workbook,
) -> List[int]:
    """
    Organiza dados de distância/velocidade do Topscan em abas por dia.

    Lê a aba 'Bin Measure' do arquivo Excel, calcula Bin1+Bin2,
    separa por dia, e cria uma aba formatada para cada dia no workbook.

    Args:
        caminho_arquivo: Caminho completo do arquivo Excel do Topscan.
        workbook:        Workbook do openpyxl para escrita.

    Returns:
        Lista com os dias únicos processados (inteiros), ou lista vazia em caso de erro.
    """
    # Carregamento dos dados
    try:
        df = pd.read_excel(
            caminho_arquivo,
            header=TOPSCAN_HEADER_ROW,
            sheet_name=SHEET_NAME,
        )
    except Exception as exc:
        logger.error("Erro ao ler a aba '%s': %s", SHEET_NAME, exc)
        return []

    # Pré-processamento
    df = _normalize_day_column(df)
    df = _calculate_bin_sum(df)

    unique_days = sorted(df["DAY"].unique().astype(int))

    # Processamento por dia
    for day in unique_days:
        # Criar aba ANTES de verificar dados (mantém compatibilidade com o original)
        ws = _get_or_create_sheet(workbook, str(day))

        df_day = _merge_distance_velocity(df, day)

        if df_day.empty:
            logger.debug("Dia %d sem dados de distância/velocidade, pulando.", day)
            continue

        # Escrever dados na aba
        for row in dataframe_to_rows(df_day, index=False, header=True):
            ws.append(row)

        # Formatação visual
        _apply_worksheet_formatting(ws)
        logger.info("Dia %d processado com sucesso.", day)

    return unique_days
