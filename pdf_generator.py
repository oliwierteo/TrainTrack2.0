from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import sys
import platform
from datetime import datetime


def resource_path(relative_path):
    """Zwraca poprawną ścieżkę do zasobu - Windows/macOS/PyInstaller"""
    # 1. PyInstaller (spakowana aplikacja)
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(sys.executable)
    else:
        # 2. Normalny Python - folder z GŁÓWNYM skryptem
        base = os.path.dirname(os.path.abspath(__file__))
    
    full_path = os.path.join(base, relative_path)
    
    # 3. Jeśli nie znaleziono, szukaj w katalogu nadrzędnym
    if not os.path.exists(full_path):
        parent = os.path.dirname(base)
        full_path_parent = os.path.join(parent, relative_path)
        if os.path.exists(full_path_parent):
            return full_path_parent
    
    return full_path


def find_arial_font():
    """Szuka czcionki Arial na wszystkich platformach"""
    candidates = [
        # Folder assets (projekt)
        resource_path(os.path.join("assets", "arial.ttf")),
        resource_path(os.path.join("assets", "Arial.ttf")),
    ]
    
    if platform.system() == "Windows":
        windir = os.environ.get('WINDIR', r'C:\Windows')
        candidates.extend([
            os.path.join(windir, "Fonts", "arial.ttf"),
            os.path.join(windir, "Fonts", "Arial.ttf"),
        ])
    
    elif platform.system() == "Darwin":  # macOS
        candidates.extend([
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Arial.ttf",
            os.path.expanduser("~/Library/Fonts/Arial.ttf"),
            os.path.expanduser("~/Library/Fonts/arial.ttf"),
        ])
    
    else:  # Linux
        candidates.extend([
            "/usr/share/fonts/truetype/msttcorefonts/arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ])
    
    for path in candidates:
        if os.path.exists(path):
            print(f"[PDF] Znaleziono czcionkę: {path}")
            return path
    
    print(f"[PDF] Nie znaleziono Arial! Sprawdzone: {candidates[:4]}...")
    return None


def find_arial_bold_font():
    """Szuka czcionki Arial Bold"""
    candidates = [
        resource_path(os.path.join("assets", "arialbd.ttf")),
        resource_path(os.path.join("assets", "Arial Bold.ttf")),
        resource_path(os.path.join("assets", "Arialbd.ttf")),
    ]
    
    if platform.system() == "Windows":
        windir = os.environ.get('WINDIR', r'C:\Windows')
        candidates.extend([
            os.path.join(windir, "Fonts", "arialbd.ttf"),
        ])
    
    elif platform.system() == "Darwin":
        candidates.extend([
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ])
    
    for path in candidates:
        if os.path.exists(path):
            print(f"[PDF] Znaleziono czcionkę bold: {path}")
            return path
    
    return None


class PDFGenerator:
    def __init__(self, club_name, bank_account="", bank_name=""):
        self.club_name = club_name or "Klub"
        self.bank_account = bank_account or ""
        self.bank_name = bank_name or ""
        self._register_fonts()
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _register_fonts(self):
        """Rejestruje czcionki z polskimi znakami - CROSS-PLATFORM"""
        self.font_reg = 'Helvetica'
        self.font_bold = 'Helvetica-Bold'
        
        try:
            # Szukaj Arial Regular
            reg_path = find_arial_font()
            
            if reg_path and os.path.exists(reg_path):
                pdfmetrics.registerFont(TTFont('Arial-PL', reg_path))
                self.font_reg = 'Arial-PL'
                
                # Szukaj Arial Bold
                bold_path = find_arial_bold_font()
                
                if bold_path and os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont('Arial-PL-Bold', bold_path))
                    self.font_bold = 'Arial-PL-Bold'
                else:
                    # Brak bold - użyj regular jako bold
                    self.font_bold = 'Arial-PL'
                
                print(f"[PDF] ✅ Czcionki załadowane: {self.font_reg}, {self.font_bold}")
            else:
                print("[PDF] ⚠️ Brak Arial - używam Helvetica (bez polskich znaków)")
                
        except Exception as e:
            print(f"[PDF] ❌ Błąd rejestracji czcionek: {e}")
            self.font_reg = 'Helvetica'
            self.font_bold = 'Helvetica-Bold'

    def _create_custom_styles(self):
        """Style z poprawną czcionką"""
        self.styles.add(ParagraphStyle(
            name='Header', fontName=self.font_bold, 
            fontSize=18, alignment=1, spaceAfter=20
        ))
        self.styles.add(ParagraphStyle(
            name='SubHeader', fontName=self.font_reg, 
            fontSize=12, alignment=1, spaceAfter=10
        ))
        self.styles.add(ParagraphStyle(
            name='NormalPL', fontName=self.font_reg, 
            fontSize=10
        ))
        self.styles.add(ParagraphStyle(
            name='Footer', fontName=self.font_reg, 
            fontSize=8, alignment=1, textColor=colors.gray
        ))

    def _get_logo(self):
        """Pobiera logo z poprawnej ścieżki"""
        path = resource_path(os.path.join("assets", "logo.png"))
        if os.path.exists(path):
            try:
                return Image(path, width=60, height=60)
            except Exception as e:
                print(f"[PDF] Błąd logo: {e}")
        return None

    def _safe_output_path(self, filename):
        """Normalizuje ścieżkę wyjściową - CROSS-PLATFORM"""
        # Rozwiń ~ (macOS/Linux)
        filename = os.path.expanduser(filename)
        # Normalizuj separatory
        filename = os.path.normpath(filename)
        # Upewnij się, że folder istnieje
        folder = os.path.dirname(filename)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        return filename

    def generate_monthly_report(self, year, month, players_data, month_finances, filename):
        """Raport miesięczny"""
        filename = self._safe_output_path(filename)
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        
        logo = self._get_logo()
        if logo:
            elements.append(logo)
        
        m_names = [
            "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"
        ]
        m_name = m_names[month - 1] if 1 <= month <= 12 else str(month)
        
        elements.append(Paragraph(
            f"RAPORT FINANSOWY - {m_name.upper()} {year}", 
            self.styles['Header']
        ))
        elements.append(Paragraph(
            f"Klub: {self.club_name}", 
            self.styles['SubHeader']
        ))
        elements.append(Spacer(1, 20))

        data = [['Nr', 'Zawodnik', 'Status', 'Wpłata', 'Zaległość', 'Saldo']]
        total_paid = 0
        total_due = 0
        
        for p in sorted(players_data, key=lambda x: x.get('full_name', '')):
            pid = p['id']
            f_rec = month_finances.get(pid, {})
            fee = p.get('monthly_fee') or 100
            
            is_paid = f_rec.get('is_paid', False)
            if is_paid:
                amt_val = f_rec.get('amount', 0) or 0
                st = "OPŁACONY"
                amt = f"{int(amt_val)} zł"
                due = "-"
                total_paid += amt_val
            else:
                st = "BRAK"
                amt = "-"
                due = f"{int(fee)} zł"
                total_due += fee
                
            bal = f"{int(p.get('balance', 0) or 0)}"
            data.append([
                str(p.get('jersey_number', '-')), 
                p.get('full_name', '?'), 
                st, amt, due, bal
            ])

        table = Table(data, colWidths=[30, 180, 80, 80, 80, 60])
        self._apply_table_style(table, data)
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        self._add_summary(elements, total_paid, total_due)
        self._add_footer(elements)
        
        doc.build(elements)
        print(f"[PDF] ✅ Wygenerowano: {filename}")

    def generate_total_debt_report(self, debt_data, filename):
        """Zestawienie zaległości"""
        filename = self._safe_output_path(filename)
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        
        logo = self._get_logo()
        if logo:
            elements.append(logo)
        
        elements.append(Paragraph(
            "ZESTAWIENIE ZALEGŁOŚCI", 
            self.styles['Header']
        ))
        elements.append(Paragraph(
            f"Stan na dzień: {datetime.now().strftime('%d.%m.%Y')}", 
            self.styles['SubHeader']
        ))
        elements.append(Spacer(1, 20))
        
        sorted_data = sorted(debt_data, key=lambda x: x.get('total_debt', 0), reverse=True)
        
        data = [['Nr', 'Zawodnik', 'Mies. Składka', 'Zaległe Mies.', 'KWOTA DŁUGU', 'Saldo']]
        
        total_club_debt = 0
        
        for p in sorted_data:
            nr = str(p.get('number', '-'))
            name = p.get('name', '?')
            fee = f"{int(p.get('fee', 0))} zł"
            
            months_count = p.get('arrears_months', 0)
            total_debt = p.get('total_debt', 0)
            total_club_debt += total_debt
            
            balance = p.get('balance', 0) or 0
            bal_str = f"+{int(balance)} zł" if balance > 0 else "-"
            
            if total_debt > 0:
                months_str = f"{months_count} mies."
                debt_str = f"{int(total_debt)} zł"
            else:
                months_str = "OK"
                debt_str = "-"
            
            data.append([nr, name, fee, months_str, debt_str, bal_str])
            
        table = Table(data, colWidths=[30, 170, 80, 80, 100, 70])
        
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1e1e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.font_reg),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ]
        
        for i in range(len(sorted_data)):
            row_idx = i + 1
            debt_val = sorted_data[i].get('total_debt', 0)
            if debt_val > 0:
                style.append(('TEXTCOLOR', (3, row_idx), (4, row_idx), colors.red))
                style.append(('FONTNAME', (4, row_idx), (4, row_idx), self.font_bold))
            else:
                style.append(('TEXTCOLOR', (3, row_idx), (4, row_idx), colors.green))
                
        table.setStyle(TableStyle(style))
        elements.append(table)
        
        elements.append(Spacer(1, 30))
        sum_data = [
            ['PODSUMOWANIE KLUBU', ''],
            ['Łączna kwota zaległości:', f"{int(total_club_debt)} PLN"]
        ]
        t_sum = Table(sum_data, hAlign='LEFT')
        t_sum.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_bold),
            ('TEXTCOLOR', (1, 1), (1, 1), colors.red),
            ('SIZE', (0, 0), (-1, -1), 12),
        ]))
        elements.append(t_sum)
        
        self._add_footer(elements)
        doc.build(elements)
        print(f"[PDF] ✅ Wygenerowano: {filename}")

    def generate_player_card(self, player, finances_history, filename):
        """Karta Finansowa Zawodnika"""
        filename = self._safe_output_path(filename)
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        
        logo = self._get_logo()
        if logo:
            elements.append(logo)
        
        elements.append(Paragraph("KARTA FINANSOWA ZAWODNIKA", self.styles['Header']))
        elements.append(Paragraph(f"Klub: {self.club_name}", self.styles['SubHeader']))
        elements.append(Spacer(1, 20))
        
        # Dane zawodnika
        monthly_fee = int(player.get('monthly_fee') or 100)
        balance_val = int(player.get('balance', 0) or 0)
        join_date = str(player.get('join_date', '-'))[:10]
        
        p_data = [
            [f"Imię i Nazwisko: {player.get('full_name', '?')}", 
             f"Data dołączenia: {join_date}"],
            [f"Numer: {player.get('jersey_number', '-')}", 
             f"Składka miesięczna: {monthly_fee} PLN"],
            [f"SALDO (Nadpłata): {balance_val} PLN", ""]
        ]
        
        t_info = Table(p_data, colWidths=[250, 250])
        t_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('FONTNAME', (0, 0), (-1, -1), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(t_info)
        elements.append(Spacer(1, 30))
        
        # Historia płatności
        elements.append(Paragraph("HISTORIA PŁATNOŚCI", self.styles['SubHeader']))
        
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        # Data startu
        try:
            start_str = player.get('fee_start_date') or player.get('join_date') or '2024-01-01'
            start_date = datetime.strptime(str(start_str)[:10], "%Y-%m-%d").date().replace(day=1)
            if not player.get('fee_start_date'):
                start_date += relativedelta(months=1)
        except:
            start_date = date(2024, 1, 1)
            
        today = date.today().replace(day=1)
        
        # Mapa opłaconych
        paid_map = {}
        for f in finances_history:
            if f.get('is_paid'):
                key = (f.get('year'), f.get('month'))
                paid_map[key] = f
        
        m_names = [
            "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"
        ]
        
        table_data = [['Rok', 'Miesiąc', 'Kwota', 'Data wpłaty', 'Status']]
        
        total_paid = 0
        total_debt = 0
        
        # Miesiące wolne
        exempt_months = []
        if player.get('exempt_months'):
            try:
                exempt_months = [int(x) for x in str(player['exempt_months']).split(',') if x.strip()]
            except:
                pass
        
        # Generuj listę (od dziś wstecz)
        curr = today
        while curr >= start_date:
            y, m = curr.year, curr.month
            m_name = m_names[m - 1] if 1 <= m <= 12 else str(m)
            
            record = paid_map.get((y, m))
            
            if record:
                status = "OPŁACONY"
                amt_val = record.get('amount', 0) or 0
                amount = f"{int(amt_val)} zł"
                date_str = str(record.get('paid_date', '-'))
                total_paid += amt_val
            elif m in exempt_months:
                status = "WOLNY"
                amount = "-"
                date_str = "-"
            else:
                status = "ZALEGŁOŚĆ"
                fee = int(player.get('monthly_fee') or 100)
                amount = f"{fee} zł"
                date_str = "-"
                total_debt += fee
            
            table_data.append([str(y), m_name, amount, date_str, status])
            curr -= relativedelta(months=1)
            
        t_hist = Table(table_data, colWidths=[60, 100, 100, 100, 120])
        
        hist_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1e1e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTNAME', (0, 1), (-1, -1), self.font_reg),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
        ]
        
        # Kolorowanie statusów
        for i, row in enumerate(table_data[1:], 1):
            st = row[4]
            if st == "OPŁACONY":
                col = colors.green
            elif st == "WOLNY":
                col = colors.grey
            else:
                col = colors.red
            hist_style.append(('TEXTCOLOR', (4, i), (4, i), col))
        
        t_hist.setStyle(TableStyle(hist_style))
        elements.append(t_hist)
        elements.append(Spacer(1, 30))
        
        # Podsumowanie
        sum_data = [
            ['PODSUMOWANIE FINANSOWE', ''],
            ['Łącznie wpłacono:', f"{int(total_paid)} PLN"],
            ['Aktualne zaległości:', f"{int(total_debt)} PLN"],
            ['Saldo (nadpłata):', f"{balance_val} PLN"]
        ]
        
        t_sum = Table(sum_data, colWidths=[200, 150], hAlign='LEFT')
        t_sum.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_bold),
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.red),
            ('TEXTCOLOR', (0, 3), (-1, 3), colors.green),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(t_sum)
        
        # Stopka z danymi bankowymi
        elements.append(Spacer(1, 40))
        if self.bank_account:
            elements.append(Paragraph("DANE DO PRZELEWU:", self.styles['SubHeader']))
            elements.append(Paragraph(f"Odbiorca: {self.club_name}", self.styles['NormalPL']))
            elements.append(Paragraph(f"Bank: {self.bank_name}", self.styles['NormalPL']))
            elements.append(Paragraph(f"Numer konta: {self.bank_account}", self.styles['Header']))
            elements.append(Paragraph(
                f"Tytułem: Składka - {player.get('full_name', '?')}", 
                self.styles['NormalPL']
            ))
            
        doc.build(elements)
        print(f"[PDF] ✅ Wygenerowano: {filename}")
    
    # --- METODY POMOCNICZE ---
    
    def _apply_table_style(self, table, data):
        """Stylizuje tabelę z kolorowaniem statusów"""
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1e1e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), self.font_reg),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ]
        for i, row in enumerate(data[1:], 1):
            if "OPŁACONY" in row:
                style.append(('TEXTCOLOR', (2, i), (2, i), colors.green))
            elif "BRAK" in row:
                style.append(('TEXTCOLOR', (2, i), (2, i), colors.red))
        table.setStyle(TableStyle(style))

    def _add_summary(self, elements, paid, due):
        """Dodaje podsumowanie kwot"""
        data = [
            ['Podsumowanie:', ''], 
            ['Wpłynęło:', f"{int(paid)} zł"], 
            ['Zaległości:', f"{int(due)} zł"]
        ]
        t = Table(data, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_bold),
            ('TEXTCOLOR', (1, 2), (1, 2), colors.red),
        ]))
        elements.append(t)

    def _add_footer(self, elements):
        """Dodaje stopkę z danymi bankowymi"""
        elements.append(Spacer(1, 40))
        if self.bank_account:
            elements.append(Paragraph("DANE DO PRZELEWU:", self.styles['SubHeader']))
            elements.append(Paragraph(f"Bank: {self.bank_name}", self.styles['NormalPL']))
            elements.append(Paragraph(f"Konto: {self.bank_account}", self.styles['Header']))