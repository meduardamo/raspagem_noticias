import re
import time
from typing import Dict, List, Optional, Iterable
from datetime import datetime
import os
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import pytz

# CONFIG
SHEET_ID = os.getenv("SHEET_ID")
JSON_KEYFILE = "credentials.json"
TZ = pytz.timezone("America/Sao_Paulo")
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

RATE_LIMIT_PAT = re.compile(
    r"(RATE_LIMIT_EXCEEDED|ReadRequestsPerMinutePerUser|quota.*per minute|RESOURCE_EXHAUSTED)",
    re.I,
)

# HELPERS: gspread com retry e gerenciador da planilha
def with_gspread_retry(fn, *args, **kwargs):
    """Retry exponencial para erros 429/limite de cota."""
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
                sleep_s *= 1 + 0.2 * (attempt % 3)  # jitter leve
                print(f"⏳ Rate limit (tentativa {attempt+1}/{max_attempts}). Aguardando {sleep_s:.1f}s…")
                time.sleep(sleep_s)
                attempt += 1
                continue
            raise

class SheetManager:
    """
    - Abre a planilha 1x; cache de worksheets
    - NÃO cria novas abas (exceto 'URLs' se ausente)
    - Lê cache de URLs 1x
    - Insere linhas com insert_rows(row=2) respeitando o header
    """
    def __init__(self, sheet_id: str, json_keyfile: str, urls_tab: str = "URLs"):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(json_keyfile, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.sheet = with_gspread_retry(self.client.open_by_key, sheet_id)
        self.urls_tab_name = urls_tab
        self._ws_cache: Dict[str, gspread.Worksheet] = {}
        self._urls_ws = self._get_or_create_urls_ws()
        self._url_set = self._load_url_set()
        self._buffers: Dict[str, List[List[str]]] = {}

    def now_br(self) -> str:
        return datetime.now(TZ).strftime("%d/%m/%Y")

    # ---------- URLs (de-dup) ----------
    def _get_or_create_urls_ws(self) -> gspread.Worksheet:
        try:
            ws = with_gspread_retry(self.sheet.worksheet, self.urls_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = with_gspread_retry(self.sheet.add_worksheet, title=self.urls_tab_name, rows="1", cols="1")
            with_gspread_retry(ws.append_row, ["URLs"])
        return ws

    def _load_url_set(self) -> set:
        vals = with_gspread_retry(self._urls_ws.col_values, 1) or []
        if not vals:
            with_gspread_retry(self._urls_ws.append_row, ["URLs"])
            return set()
        return set(vals[1:])

    def seen_url(self, url: str) -> bool:
        return url in self._url_set

    def add_url(self, url: str):
        if url and url not in self._url_set:
            with_gspread_retry(self._urls_ws.append_row, [url])
            self._url_set.add(url)

    # Worksheets
    def _get_ws_existing(self, title: str) -> Optional[gspread.Worksheet]:
        """Retorna worksheet existente; se não existir, retorna None (não cria)."""
        if title in self._ws_cache:
            return self._ws_cache[title]
        try:
            ws = with_gspread_retry(self.sheet.worksheet, title)
            self._ws_cache[title] = ws
            return ws
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Aba '{title}' não encontrada. Pulando sem criar.")
            return None

    # Inserção (sempre na linha 2)
    def insert_rows_top(self, tab: str, rows: Iterable[List[str]]):
        ws = self._get_ws_existing(tab)
        if ws is None:
            return
        rows = list(rows)
        if not rows:
            return
        # Para manter a ordem original (primeiro da lista aparece no topo),
        # insere todas as linhas de uma vez a partir da linha 2.
        with_gspread_retry(ws.insert_rows, rows, row=2, value_input_option="USER_ENTERED")

# HELPERS: rede
def get_html(url: str, timeout: int = 25) -> Optional[BeautifulSoup]:
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException as e:
        print(f"Erro ao acessar {url}: {e}")
        return None

# RASPAGENS (MINISTÉRIOS -> aba 'gov')
def rasp_gov_li_default(manager: SheetManager, url: str):
    """
    Páginas gov.br com <li> contendo:
      <span class='data'>dd/mm/aaaa</span>
      <h2 class='titulo'><a href='...'>Título</a></h2>
      <div class='subtitulo-noticia'>...</div> (opcional)
      <span class='descricao'>[data] - resumo</span> (opcional)
    Saída (aba 'gov'): [Data, Ministério, Subtítulo, Título, Resumo, Link]
    """
    soup = get_html(url)
    if not soup:
        return

    data_desejada = manager.now_br()
    og = soup.find("meta", property="og:site_name")
    ministerio = og["content"].strip() if og and og.get("content") else "—"

    novos: List[List[str]] = []

    for li in soup.find_all("li"):
        data_tag = li.find("span", class_="data")
        if not data_tag:
            continue
        data_raw = data_tag.get_text(strip=True)
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        h2 = li.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        subt_tag = li.find("div", class_="subtitulo-noticia")
        subtitulo = subt_tag.get_text(strip=True) if subt_tag else "Subtítulo não disponível"

        titulo = a.get_text(strip=True)
        desc_span = li.find("span", class_="descricao")
        if desc_span:
            texto = desc_span.get_text(strip=True)
            resumo = texto.split("-", 1)[1].strip() if "-" in texto else texto
        else:
            resumo = "Resumo não disponível"

        novos.append([data_fmt, ministerio, subtitulo, titulo, resumo, link])
        manager.add_url(link)

    if novos:
        # Inserir no topo da aba gov
        manager.insert_rows_top("gov", novos)

def rasp_saude(manager: SheetManager):
    """
    Ministério da Saúde (estrutura diferente)
    Saída 'gov': [Data, Ministério, Subtítulo, Título, Resumo, Link]
    """
    url = "https://www.gov.br/saude/pt-br/assuntos/noticias"
    soup = get_html(url)
    if not soup:
        return

    data_desejada = manager.now_br()
    ministerio = "Ministério da Saúde"
    novos: List[List[str]] = []

    for art in soup.find_all("article", class_="tileItem"):
        icon = art.find("i", class_="icon-day")
        data_raw = icon.find_next_sibling(string=True).strip() if icon else ""
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        subt = art.find("span", class_="subtitle")
        subtitulo = subt.get_text(strip=True) if subt else "Subtítulo não disponível"

        a = art.find("h2", class_="tileHeadline")
        a = a.find("a") if a else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        desc = art.find("span", class_="description")
        resumo = desc.get_text(strip=True) if desc else "Resumo não disponível"

        novos.append([data_fmt, ministerio, subtitulo, titulo, resumo, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("gov", novos)

def rasp_povos_indigenas(manager: SheetManager):
    """
    Ministério dos Povos Indígenas – usa "última modificação".
    Saída em 'gov'.
    """
    # Ajuste a URL mensal se necessário
    url = "https://www.gov.br/povosindigenas/pt-br/assuntos/noticias/2025/07"
    soup = get_html(url)
    if not soup:
        return
    data_hoje = manager.now_br()
    ministerio = "Ministério dos Povos Indígenas"

    novos: List[List[str]] = []

    for art in soup.find_all("article", class_="entry"):
        sum_tag = art.find("span", class_="summary")
        a = sum_tag.find("a") if sum_tag else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        byline = art.find("span", class_="documentByLine")
        if not byline:
            continue
        texto_data = byline.get_text(strip=True)
        if "última modificação" not in texto_data:
            continue
        data_raw = texto_data.split("última modificação")[-1].strip().split()[0]
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_hoje:
            continue

        desc = art.find("p", class_="description discreet")
        resumo = desc.get_text(strip=True) if desc else "Resumo não disponível"

        novos.append([data_fmt, ministerio, "Não disponível", titulo, resumo, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("gov", novos)

def rasp_igualdade_racial(manager: SheetManager):
    """
    Ministério da Igualdade Racial (estrutura em <div class='conteudo'>)
    Saída 'gov'.
    """
    url = "https://www.gov.br/igualdaderacial/pt-br/assuntos/copy2_of_noticias"
    soup = get_html(url)
    if not soup:
        return
    data_desejada = manager.now_br()
    ministerio = "Ministério da Igualdade Racial"

    novos: List[List[str]] = []

    for card in soup.find_all("div", class_="conteudo"):
        h2 = card.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        cat = card.find("div", class_="categoria-noticia")
        subtitulo = cat.get_text(strip=True) if cat else "Categoria não disponível"

        data_tag = card.find("span", class_="data")
        if not data_tag:
            continue
        data_raw = data_tag.get_text(strip=True)
        try:
            data_fmt = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%d/%m/%Y")
        except ValueError:
            continue
        if data_fmt != data_desejada:
            continue

        desc = card.find("span", class_="descricao")
        resumo = desc.get_text(strip=True) if desc else "Resumo não disponível"

        novos.append([data_fmt, ministerio, subtitulo, titulo, resumo, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("gov", novos)

# =============== RASPAGENS (OUTRAS ABAS) ===============
def rasp_cfm(manager: SheetManager):
    """
    Aba 'cfm' — colunas: [Data, Título, Descrição, Link]
    """
    url = "https://portal.cfm.org.br/noticias/?s="
    soup = get_html(url)
    if not soup:
        return

    # A página inicial mostra 1 destaque; coletamos esse bloco
    novos: List[List[str]] = []

    # Data (dia no <h3> e mês/ano no <div> ao lado)
    date_div = soup.find("div", class_="noticia-date")
    if date_div:
        day_tag = date_div.find("h3")
        day = day_tag.get_text(strip=True) if day_tag else ""
        month_year = date_div.find("div").get_text(separator=" ").split() if date_div.find("div") else []
        if len(month_year) >= 2:
            month, year = month_year[0], month_year[1]
        else:
            month, year = "", ""
        data_txt = f"{day} {month} {year}".strip()
    else:
        data_txt = ""

    title_tag = soup.find("h3")
    titulo = title_tag.get_text(strip=True) if title_tag else "Conselho Federal de Medicina"

    link_tag = soup.find("a", class_="c-default", href=True)
    link = link_tag["href"] if link_tag else ""
    if link and not manager.seen_url(link):
        desc_tag = soup.find("p")
        descricao = desc_tag.get_text(strip=True) if desc_tag else ""
        novos.append([data_txt, titulo, descricao, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("cfm", novos)

def rasp_fiocruz(manager: SheetManager):
    """
    Aba 'fiocruz' — [Data, Título, Descrição, Link]
    Só insere itens da data de hoje.
    """
    url = "https://fiocruz.br/noticias"
    soup = get_html(url)
    if not soup:
        return
    data_desejada = manager.now_br()
    novos: List[List[str]] = []

    for bloco in soup.select("div.views-row"):
        data_host = bloco.find("div", class_="data-busca")
        if not data_host:
            continue
        data = (data_host.find("time").get_text(strip=True) if data_host.find("time") else "").strip()
        if data != data_desejada:
            continue

        t = bloco.find("div", class_="titulo-busca")
        a = t.find("a") if t else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = "https://www.fiocruz.br" + a.get("href", "")
        if not link or manager.seen_url(link):
            continue

        ch = bloco.find("div", class_="chamada-busca")
        descricao = ch.get_text(strip=True) if ch else ""

        novos.append([data, titulo, descricao, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("fiocruz", novos)

def rasp_consed(manager: SheetManager, max_pages: int = 3):
    """
    Aba 'consed' — [Data, Título, Descrição, Link]
    Busca na(s) primeira(s) páginas; filtra pela data de hoje.
    """
    base = "https://www.consed.org.br/noticias?page="
    data_desejada = manager.now_br()
    novos: List[List[str]] = []

    for page in range(1, max_pages + 1):
        soup = get_html(f"{base}{page}")
        if not soup:
            break
        for a in soup.find_all("a", href=True):
            title_tag = a.find("h2")
            date_tag = a.find("small")
            desc_tag = a.find("p")
            if not (title_tag and date_tag and desc_tag):
                continue
            date_txt = date_tag.get_text(strip=True)
            if date_txt != data_desejada:
                continue
            link = a["href"]
            link = link if link.startswith("http") else f"https://www.consed.org.br{link}"
            if manager.seen_url(link):
                continue
            titulo = title_tag.get_text(strip=True)
            descricao = desc_tag.get_text(strip=True)
            novos.append([date_txt, titulo, descricao, link])
            manager.add_url(link)

    if novos:
        manager.insert_rows_top("consed", novos)

def rasp_undime(manager: SheetManager):
    """
    Aba 'undime' — [Data, Título, Descrição, Link]
    A data é inferida do próprio link (dd-mm-aaaa).
    """
    url = "https://undime.org.br/noticia/page/1"
    soup = get_html(url)
    if not soup:
        return
    data_desejada = manager.now_br()
    novos: List[List[str]] = []

    for bloco in soup.find_all("div", class_="noticia mt-4 shadow2 p-3 border-radius"):
        a = bloco.find("a", href=True)
        if not a:
            continue
        link = "https://undime.org.br" + a["href"]
        if manager.seen_url(link):
            continue

        m = re.search(r"\d{2}-\d{2}-\d{4}", link)
        if not m:
            continue
        dt = datetime.strptime(m.group(0), "%d-%m-%Y").strftime("%d/%m/%Y")
        if dt != data_desejada:
            continue

        h4 = bloco.find("h4")
        titulo = h4.get_text(strip=True) if h4 else ""

        try:
            descricao_tag = bloco.select_one("p.acessibilidade > a")
            descricao = descricao_tag.get_text(strip=True) if descricao_tag else ""
        except Exception:
            descricao = ""

        novos.append([dt, titulo, descricao, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("undime", novos)

def rasp_ans(manager: SheetManager):
    """
    Aba 'ans' — [Data, Subtítulo, Título, Link]  (sem descrição, de acordo com sua aba)
    """
    url = "https://www.gov.br/ans/pt-br/assuntos/noticias"
    soup = get_html(url)
    if not soup:
        return

    novos: List[List[str]] = []

    for card in soup.find_all("div", class_="conteudo"):
        a = card.find("a", href=True)
        if not a:
            continue
        link = a["href"].strip()
        if not link or manager.seen_url(link):
            continue

        titulo = a.get_text(strip=True)
        subt_tag = card.find("div", class_="subtitulo-noticia")
        subtitulo = subt_tag.get_text(strip=True) if subt_tag else "N/A"

        data_tag = card.find("span", class_="data")
        data = data_tag.get_text(strip=True) if data_tag else ""

        novos.append([data, subtitulo, titulo, link])
        manager.add_url(link)

    if novos:
        manager.insert_rows_top("ans", novos)

def rasp_anvisa(manager: SheetManager):
    """
    Aba 'anvisa' — [Data, Subtítulo, Título, Descrição, Tags, Link]
    Apenas itens do dia atual.
    """
    url = "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa"
    soup = get_html(url)
    if not soup:
        return
    data_hoje = manager.now_br()
    novos: List[List[str]] = []

    items = soup.select("ul.noticias.listagem-noticias-com-foto > li")
    for it in items:
        h2 = it.find("h2", class_="titulo")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        titulo = a.get_text(strip=True)
        link = a.get("href", "").strip()
        if not link or manager.seen_url(link):
            continue

        subt = it.find("div", class_="subtitulo-noticia")
        subtitulo = subt.get_text(strip=True) if subt else "ANVISA"  # sua aba mostra "ANVISA" nessa coluna

        desc_span = it.find("span", class_="descricao")
        if not desc_span:
            continue
        full = desc_span.get_text(strip=True)
        partes = [p.strip() for p in full.split("-")]
        data_lida = partes[0] if partes else ""
        descricao = partes[1] if len(partes) > 1 else full
        tags = ""  # se você quiser extrair tags específicas, troque aqui

        if data_lida == data_hoje:
            novos.append([data_lida, subtitulo, titulo, descricao, tags, link])
            manager.add_url(link)

    if novos:
        manager.insert_rows_top("anvisa", novos)

# EXECUÇÃO
def main():
    mgr = SheetManager(SHEET_ID, JSON_KEYFILE)

    # Ministérios -> gov
    rasp_gov_li_default(mgr, "https://www.gov.br/esporte/pt-br/noticias-e-conteudos/esporte")
    rasp_gov_li_default(mgr, "https://www.gov.br/mec/pt-br/assuntos/noticias")
    rasp_saude(mgr)
    rasp_povos_indigenas(mgr)
    rasp_igualdade_racial(mgr)

    # Outras abas no formato existente
    rasp_cfm(mgr)
    rasp_fiocruz(mgr)
    rasp_consed(mgr, max_pages=5)
    rasp_undime(mgr)
    rasp_ans(mgr)
    rasp_anvisa(mgr)

if __name__ == "__main__":
    main()
