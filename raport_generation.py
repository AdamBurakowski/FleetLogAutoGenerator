import pandas as pd
import locale
import calendar
import os
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, KeepTogether
)

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import landscape, A4

def aggregate_trips(file):
    df = file

    df["Stan Licznika"] = df["Stan Licznika"].astype(str).str.replace(" ", "").astype(int)

    df["Data i Godzina"] = pd.to_datetime(
        df["Data i Godzina"],
        format="%d.%m.%Y %H:%M",
        errors="coerce"
    )

    df = df.sort_values("Data i Godzina").reset_index(drop=True)

    df = df.sort_values("Data i Godzina").reset_index(drop=True)

    df["Data i Godzina_display"] = df["Data i Godzina"].dt.strftime("%d.%m.%Y")

    trips = []
    current_trip = None

    for _, row in df.iterrows():
        if row["Cel Trasy"] != "Powrót" and current_trip is None:
            start_tacho = row["Stan Licznika"]
            current_trip = {
                "Data wyjazdu": row["Data i Godzina_display"],
                "Cel trasy": row["Cel Trasy"],
                "Stan licznika\nwyjazd": row["Stan Licznika"],
            }
        elif row["Cel Trasy"] == "Powrót" and current_trip is not None:
            current_trip["Stan licznika\nprzyjazd"] = row["Stan Licznika"]
            current_trip["Liczba faktycznie przejechanych kilometrów"] = row["Stan Licznika"] - start_tacho
            current_trip["Kierowca"] = row["Kierowca"]
            trips.append(current_trip)
            current_trip = None

    result = pd.DataFrame(trips)

    return result

def raport_generate(df, other_data=[], save_path=""):
    locale.setlocale(locale.LC_TIME, 'pl_PL.UTF-8')
    styles = getSampleStyleSheet()
    pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSerif.ttf'))

    if not df.empty:
        first_date = pd.to_datetime(df.iloc[0]["Data wyjazdu"], format="%d.%m.%Y", errors="coerce")
        month_names = ["styczeń","luty","marzec","kwiecień","maj",
            "czerwiec","lipiec","sierpień","wrzesień",
            "październik","listopad","grudzień"]
        month_name = month_names[first_date.month - 1]
        year = first_date.year
        tacho_start = df.iloc[0]["Stan licznika\nwyjazd"]
        tacho_end = df.iloc[-1]["Stan licznika\nprzyjazd"]
    else:
        month_name = "_" * 8
        year = "_" * 8

    if len(other_data) == 4:
        registration_plate = other_data[0]
        driver_assigned = other_data[1]
        start_date = other_data[2]
        end_date = other_data[3]
        filename = f"{registration_plate}_{month_name}_{year}.pdf"
        kilometers = round((tacho_end - tacho_start) / max((
            datetime.strptime(end_date, "%d.%m.%Y"
        ) - datetime.strptime(start_date, "%d.%m.%Y")).days, 1), 1)
        kilometers = str(kilometers).replace('.', ',')
    elif len(other_data) > 4:  # manual mode
        registration_plate = other_data[0]
        driver_assigned = other_data[1]
        start_date = other_data[2]
        end_date = other_data[3]
        tacho_start = other_data[4]
        tacho_end = other_data[5]
        kilometers = other_data[6]
        filename = f"{registration_plate}_{month_name}_{year}.pdf"
    else:
        filename = "raport.pdf"
        len_of_line = 40
        driver_assigned = "_" * len_of_line
        registration_plate = "_" * len_of_line
        start_date = "_" * len_of_line
        end_date = "_" * len_of_line
        tacho_start = "_" * len_of_line
        tacho_end = "_" * len_of_line
        kilometers = "_" * len_of_line

    l_style = ParagraphStyle(
        'left_style',
        fontName='DejaVu',
        fontSize=10,
        alignment=0  # left
    )

    r_style = ParagraphStyle(
        'right_style',
        fontName='DejaVu',
        fontSize=10,
        alignment=2  # right
    )

    import_data = [
    [Paragraph(f"Dane podatnika:<br/>{driver_assigned}", l_style),
     Paragraph(f"Numer rejestracyjny pojazdu samochodowego:<br/>{registration_plate}", r_style)],

    [Paragraph(f"Dzień rozpoczęcia prowadzenia ewidencji:<br/>{start_date}", l_style),
     Paragraph(f"Dzień zakończenia prowadzenia ewidencji:<br/>{end_date}", r_style)],

    [Paragraph(f"Stan licznika na dzień rozpoczęcia prowadzenia ewidencji:<br/>{tacho_start} km", l_style),
     Paragraph(f"Stan Licznika na dzień zakończenia prowadzenia ewidencji:<br/>{tacho_end} km", r_style)],

    [Paragraph("", l_style),
     Paragraph(f"Liczba przejechanych kilometrów na dzień:<br/>{kilometers} km", r_style)]
    ]

    borderless_table = Table(import_data, colWidths=[250, 250])

    borderless_table.setStyle(TableStyle([
    ('BOX', (0,0), (-1,-1), 0, colors.white),
    ('INNERGRID', (0,0), (-1,-1), 0, colors.white),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))

    page_width = A4[0] - 40  # margins: left+right = 40
    col_ratios = [1.0, 1.5, 1.2, 1.5, 1.5, 1.2]  # relative widths
    total_ratio = sum(col_ratios)
    col_widths = [page_width * r / total_ratio for r in col_ratios]

    wrap_style = ParagraphStyle(
        'wrap',
        parent=styles['BodyText'],
        fontName='DejaVu',
        fontSize=8,
        leading=12,
        alignment=1  # center
    )

    header_row_height = 100
    last_col_width = col_widths[4]

    last_header_table = Table(
        [
            [Paragraph("Stan licznika na dzień udostępnienia pojazdu", wrap_style)],
            [Paragraph("Stan licznika na dzień zwrotu pojazdu", wrap_style)]
        ],
        colWidths=[last_col_width],
        rowHeights=[header_row_height/2]*2,
        style=TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE")
        ])
    )

    header_row = [
        Paragraph("Data udostępnienia pojazdu", wrap_style),
        Paragraph("Cel wyjazdu", wrap_style),
        Paragraph("Liczba faktycznie przejechanych kilometrów", wrap_style),
        Paragraph("Imię i nazwisko osoby kierującej pojazdem", wrap_style),
        last_header_table,
        Paragraph("Sprawdzenie stanu technicznego pojazdu", wrap_style)
    ]

    data = [header_row]

    data_row_height = 60

    for _, row in df.iterrows():
        last_col_table = Table(
            [
                [Paragraph(str(row['Stan licznika\nwyjazd']), wrap_style)],
                [Paragraph(str(row['Stan licznika\nprzyjazd']), wrap_style)]
            ],
            colWidths=last_col_width,
            rowHeights=[data_row_height/2]*2,
            style=TableStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE")
            ])
        )

        data.append([
            Paragraph(str(row["Data wyjazdu"]), wrap_style),
            Paragraph(str(row["Cel trasy"]), wrap_style),
            Paragraph(str(row["Liczba faktycznie przejechanych kilometrów"]), wrap_style),
            Paragraph(str(row["Kierowca"]), wrap_style),
            last_col_table,
            Paragraph("", wrap_style)
        ])

    title_text = f"EWIDENCJA PRZEBIEGU POJAZDU<br/>za miesiąc {month_name} roku {year}"
    title_style = ParagraphStyle(
        'title',
        parent=getSampleStyleSheet()['Title'],
        fontName='DejaVu',
        fontSize=16,
        leading=20,
        alignment=1  # centered
    )

    title_para = Paragraph(title_text, title_style)
    spacer = Spacer(1, 20)
    os.makedirs(save_path, exist_ok=True)
    filename = os.path.join(save_path, filename)
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    table = Table(data, colWidths=col_widths, repeatRows=1, rowHeights=[header_row_height] + [data_row_height]*(len(data)-1))

    style = TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND", (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6)
    ])
    table.setStyle(style)

    additional_para = Paragraph(
    "Cotygodniowe i comiesięczne sprawdzenie stanu technicznego",
    ParagraphStyle(
        'additional',
        parent=styles['BodyText'],
        fontName='DejaVu',
        fontSize=10,
        alignment=1  # centered
        )
    )

    small_spacer = Spacer(1, 12)

    weekly_table_data = [[Paragraph(f"Tydzień {i+1}", wrap_style) for i in range(6)], [""] * 6]

    weekly_table = Table(
        weekly_table_data,
        colWidths=[(A4[0]-40)/6]*6,
        rowHeights=[20, 40],
        style=TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BACKGROUND", (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)),
        ])
    )

    monthly_table_data = [[Paragraph("Miesiąc", wrap_style)], [""]]
    monthly_table = Table(
        monthly_table_data,
        colWidths=[(A4[0]-40)],
        rowHeights=[40, 80],
        style=TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BACKGROUND", (0,0), (-1,0), colors.Color(0.95, 0.95, 0.95)),
        ])
    )

    additional_content = KeepTogether([spacer, additional_para,
    small_spacer, weekly_table, small_spacer, monthly_table])

    doc.build([
        borderless_table, spacer, title_para,
        spacer, table, spacer, additional_content
        ])

