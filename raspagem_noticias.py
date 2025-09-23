# -*- coding: utf-8 -*-
"""
Raspagem de notícias – múltiplas fontes gov/órgãos
- Anti-rate-limit do Google Sheets (abre planilha 1x, cache de URLs, append em lote)
- Retry com backoff em erros 429/limite
- Fuso America/Recife

Ajuste o SHEET_ID se necessário e garanta que 'credentials.json' esteja no diretório.
"""

import re
import time
from typing import Dict, List, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import pytz

# -------------------------------------------------------------------
# Configs globais
# -------------------------------------------------------------------
TZ = pytz.timezone("America/Recife")
SHEET_ID = "1G81BndSPpnViMDxRKQCth8PwK0xmAwH-w-T7FjgnwcY"
JSON_KEYFILE = "credentials.json"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

RATE_LIMIT_PAT = re.compile(r"(RATE_LIMIT_EXCEEDED|ReadRequestsPerMinutePerUser|quota.*per minute)", re.I)


def with_gspread_retry(fn, *args, **kwargs):
    """Executa chamadas gspread com retry exponencial quando tomar 429/limite."""
    max_attempts = kwargs.pop("_max_attempts", 6)
    backoff = kwargs.pop("_backoff_start", 1.5)
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            msg = str(e)
            if RATE_LIMIT_PAT.search(msg) and attempt < max_attempts - 1:
                sleep_s = backoff * (2 ** attempt)
                # jitter leve
                sleep_s = sleep_s * (1 + 0.15 * (attempt % 3))
                print(f"⏳ Rate limit do Sheets (tentativa {attempt+1}/{max_attempts}). Aguardando {sleep_s:.1f}s…")
                time.sleep(sleep_s)
                attempt += 1
                continue
            raise  # outros erros, ou excedeu tentativas


class SheetManager:
    """
    - Abre a planilha 1x (por key).
    - Mantém cache do set de URLs (aba 'URLs').
    - Bufferiza appends por aba e envia em lote (append_rows).
    """
    def __init__(self, sheet_id: str, json_keyfile: str, urls_tab: str = "URLs", batch_size: int = 50):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(json_keyfile, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.sheet = with_gspread_retry(self.client.open_by_key, sheet_id)
        self.urls_tab_name = urls_tab
        self.batch_size = batch_size
        self._ws_cache: Dict[str, gspread.Worksheet] = {}
        self._urls_ws = self._get_or_create_ws(urls_tab, rows=1, cols=1)
        self._url_set = self._load_url_set()
        self._buffers: Dict[str, List[List[str]]] = {}

    def now_br(self) -> str:
        return datetime.now(TZ).strftime("%d/%m/%Y")

    # ---------- Worksheet helpers ----------
    def _get_or_create_ws(self, title: str, rows: int = 100, cols: int = 10) -> gspread.Worksheet:
        try:
            return with_gspread_retry(self.sheet.worksheet, title)
        except gspread.exceptions.WorksheetNotFound:
            return with_gspread_retry(self.sheet.add_worksheet, title=title, rows=str(rows), cols=str(cols))

    def worksheet(self, title: str) -> gspread.Worksheet:
        if title not in self._ws_cache:
            self._ws_cache[title] = self._get_or_create_ws(title)
        return self._ws_cache[title]

    def ensure_header(self, tab: str, header: List[str]):
        ws = self.worksheet(tab)
        first = with_gspread_retry(ws.row_values, 1)
        if not first:
            with_gspread_retry(ws.append_row, header)

    # ---------- URLs cache ----------
    def _load_url_set(self) -> set:
        vals = with_gspread_retry(self._urls_ws.col_values, 1) or []
        if not vals:
            with_gspread_retry(self._urls_ws.append_row, ["URLs"])
            return set()
        return set(vals[1:])  # sem header

    def seen_url(self, url: str) -> bool:
        return url in self._url_set

    def add_url(self, url: str):
        if url and url not in self._url_set:
            with_gspread_retry(self._urls_ws.append_row, [url])
            self._url_set.add(url)

    # ---------- Buffer ----------
    def buffer_row(self, tab: str, row: List[str]):
        if tab not in self._buffers:
            self._buffers[tab] = []
        self._buffers[tab].append(row)
        if len(self._buffers[tab]) >= self.batch_size:
            self.flush(tab)

    def flush(self, tab: Optional[str] = None):
        tabs = [tab] if tab else list(self._buffers.keys())
        for t in tabs:
            buf = self._buffers.get(t, [])
            if not buf:
                continue
            ws = self.worksheet(t)
            with_gspread_retry(ws.append_rows, buf, value_input_option="USER_ENTERED")
            self._buffers[t] = []

    def close(self):
        self.flush()


# -------------------------------------------------------------------
# Scrapers
# -------------------------------------------------------------------

def scrape_gov_listagem_padrao(manager: SheetManager, url: str, tab: str):
    """
    Padrão gov.br (listas em <li>, data em <span class='data'>, título em <h2 class='titulo'> <a>).
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    data_desejada = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ao acessar {url}: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    og = soup.find("meta", property="og:site_name")
    orgao = og["content"].strip() if og and og.get("content") else "—"
    itens = soup.find_all("li")

    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    added = 0
    for it in itens:
        sd = it.find("span", class_="data")
        if not sd:
            continue
        data_raw = sd.get_text(strip=True)
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        h2 = it.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        subt_tag = it.find("div", class_="subtitulo-noticia")
        subt = subt_tag.get_text(strip=True) if subt_tag else "—"
        titulo = a.get_text(strip=True)

        desc_span = it.find("span", class_="descricao")
        if desc_span:
            txt = desc_span.get_text(strip=True)
            # padrão "DD/MM/AAAA - descrição"
            if "-" in txt:
                descricao = txt.split("-", 1)[1].strip()
            else:
                descricao = txt
        else:
            descricao = "—"

        manager.buffer_row(tab, [data_fmt, orgao, subt, titulo, descricao, link])
        manager.add_url(link)
        added += 1
    print(f"✅ {tab}: {added} item(ns) bufferizados.")


def scrape_saude(manager: SheetManager):
    """
    Ministério da Saúde (estrutura em <article class='tileItem'>)
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    url = "https://www.gov.br/saude/pt-br/assuntos/noticias"
    data_desejada = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro Saúde: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    org_tag = soup.find('a', href="https://www.gov.br/saude/pt-br")
    orgao = org_tag.text.strip() if org_tag else "Ministério da Saúde"
    noticias = soup.find_all("article", class_="tileItem")

    tab = "saude"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    added = 0
    for n in noticias:
        data_icon = n.find("i", class_="icon-day")
        data_raw = data_icon.find_next_sibling(string=True).strip() if data_icon else ""
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        subt = n.find("span", class_="subtitle")
        subtitulo = subt.get_text(strip=True) if subt else "—"

        h2a = n.find("h2", class_="tileHeadline")
        a = h2a.find("a") if h2a else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        desc = n.find("span", class_="description")
        descricao = desc.get_text(strip=True) if desc else "—"

        manager.buffer_row(tab, [data_fmt, orgao, subtitulo, titulo, descricao, link])
        manager.add_url(link)
        added += 1

    print(f"✅ saude: {added} item(ns) bufferizados.")


def scrape_povos_indigenas(manager: SheetManager):
    """
    Ministério dos Povos Indígenas (página por mês/ano; usa 'última modificação' no byline)
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    # Ajuste a URL conforme o mês corrente se preferir.
    url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/07"
    data_hoje = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro Povos Indígenas: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    tab = "povos_indigenas"
    org_tag = soup.find('a', href="https://www.gov.br/povosindigenas/pt-br")
    orgao = org_tag.text.strip() if org_tag else "Ministério dos Povos Indígenas"

    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    noticias = soup.find_all('article', class_='entry')
    added = 0
    for noticia in noticias:
        sum_tag = noticia.find('span', class_='summary')
        a = sum_tag.find('a') if sum_tag else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        data_tag = noticia.find('span', class_='documentByLine')
        if not data_tag:
            continue
        texto_data = data_tag.get_text(strip=True)
        if "última modificação" not in texto_data.lower():
            continue

        try:
            # tenta primeira data com padrão dd/mm/aaaa
            m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", texto_data)
            if not m:
                continue
            data_fmt = datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue

        if data_fmt != data_hoje:
            continue

        desc_tag = noticia.find('p', class_='description discreet')
        descricao = desc_tag.get_text(strip=True) if desc_tag else "—"

        manager.buffer_row(tab, [data_fmt, orgao, "—", titulo, descricao, link])
        manager.add_url(link)
        added += 1

    print(f"✅ povos_indigenas: {added} item(ns) bufferizados.")


def scrape_ans(manager: SheetManager):
    """
    ANS – listas em <div class='conteudo'>
    Colunas: Data | Subtítulo | Título | Descrição | Link (mantemos padrão geral Data | Órgão | Subtítulo | Título | Descrição | Link)
    """
    url = "https://www.gov.br/ans/pt-br/assuntos/noticias"
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ANS: {e}")
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    blocks = soup.find_all("div", class_="conteudo")

    tab = "ans"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    added = 0
    for b in blocks:
        subt_tag = b.find("div", class_="subtitulo-noticia")
        subt = subt_tag.get_text(strip=True) if subt_tag else "—"

        a = b.find("a", href=True)
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        data_tag = b.find("span", class_="data")
        data_txt = data_tag.get_text(strip=True) if data_tag else ""
        # descrição: texto de <span class='descricao'>, menos a data no início, quando existir
        desc_tag = b.find("span", class_="descricao")
        if desc_tag:
            full = desc_tag.get_text(strip=True)
            descricao = full.replace(data_txt, "").strip() if data_txt else full
        else:
            descricao = "—"

        manager.buffer_row(tab, [data_txt, "ANS", subt, titulo, descricao, link])
        manager.add_url(link)
        added += 1

    print(f"✅ ans: {added} item(ns) bufferizados.")


def scrape_cfm(manager: SheetManager):
    """
    CFM – página inicial de notícias, captura primeiro card (título/link/data/descrição).
    Colunas: Data | Título | Descrição | Link  (aqui manteremos padrão com Órgão também)
    """
    url = "https://portal.cfm.org.br/noticias/?s="
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro CFM: {e}")
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    tab = "cfm"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    # Título (primeiro h3 da listagem), link (a.c-default), data (div.noticia-date), descrição (primeiro <p>)
    title_tag = soup.find("h3")
    title = title_tag.get_text(strip=True) if title_tag else None

    link_tag = soup.find("a", class_="c-default", href=True)
    link = link_tag.get("href", "").strip() if link_tag else None

    if not title or not link or manager.seen_url(link):
        print("✅ cfm: nada novo.")
        return

    date_div = soup.find("div", class_="noticia-date")
    day_tag = date_div.find("h3") if date_div else None
    day = day_tag.get_text(strip=True) if day_tag else ""

    month_year_div = date_div.find("div") if date_div else None
    month, year = "", ""
    if month_year_div:
        parts = month_year_div.get_text(separator=" ").split()
        if len(parts) >= 2:
            month, year = parts[0], parts[1]
    data_txt = f"{day} {month} {year}".strip()

    desc_tag = soup.find("p")
    descricao = desc_tag.get_text(strip=True) if desc_tag else "—"

    manager.buffer_row(tab, [data_txt, "CFM", "—", title, descricao, link])
    manager.add_url(link)
    print("✅ cfm: 1 item bufferizado.")


def scrape_fiocruz(manager: SheetManager):
    """
    Fiocruz – lista em div.views-row
    Colunas: Data | Título | Descrição | Link  (padronizado com Órgão e Subtítulo '—')
    """
    url = "https://fiocruz.br/noticias"
    data_desejada = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro Fiocruz: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    blocks = soup.select("div.views-row")

    tab = "fiocruz"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    added = 0
    for bloco in blocks:
        data_tag = bloco.find("div", class_="data-busca")
        if not data_tag:
            continue
        time_tag = data_tag.find("time")
        data_txt = time_tag.get_text(strip=True) if time_tag else ""
        if data_txt != data_desejada:
            continue

        titulo_tag = bloco.find("div", class_="titulo-busca")
        a = titulo_tag.find("a") if titulo_tag else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        href = a.get("href", "").strip()
        link = f"https://www.fiocruz.br{href}" if href and href.startswith("/") else href
        if not link or manager.seen_url(link):
            continue

        ch = bloco.find("div", class_="chamada-busca")
        descricao = ch.get_text(strip=True) if ch else "—"

        manager.buffer_row(tab, [data_txt, "Fiocruz", "—", titulo, descricao, link])
        manager.add_url(link)
        added += 1

    print(f"✅ fiocruz: {added} item(ns) bufferizados.")


def scrape_igualdade_racial(manager: SheetManager):
    """
    Igualdade Racial – div.conteudo
    Colunas: Data | Órgão | Categoria | Título | Descrição | Link
    (Categoria vai na coluna 'Subtítulo' para padronização)
    """
    url = "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias"
    data_desejada = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro Igualdade Racial: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    blocks = soup.find_all("div", class_="conteudo")

    tab = "igualdade_racial"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    org_tag = soup.find('a', href="https://www.gov.br/igualdaderacial/pt-br")
    orgao = org_tag.get_text(strip=True) if org_tag else "Ministério da Igualdade Racial"

    added = 0
    for b in blocks:
        cat_tag = b.find("div", class_="categoria-noticia")
        subt = cat_tag.get_text(strip=True) if cat_tag else "—"

        h2 = b.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        data_tag = b.find("span", class_="data")
        data_raw = data_tag.get_text(strip=True) if data_tag else ""
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        desc_tag = b.find("span", class_="descricao")
        descricao = desc_tag.get_text(strip=True) if desc_tag else "—"

        manager.buffer_row(tab, [data_fmt, orgao, subt, titulo, descricao, link])
        manager.add_url(link)
        added += 1

    print(f"✅ igualdade_racial: {added} item(ns) bufferizados.")


def scrape_anvisa(manager: SheetManager):
    """
    ANVISA – ul.noticias.listagem-noticias-com-foto > li
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    url = "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa"
    data_hoje = manager.now_br()
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ANVISA: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    itens = soup.select("ul.noticias.listagem-noticias-com-foto > li")

    tab = "anvisa"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    added = 0
    for li in itens:
        h2 = li.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        subt_tag = li.find("div", class_="subtitulo-noticia")
        subt = subt_tag.get_text(strip=True) if subt_tag else "—"

        desc_span = li.find("span", class_="descricao")
        if not desc_span:
            continue
        full = desc_span.get_text(strip=True)
        partes = [p.strip() for p in full.split("-")]
        data_lida = partes[0] if partes else ""
        descricao = partes[1] if len(partes) > 1 else full

        if data_lida == data_hoje:
            manager.buffer_row(tab, [data_lida, "ANVISA", subt, titulo, descricao, link])
            manager.add_url(link)
            added += 1

    print(f"✅ anvisa: {added} item(ns) bufferizados.")


def scrape_consed(manager: SheetManager, max_pages: int = 5):
    """
    Consed – paginação ?page=N; itens com <a> contendo <h2>, <small> (data), <p> (descrição)
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    base = "https://www.consed.org.br/noticias?page="
    data_desejada = manager.now_br()

    tab = "consed"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    already = 0
    added = 0

    for page in range(1, max_pages + 1):
        url = f"{base}{page}"
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Erro Consed {url}: {e}")
            break

        soup = BeautifulSoup(resp.content, "html.parser")
        anchors = soup.find_all("a", href=True)
        if not anchors:
            break

        for a in anchors:
            title_tag = a.find("h2")
            date_tag = a.find("small")
            desc_tag = a.find("p")
            if not (title_tag and date_tag and desc_tag):
                continue

            title = title_tag.get_text(strip=True)
            date_txt = date_tag.get_text(strip=True)
            desc = desc_tag.get_text(strip=True)
            href = a.get("href", "").strip()
            link = href if href.startswith("http") else f"https://www.consed.org.br{href}"

            if date_txt != data_desejada:
                continue
            if not link or manager.seen_url(link):
                already += 1
                continue

            manager.buffer_row(tab, [date_txt, "Consed", "—", title, desc, link])
            manager.add_url(link)
            added += 1

    print(f"✅ consed: {added} novo(s), {already} já existiam no cache.")


def scrape_undime(manager: SheetManager):
    """
    Undime – lista na página /noticia/page/1 com cards que incluem no link a data dd-mm-aaaa
    Colunas: Data | Órgão | Subtítulo | Título | Descrição | Link
    """
    url = "https://undime.org.br/noticia/page/1"
    data_desejada = manager.now_br()

    tab = "undime"
    manager.ensure_header(tab, ["Data", "Órgão", "Subtítulo", "Título", "Descrição", "Link"])

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro Undime: {e}")
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    cards = soup.find_all("div", class_="noticia mt-4 shadow2 p-3 border-radius")

    added = 0
    for card in cards:
        link_elem = card.find("a", href=True)
        if not link_elem:
            continue
        link = "https://undime.org.br" + link_elem["href"]

        # Data no padrão dd-mm-aaaa dentro da URL
        m = re.search(r"\b(\d{2}-\d{2}-\d{4})\b", link)
        if not m:
            continue
        data_fmt = datetime.strptime(m.group(1), "%d-%m-%Y").strftime("%d/%m/%Y")
        if data_fmt != data_desejada:
            continue
        if manager.seen_url(link):
            continue

        title_elem = card.find("h4")
        titulo = title_elem.get_text(strip=True) if title_elem else "—"

        # Descrição: seletor p.acessibilidade > a
        desc = "—"
        de = card.select_one("p.acessibilidade > a")
        if de:
            desc = de.get_text(strip=True)

        manager.buffer_row(tab, [data_fmt, "Undime", "—", titulo, desc, link])
        manager.add_url(link)
        added += 1

    print(f"✅ undime: {added} item(ns) bufferizados.")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main():
    mgr = SheetManager(SHEET_ID, JSON_KEYFILE, urls_tab="URLs", batch_size=60)

    # Ministérios padrão gov.br listagem <li>
    scrape_gov_listagem_padrao(mgr, "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte", tab="esporte")
    scrape_gov_listagem_padrao(mgr, "https://www.gov.br/mec/pt-br/assuntos/noticias", tab="mec")

    # Saúde (estrutura própria)
    scrape_saude(mgr)

    # Povos Indígenas (byline 'última modificação' – ajuste URL mensal se quiser)
    scrape_povos_indigenas(mgr)

    # ANS
    scrape_ans(mgr)

    # CFM
    scrape_cfm(mgr)

    # Fiocruz
    scrape_fiocruz(mgr)

    # Igualdade Racial
    scrape_igualdade_racial(mgr)

    # ANVISA
    scrape_anvisa(mgr)

    # Consed
    scrape_consed(mgr, max_pages=5)

    # Undime
    scrape_undime(mgr)

    # envia tudo o que ficou no buffer
    mgr.close()
    print("🏁 Finalizado com sucesso (leituras minimizadas e escritas em lote).")


if __name__ == "__main__":
    main()
