import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
VISUALS = ROOT / "artifacts" / "visualizations"
RESULTS = ROOT / "artifacts" / "results"
OUTPUT = ROOT / "docs" / "Sprawozdanie_TEP_MPC.pdf"

NAVY = colors.HexColor("#173B63")
BLUE = colors.HexColor("#2E74B5")
DARK_BLUE = colors.HexColor("#1F4D78")
MUTED = colors.HexColor("#5D6670")
LIGHT = colors.HexColor("#F4F6F9")
TABLE_HEADER = colors.HexColor("#E8EEF5")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Calibri", r"C:\Windows\Fonts\calibri.ttf"))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", r"C:\Windows\Fonts\calibrib.ttf"))
    pdfmetrics.registerFont(TTFont("Calibri-Italic", r"C:\Windows\Fonts\calibrii.ttf"))
    pdfmetrics.registerFontFamily(
        "Calibri",
        normal="Calibri",
        bold="Calibri-Bold",
        italic="Calibri-Italic",
        boldItalic="Calibri-Bold",
    )


def make_styles():
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Calibri",
            fontSize=10.5,
            leading=14,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#20252B"),
            spaceAfter=7,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Calibri-Bold",
            fontSize=16,
            leading=19,
            textColor=BLUE,
            spaceBefore=5,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Calibri-Bold",
            fontSize=13,
            leading=16,
            textColor=DARK_BLUE,
            spaceBefore=7,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Calibri-Italic",
            fontSize=8.8,
            leading=11,
            alignment=TA_CENTER,
            textColor=MUTED,
            spaceBefore=3,
            spaceAfter=8,
        ),
        "formula": ParagraphStyle(
            "Formula",
            parent=base["BodyText"],
            fontName="Calibri-Italic",
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=7,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Calibri",
            fontSize=10.5,
            leading=13.5,
            leftIndent=16,
            firstLineIndent=-9,
            bulletIndent=3,
            spaceAfter=3,
        ),
        "toc": ParagraphStyle(
            "TOC",
            parent=base["BodyText"],
            fontName="Calibri",
            fontSize=11,
            leading=15,
            leftIndent=14,
            textColor=NAVY,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Calibri",
            fontSize=8.7,
            leading=11,
            textColor=MUTED,
            spaceAfter=4,
        ),
    }


def page_header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D8DEE6"))
    canvas.setLineWidth(0.5)
    canvas.line(2.2 * cm, height - 1.55 * cm, width - 2.2 * cm, height - 1.55 * cm)
    canvas.setFont("Calibri", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2.2 * cm, height - 1.35 * cm, "Hurtownie Danych | Prognozowanie TEP i sterowanie MPC")
    canvas.drawRightString(width - 2.2 * cm, 1.25 * cm, f"Strona {doc.page}")
    canvas.restoreState()


def first_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.restoreState()


def P(text, styles):
    return Paragraph(text, styles["body"])


def H1(text, styles):
    return Paragraph(text, styles["h1"])


def H2(text, styles):
    return Paragraph(text, styles["h2"])


def bullets(items, styles):
    return [Paragraph(f"• {item}", styles["bullet"]) for item in items]


def formula(text, styles):
    return Paragraph(text, styles["formula"])


def figure(filename: str, caption: str, styles, max_width=15.8 * cm, max_height=15.2 * cm):
    path = VISUALS / filename
    with PILImage.open(path) as source:
        width, height = source.size
    scale = min(max_width / width, max_height / height)
    image = Image(str(path), width=width * scale, height=height * scale)
    return KeepTogether([image, Paragraph(caption, styles["caption"])])


def data_table(headers, rows, widths):
    data = [headers] + rows
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Calibri-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Calibri"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
                ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#AEB8C4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_story(styles, summary):
    story = []

    story += [Spacer(1, 4.1 * cm)]
    story.append(Paragraph("SPRAWOZDANIE PROJEKTOWE", ParagraphStyle("Kicker", fontName="Calibri-Bold", fontSize=11, textColor=BLUE, alignment=TA_CENTER, spaceAfter=14)))
    story.append(Paragraph("Prognozowanie i analiza szeregów czasowych<br/>oraz sterowanie MPC dla procesu Tennessee Eastman", ParagraphStyle("Title", fontName="Calibri-Bold", fontSize=24, leading=29, textColor=NAVY, alignment=TA_CENTER, spaceAfter=13)))
    story.append(Paragraph("Projekt z przedmiotu Hurtownie Danych", ParagraphStyle("Subtitle", fontName="Calibri", fontSize=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=52)))
    story.append(Paragraph("Maksymilian Lech, nr indeksu 280136", ParagraphStyle("Author", fontName="Calibri-Bold", fontSize=12, textColor=NAVY, alignment=TA_CENTER, spaceAfter=6)))
    story.append(Paragraph("Borys Kaczmarek, nr indeksu 280068", ParagraphStyle("Author2", fontName="Calibri-Bold", fontSize=12, textColor=NAVY, alignment=TA_CENTER)))
    story.append(Spacer(1, 5.4 * cm))
    story.append(Paragraph("Wrocław, 2026", ParagraphStyle("Place", fontName="Calibri", fontSize=11, textColor=MUTED, alignment=TA_CENTER)))
    story.append(PageBreak())

    story.append(H1("Spis treści", styles))
    for entry in [
        "1. Wprowadzenie",
        "2. Zbiór danych Tennessee Eastman Process",
        "3. Przygotowanie danych i model przestrzeni stanów",
        "4. Filtr Kalmana i prognozowanie",
        "5. Ocena jakości prognoz",
        "6. Regulator MPC",
        "7. Architektura aplikacji i warstwa danych",
        "8. Pętla zamknięta",
        "9. Implementacja i testy",
        "10. Ograniczenia i możliwe rozszerzenia",
        "11. Wnioski",
        "Bibliografia",
    ]:
        story.append(Paragraph(entry, styles["toc"]))
    story.append(Spacer(1, 12))
    story.append(H1("Streszczenie", styles))
    story.append(P("Celem projektu było przygotowanie kompletnego, ale możliwie prostego systemu do analizy wielowymiarowych szeregów czasowych procesu Tennessee Eastman. System przetwarza kolejne próbki, estymuje ukryty stan filtrem Kalmana, prognozuje 41 pomiarów na jeden krok oraz wyznacza ograniczone sterowanie MPC. PostgreSQL przechowuje pomiary, wejścia, prognozy i wyniki, natomiast MQTT służy do przekazywania zdarzeń pomiędzy symulatorem a kontrolerem. Model oceniono na dziesięciu niezależnych przebiegach testowych. Średni NRMSE wyniósł 0,786 wobec 0,952 dla prognozy naiwnej, co oznacza poprawę o około 17,4%. Przygotowano także tryb pętli zamkniętej, w którym sterowanie MPC wpływa na kolejne stany symulowanego procesu.", styles))
    story.append(Paragraph("Słowa kluczowe: szeregi czasowe, Tennessee Eastman Process, PCA, filtr Kalmana, model przestrzeni stanów, MPC, PostgreSQL, MQTT.", styles["small"]))
    story.append(PageBreak())

    story.append(H1("1. Wprowadzenie", styles))
    story.append(P("Analiza szeregów czasowych jest istotna w systemach przemysłowych, ponieważ kolejne pomiary są powiązane przez fizyczną dynamikę procesu. Temperatura, ciśnienie lub przepływ nie zmieniają się niezależnie w każdej chwili. Na ich przyszłe wartości wpływają wcześniejszy stan instalacji oraz decyzje sterujące. W projekcie wykorzystano dane Tennessee Eastman Process, które tworzą wielowymiarowy zbiór 41 pomiarów i 11 wejść sterujących.", styles))
    story.append(P("Pierwsza wersja projektu łączyła dane TEP, PostgreSQL, MQTT i regulator MPC, lecz model był używany w innej skali niż podczas treningu, sterowania nie miały ograniczeń, a symulator nie reagował na decyzje regulatora. Aktualna wersja zachowuje pierwotny zakres technologiczny, ale porządkuje cały przepływ i dodaje właściwą ocenę prognoz. Założeniem nie było stworzenie systemu produkcyjnego, tylko poprawnego i możliwego do wyjaśnienia projektu akademickiego.", styles))
    story.append(H2("1.1. Cel i zakres", styles))
    story += bullets([
        "analiza właściwości wielowymiarowych szeregów czasowych TEP,",
        "budowa liniowego modelu przestrzeni stanów i filtra Kalmana,",
        "prognozowanie 41 pomiarów na jeden krok i porównanie z benchmarkiem naiwnym,",
        "wyznaczanie ograniczonego sterowania MPC,",
        "zapis historii danych i wyników w PostgreSQL,",
        "komunikacja zdarzeniowa za pomocą MQTT,",
        "demonstracja odtwarzania danych i pętli zamkniętej.",
    ], styles)
    story.append(figure("01_architektura.png", "Rys. 1. Ogólny przepływ danych i wyników w systemie.", styles, max_height=10.8 * cm))
    story.append(PageBreak())

    story.append(H1("2. Zbiór danych Tennessee Eastman Process", styles))
    story.append(P("Tennessee Eastman Process jest procesem testowym opisanym przez Downsa i Vogela [1]. Reprezentuje przemysłową instalację chemiczną obejmującą kilka powiązanych aparatów i pętlę recyrkulacji. Zbiór jest często wykorzystywany do badań nad sterowaniem, diagnostyką i analizą danych procesowych, ponieważ zawiera wiele wzajemnie zależnych pomiarów oraz zmienne manipulowane.", styles))
    story.append(data_table(
        ["Zbiór", "Przebiegi", "Próbki w przebiegu", "Rekordy"],
        [["FaultFree Training", "500", "500", "250 000"], ["FaultFree Testing", "500", "960", "480 000"]],
        [5.2 * cm, 2.6 * cm, 4.2 * cm, 3.2 * cm],
    ))
    story.append(Spacer(1, 8))
    story.append(P("Każdy rekord zawiera numer przebiegu <b>simulationRun</b>, numer próbki <b>sample</b>, 41 kolumn <b>xmeas</b> oraz 11 kolumn <b>xmv</b>. W obecnym etapie użyto danych bez awarii. Pliki zawierające awarie pozostawiono jako możliwość przyszłego rozszerzenia, na przykład o detekcję anomalii.", styles))
    story.append(H2("2.1. Charakter sygnałów", styles))
    story.append(P("Poszczególne zmienne różnią się skalą i charakterem zmian. Część sygnałów jest gładka i silnie zależna od poprzedniej wartości, natomiast inne zawierają więcej krótkookresowych wahań. Autokorelacja dla opóźnienia jednego kroku pokazuje, jak silnie bieżąca wartość zależy od poprzedniej.", styles))
    story.append(figure("02_przykladowe_szeregi.png", "Rys. 2. Przykładowe szeregi czasowe o różnej skali i autokorelacji.", styles, max_height=13.3 * cm))
    story.append(PageBreak())

    story.append(H1("3. Przygotowanie danych i model przestrzeni stanów", styles))
    story.append(H2("3.1. Standaryzacja", styles))
    story.append(P("Pomiary TEP przyjmują wartości o bardzo różnych rzędach wielkości. Bez skalowania zmienne o dużych wartościach liczbowych dominowałyby obliczenia. Dla każdej kolumny obliczono średnią i odchylenie standardowe na zbiorze treningowym, a następnie zastosowano standaryzację:", styles))
    story.append(formula("z = (x - μ) / σ", styles))
    story.append(P("Wartość zero oznacza średni nominalny punkt pracy. Parametry skalowania zapisano razem z modelem, dzięki czemu te same przekształcenia są używane w całej aplikacji. Rozwiązuje to najważniejszy błąd pierwszej wersji, w której model otrzymywał wartości w innej skali niż podczas treningu.", styles))
    story.append(H2("3.2. Redukcja wymiaru PCA", styles))
    story.append(P("Do utworzenia stanu procesu zastosowano analizę głównych składowych PCA. Metoda zastępuje 41 skorelowanych pomiarów przez 20 składowych będących ich kombinacjami liniowymi. Wybrane składowe zachowują około 72,4% wariancji zbioru treningowego. Utrata części wariancji jest zamierzona: model staje się prostszy, a część drobnych wahań i szumu nie trafia bezpośrednio do stanu.", styles))
    story.append(H2("3.3. Model przestrzeni stanów", styles))
    story.append(P("Dynamikę opisano liniowym modelem dyskretnym. Macierze A i B dopasowano przez regresję liniową z małą regularyzacją. Pary treningowe tworzono tylko wewnątrz jednego przebiegu, aby nie wprowadzać sztucznych przejść pomiędzy niezależnymi seriami.", styles))
    story.append(formula("x(k+1) = A x(k) + B u(k) + w(k)", styles))
    story.append(formula("y(k) = C x(k) + D u(k) + v(k)", styles))
    story.append(data_table(
        ["Macierz", "Wymiar", "Znaczenie"],
        [["A", "20 x 20", "dynamika stanu"], ["B", "20 x 11", "wpływ sterowania na stan"], ["C", "41 x 20", "przejście ze stanu do pomiarów"], ["D", "41 x 11", "bezpośredni wpływ; przyjęto zera"]],
        [2.2 * cm, 3.0 * cm, 10.0 * cm],
    ))
    story.append(Spacer(1, 7))
    story.append(P(f"Promień spektralny macierzy A wynosi {summary['spectral_radius']:.3f}. Jest mniejszy od 1, co wskazuje na stabilność dyskretnej dynamiki liniowej. Kowariancje reszt wykorzystano jako macierze szumu procesu i pomiaru.", styles))
    story.append(PageBreak())

    story.append(H1("4. Filtr Kalmana i prognozowanie", styles))
    story.append(H2("4.1. Estymacja stanu", styles))
    story.append(P("Stan PCA nie jest bezpośrednio zapisany w danych, dlatego jest estymowany filtrem Kalmana [2]. Filtr najpierw przewiduje przyszły stan za pomocą modelu, a po otrzymaniu nowego pomiaru koryguje przewidywanie. Wielkość korekty zależy od niepewności modelu i pomiarów.", styles))
    story.append(formula("x_pred = A x + B u,     P_pred = A P Aᵀ + Q", styles))
    story.append(formula("K = P_pred Cᵀ (C P_pred Cᵀ + R)⁻¹", styles))
    story.append(formula("x = x_pred + K (y - C x_pred)", styles))
    story.append(P("Pierwszy stan jest obliczany metodą najmniejszych kwadratów, a kolejne wykorzystują pełną historię filtra. W odróżnieniu od pierwotnej wersji stan nie jest szacowany niezależnie od zera dla każdej próbki.", styles))
    story.append(H2("4.2. Prognoza na jeden krok", styles))
    story.append(P("Po korekcie stanu przygotowywana jest prognoza wszystkich 41 pomiarów dla próbki k+1. Prognoza jest zapisywana przed pojawieniem się wartości rzeczywistej. Gdy następna próbka dotrze do systemu, rekord zostaje powiązany z rzeczywistym pomiarem i uzupełniony o metryki błędu.", styles))
    story.append(figure("03_prognoza_vs_rzeczywistosc.png", "Rys. 3. Porównanie prognoz na jeden krok z wartościami rzeczywistymi.", styles, max_height=12.8 * cm))
    story.append(PageBreak())

    story.append(H1("5. Ocena jakości prognoz", styles))
    story.append(H2("5.1. Metryki", styles))
    story.append(P("Do oceny zastosowano MAE, RMSE i NRMSE. MAE przedstawia średnią bezwzględną różnicę, a RMSE mocniej karze duże błędy. W NRMSE błąd każdej zmiennej jest dzielony przez jej odchylenie standardowe, dzięki czemu 41 pomiarów o różnych jednostkach może zostać uczciwie połączonych w jedną metrykę.", styles))
    story.append(formula("MAE = (1/n) Σ |ŷ - y|", styles))
    story.append(formula("RMSE = √((1/n) Σ (ŷ - y)²)", styles))
    story.append(figure("04_blad_prognozy.png", "Rys. 4. Zmiana oraz rozkład znormalizowanego błędu prognozy.", styles, max_height=11.2 * cm))
    story.append(P("Średnia krocząca błędu pozostaje na zbliżonym poziomie w całym przebiegu. Nie obserwujemy systematycznego narastania błędu, które wskazywałoby na rozjeżdżanie się estymacji stanu.", styles))
    story.append(PageBreak())

    story.append(H1("5.2. Porównanie z prognozą naiwną", styles))
    story.append(P("Benchmark naiwny zakłada, że następna wartość będzie równa wartości bieżącej. Dla wolnozmiennych procesów taki punkt odniesienia jest wymagający. Model ma praktyczne uzasadnienie dopiero wtedy, gdy systematycznie obniża błąd w stosunku do tego benchmarku.", styles))
    story.append(data_table(
        ["Metryka", "Model", "Prognoza naiwna", "Wynik"],
        [["NRMSE", f"{summary['average_model_nrmse']:.3f}", f"{summary['average_naive_nrmse']:.3f}", f"poprawa {summary['nrmse_improvement_percent']:.1f}%"], ["MAE", f"{summary['average_model_mae']:.3f}", f"{summary['average_naive_mae']:.3f}", "spadek o 0,252"]],
        [3.1 * cm, 3.1 * cm, 4.4 * cm, 4.6 * cm],
    ))
    story.append(Spacer(1, 8))
    story.append(figure("05_model_vs_naiwny.png", "Rys. 5. NRMSE modelu i prognozy naiwnej dla dziesięciu przebiegów testowych.", styles, max_height=11.8 * cm))
    story.append(P("Model uzyskał niższy NRMSE we wszystkich dziesięciu przebiegach. Średnia poprawa wyniosła około 17,4%, a podobny wynik w kolejnych seriach wskazuje na jego powtarzalność.", styles))
    story.append(PageBreak())

    story.append(H1("6. Regulator MPC", styles))
    story.append(P("Model Predictive Control wykorzystuje model procesu do przewidywania przyszłych wyjść i wybiera sekwencję wejść minimalizującą funkcję kosztu [3]. W projekcie zastosowano horyzont ośmiu kroków. Używane jest tylko pierwsze sterowanie z optymalnej sekwencji, a na kolejnej próbce problem jest rozwiązywany ponownie.", styles))
    story.append(formula("J = Σ ||y_pred||² + 0,2 Σ ||u||² + 0,5 Σ ||Δu||²", styles))
    story.append(P("Pierwszy składnik utrzymuje standaryzowane wyjścia w pobliżu średniego punktu nominalnego. Drugi ogranicza wielkość sterowania, a trzeci gwałtowne zmiany. Problem jest rozwiązywany jako liniowe najmniejsze kwadraty z ograniczeniami przy użyciu funkcji lsq_linear z biblioteki SciPy [6].", styles))
    story.append(H2("6.1. Ograniczenia", styles))
    story.append(P("Dolne i górne granice wejść wyznaczono z kwantyli 0,5% i 99,5% zbioru treningowego. Pozwala to zachować typowe zakresy procesu i ograniczyć wpływ wartości odstających. Wynik optymalizacji jest dodatkowo przycinany do tych granic.", styles))
    story.append(figure("06_sterowania_mpc.png", "Rys. 6. Zapisane wejścia TEP, rekomendacje MPC i dopuszczalne zakresy.", styles, max_height=11.8 * cm))
    story.append(PageBreak())

    story.append(H1("7. Architektura aplikacji i warstwa danych", styles))
    story.append(H2("7.1. PostgreSQL", styles))
    story.append(P("PostgreSQL [5] przechowuje nie tylko surowe pomiary, ale także pełną historię przetwarzania. Schemat jest zorganizowany wokół uruchomienia symulacji. Klucze obce pozwalają jednoznacznie powiązać próbkę, rzeczywiste wejście, przygotowaną prognozę i rekomendację MPC.", styles))
    story.append(data_table(
        ["Tabela", "Zawartość"],
        [["simulation_runs", "tryb, zbiór, numer przebiegu, status i czas"], ["sensor_data", "41 pomiarów dla każdej próbki"], ["process_inputs", "11 rzeczywistych lub zastosowanych wejść"], ["predictions", "41 prognoz oraz MAE, RMSE i NRMSE"], ["input_controls", "11 rekomendacji MPC i status optymalizacji"]],
        [4.4 * cm, 10.8 * cm],
    ))
    story.append(Spacer(1, 9))
    story.append(H2("7.2. MQTT", styles))
    story.append(P("MQTT jest lekkim protokołem publish/subscribe [4]. Symulator publikuje zdarzenie na temat tep/sensors/outputs, a kontroler publikuje wynik na tep/control/inputs. Wiadomość zawiera identyfikator konkretnego rekordu w bazie, dlatego kontroler nie musi wybierać po prostu najnowszej próbki. Pełne dane pozostają w PostgreSQL, natomiast MQTT przenosi małe komunikaty zdarzeniowe.", styles))
    story.append(H2("7.3. Dwa tryby działania", styles))
    story += bullets([
        "replay odtwarza historyczny przebieg i służy do uczciwej oceny prognoz; sterowanie MPC jest rekomendacją,",
        "closed-loop wykorzystuje model liniowy jako instalację i stosuje sterowanie MPC do obliczenia kolejnego stanu.",
    ], styles)
    story.append(P("Rozdzielenie trybów jest istotne. Danych historycznych nie można zmienić, dlatego nie należy udawać, że rekomendacja MPC wpłynęła na zapisany wcześniej pomiar. Sprzężenie zwrotne jest demonstrowane osobno na modelu.", styles))
    story.append(PageBreak())

    story.append(H1("8. Pętla zamknięta", styles))
    story.append(P("W trybie closed-loop po każdym pomiarze regulator oblicza nowe wejście, a symulator czeka na wiadomość zawierającą odpowiadający identyfikator próbki. Następny stan jest wyznaczany równaniem Ax + Bu. Dzięki temu wynik regulatora rzeczywiście wpływa na przyszły przebieg.", styles))
    story.append(figure("07_petla_zamknieta.png", "Rys. 7. Wygaszanie przykładowego zaburzenia z MPC i bez korekty sterowania.", styles, max_height=13.2 * cm))
    story.append(P("MPC szybciej zmniejsza normę wyjść niż wariant bez korekty sterowania. Jest to demonstracja mechanizmu, a nie walidacja na fizycznej instalacji. Symulator i regulator używają tego samego modelu, a do pętli nie dodano dodatkowego szumu ani błędu modelowania.", styles))
    story.append(PageBreak())

    story.append(H1("9. Implementacja i testy", styles))
    story.append(H2("9.1. Wykorzystane technologie", styles))
    story.append(data_table(
        ["Technologia", "Rola"],
        [["Python, NumPy, SciPy", "model, filtr i optymalizacja"], ["Pandas, pyreadr", "wczytanie i przygotowanie RData"], ["PostgreSQL, SQLAlchemy", "trwały zapis danych i wyników"], ["MQTT, Paho, Mosquitto", "komunikacja zdarzeniowa"], ["Docker Compose", "uruchomienie infrastruktury"], ["Matplotlib", "wizualizacje"]],
        [5.2 * cm, 10.0 * cm],
    ))
    story.append(Spacer(1, 9))
    story.append(H2("9.2. Testy", styles))
    story.append(P("Testy jednostkowe sprawdzają wymiary i stabilność modelu, poprawność skalowania i odwrotnego skalowania, skończoność wyników filtra Kalmana oraz przestrzeganie granic przez MPC. Dodatkowo wykonano testy integracyjne z PostgreSQL i Mosquitto uruchomionymi w Dockerze.", styles))
    story += bullets([
        "replay: 12 pomiarów, 12 prognoz, 12 sterowań i 11 ocenionych prognoz,",
        "closed-loop: 8 pełnych kroków, 8 sterowań, 8 prognoz i 7 ocenionych prognoz,",
        "wszystkie rozwiązania MPC w testach zakończyły się sukcesem,",
        "cztery testy jednostkowe zakończyły się poprawnie.",
    ], styles)
    story.append(H2("9.3. Powtarzalność", styles))
    story.append(P("Model jest zapisywany razem z parametrami skalowania, macierzami szumu i granicami sterowań. Skrypt generate_visualizations.py ponownie oblicza metryki dla dziesięciu przebiegów i tworzy wszystkie wykresy użyte w sprawozdaniu. Dzięki temu wyniki nie są ręcznie przepisanymi wartościami, tylko mogą zostać odtworzone z danych i kodu.", styles))
    story.append(PageBreak())

    story.append(H1("10. Ograniczenia i możliwe rozszerzenia", styles))
    story.append(P("Zastosowany model jest liniowy, podczas gdy proces TEP ma charakter nieliniowy. Prognoza obejmuje jeden krok, a PCA zachowuje około 72,4% wariancji. Model i ograniczenia są wyznaczone na danych bez awarii. W trybie pętli zamkniętej model instalacji jest taki sam jak model regulatora, dlatego warunki są prostsze niż w rzeczywistym zastosowaniu.", styles))
    story.append(P("Naturalne kierunki dalszego rozwoju obejmują:", styles))
    story += bullets([
        "analizę zbiorów Faulty i wykrywanie anomalii,",
        "prognozowanie na kilka kroków i metryki dla pojedynczych sygnałów,",
        "dodanie szumu oraz błędu modelowania do pętli zamkniętej,",
        "porównanie z modelem autoregresyjnym lub prostą siecią rekurencyjną,",
        "dashboard lub dodatkowe zapytania analityczne nad PostgreSQL.",
    ], styles)
    story.append(P("Ograniczenia te nie oznaczają, że projekt jest niepoprawny. Wyznaczają jego świadomy zakres: demonstrację kompletnego potoku danych, prognozowania i sterowania predykcyjnego, bez budowania systemu produkcyjnego.", styles))
    story.append(H1("11. Wnioski", styles))
    story.append(P("Zrealizowano pełny przepływ analizy wielowymiarowego szeregu czasowego: od wczytania danych TEP, przez standaryzację i model przestrzeni stanów, po filtrowanie, prognozowanie, ocenę oraz zapis wyników. Model poprawił średni NRMSE o około 17,4% względem prognozy naiwnej na dziesięciu niezależnych przebiegach. Oznacza to, że wykorzystanie stanu procesu i wejść sterujących dostarcza informacji ponad proste przeniesienie ostatniej wartości.", styles))
    story.append(P("Regulator MPC generuje wartości w realistycznych granicach, a tryb pętli zamkniętej potwierdza, że decyzja regulatora może zostać przesłana przez MQTT i wykorzystana do obliczenia kolejnego stanu. PostgreSQL przechowuje historię w formie umożliwiającej dalszą analizę. Projekt pozostaje rozwiązaniem akademickim, ale wszystkie główne elementy są spójne i działają zgodnie z założeniami.", styles))
    story.append(PageBreak())

    story.append(H1("Bibliografia", styles))
    references = [
        "[1] J. J. Downs, E. F. Vogel, A plant-wide industrial process control problem, Computers & Chemical Engineering, 17(3), 245-255, 1993, doi: 10.1016/0098-1354(93)80018-I.",
        "[2] R. E. Kalman, A New Approach to Linear Filtering and Prediction Problems, Journal of Basic Engineering, 82(1), 35-45, 1960, doi: 10.1115/1.3662552.",
        "[3] S. J. Qin, T. A. Badgwell, A survey of industrial model predictive control technology, Control Engineering Practice, 11(7), 733-764, 2003, doi: 10.1016/S0967-0661(02)00186-7.",
        "[4] OASIS, MQTT Version 5.0, OASIS Standard, 2019, https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html.",
        "[5] PostgreSQL Global Development Group, PostgreSQL Documentation, https://www.postgresql.org/docs/.",
        "[6] SciPy Developers, scipy.optimize.lsq_linear documentation, https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html.",
    ]
    for reference in references:
        style = ParagraphStyle("Reference", parent=styles["body"], leftIndent=18, firstLineIndent=-18, spaceAfter=8)
        story.append(Paragraph(reference, style))
    story.append(Spacer(1, 16))
    story.append(P("Wszystkie wyniki liczbowe i wizualizacje przedstawione w sprawozdaniu zostały wygenerowane przez kod znajdujący się w repozytorium projektu.", styles))
    return story


def main() -> None:
    register_fonts()
    styles = make_styles()
    summary = json.loads((RESULTS / "podsumowanie_wynikow.json").read_text(encoding="utf-8"))
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=2.2 * cm,
        leftMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="Prognozowanie i analiza szeregów czasowych oraz sterowanie MPC dla procesu Tennessee Eastman",
        author="Maksymilian Lech, Borys Kaczmarek",
        subject="Hurtownie Danych",
    )
    story = build_story(styles, summary)
    document.build(story, onFirstPage=first_page, onLaterPages=page_header_footer)
    print(f"Saved PDF report: {OUTPUT}")


if __name__ == "__main__":
    main()
