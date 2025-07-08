# ministerios.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils import (
    initialize_sheet,
    get_already_scraped_urls,
    add_scraped_url,
    get_or_create_worksheet,
    hoje_brasil_str,
    hoje_brasil_dt,
)

HEADERS = {'User-Agent': 'Mozilla/5.0'}

def processar_mec(sheet, url, data_desejada=None):
    data_desejada = data_desejada or hoje_brasil_str()
    gov_sheet = get_or_create_worksheet(sheet, "gov", headers=["Data", "Ministério", "Subtítulo", "Título", "Descrição", "URL"])
    urls_ja_lidas = get_already_scraped_urls(sheet)

    try:
        html = requests.get(url, headers=HEADERS, verify=False).text
        soup = BeautifulSoup(html, 'html.parser')
        nome_ministerio = soup.find('meta', property="og:site_name")
        nome_ministerio = nome_ministerio['content'] if nome_ministerio else "Ministério da Educação"

        novas_linhas = []

        for noticia in soup.find_all('li'):
            data_tag = noticia.find('span', class_='data')
            if not data_tag:
                continue
            try:
                data_dt = datetime.strptime(data_tag.text.strip(), "%d/%m/%Y")
            except ValueError:
                continue
            if data_dt.strftime("%d/%m/%Y") != data_desejada:
                continue

            titulo_tag = noticia.find('h2', class_='titulo')
            link_tag = titulo_tag.find('a') if titulo_tag else None
            if not link_tag or 'href' not in link_tag.attrs:
                continue

            url_noticia = link_tag['href']
            if url_noticia in urls_ja_lidas:
                continue

            subtitulo_tag = noticia.find('div', class_='subtitulo-noticia')
            subtitulo = subtitulo_tag.text.strip() if subtitulo_tag else "Subtítulo não disponível"

            descricao_tag = noticia.find('span', class_='descricao')
            descricao = (
                descricao_tag.text.split('-')[1].strip()
                if descricao_tag and '-' in descricao_tag.text
                else (descricao_tag.text.strip() if descricao_tag else "Descrição não disponível")
            )

            linha = [data_dt, nome_ministerio, subtitulo, titulo_tag.text.strip(), descricao, url_noticia]
            novas_linhas.append(linha)
            add_scraped_url(sheet, url_noticia)

        if novas_linhas:
            gov_sheet.append_rows(novas_linhas, value_input_option='USER_ENTERED')
            print(f"✅ {len(novas_linhas)} notícia(s) adicionada(s) do MEC.")
        else:
            print("ℹ️ Nenhuma notícia nova do MEC.")

    except Exception as e:
        print(f"❌ Erro MEC: {e}")