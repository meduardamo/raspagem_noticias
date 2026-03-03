import sys
sys.dont_write_bytecode = True

import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import urllib3
import re
import ssl
import unicodedata
from email.utils import parsedate_to_datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Desabilita avisos de certificados SSL inseguros (comum em sites do governo)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MESES_PT = {
    'janeiro': '01',
    'fevereiro': '02',
    'marÃ§o': '03',
    'abril': '04',
    'maio': '05',
    'junho': '06',
    'julho': '07',
    'agosto': '08',
    'setembro': '09',
    'outubro': '10',
    'novembro': '11',
    'dezembro': '12'
}

HOSTS_SELENIUM = (
    "see.ac.gov.br",
    "rj.gov.br",
    "seduc.pa.gov.br",
    "rn.gov.br",
    "rondonia.ro.gov.br",
    "ba.gov.br",
    "educacao.rr.gov.br",
    "educacao.rs.gov.br",
    "estado.rs.gov.br",
)


def data_hoje_br():
    return datetime.now().strftime('%d/%m/%Y')


def normalizar_link(base_url, link):
    if str(link).startswith('http'):
        return link
    return base_url + (link if str(link).startswith('/') else '/' + str(link))


def _sanitizar_href_extraido(href):
    link = str(href or '').strip()
    if not link:
        return ''

    link = link.replace('\r', '').replace('\n', '').replace('\t', '').strip()

    urls_no_texto = re.findall(r'https?://[^\s"\'<>]+', link, flags=re.IGNORECASE)
    if urls_no_texto:
        return urls_no_texto[-1].strip()

    return link


def timestamp_coleta():
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def limite_noticias_atingido(noticias):
    try:
        limite = int(os.getenv("MAX_NOTICIAS_POR_FONTE", "0"))
    except ValueError:
        limite = 0
    return limite > 0 and len(noticias) >= limite


def _normalizar_texto_data(texto):
    txt = str(texto or "").strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return txt


def _montar_data_segura(dia, mes, ano):
    try:
        dia_i = int(str(dia).strip())
        mes_i = int(str(mes).strip())
        ano_i = int(str(ano).strip())
    except Exception:
        return None

    if not (2000 <= ano_i <= 2035):
        return None

    try:
        dt = datetime(ano_i, mes_i, dia_i)
    except Exception:
        return None

    # Evita falso positivo de datas futuras extraídas de atributos/arquivos.
    if dt.date() > (datetime.now().date() + timedelta(days=1)):
        return None

    return dt.strftime('%d/%m/%Y')


def _extrair_data_ptbr(texto):
    txt = _normalizar_texto_data(texto)
    if not txt:
        return None

    hoje = datetime.now().strftime('%d/%m/%Y')
    if 'hoje' in txt:
        return hoje

    if re.search(r'\bha\s*\d+\s*(hora|horas|minuto|minutos)\b', txt):
        return hoje

    if 'ontem' in txt:
        return (datetime.now() - timedelta(days=1)).strftime('%d/%m/%Y')

    # yyyy-mm-dd ou yyyy/mm/dd (com borda para evitar match parcial)
    m = re.search(r'(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)', txt)
    if m:
        ano, mes, dia = m.groups()
        data = _montar_data_segura(dia, mes, ano)
        if data:
            return data

    # dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy (com borda para evitar match parcial)
    m = re.search(r'(?<!\d)(\d{1,2})[/. -](\d{1,2})[/. -](\d{4})(?!\d)', txt)
    if m:
        dia, mes, ano = m.groups()
        data = _montar_data_segura(dia, mes, ano)
        if data:
            return data

    # dd/mm/yy, dd-mm-yy, dd.mm.yy (com borda para evitar match parcial)
    m = re.search(r'(?<!\d)(\d{1,2})[/. -](\d{1,2})[/. -](\d{2})(?!\d)', txt)
    if m:
        dia, mes, ano2 = m.groups()
        ano = f"20{ano2}" if int(ano2) <= 69 else f"19{ano2}"
        data = _montar_data_segura(dia, mes, ano)
        if data:
            return data

    meses = {
        'janeiro': '01', 'jan': '01',
        'fevereiro': '02', 'fev': '02',
        'marco': '03', 'mar': '03',
        'abril': '04', 'abr': '04',
        'maio': '05', 'mai': '05',
        'junho': '06', 'jun': '06',
        'julho': '07', 'jul': '07',
        'agosto': '08', 'ago': '08',
        'setembro': '09', 'set': '09',
        'outubro': '10', 'out': '10',
        'novembro': '11', 'nov': '11',
        'dezembro': '12', 'dez': '12',
    }

    # 26/fevereiro/2026, 26-fevereiro-2026, 26.fevereiro.2026
    m = re.search(r'(?<!\d)(\d{1,2})\s*[/.-]\s*([a-z]+)\s*[/.-]\s*(\d{4})(?!\d)', txt)
    if m and m.group(2) in meses:
        dia, mes_txt, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    # 26 de fevereiro de 2026
    m = re.search(r'(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})', txt)
    if m and m.group(2) in meses:
        dia, mes_txt, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    # 26 fevereiro 2026
    m = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', txt)
    if m and m.group(2) in meses:
        dia, mes_txt, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    # 26 fevereiro, 2026
    m = re.search(r'(\d{1,2})\s+([a-z]+),\s+(\d{4})', txt)
    if m and m.group(2) in meses:
        dia, mes_txt, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    # fevereiro 26, 2026
    m = re.search(r'([a-z]+)\s+(\d{1,2}),\s*(\d{4})', txt)
    if m and m.group(1) in meses:
        mes_txt, dia, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    # fevereiro 26 2026
    m = re.search(r'([a-z]+)\s+(\d{1,2})\s+(\d{4})', txt)
    if m and m.group(1) in meses:
        mes_txt, dia, ano = m.groups()
        data = _montar_data_segura(dia, meses[mes_txt], ano)
        if data:
            return data

    return None


def noticia_eh_de_hoje(data_publicacao):
    data = _extrair_data_ptbr(data_publicacao)
    if not data:
        return False
    try:
        return datetime.strptime(data, '%d/%m/%Y').date() == datetime.now().date()
    except Exception:
        return False


def extrair_data_da_pagina_noticia(url, headers=None):
    try:
        response = requests.get(url, headers=headers, timeout=(4, 8), verify=False)
        if response.status_code != 200:
            return ''

        soup = BeautifulSoup(response.text, 'html.parser')

        candidatos = []

        for prop in ['article:published_time', 'og:published_time', 'publish_date']:
            tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
            if tag and tag.get('content'):
                candidatos.append(tag.get('content'))

        for time_tag in soup.find_all('time'):
            if time_tag.has_attr('datetime'):
                candidatos.append(time_tag['datetime'])
            texto_time = time_tag.get_text(' ', strip=True)
            if texto_time:
                candidatos.append(texto_time)

        # Muitos portais (incluindo AC) trazem data apenas em atributos de mídia/links.
        attrs_interesse = {
            'datetime', 'content', 'href', 'src', 'srcset',
            'data-permalink', 'data-orig-file', 'data-medium-file', 'data-large-file',
            'data-image-title', 'data-image-caption', 'title'
        }
        for tag in soup.find_all(True):
            for attr, value in tag.attrs.items():
                if attr in attrs_interesse:
                    if isinstance(value, list):
                        candidatos.extend(str(v) for v in value)
                    else:
                        candidatos.append(str(value))

        # JSON-LD e scripts podem conter datePublished/dateModified em ISO.
        for script in soup.find_all('script'):
            texto_script = script.string or script.get_text(' ', strip=True)
            if texto_script:
                candidatos.append(texto_script)

        body_txt = soup.get_text(' ', strip=True)
        if body_txt:
            candidatos.append(body_txt)

        for c in candidatos:
            data = _extrair_data_ptbr(c)
            if data:
                return data
    except Exception:
        return ''

    return ''


def link_parece_noticia(url):
    link = str(url or '').lower().strip()
    if not link.startswith('http'):
        return False
    if any(ext in link for ext in ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']):
        return False
    if any(t in link for t in ['/categoria/', '/tag/', '/author/', '/wp-content/', '/documents/']):
        return False
    if 'agencia.ac.gov.br' in link:
        if any(t in link for t in [
            '/ultimas-noticias', '/contato', '/sobre', '/revista-deracre', '/portifolio-governo',
            '/acre-floresta-em-pe', '/governador', '/vice-governadora', '/sala-de-imprensa',
            '/servicos', '/manual-de-redacao', '/categoria/', '/feed/'
        ]):
            return False
        path = link.split('agencia.ac.gov.br', 1)[-1].split('#', 1)[0].split('?', 1)[0].strip('/').lower()
        if not path or path.startswith('inicio-'):
            return False
        return True
    if 'see.ac.gov.br' in link:
        if any(t in link for t in ['/noticias/', '/contato', '/sobre', '/ouvidoria', '/acesso-a-informacao', '/orgaos-vinculados']):
            return False
        return True
    if 'agenciadenoticias.ms.gov.br' in link:
        if any(t in link for t in ['/ultimas-noticias', '/contato', '/sobre', '/categoria/', '/tag/', '/geral/']):
            return False
        return True
    if 'seduc.am.gov.br' in link:
        if any(t in link for t in ['/component/users/', '/component/search/', '/contato', '/ouvidoria']):
            return False
        return '/component/content/article/' in link
    if 'cl.df.gov.br' in link:
        if any(t in link for t in ['/documents/', '/web/', '/category/', '/tag/', '/author/']):
            return False
        return '/-/' in link
    if 'educacao.df.gov.br' in link:
        if any(t in link for t in ['/documents/', '/web/', '/category/', '/wp-content/']):
            return False
        return '/w/' in link
    if 'agenciasp.sp.gov.br' in link:
        if any(t in link for t in ['/editoria/', '/regiao/', '/categoria/', '/tag/', '/author/']):
            return False
        return True
    if 'al.se.leg.br' in link:
        if any(t in link for t in ['/audios-das-sessoes-legislativas', '/categoria/', '/tag/', '/author/']):
            return False
        caminho = link.split('al.se.leg.br', 1)[-1].split('?', 1)[0].strip('/')
        return bool(caminho)
    if 'al.ac.leg.br' in link:
        if any(t in link for t in ['/categoria/', '/category/', '/tag/', '/author/', '/wp-content/']):
            return False
        if re.search(r'[?&]p=\d+', link):
            return True
        caminho = link.split('al.ac.leg.br', 1)[-1].split('?', 1)[0].strip('/').lower()
        if caminho in {'', 'home'}:
            return False
        return '/noticia' in link or '/noticias' in link
    if 'al.ap.leg.br' in link:
        if any(t in link for t in ['/categoria/', '/category/', '/tag/', '/author/', '/wp-content/']):
            return False
        return 'pagina.php?pg=exibir_noticia' in link and bool(re.search(r'[?&]idnoticia=\d+', link))
    if 'pi.gov.br' in link:
        if any(t in link for t in ['/categoria/', '/tag/', '/author/', '/wp-content/', '/contato', '/sobre']):
            return False
        return True
    if 'ceara.gov.br' in link:
        if any(t in link for t in ['/categoria/', '/tag/', '/author/', '/wp-content/']):
            return False
        return bool(re.search(r'/\d{4}/\d{2}/', link))
    if 'goias.gov.br' in link:
        if any(t in link for t in ['/categoria/', '/tag/', '/author/', '/wp-content/', '/administracao/', '/ouvidoria', '/transparencia']):
            return False
        caminho = link.split('goias.gov.br', 1)[-1].split('?', 1)[0].strip('/').lower()
        if caminho in {'', 'noticias', 'categoria/noticias'}:
            return False
        return True
    if 'sedu.es.gov.br' in link:
        return '/notícia/' in link or '/noticia/' in link
    if 'educacao.ma.gov.br' in link:
        if any(t in link for t in ['/secao/', '/categoria/', '/tag/', '/author/', '/wp-content/']):
            return False
        path = link.split('educacao.ma.gov.br', 1)[-1].split('?', 1)[0].strip('/').lower()
        if path in {'', 'inicio'}:
            return False
        return True
    if 'seeduc.rj.gov.br' in link:
        return '/not%c3%adcias' in link or '/noticias' in link
    if '.mt.gov.br' in link and '/w/' in link:
        return True
    if 'seduc.mt.gov.br' in link:
        if '/noticias' in link and '/w/' not in link:
            return False
        return '/w/' in link
    if 'aleam.gov.br' in link:
        if any(t in link for t in [
            '/deputados/',
            '/acessibilidade',
            '/category/',
            '/categoria/',
            '/tag/',
            '/author/',
            '/wp-content/',
            '/#',
        ]):
            return False
        path = link.split('aleam.gov.br', 1)[-1].split('?', 1)[0].strip()
        if path in {'', '/'}:
            return False
        return True
    if 'rondonia.ro.gov.br' in link:
        if any(t in link for t in ['/portal/noticias/', '/seduc/noticias/', '/categoria/', '/tag/', '/author/']):
            return False
        resto = link.split('rondonia.ro.gov.br', 1)[-1].split('?', 1)[0].strip()
        return len(resto.strip('/')) > 0
    return any(t in link for t in ['/noticia', '/noticias', '/materia', '/news'])


def _link_parece_institucional(link):
    link_lower = str(link or '').strip().lower()
    if not link_lower:
        return True

    termos_institucionais = [
        '/contato', '/sobre', '/ouvidoria', '/acesso-a-informacao', '/transparencia',
        '/mapa-do-site', '/secretaria', '/governo', '/governador', '/agenda',
        '/servicos', '/serviço', '/web/', '/documents/', '/categoria/', '/tag/', '/author/'
    ]
    return any(t in link_lower for t in termos_institucionais)


def noticia_parece_valida(linha):
    if not linha or len(linha) < 4:
        return False

    titulo = str(linha[1] or '').strip().lower()
    link = extrair_url_da_formula_hyperlink(linha[2])
    link_lower = str(link or '').strip().lower()

    if len(titulo) < 12:
        return False

    termos_ruido_titulo = [
        'portal de governança',
        'portal de governanca',
        'guia prático',
        'guia pratico',
        'ouvidoria',
        'transparência',
        'transparencia',
        'mapa do site',
        'acessibilidade',
        'links úteis',
        'links uteis',
        'página inicial',
        'pagina inicial',
    ]
    if any(t in titulo for t in termos_ruido_titulo):
        return False

    if not link_lower:
        return False
    if any(ext in link_lower for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']):
        return False
    if any(t in link_lower for t in ['/documents/', '/wp-content/', '/categoria/', '/tag/', '/author/']):
        return False

    # Mantém links de notícia clássicos e aceita exceções conhecidas por portal.
    if link_parece_noticia(link_lower):
        return True

    excecoes_noticia = [
        'agenciaamazonas.am.gov.br',
        'agenciabrasilia.df.gov.br',
        'agenciaamapa.com.br',
        'see.ac.gov.br',
        'agenciadenoticias.ms.gov.br',
        'pi.gov.br',
    ]
    if any(e in link_lower for e in excecoes_noticia):
        return True

    # Fallback robusto: muitos portais usam URLs sem /noticia(s),
    # mas com data válida + título consistente + slug de matéria.
    data_valida = _extrair_data_ptbr(str(linha[0] or ''))
    if not data_valida:
        return False

    if _link_parece_institucional(link_lower):
        return False

    path = link_lower.split('://', 1)[-1]
    path = path.split('/', 1)[1] if '/' in path else ''
    path = path.split('?', 1)[0].strip('/').lower()
    if not path:
        return False

    # Aceita URLs com estrutura de matéria (segmentada ou com slug extenso).
    if '/' in path:
        return True
    return ('-' in path and len(path) >= 20)


def filtrar_noticias_reais(noticias):
    return [linha for linha in noticias if noticia_parece_valida(linha)]


def log_status_noticias(uf, noticias, etapa="FINAL", somente_entrou=False):
    if os.getenv("LOG_STATUS_NOTICIAS", "1").strip().lower() in {"0", "false", "no", "off"}:
        return

    etapa_norm = str(etapa or "FINAL").strip().upper()
    if etapa_norm not in {"RAW", "FINAL", "SITE"}:
        etapa_norm = "FINAL"

    if etapa_norm == "RAW" and os.getenv("LOG_STATUS_RAW", "0").strip().lower() in {"0", "false", "no", "off"}:
        return
    if etapa_norm == "FINAL" and os.getenv("LOG_STATUS_FINAL", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    if etapa_norm == "SITE" and os.getenv("LOG_STATUS_SITE_NOTICIAS", "0").strip().lower() in {"0", "false", "no", "off"}:
        return

    ufs_log = {
        item.strip().upper()
        for item in os.getenv("LOG_STATUS_UF", "").split(",")
        if item and item.strip()
    }
    if ufs_log and uf.upper() not in ufs_log:
        return

    for linha in noticias:
        if len(linha) < 4:
            continue
        data_extraida = str(linha[0] or '').strip() or 'SEM_DATA'
        titulo = str(linha[1] or '').replace('\n', ' ').replace('\r', ' ').strip()
        origem = str(linha[3] or '').strip() or 'SEM_ORIGEM'
        data_ok = bool(_extrair_data_ptbr(data_extraida))
        status_data = 'DATA_OK' if data_ok else 'SEM_DATA'
        status = 'ENTROU' if noticia_eh_de_hoje(linha[0]) else 'FICOU_FORA'
        if somente_entrou and status != 'ENTROU':
            continue

        tag_log = f"LOG-{etapa_norm}"
        if etapa_norm == "FINAL":
            tag_log = "LOG"
        elif etapa_norm == "SITE":
            tag_log = "LOG-SITE-NOTICIA"

        print(f"[{tag_log}] {uf} | {origem} | {titulo[:140]} | {data_extraida} | {status_data} | {status}")


def extrair_url_da_formula_hyperlink(valor_link):
    texto = str(valor_link or "").strip()
    if not texto:
        return ""

    m = re.search(r'^=HYPERLINK\("([^"]+)";"[^"]+"\)$', texto, re.IGNORECASE)
    if m:
        return m.group(1)

    if texto.startswith('http'):
        return texto

    return ""


def enriquecer_datas_por_link(noticias):
    if not noticias:
        return noticias

    if os.getenv("ENABLE_DATE_ENRICHMENT", "1").strip().lower() in {"0", "false", "no", "off"}:
        return noticias

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    cache_data_por_url = {}
    modo_rapido = os.getenv("MODO_RAPIDO", "0").strip().lower() in {"1", "true", "yes", "on"}
    limite_padrao = "8" if modo_rapido else "25"
    try:
        limite_enriquecimento = int(os.getenv("MAX_ENRIQUECER_LINKS_POR_UF", limite_padrao))
    except ValueError:
        limite_enriquecimento = 8 if modo_rapido else 25
    enriquecidos = 0

    for linha in noticias:
        if limite_enriquecimento > 0 and enriquecidos >= limite_enriquecimento:
            break

        if len(linha) < 3:
            continue

        data_atual = str(linha[0] or '').strip()
        precisa_validar = (not data_atual) or (not noticia_eh_de_hoje(data_atual))
        if not precisa_validar:
            continue

        url_noticia = extrair_url_da_formula_hyperlink(linha[2])
        if not url_noticia:
            continue
        if not link_parece_noticia(url_noticia):
            continue

        if url_noticia not in cache_data_por_url:
            cache_data_por_url[url_noticia] = extrair_data_da_pagina_noticia(url_noticia, headers=headers)
            enriquecidos += 1

        data_extraida = cache_data_por_url[url_noticia]
        if data_extraida:
            linha[0] = data_extraida

    return noticias


def filtrar_noticias_de_hoje_com_resolucao(noticias):
    if not noticias:
        return []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        max_checks = int(os.getenv("MAX_VERIFICACOES_DATA_HOJE", "40"))
    except ValueError:
        max_checks = 40

    cache_data_por_url = {}
    checks = 0
    noticias_hoje = []

    for linha in noticias:
        if len(linha) < 3:
            continue

        # 1) Usa data já extraída, se válida.
        if noticia_eh_de_hoje(linha[0]):
            noticias_hoje.append(linha)
            continue

        # 2) Tenta data pela URL da matéria.
        link = extrair_url_da_formula_hyperlink(linha[2])
        if not link or not link_parece_noticia(link):
            continue

        data_link = _extrair_data_ptbr(link)
        if data_link:
            linha[0] = data_link
            if noticia_eh_de_hoje(linha[0]):
                noticias_hoje.append(linha)
                continue

        # 3) Último recurso geral: abre a matéria e extrai data real.
        if max_checks > 0 and checks >= max_checks:
            continue

        if link not in cache_data_por_url:
            cache_data_por_url[link] = extrair_data_da_pagina_noticia(link, headers=headers)
            checks += 1

        data_pagina = cache_data_por_url[link]
        if data_pagina:
            linha[0] = data_pagina
            if noticia_eh_de_hoje(linha[0]):
                noticias_hoje.append(linha)

    return noticias_hoje


def selecionar_primeiras_noticias_por_site(noticias, limite_por_site=5):
    if not noticias:
        return []

    selecionadas = []
    contagem_por_origem = {}

    for linha in noticias:
        if len(linha) < 4:
            continue

        origem = str(linha[3] or '').strip().upper() or 'SEM_ORIGEM'
        atual = contagem_por_origem.get(origem, 0)
        if atual >= limite_por_site:
            continue

        selecionadas.append(linha)
        contagem_por_origem[origem] = atual + 1

    return selecionadas


def montar_linha_noticia(data_publicacao, titulo, link, origem):
    return [
        data_publicacao,
        titulo[:200],
        f'=HYPERLINK("{link}";"{link}")',
        origem,
        timestamp_coleta()
    ]


def extrair_seduc_ac(soup, origem):
    noticias = []
    cards = soup.find_all('div', class_='anwp-pg-post-teaser')
    if not cards:
        return noticias

    for card in cards:
        title_div = card.find('div', class_='anwp-pg-post-teaser__title')
        if not title_div:
            continue

        titulo = title_div.get_text(strip=True)

        a_tag = card.find('a', href=True)
        if not a_tag:
            continue
        link = a_tag['href']

        if any(termo in titulo.lower() for termo in [
            'pular para o conteúdo', 'serviços ac.gov', 'acesso à informação', 'órgãos do governo',
            'representações da see', 'cartilhas institucionais', 'órgãos vinculados', 'chamada pública',
            'editor de pdfs', 'vozes na rede', 'jogos estudantis', 'alto acre geral', 'baixo acre geral',
            'plácido de castro', 'senador guiomard', 'santa rosa do purus', 'cruzeiro do sul',
            'marechal thaumaturgo', 'rodrigues alves', 'plano estadual de educação', 'matriculas on-line 2026'
        ]):
            continue

        data_publicacao = ''
        time_tag = card.find('time', class_='anwp-pg-published')
        if time_tag and time_tag.has_attr('datetime'):
            try:
                dt_obj = datetime.strptime(time_tag['datetime'][:10], '%Y-%m-%d')
                data_publicacao = dt_obj.strftime('%d/%m/%Y')
            except:
                pass

        noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
        if limite_noticias_atingido(noticias):
            break

    return noticias


def extrair_seduc_am(soup, origem):
    noticias = []
    cards = soup.find_all('div', class_='sppb-addon-article')
    if not cards:
        return noticias

    links_vistos_am = set()
    for card in cards:
        h3 = card.find('h3', class_='uk-article-title')
        if not h3:
            continue
        a_tag = h3.find('a')
        if not a_tag:
            continue

        titulo = a_tag.get_text(strip=True)
        link = normalizar_link("https://www.seduc.am.gov.br", a_tag['href'])

        if link in links_vistos_am:
            continue
        links_vistos_am.add(link)

        data_publicacao = ''
        date_span = card.find('span', class_='sppb-meta-date')
        if date_span:
            texto_data = date_span.get_text(strip=True).lower()
            match = re.search(r'(\d{1,2})\s+([a-zÃ§]+)\s+(\d{4})', texto_data)
            if match and match.group(2) in MESES_PT:
                data_publicacao = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"

        noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
        if limite_noticias_atingido(noticias):
            break

    return noticias


def extrair_governo_am(soup, origem):
    noticias = []
    cards = soup.find_all('div', class_='card-blog')
    if not cards:
        return noticias

    for card in cards:
        h2 = card.find('h2')
        if not h2:
            continue
        titulo = h2.get_text(strip=True)

        a_tag = card.find('a', class_='stretched-link')
        if not a_tag:
            continue
        link = a_tag['href']

        data_publicacao = ''
        date_small = card.find('small', class_='time-list-post')
        if date_small:
            texto_data = date_small.get_text(strip=True).lower()
            if "hÃ¡" not in texto_data and "minuto" not in texto_data:
                match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                if match and match.group(2) in MESES_PT:
                    data_publicacao = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"

        noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
        if limite_noticias_atingido(noticias):
            break

    return noticias


def extrair_governo_ap(soup, origem):
    noticias = []
    cards = soup.find_all('div', class_='card')
    if not cards:
        return noticias

    for card in cards:
        a_tag = card.find('a', href=True)
        if not a_tag:
            continue
        link = a_tag['href']
        if '/noticia/' not in link:
            continue

        titulo_el = card.find(['h4', 'h5', 'h3', 'h2', 'h6'])
        if titulo_el:
            titulo = titulo_el.get_text(strip=True)
        else:
            titulo = a_tag.get_text(" ", strip=True)

        data_publicacao = ''
        texto_card = card.get_text(" ", strip=True)
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_card)
        if match:
            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

        link = normalizar_link("https://agenciaamapa.com.br", link)
        noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
        if limite_noticias_atingido(noticias):
            break

    return noticias

def setup_gspread():
    print("[DEBUG] Autenticando no Google Sheets...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    if creds_json:
        try:
            payload = json.loads(creds_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_CREDENTIALS_JSON inválido (não é JSON válido).") from exc
        creds = ServiceAccountCredentials.from_json_keyfile_dict(payload, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    return gspread.authorize(creds)


def executar_com_retry(func, descricao, tentativas=5, espera_inicial=2):
    termos_transitorios = [
        '10053',
        'connection aborted',
        'connection reset',
        'timed out',
        'timeout',
        'temporarily unavailable',
        'protocolerror',
        'ssl',
        'remote disconnected'
    ]

    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except Exception as e:
            erro = str(e).lower()
            erro_transitorio = any(termo in erro for termo in termos_transitorios)
            ultima_tentativa = tentativa == tentativas

            if erro_transitorio and not ultima_tentativa:
                espera = espera_inicial * tentativa
                print(f"[AVISO] Falha temporária em {descricao} (tentativa {tentativa}/{tentativas}): {e}")
                print(f"[AVISO] Aguardando {espera}s para tentar novamente...")
                time.sleep(espera)
                continue

            raise


def scraping_noticias(url, origem):
    noticias = []
    data_referencia_http = ''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        # ALEPE: evita tentativa inicial em HTTPS (lenta/falha) e usa HTTP direto.
        if "alepe.pe.gov.br" in str(url).lower() and str(url).startswith("https://"):
            url = "http://" + str(url)[8:]

        # BA: a rota /noticias pode cair em página de segurança; usa rota estável.
        if "ba.gov.br/noticias" in str(url).lower() and "ba.gov.br/comunicacao/noticias" not in str(url).lower():
            url = "https://www.ba.gov.br/comunicacao/noticias"

        print(f"[DEBUG] Tentando: {url}")

        usar_selenium = any(host in url for host in HOSTS_SELENIUM)
        if "ba.gov.br/comunicacao/noticias" in str(url).lower():
            usar_selenium = False
        if "seeduc.rj.gov.br" in str(url).lower():
            usar_selenium = False

        if usar_selenium:
            # Use Selenium for dynamic content
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-infobars")
            options.add_argument("--no-first-run")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

            driver = None
            try:
                try:
                    driver = webdriver.Chrome(options=options)
                except Exception as driver_err:
                    print(f"[AVISO] Selenium Manager falhou ({driver_err}). Tentando webdriver-manager...")
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

                driver.set_page_load_timeout(40)
                driver.get(url)
                WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                soup = BeautifulSoup(driver.page_source, 'html.parser')
            finally:
                if driver is not None:
                    driver.quit()
        else:
            session = requests.Session()
            retry = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            try:
                response = session.get(url, headers=headers, timeout=30, verify=False)
            except requests.exceptions.RequestException as req_err:
                response = None
                erro_txt = str(req_err)

                # Fallback automÃ¡tico: tenta HTTP quando HTTPS falha por bloqueio/rede.
                if str(url).startswith("https://"):
                    url_http = "http://" + str(url)[8:]
                    try:
                        print(f"[AVISO] Erro no HTTPS. Tentando conexÃ£o alternativa via HTTP: {url_http}")
                        response = session.get(url_http, headers=headers, timeout=30, verify=False)
                        url = url_http
                    except requests.exceptions.RequestException:
                        response = None

                if response is None:
                    if "10013" in erro_txt or "acesso a um soquete" in erro_txt.lower():
                        print(f"[AVISO] Host bloqueado/inacessÃ­vel em rede local: {url}. Ignorando.")
                    else:
                        print(f"[AVISO] Falha de conexÃ£o em {url}. Ignorando.")
                    return noticias

            if response.status_code != 200:
                msg = "Link Quebrado (404)" if response.status_code == 404 else f"Status {response.status_code}"
                print(f"[ERRO] Falha ao acessar {url}: {msg}")
                return noticias

            # Alguns portais (ex.: SEDUC RJ em Google Sites) não expõem data no HTML.
            # Usa a data do header HTTP como fallback de referência da publicação/coleta.
            data_http = response.headers.get('Date', '')
            if data_http:
                try:
                    dt_http = parsedate_to_datetime(data_http)
                    data_referencia_http = dt_http.strftime('%d/%m/%Y')
                except Exception:
                    data_referencia_http = ''

            # Fix encoding for Agencia Amapa (Governo AP)
            if "agenciaamapa.com.br" in url or "agenciapara.com.br" in url:
                response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- LÃ“GICA ESPECÃFICA: SEDUC AC (Layout de Cards Elementor) ---
        if "see.ac.gov.br" in url:
            noticias_portal = extrair_seduc_ac(soup, origem)
            if noticias_portal:
                return noticias_portal

        # --- LÃ“GICA ESPECÃFICA: SEDUC AM (Joomla/SP Page Builder) ---
        if "seduc.am.gov.br" in url:
            noticias_portal = extrair_seduc_am(soup, origem)
            if noticias_portal:
                return noticias_portal

        # --- LÃ“GICA ESPECÃFICA: GOVERNO AM (Agencia Amazonas) ---
        if "agenciaamazonas.am.gov.br" in url:
            noticias_portal = extrair_governo_am(soup, origem)
            if noticias_portal:
                return noticias_portal

        # --- LÃ“GICA ESPECÃFICA: GOVERNO AP (AgÃªncia AmapÃ¡) ---
        if "agenciaamapa.com.br" in url:
            noticias_portal = extrair_governo_ap(soup, origem)
            if noticias_portal:
                return noticias_portal

        # --- LÓGICA ESPECÍFICA: GOVERNO AC (agencia.ac.gov.br / Elementor posts) ---
        if "agencia.ac.gov.br" in url:
            cards = soup.find_all('article', class_=lambda c: c and 'elementor-post' in str(c).lower())
            if cards:
                links_vistos_ac = set()
                for card in cards:
                    title_link = card.select_one('h3.elementor-post__title a[href]') or card.select_one('a.elementor-post__thumbnail__link[href]')
                    if not title_link:
                        continue

                    link = str(title_link.get('href') or '').strip()
                    if not link:
                        continue
                    if not link.startswith('http'):
                        link = normalizar_link('https://agencia.ac.gov.br', link)

                    if link in links_vistos_ac:
                        continue

                    titulo = title_link.get_text(' ', strip=True)
                    if len(titulo) < 12:
                        continue

                    link_lower = link.lower()
                    if any(t in link_lower for t in [
                        '/governador', '/vice-governadora', '/sala-de-imprensa', '/contato', '/sobre',
                        '/revista-deracre', '/portifolio-governo', '/acre-floresta-em-pe', '/manual-de-redacao'
                    ]):
                        continue

                    data_publicacao = ''
                    date_el = card.select_one('.elementor-post-date') or card.find('time')
                    if date_el:
                        data_publicacao = _extrair_data_ptbr(date_el.get_text(' ', strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(link) or ''

                    noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
                    links_vistos_ac.add(link)

                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÓGICA ESPECÍFICA: GOVERNO MS (agenciadenoticias.ms.gov.br) ---
        if "agenciadenoticias.ms.gov.br" in url:
            cards = soup.find_all('div', class_='postBox')
            if cards:
                links_vistos_ms = set()
                for card in cards:
                    h3 = card.find('h3')
                    a_tag = h3.find('a', href=True) if h3 else None
                    if not a_tag:
                        continue

                    titulo = a_tag.get_text(" ", strip=True)
                    link = a_tag.get('href', '').strip()
                    if not titulo or not link:
                        continue

                    if not link.startswith('http'):
                        link = "https://agenciadenoticias.ms.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_ms:
                        continue
                    links_vistos_ms.add(link)

                    data_publicacao = ''
                    contexto_card = card.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(contexto_card) or _extrair_data_ptbr(link) or ''

                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO BA (Portal BA) ---
        if "ba.gov.br" in url:
            try:
                titulo_pagina = (soup.title.get_text(" ", strip=True).lower() if soup.title else "")
                texto_pagina = soup.get_text(" ", strip=True).lower()
                bloqueado_ba = (
                    "ba.gov segurança" in titulo_pagina
                    or "temporariamente bloqueada" in texto_pagina
                    or "atividade considerada suspeita" in texto_pagina
                )
                if bloqueado_ba:
                    url_ba_fallback = "https://www.ba.gov.br/comunicacao/noticias"
                    resp_ba = requests.get(url_ba_fallback, headers=headers, timeout=30, verify=False)
                    if resp_ba.status_code == 200:
                        soup = BeautifulSoup(resp_ba.text, 'html.parser')
                        url = url_ba_fallback
            except Exception:
                pass

            # EstratÃ©gia: Buscar links que tenham estrutura de notÃ­cia
            links = soup.find_all('a', href=True)
            links_vistos_ba = set()
            
            for a in links:
                href = a['href']
                titulo = a.get_text(" ", strip=True)
                
                # Se o tÃ­tulo estiver vazio, tenta buscar em tags filhas comuns
                if not titulo:
                    child = a.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span', 'p'])
                    if child:
                        titulo = child.get_text(" ", strip=True)

                # Filtros de URL
                if '/noticias/' not in href and '/materia/' not in href:
                    continue
                
                # Filtros de lixo
                if any(x in href for x in ['/page/', '/tag/', '/categoria/', '/author/']):
                    continue
                
                # Filtros de TÃ­tulo
                if len(titulo) < 15 or any(x in titulo.lower() for x in ['leia mais', 'saiba mais', 'notÃ­cias', 'pÃ¡gina inicial']):
                    continue
                
                # Normaliza URL
                if not href.startswith('http'):
                    href = "https://www.ba.gov.br" + (href if href.startswith('/') else '/' + href)
                
                if href in links_vistos_ba:
                    continue
                links_vistos_ba.add(href)

                # Tenta extrair data
                data_publicacao = ''
                contexto = a.get_text(" ", strip=True)
                parent = a.parent
                if parent:
                    contexto += " " + parent.get_text(" ", strip=True)
                    for t in parent.find_all('time'):
                        if t.has_attr('datetime'):
                            contexto += " " + str(t['datetime'])
                    if parent.parent:
                        contexto += " " + parent.parent.get_text(" ", strip=True)
                        for t in parent.parent.find_all('time'):
                            if t.has_attr('datetime'):
                                contexto += " " + str(t['datetime'])

                data_publicacao = _extrair_data_ptbr(contexto) or _extrair_data_ptbr(href) or ''

                if not data_publicacao:
                    data_publicacao = extrair_data_da_pagina_noticia(href, headers=headers)

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{href}";"{href}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE CE (al.ce.gov.br) ---
        if "al.ce.gov.br" in url:
            items = soup.find_all('div', class_='noticias_item')
            if items:
                for item in items:
                    h3 = item.find('h3', class_='noticias_title')
                    if not h3: continue
                    
                    a_tag = h3.find_parent('a')
                    if not a_tag: continue
                    
                    titulo = h3.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    span_data = item.find('span', class_='noticias_data')
                    if span_data:
                        data_publicacao = span_data.get_text(strip=True)

                    if not link.startswith('http'):
                        link = "https://www.al.ce.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC AP (Portal AP) ---
        if "seed.portal.ap.gov.br" in url:
            container = soup.find('div', id='noticias')
            if container:
                chamadas = container.find_all('div', class_='chamada')
                for chamada in chamadas:
                    a_tag = chamada.find_parent('a')
                    if not a_tag: continue
                    
                    titulo = chamada.get_text(strip=True)
                    link = a_tag.get('href')
                    
                    data_publicacao = ''
                    div_data = a_tag.find('div', class_='data')
                    if div_data:
                        texto_data = div_data.get_text(strip=True).lower()
                        match = re.search(r'(\d{1,2})\s+([a-zÃ§]{3})\s+(\d{2})', texto_data)
                        if match:
                            dia, mes_abrev, ano_short = match.groups()
                            meses = {'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'}
                            if mes_abrev in meses:
                                data_publicacao = f"{dia.zfill(2)}/{meses[mes_abrev]}/20{ano_short}"

                    if not link.startswith('http'):
                        link = "https://seed.portal.ap.gov.br" + (link if link.startswith('/') else '/' + link)

                    if not data_publicacao:
                        contexto = a_tag.get_text(" ", strip=True)
                        data_publicacao = _extrair_data_ptbr(contexto) or _extrair_data_ptbr(link) or ''

                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)
                    
                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO CE (ceara.gov.br) ---
        if "ceara.gov.br" in url:
            # EstratÃ©gia: Baseada na estrutura "Todas as NotÃ­cias" (cc-post) fornecida
            posts = soup.find_all('div', class_='cc-post')
            
            # Se nÃ£o encontrar (ex: pÃ¡gina inicial), tenta fallback genÃ©rico de links
            if not posts:
                posts = soup.find_all('div', class_='td-module-container') # Fallback para tema Newspaper da home

            if posts:
                for post in posts:
                    # Busca TÃ­tulo e Link
                    a_tag = post.find('a', class_='cc-post-title') or post.find('h3', class_='entry-title').find('a') if post.find('h3', class_='entry-title') else post.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                

                    # Data
                    data_publicacao = ''
                    date_span = post.find('span', class_='cc-post-metas-date')
                    if date_span:
                        texto_data = date_span.get_text(strip=True).lower()
                        # Formato: 24 de fevereiro de 2026 - 13:53
                        match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                        if match:
                            if match.group(2) in MESES_PT:
                                data_publicacao = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"
                    
                    # Fallback de data pela URL se nÃ£o achou no span
                    if not data_publicacao:
                        match_url = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
                        if match_url:
                            data_publicacao = f"{match_url.group(3)}/{match_url.group(2)}/{match_url.group(1)}"

                    if not link.startswith('http'):
                        link = "https://www.ceara.gov.br" + (link if link.startswith('/') else '/' + link)

                    # Evita duplicatas na lista final
                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC DF (educacao.df.gov.br) ---
        if "educacao.df.gov.br" in url:
            view_content = soup.find('div', class_='view-content')
            if view_content:
                articles = view_content.find_all('article', class_='item')
                current_date = ''

                for article in articles:
                    classes = article.get('class', [])

                    if 'item-date' in classes and 'formatted' in classes:
                        span_date = article.find('span')
                        if span_date:
                            texto_data = span_date.get_text(strip=True).lower()
                            match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                            if match:
                                if match.group(2) in MESES_PT:
                                    current_date = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"
                        continue

                    if 'item-news' in classes:
                        h3 = article.find('h3')
                        if not h3:
                            continue
                        a_tag = h3.find('a')
                        if not a_tag:
                            continue

                        titulo = a_tag.get_text(strip=True)
                        link = a_tag['href']
                    else:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.educacao.df.gov.br" + (link if link.startswith('/') else '/' + link)

                    link_lower = link.lower()
                    titulo_lower = titulo.lower()
                    if (
                        '/documents/' in link_lower
                        or '/wp-content/' in link_lower
                        or link_lower.endswith(('.pdf', '.doc', '.docx'))
                        or 'governancaeducadf.se.df.gov.br' in link_lower
                        or 'portal-dados' in link_lower
                        or any(t in titulo_lower for t in ['guia prático', 'portal de governança', 'portal de governanca'])
                    ):
                        continue

                    data_publicacao = current_date or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(article.get_text(" ", strip=True)) or _extrair_data_ptbr(link) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias):
                        break
                if noticias:
                    return noticias

            # Layout atual: cards em linhas .row.align-items-center com .data-post e links /w/
            rows_df = soup.select('div.row.align-items-center')
            if rows_df:
                links_vistos_df = set()
                for row in rows_df:
                    anchors = row.find_all('a', href=True)
                    if not anchors:
                        continue

                    link = ''
                    titulo = ''
                    for a in anchors:
                        href = (a.get('href') or '').strip()
                        if not href:
                            continue
                        href_abs = href if href.startswith('http') else "https://www.educacao.df.gov.br" + (href if href.startswith('/') else '/' + href)
                        href_lower = href_abs.lower()
                        if (
                            '/w/' not in href_lower
                            or '/documents/' in href_lower
                            or '/web/' in href_lower
                            or href_lower.endswith(('.pdf', '.doc', '.docx'))
                            or 'governancaeducadf.se.df.gov.br' in href_lower
                            or 'portal-dados' in href_lower
                        ):
                            continue

                        texto_ancora = a.get_text(" ", strip=True)
                        if len(texto_ancora) >= 15:
                            link = href_abs
                            titulo = texto_ancora
                            break

                        if not link:
                            link = href_abs

                    if not link:
                        continue

                    if not titulo:
                        titulo_tag = row.select_one('h3 a, h2 a, h3, h2')
                        if titulo_tag:
                            titulo = titulo_tag.get_text(" ", strip=True)
                    if not titulo:
                        continue

                    data_publicacao = ''
                    data_tag = row.select_one('.data-post')
                    if data_tag:
                        data_publicacao = _extrair_data_ptbr(data_tag.get_text(" ", strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(row.get_text(" ", strip=True)) or _extrair_data_ptbr(link) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    if link in links_vistos_df:
                        continue
                    links_vistos_df.add(link)

                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE DF (cl.df.gov.br) ---
        if "cl.df.gov.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                # Filtra links que nÃ£o contÃªm '/-/' (padrÃ£o de notÃ­cias do Liferay neste portal)
                if "/-/" not in link:
                    continue
                
                titulo = a.get_text(strip=True)
                # Limpa data/hora do inÃ­cio do tÃ­tulo (ex: "24/02/2026 - 13h30TÃ­tulo...")
                titulo = re.sub(r'^\d{2}/\d{2}/\d{4}\s*-\s*\d{2}h\d{2}\s*', '', titulo)
                
                if len(titulo) < 15: continue

                data_publicacao = ''
                match = re.search(r'(\d{2})/(\d{2})/(\d{4})', a.get_text())
                if match:
                    data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://www.cl.df.gov.br" + (link if link.startswith('/') else '/' + link)

                link_lower = link.lower()
                if any(t in link_lower for t in ['/documents/', '.pdf', '.doc', '.docx']):
                    continue

                if not data_publicacao:
                    contexto = a.get_text(" ", strip=True)
                    if a.parent:
                        contexto += " " + a.parent.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(contexto) or _extrair_data_ptbr(link) or ''
                if not data_publicacao:
                    data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)
                
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO DF  ---
        if "agenciabrasilia.df.gov.br" in url:
            cards = soup.find_all('a', class_='card-result')
            if cards:
                for card in cards:
                    h3 = card.find('h3')
                    if not h3: continue
                    
                    titulo = h3.get_text(strip=True)
                    link = card['href']
                    
                    data_publicacao = ''
                    label_date = card.find('label')
                    if label_date:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', label_date.get_text(strip=True))
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://www.agenciabrasilia.df.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC ES (sedu.es.gov.br) ---
        if "sedu.es.gov.br" in url:
            articles = soup.find_all('article', class_='noticia')
            if articles:
                for article in articles:
                    h4 = article.find('h4', class_='title-list')
                    if not h4: continue
                    a_tag = h4.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    div_published = article.find('div', class_='published')
                    if div_published:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', div_published.get_text(strip=True))
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://sedu.es.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO ES (es.gov.br) ---
        if "es.gov.br" in url and "sedu.es.gov.br" not in url:
            articles = soup.find_all('article', class_='noticia')
            if articles:
                for article in articles:
                    h4 = article.find('h4', class_='title-list')
                    if not h4: continue
                    a_tag = h4.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    div_published = article.find('div', class_='published')
                    if div_published:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', div_published.get_text(strip=True))
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://www.es.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE ES (al.es.gov.br) ---
        if "al.es.gov.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                # Filtra apenas notÃ­cias reais e remove links externos (YouTube)
                if "/Noticia/" not in link or "youtube.com" in link:
                    continue
                
                titulo = a.get_text(strip=True)
                if not titulo:
                    child = a.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'])
                    if child: titulo = child.get_text(strip=True)
                
                if not titulo or len(titulo) < 15: continue

                if not link.startswith('http'):
                    link = "https://www.al.es.gov.br" + (link if link.startswith('/') else '/' + link)

                data_publicacao = ''
                # Tenta achar data no texto do elemento pai
                if a.parent:
                    contexto = a.parent.get_text(" ", strip=True)
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', contexto)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO GO (goias.gov.br) ---
        if "goias.gov.br" in url:
            articles = soup.find_all('article', class_='tease')
            if articles:
                for article in articles:
                    h2 = article.find('h2', class_='entry-title')
                    if not h2: continue
                    a_tag = h2.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']

                    if not link.startswith('http'):
                        link = "https://goias.gov.br" + (link if link.startswith('/') else '/' + link)
                    
                    data_publicacao = ''
                    entry_meta = article.find('div', class_='entry-meta')
                    if entry_meta:
                        data_publicacao = _extrair_data_ptbr(entry_meta.get_text(" ", strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(article.get_text(" ", strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(link) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE GO (portal.al.go.leg.br) ---
        if "portal.al.go.leg.br" in url:
            dias = soup.find_all('div', class_='noticias__dia')
            if dias:
                for dia in dias:
                    # Data estÃ¡ no atributo data-title ou no span
                    data_str = dia.get('data-title')
                    if not data_str:
                        span = dia.find('span')
                        if span: data_str = span.get_text(strip=True)
                    
                    data_publicacao = ''
                    if data_str:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', data_str)
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    itens = dia.find_all('a', class_='noticia')
                    for item in itens:
                        h5 = item.find('h5', class_='titulo')
                        if not h5: continue
                        
                        titulo = h5.get_text(strip=True)
                        link = item['href']
                        
                        if not link.startswith('http'):
                            link = "https://portal.al.go.leg.br" + (link if link.startswith('/') else '/' + link)

                        noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                        if limite_noticias_atingido(noticias): break
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE MS (al.ms.gov.br) ---
        if "al.ms.gov.br" in url:
            container = soup.find('div', id='news-container')
            lista = container.find('ul', class_='newslist') if container else None
            if lista:
                data_corrente = ''

                for elemento in lista.children:
                    if not getattr(elemento, 'name', None):
                        continue

                    if elemento.name == 'b':
                        data_corrente = _extrair_data_ptbr(elemento.get_text(" ", strip=True)) or ''
                        continue

                    if elemento.name != 'li':
                        continue

                    a_tag = elemento.find('a', class_='Titulo_noticia', href=True) or elemento.find('a', href=True)
                    if not a_tag:
                        continue

                    link = a_tag.get('href', '').strip()
                    if not link:
                        continue

                    titulo = a_tag.get('title') or a_tag.get_text(" ", strip=True)
                    titulo = re.sub(r'^\d{1,2}:\d{2}\s*-\s*', '', str(titulo or '').strip())

                    if not titulo or len(titulo) < 12:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.al.ms.gov.br" + (link if link.startswith('/') else '/' + link)

                    data_publicacao = data_corrente or _extrair_data_ptbr(elemento.get_text(" ", strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(link) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

            # Fallback: quando não há news-container no HTML inicial,
            # usa links de notícia e resolve data na matéria.
            links_ale_ms = soup.find_all('a', href=True)
            if links_ale_ms:
                for a_tag in links_ale_ms:
                    href = a_tag.get('href', '').strip()
                    if not href:
                        continue

                    href_lower = href.lower()
                    if '/noticias/' not in href_lower:
                        continue

                    titulo = a_tag.get('title') or a_tag.get_text(" ", strip=True)
                    titulo = re.sub(r'^\d{1,2}:\d{2}\s*-\s*', '', str(titulo or '').strip())
                    if not titulo or len(titulo) < 12:
                        continue

                    link = href
                    if not link.startswith('http'):
                        link = "https://al.ms.gov.br" + (link if link.startswith('/') else '/' + link)

                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    data_publicacao = ''
                    parent = a_tag.parent
                    if parent:
                        data_publicacao = _extrair_data_ptbr(parent.get_text(" ", strip=True)) or ''
                    if not data_publicacao and parent and parent.parent:
                        data_publicacao = _extrair_data_ptbr(parent.parent.get_text(" ", strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(link) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO MA (ma.gov.br) ---
        if "ma.gov.br" in url and "educacao.ma.gov.br" not in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                if "/noticia/" not in link: continue
                
                titulo = a.get_text(strip=True)
                if len(titulo) < 15: continue
                
                data_publicacao = ''
                
                if not link.startswith('http'):
                    link = "https://www.ma.gov.br" + (link if link.startswith('/') else '/' + link)
                
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC MG (educacao.mg.gov.br) ---
        if "educacao.mg.gov.br" in url:
            # Fonte mais estável: API REST do WordPress.
            try:
                api_url = "https://www.educacao.mg.gov.br/wp-json/wp/v2/posts?per_page=30&categories=5&_fields=link,date,title"
                resp_api = requests.get(api_url, headers=headers, timeout=30, verify=False)
                if resp_api.status_code == 200:
                    posts = resp_api.json() or []
                    if isinstance(posts, list):
                        links_vistos_mg = set()
                        for post in posts:
                            link = str(post.get('link') or '').strip()
                            if not link or link in links_vistos_mg:
                                continue

                            titulo_raw = ''
                            if isinstance(post.get('title'), dict):
                                titulo_raw = str(post.get('title', {}).get('rendered') or '').strip()
                            titulo = BeautifulSoup(titulo_raw, 'html.parser').get_text(' ', strip=True)
                            if len(titulo) < 15:
                                continue

                            data_publicacao = ''
                            data_iso = str(post.get('date') or '').strip()
                            if data_iso:
                                try:
                                    data_publicacao = datetime.strptime(data_iso[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                                except Exception:
                                    data_publicacao = ''

                            noticias.append([
                                data_publicacao,
                                titulo[:200],
                                f'=HYPERLINK("{link}";"{link}")',
                                origem,
                                datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                            ])
                            links_vistos_mg.add(link)

                            if limite_noticias_atingido(noticias):
                                break

                        if noticias:
                            return noticias
            except Exception:
                pass

            # Fallback: seletor HTML legado.
            articles = soup.find_all('article', class_='news')
            if articles:
                for article in articles:
                    a_tag = article.find('a', class_='news__infos__link')
                    if not a_tag: continue
                    
                    link = a_tag['href']
                    
                    header = a_tag.find('header', class_='news__infos__header--title')
                    if not header: continue
                    titulo = header.get_text(strip=True)
                    
                    data_publicacao = ''
                    div_date = article.find('div', class_='news__infos--date')
                    if div_date:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', div_date.get_text(strip=True))
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://www.educacao.mg.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO MG (agenciaminas.mg.gov.br) ---
        if "agenciaminas.mg.gov.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                
                # Filtra links de arquivo e outros indesejados
                if "2005-2015" in link or "2015-2018" in link or "arquivo" in link:
                    continue
                
                # Filtra apenas links de notÃ­cia
                if "/noticia/" not in link:
                    continue

                full_text = a.get_text(" ", strip=True)
                
                # Regex para capturar data e limpar tÃ­tulo
                # Ex: "Ter 24 fevereiro15:00atualizado em 15:10Governo de Minas..."
                match = re.search(r'^[a-zA-Z]{3}\s+(\d{1,2})\s+([a-zÃ§]+)\s*(\d{2}:\d{2})', full_text, re.IGNORECASE)
                
                titulo = full_text
                data_publicacao = ''

                if match:
                    dia = match.group(1)
                    mes_txt = match.group(2).lower()
                    
                    # Limpa o tÃ­tulo removendo o prefixo de data/hora
                    titulo = re.sub(r'^[a-zA-Z]{3}\s+\d{1,2}\s+[a-zÃ§]+\s*\d{2}:\d{2}(?:\s*atualizado em \d{2}:\d{2})?', '', full_text, flags=re.IGNORECASE).strip()
                    
                    if mes_txt in MESES_PT:
                        ano = datetime.now().year
                        data_publicacao = f"{dia.zfill(2)}/{MESES_PT[mes_txt]}/{ano}"
                
                if len(titulo) < 15: continue

                if not link.startswith('http'):
                    link = "https://www.agenciaminas.mg.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC MS (sed.ms.gov.br) ---
        if "sed.ms.gov.br" in url:
            cards = soup.find_all('div', class_='post-item')
            if cards:
                for card in cards:
                    h2 = card.find('h2', class_='post-title')
                    if not h2: continue
                    a_tag = h2.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    p_date = card.find('p', class_='post-date')
                    if p_date:
                        texto_data = p_date.get_text(strip=True).lower()
                        match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                        if match:
                            if match.group(2) in MESES_PT:
                                data_publicacao = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://www.sed.ms.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÓGICA ESPECÍFICA: SEDUC MT (www3.seduc.mt.gov.br /noticias) ---
        if "seduc.mt.gov.br" in url:
            itens = soup.find_all('div', class_='news-item')
            if itens:
                links_vistos_mt = set()
                for item in itens:
                    a_tag = item.find('a', class_='title')
                    if not a_tag:
                        h3 = item.find('h3')
                        if h3:
                            a_tag = h3.find('a', href=True)
                    if not a_tag:
                        continue

                    titulo = a_tag.get_text(" ", strip=True)
                    link = a_tag.get('href', '').strip()
                    if not titulo or not link:
                        continue

                    if not link.startswith('http'):
                        link = "https://www3.seduc.mt.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_mt:
                        continue
                    links_vistos_mt.add(link)

                    data_publicacao = ''
                    p_data = item.find('p')
                    if p_data:
                        texto_data = p_data.get_text(" ", strip=True)
                        data_publicacao = _extrair_data_ptbr(texto_data) or ''

                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(link) or ''

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])
                    if limite_noticias_atingido(noticias):
                        break
                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE MT (al.mt.gov.br) ---
        if "al.mt.gov.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                
                # Filtra apenas links de detalhe de notÃ­cia (contÃ©m /midia/texto/ + ID)
                if "/midia/texto/" not in link:
                    continue
                
                # Ignora a prÃ³pria pÃ¡gina de listagem e paginaÃ§Ã£o
                if link.endswith("/midia/texto") or "pagina" in link:
                    continue

                titulo = a.get_text(strip=True)
                if not titulo:
                    child = a.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span'])
                    if child: titulo = child.get_text(strip=True)
                
                if not titulo or len(titulo) < 20: continue

                data_publicacao = ''
                if a.parent:
                    contexto = a.parent.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(contexto) or ''

                if not data_publicacao:
                    data_publicacao = _extrair_data_ptbr(a.get_text(" ", strip=True)) or ''

                if not link.startswith('http'):
                    link = "https://www.al.mt.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE PA (alepa.pa.gov.br) ---
        if "alepa.pa.gov.br" in url:
            cards = soup.find_all('div', class_='card-container')
            if cards:
                for card in cards:
                    h3 = card.find('h3', class_='card-title')
                    if not h3: continue
                    
                    a_tag = h3.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    

                    data_publicacao = ''
                    span_date = card.find('span', class_='card-datetime')
                    if span_date:
                        data_publicacao = span_date.get_text(strip=True).split('|')[0].strip()

                    link = url
                    if a_tag.has_attr('onclick'):
                        match = re.search(r'onNoticiaClick\((\d+),\s*["\']([^"\']+)["\']\)', a_tag['onclick'])
                        if match:
                            link = f"https://www.alepa.pa.gov.br/Noticia/{match.group(1)}/{match.group(2)}"

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO PA (AgÃªncia ParÃ¡) ---
        if "agenciapara.com.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                # Filtra apenas notÃ­cias reais, ignorando publicaÃ§Ãµes e outros
                if "/noticia/" not in link: continue
                
                # Tenta extrair o tÃ­tulo separando elementos filhos (evita "CATEGORIATitulo")
                # e remove espaÃ§os extras
                full_text = a.get_text(" ", strip=True)
                
                # Remove data/hora do final do tÃ­tulo se houver (ex: ... 25/02/2026 08h00)
                titulo = re.sub(r'\d{2}/\d{2}/\d{4}\s*\d{2}h\d{2}.*$', '', full_text).strip()
                
                if len(titulo) < 15: continue

                data_publicacao = ''
                match = re.search(r'(\d{2})/(\d{2})/(\d{4})', full_text)
                if match:
                    data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://agenciapara.com.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC PB (paraiba.pb.gov.br) ---
        if "paraiba.pb.gov.br/diretas/secretaria-da-educacao" in url:
            # Busca especificamente pelos itens de listagem de notÃ­cias do portal da PB
            cards = soup.find_all('article', class_='tileItem')
            if not cards:
                # Fallback para outra classe comum no sistema Plone/Portal PadrÃ£o
                cards = soup.find_all('div', class_='tileItem')

            if cards:
                for card in cards:
                    # 1. TÃ­tulo e Link
                    a_tag = card.find('a', class_='summary url') or card.find('h2').find('a') if card.find('h2') else card.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    # 2. Data (Geralmente em um span com a classe 'tile-info')
                    data_publicacao = ''
                    info_span = card.find('span', class_='tile-info')
                    if info_span:
                        # O texto costuma ser: "25/02/2026 10h30"
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', info_span.get_text())
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    if not link.startswith('http'):
                        link = "https://paraiba.pb.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE PB (al.pb.leg.br) ---
        if "al.pb.leg.br" in url:
            # Foca especificamente no container de itens de notÃ­cia para evitar o menu lateral
            cards = soup.find_all('div', class_='page-noticias-item')
            if cards:
                for card in cards:
                    # 1. TÃ­tulo e Link
                    # O tÃ­tulo estÃ¡ dentro de um h2 com a classe noticias-item-title
                    h2_tag = card.find('h2', class_='noticias-item-title')
                    if not h2_tag: continue
                    a_tag = h2_tag.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    # 2. Data
                    # A data estÃ¡ dentro de uma div noticias-item-date > span
                    data_publicacao = ''
                    date_div = card.find('div', class_='noticias-item-date')
                    if date_div:
                        span_date = date_div.find('span')
                        if span_date:
                            texto_data = span_date.get_text(strip=True)
                            match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_data)
                            if match:
                                data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                    # ValidaÃ§Ã£o de link
                    if not link.startswith('http'):
                        link = "https://www.al.pb.leg.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([
                        data_publicacao, 
                        titulo[:200], 
                        f'=HYPERLINK("{link}";"{link}")', 
                        origem, 
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias
        # --- LÃ“GICA ESPECÃFICA: GOVERNO PB (Portal PB) ---
        if "paraiba.pb.gov.br" in url:
            # Busca os blocos de notÃ­cia especÃ­ficos do Plone/Tile
            articles = soup.find_all('article', class_='tileItem')
            if articles:
                for article in articles:
                    # 1. TÃ­tulo e Link
                    h2 = article.find('h2', class_='tileHeadline')
                    if not h2: continue
                    a_tag = h2.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    # 2. Data (Busca o Ã­cone de calendÃ¡rio 'icon-day')
                    data_publicacao = ''
                    # Tenta encontrar o span que contÃ©m a data (geralmente o que tem a classe icon-day)
                    date_spans = article.find_all('span', class_='summary-view-icon')
                    for span in date_spans:
                        if span.find('i', class_='icon-day'):
                            texto_data = span.get_text(strip=True)
                            match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_data)
                            if match:
                                data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                                break

                    if not link.startswith('http'):
                        link = "https://paraiba.pb.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC PE (portal.educacao.pe.gov.br) ---
        if "portal.educacao.pe.gov.br" in url:
            items = soup.find_all('div', class_='stk-block-posts__item')
            if items:
                for item in items:
                    h3 = item.find('h3', class_='stk-block-posts__title')
                    if not h3: continue
                    a_tag = h3.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    time_tag = item.find('time')
                    if time_tag and time_tag.has_attr('datetime'):
                        try:
                            data_publicacao = datetime.strptime(time_tag['datetime'][:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                        except: pass

                    if not link.startswith('http'):
                        link = "https://portal.educacao.pe.gov.br" + (link if link.startswith('/') else '/' + link)

                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE PE (alepe.pe.gov.br) ---
        if "alepe.pe.gov.br" in url:
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                
                # Filtra links que nÃ£o possuem padrÃ£o de data /YYYY/MM/DD/ (exclui institucionais e home)
                if not re.search(r'/\d{4}/\d{2}/\d{2}/', link):
                    continue
                
                # Filtra itens especÃ­ficos que nÃ£o sÃ£o notÃ­cias (ex: Manual de Identidade)
                if "manual-de-identidade" in link:
                    continue
                
                titulo = a.get_text(strip=True)
                # Remove data do inÃ­cio do tÃ­tulo se houver (ex: "24/02/2026TÃ­tulo")
                titulo = re.sub(r'^\d{2}/\d{2}/\d{4}', '', titulo).strip()
                
                if len(titulo) < 15: continue

                # Data da URL
                data_publicacao = ''
                match_url = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', link)
                if match_url:
                    data_publicacao = f"{match_url.group(3)}/{match_url.group(2)}/{match_url.group(1)}"

                if not link.startswith('http'):
                    link = "https://www.alepe.pe.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÓGICA ESPECÍFICA: GOVERNO PI (pi.gov.br) ---
        if "pi.gov.br" in url and "seduc.pi.gov.br" not in url:
            marcadores_data = soup.find_all(string=re.compile(r'Publicando\s+em\s*:', re.IGNORECASE))
            if marcadores_data:
                links_vistos_pi = set()
                for marcador in marcadores_data:
                    container = marcador.find_parent('div', class_='e-con-inner') or marcador.find_parent('div')
                    if not container:
                        continue

                    a_titulo = (
                        container.select_one('h1 a[href]')
                        or container.select_one('h2 a[href]')
                        or container.select_one('h3 a[href]')
                        or container.find('a', href=True)
                    )
                    if not a_titulo:
                        continue

                    link = a_titulo.get('href', '').strip()
                    titulo = a_titulo.get_text(' ', strip=True)
                    if not link or not titulo or len(titulo) < 12:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.pi.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_pi:
                        continue
                    links_vistos_pi.add(link)

                    data_publicacao = _extrair_data_ptbr(str(marcador)) or ''
                    if not data_publicacao:
                        data_publicacao = _extrair_data_ptbr(container.get_text(' ', strip=True)) or ''
                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC PI (seduc.pi.gov.br) ---
        if "seduc.pi.gov.br" in url:
            # EstratÃ©gia: Buscar elementos que contenham data (DD/MM/YYYY), pois menus nÃ£o tÃªm data.
            datas = soup.find_all(string=re.compile(r'\d{2}/\d{2}/\d{4}'))
            
            for data_node in datas:
                # Encontra o container do item de notÃ­cia (subindo na hierarquia)
                container = data_node.find_parent('div', class_='caption') or \
                            data_node.find_parent('div', class_='thumbnail') or \
                            data_node.find_parent('div') or \
                            data_node.find_parent('li')
                
                if not container: continue
                
                # Busca o link dentro desse container ou verifica se o prÃ³prio container estÃ¡ num link
                a_tag = container.find('a', href=True)
                if not a_tag:
                    a_tag = data_node.find_parent('a', href=True)
                
                if not a_tag: continue
                
                link = a_tag['href']
                if "pagina" in link or "javascript" in link: continue
                
                titulo = a_tag.get_text(strip=True)
                # Tenta melhorar o tÃ­tulo buscando um H3/H4 prÃ³ximo se o link for genÃ©rico
                h_tag = container.find(['h3', 'h4', 'h5'])
                if h_tag: titulo = h_tag.get_text(strip=True)
                
                if len(titulo) < 15: continue

                data_publicacao = ''
                match = re.search(r'(\d{2})/(\d{2})/(\d{4})', data_node)
                if match:
                    data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://seduc.pi.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC RJ (seeduc.rj.gov.br) ---
        if "seeduc.rj.gov.br" in url:
            # Google Sites com Accordion/Collapsible
            # Procura botÃµes de "Abrir"
            botoes = soup.find_all('div', role='button', attrs={'aria-label': True})
            for botao in botoes:
                aria_label = botao['aria-label']
                if not aria_label.startswith("Abrir "):
                    continue
                
                titulo = aria_label.replace("Abrir ", "").strip()
                # Remove quebras de linha se houver
                titulo = titulo.replace("\n", "").strip()
                
                if len(titulo) < 10: continue
                if "barra de pesquisa" in titulo.lower(): continue

                # Tenta encontrar o ID do container pai para criar um link Ã¢ncora
                container = botao.find_parent('div', id=True)
                link = url
                if container:
                    link = f"{url}#{container['id']}"

                # A página do Google Sites frequentemente não expõe data por notícia no HTML.
                # Tenta contexto local e, se não houver, usa a data do header HTTP da listagem.
                data_publicacao = ''
                try:
                    contexto_local = ""
                    bloco = botao.find_parent('div', class_='JNdkSc') or botao.find_parent('div')
                    if bloco:
                        contexto_local = bloco.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(contexto_local) or ''
                except Exception:
                    data_publicacao = ''

                if not data_publicacao:
                    data_publicacao = data_referencia_http or data_hoje_br()

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC RO (rondonia.ro.gov.br) ---
        if "rondonia.ro.gov.br" in url:
            # Busca por links de notÃ­cia com class="bolder"
            links = soup.find_all('a', class_='bolder', href=True)
            for a in links:
                link = a['href']
                
                titulo = a.get_text(strip=True)
                if len(titulo) < 15:
                    continue
                
                # Remove Ã­cones do tÃ­tulo se houver
                titulo = re.sub(r'<i[^>]*>.*?</i>', '', str(a)).strip()
                titulo = BeautifulSoup(titulo, 'html.parser').get_text(strip=True)
                
                data_publicacao = ''
                # Tenta extrair data do contexto do card (ex.: "26 de fevereiro de 2026").
                container = a.find_parent('article') or a.find_parent('div')
                if container:
                    contexto = container.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(contexto) or ''

                # Fallbacks para casos sem data no card.
                if not data_publicacao:
                    data_publicacao = _extrair_data_ptbr(link) or ''

                if not data_publicacao:
                    try:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)
                    except Exception:
                        data_publicacao = ''
                
                if not link.startswith('http'):
                    link = "https://rondonia.ro.gov.br" + link
                
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC RR (educacao.rr.gov.br) ---
        if "educacao.rr.gov.br" in url:
            posts = soup.find_all('div', class_='post-content ast-grid-common-col')
            if posts:
                for post in posts:
                    h2 = post.find('h2', class_='entry-title')
                    if not h2: continue
                    a_tag = h2.find('a')
                    if not a_tag: continue
                    
                    titulo = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    data_publicacao = ''
                    # Try to find date in entry-meta
                    meta = post.find('div', class_='entry-meta')
                    if meta:
                        time_tag = meta.find('time')
                        if time_tag and time_tag.has_attr('datetime'):
                            try:
                                data_publicacao = datetime.strptime(time_tag['datetime'][:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                            except: pass

                    # Fallback: alguns cards não trazem <time>; tenta extrair do texto do card.
                    if not data_publicacao:
                        texto_card = post.get_text(" ", strip=True)
                        data_publicacao = _extrair_data_ptbr(texto_card) or ''

                    # Último recurso para não deixar RR sem data no fluxo diário.
                    if not data_publicacao:
                        data_publicacao = data_hoje_br()
                    
                    if not link.startswith('http'):
                        link = "https://educacao.rr.gov.br" + link
                    
                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue
                    
                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO RR (portal.rr.gov.br) ---
        if "portal.rr.gov.br" in url:
            items = soup.find_all('div', class_='jet-listing-grid__item')
            if items:
                for item in items:
                    overlay = item.find('div', class_='jet-engine-listing-overlay-wrap')
                    if not overlay: continue
                    link = overlay.get('data-url')
                    if not link: continue
                    contents = item.find_all('div', class_='jet-listing-dynamic-field__content')
                    if len(contents) < 3: continue
                    titulo = contents[2].get_text(strip=True)
                    data_str = contents[1].get_text(strip=True)
                    data_publicacao = ''
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', data_str)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                    if len(titulo) < 15: continue
                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue
                    noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE RJ (alerj.rj.gov.br) ---
        if "alerj.rj.gov.br" in url:
            # Busca direta por links de notÃ­cia
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                if "/Visualizar/Noticia/" not in link: continue
                
                titulo = a.get_text(strip=True)
                if not titulo:
                    # Tenta pegar do H1 pai se o link estiver dentro
                    h1 = a.find_parent('h1')
                    if h1: titulo = h1.get_text(strip=True)
                
                if not titulo: continue

                # Data
                data_publicacao = ''
                # Tenta encontrar a data no container da notÃ­cia
                # Estrutura: div.conteudo > div.subtitulo (25.02.2026 - 12:25)
                container = a.find_parent('div', class_='conteudo')
                if container:
                    subtitulo = container.find('div', class_='subtitulo')
                    if subtitulo:
                        texto_data = subtitulo.get_text(strip=True)
                        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', texto_data)
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://www.alerj.rj.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias
    # --- LÃ“GICA ESPECÃFICA: GOVERNO RJ (rj.gov.br) ---
        if "rj.gov.br" in url:
            itens_filtrados = []
            for div in soup.find_all('div'):
                texto_div = div.get_text(" ", strip=True)
                if not texto_div:
                    continue
                if 'publicado' not in texto_div.lower():
                    continue
                if not re.search(r'publicado\s+\d{1,2}\s+[a-zç]+,?\s+\d{4}', texto_div, re.IGNORECASE):
                    continue
                itens_filtrados.append(div)

            vistos_titulos = set()

            for item in itens_filtrados:
                p_tags = item.find_all('p')
                if not p_tags:
                    continue

                titulo = ''
                titulo_tag = item.find('p', class_=lambda x: x and 'portal1874' in str(x))
                if titulo_tag:
                    titulo = titulo_tag.get_text(" ", strip=True)

                if not titulo:
                    candidatos_titulo = []
                    for p in p_tags:
                        text = p.get_text(" ", strip=True)
                        text_lower = text.lower()
                        if not text:
                            continue
                        if 'publicado' in text_lower or 'atualizado' in text_lower or 'edit_calendar' in text_lower:
                            continue
                        if len(text) < 25:
                            continue
                        candidatos_titulo.append(text)
                    if candidatos_titulo:
                        titulo = candidatos_titulo[0]

                if len(titulo) < 20:
                    continue

                titulo_key = re.sub(r'\s+', ' ', titulo.strip().lower())
                if titulo_key in vistos_titulos:
                    continue

                data_publicacao = ''
                data_tag = item.find('p', class_=lambda x: x and 'portal1877' in str(x))
                if not data_tag:
                    for p in p_tags:
                        text = p.get_text(" ", strip=True)
                        if 'publicado' in text.lower():
                            data_tag = p
                            break
                if data_tag:
                    texto_data = data_tag.get_text(" ", strip=True)
                    data_publicacao = _extrair_data_ptbr(texto_data) or ''

                link = ''
                link_tag = item.find('a', href=True)
                if not link_tag and item.parent:
                    link_tag = item.parent.find('a', href=True)
                if link_tag:
                    link = str(link_tag.get('href') or '').strip()
                    if link and not link.startswith('http'):
                        link = "https://www.rj.gov.br" + (link if link.startswith('/') else '/' + link)

                if not link:
                    slug = re.sub(r'[^a-z0-9]+', '-', _normalizar_texto_data(titulo)).strip('-')
                    if not slug:
                        slug = str(abs(hash(titulo_key)))
                    link = f"{url}#{slug}"

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue

                noticias.append([
                    data_publicacao,
                    titulo[:200],
                    f'=HYPERLINK("{link}";"{link}")',
                    origem,
                    datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                ])
                vistos_titulos.add(titulo_key)

                if limite_noticias_atingido(noticias):
                    break

            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO RN (rn.gov.br) ---
        if "rn.gov.br" in url:
            # Busca por containers de notÃ­cias (div com class="list-news border-0 border-bottom")
            itens = soup.find_all('div', class_='list-news border-0 border-bottom')
            
            for item in itens:
                # Captura de TÃ­tulo e Link: h4 > a
                h4_tag = item.find('h4')
                if h4_tag:
                    a_tag = h4_tag.find('a', href=True)
                    if a_tag:
                        titulo = a_tag.get_text(strip=True)
                        link = a_tag['href']
                        if not link.startswith('http'):
                            link = "https://www.rn.gov.br" + link
                    else:
                        continue
                else:
                    continue
                
                # Filtro de qualidade
                if len(titulo) < 15 or any(x in titulo.lower() for x in ['leia mais', 'ver todas']):
                    continue
                
                # ExtraÃ§Ã£o de Data: p com class="small"
                data_publicacao = ''
                data_tag = item.find('p', class_='small')
                if data_tag:
                    texto_data = data_tag.get_text(strip=True)
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_data)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                
                # Evita duplicatas
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                
                if limite_noticias_atingido(noticias): break
            
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO SE (se.gov.br) ---
        if "se.gov.br" in url:
            links_vistos_se = set()
            blocos_texto = soup.select('div.col-md-8')

            if blocos_texto:
                for bloco in blocos_texto:
                    a_tag = bloco.find('a', href=True)
                    if not a_tag:
                        continue

                    link = a_tag.get('href', '').strip()
                    if not link or '/agencia/noticias/' not in link:
                        continue

                    titulos = [
                        div.get_text(" ", strip=True)
                        for div in bloco.find_all('div', class_='titulo')
                        if div.get_text(" ", strip=True)
                    ]
                    titulo = max(titulos, key=len) if titulos else ""

                    if not titulo or len(titulo) < 15:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.se.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_se:
                        continue
                    links_vistos_se.add(link)

                    data_publicacao = ''
                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])

                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC SP (educacao.sp.gov.br) ---
        if "educacao.sp.gov.br" in url:
            links_vistos_sp = set()
            artigos = soup.select('section.custom-col-lg-8 article[id^="post-"]')
            if not artigos:
                artigos = soup.find_all('article', id=re.compile(r'^post-'))

            if artigos:
                for artigo in artigos:
                    a_tag = artigo.select_one('h2.title a[href]') or artigo.find('a', href=True)
                    if not a_tag:
                        continue

                    link = a_tag.get('href', '').strip()
                    titulo = a_tag.get_text(" ", strip=True)

                    if not link or len(titulo) < 15:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.educacao.sp.gov.br" + (link if link.startswith('/') else '/' + link)

                    link_lower = link.lower()
                    if (
                        "/noticias/" in link_lower
                        or link_lower.endswith('/noticia/')
                        or link_lower.endswith('/destaque-home/')
                    ):
                        continue

                    if link in links_vistos_sp:
                        continue
                    links_vistos_sp.add(link)

                    data_publicacao = ''
                    span_data = artigo.find('span', class_='date')
                    if span_data:
                        match_data = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', span_data.get_text(" ", strip=True))
                        if match_data:
                            data_publicacao = f"{match_data.group(1)}/{match_data.group(2)}/{match_data.group(3)}"

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])

                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC PA (seduc.pa.gov.br) ---
        if "seduc.pa.gov.br" in url:
            itens = soup.find_all('div', class_='col-lg-12 col-md-12 margintop col-sem-margem')
            
            for item in itens:
                a_tag = item.find('a', href=True)
                if not a_tag: continue
                
                link = a_tag['href']
                
                titulo_tag = a_tag.find('h4', class_='margintop')
                if titulo_tag:
                    titulo = titulo_tag.get_text(strip=True)
                else:
                    titulo = a_tag.get_text(strip=True)
                
                data_tag = a_tag.find('div', class_='item_busca_data')
                data_publicacao = ''
                if data_tag:
                    texto_data = data_tag.get_text(strip=True)
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_data)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                
                # NormalizaÃ§Ã£o do Link
                if not link.startswith('http'):
                    link = "https://www.seduc.pa.gov.br" + link
                
                # Filtro de qualidade
                if len(titulo) < 15 or any(x in titulo.lower() for x in ['leia mais', 'ver todas']):
                    continue
                
                # Evita duplicatas
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                
                if limite_noticias_atingido(noticias): break
            
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO BA (ba.gov.br) ---
        if "ba.gov.br" in url:
            itens = soup.find_all('a', class_='item-not-list')
            
            for item in itens:
                link = item.get('href')
                if not link: continue
                
                titulo_tag = item.find('h3')
                if titulo_tag:
                    titulo = titulo_tag.get_text(strip=True)
                else:
                    titulo = item.get_text(strip=True)[:200]
                
                # Filtro de qualidade
                if len(titulo) < 15 or any(x in titulo.lower() for x in ['leia mais', 'ver todas']):
                    continue
                
                data_publicacao = ''
                
                # NormalizaÃ§Ã£o do Link
                if not link.startswith('http'):
                    link = "https://www.ba.gov.br" + link
                
                # Evita duplicatas
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                
                if limite_noticias_atingido(noticias): break
            
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC PR (educacao.pr.gov.br) ---
        if "educacao.pr.gov.br" in url:
            # 1. Tentativa: Estrutura de View com artigos e datas intercaladas (Drupal)
            view_content = soup.find('div', class_='view-content')
            if view_content:
                articles = view_content.find_all('article', class_='item')
                current_date = datetime.now().strftime('%d/%m/%Y')
                
                for article in articles:
                    classes = article.get('class', [])
                    
                    # Atualiza data se encontrar o divisor (ex: "24 de Fevereiro de 2026")
                    if 'item-date' in classes and 'formatted' in classes:
                        span_date = article.find('span')
                        if span_date:
                            texto_data = span_date.get_text(strip=True).lower()
                            match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                            if match:
                                if match.group(2) in MESES_PT:
                                    current_date = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"
                        continue

                    # Captura notÃ­cia
                    if 'item-news' in classes:
                        h3 = article.find('h3')
                        if not h3: continue
                        a_tag = h3.find('a')
                        if not a_tag: continue
                        
                        titulo = a_tag.get_text(strip=True)
                        link = a_tag['href']
                        
                        if not link.startswith('http'):
                            link = "https://www.educacao.pr.gov.br" + (link if link.startswith('/') else '/' + link)

                        if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                            continue

                        noticias.append([current_date, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                        if limite_noticias_atingido(noticias): break
                if noticias: return noticias

            conteudo = soup.find('div', id='conteudo') or soup
            links = conteudo.find_all('a', href=True)
            for a in links:
                link = a['href']
                # Filtra links que contÃªm /Noticia/ (padrÃ£o do site)
                if "/Noticia/" not in link: continue
                
                titulo = a.get_text(strip=True)
                if len(titulo) < 20: continue
                
                data_publicacao = ''
                container = a.find_parent('div') or a.parent
                if container:
                    texto = container.get_text(" ", strip=True)
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://www.educacao.pr.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

            # 2. Tentativa: Busca direta por links de notÃ­cia (Visualizar/Noticia)
            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                if "/Visualizar/Noticia" not in link: continue
                
                titulo = a.get_text(strip=True)
                if not titulo:
                    h_tag = a.find(['h1', 'h2', 'h3'])
                    if h_tag: titulo = h_tag.get_text(strip=True)
                
                if not titulo: continue

                data_publicacao = ''
                # Tenta achar data no container pai
                container = a.find_parent('div')
                if container:
                    texto_container = container.get_text(" ", strip=True)
                    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', texto_container)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://www.alerj.rj.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            
            return noticias

        # --- LÃ“GICA ESPECÃFICA: GOVERNO PR (parana.pr.gov.br) ---
        if "parana.pr.gov.br" in url:
            items_pr = soup.select('article.item.item-news')
            if items_pr:
                links_vistos_pr = set()
                for item in items_pr:
                    a_tag = item.select_one('h3 a[href]') or item.find('a', href=True)
                    if not a_tag:
                        continue

                    link = a_tag.get('href', '').strip()
                    if not link or '/Noticia/' not in link:
                        continue

                    titulo = a_tag.get_text(" ", strip=True)
                    if not titulo or len(titulo) < 12:
                        continue

                    if not link.startswith('http'):
                        link = "https://www.parana.pr.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_pr:
                        continue
                    links_vistos_pr.add(link)

                    data_publicacao = ''
                    texto_item = item.get_text(" ", strip=True)
                    match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_item)
                    if match_data:
                        data_publicacao = f"{match_data.group(1)}/{match_data.group(2)}/{match_data.group(3)}"

                    if not data_publicacao:
                        time_tag = item.find('time')
                        if time_tag:
                            hora_txt = time_tag.get_text(" ", strip=True)
                            if re.match(r'^\d{1,2}:\d{2}$', hora_txt):
                                data_publicacao = datetime.now().strftime('%d/%m/%Y')

                    if not data_publicacao:
                        data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])
                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

            links = soup.find_all('a', href=True)
            for a in links:
                link = a['href']
                # Filtra links que contÃªm /Noticia/ (padrÃ£o Celepar/PR)
                if "/Noticia/" not in link: continue
                
                titulo = a.get_text(strip=True)
                if len(titulo) < 15:
                    h_tag = a.find(['h3', 'h4', 'h5'])
                    if h_tag: titulo = h_tag.get_text(strip=True)
                    else: continue
                
                data_publicacao = ''
                container = a.find_parent('div') or a.parent
                if container:
                    texto = container.get_text(" ", strip=True)
                    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto)
                    if match:
                        data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not link.startswith('http'):
                    link = "https://www.parana.pr.gov.br" + (link if link.startswith('/') else '/' + link)

                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias): continue

                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE PR (assembleia.pr.leg.br) ---
        if "assembleia.pr.leg.br" in url:
            # O site agrupa notÃ­cias em seÃ§Ãµes de data (news-date-section)
            secoes_data = soup.find_all('div', class_='news-date-section')
            if secoes_data:
                for secao in secoes_data:
                    # Extrai a data do cabeÃ§alho da seÃ§Ã£o (ex: "25 de Fevereiro de 2026")
                    h2_data = secao.find('h2', class_='news-date-title')
                    data_secao = datetime.now().strftime('%d/%m/%Y')
                    if h2_data:
                        texto_data = h2_data.get_text(strip=True).lower()
                        match = re.search(r'(\d{1,2})\s+de\s+([a-zÃ§]+)\s+de\s+(\d{4})', texto_data)
                        if match:
                            if match.group(2) in MESES_PT:
                                data_secao = f"{match.group(1).zfill(2)}/{MESES_PT[match.group(2)]}/{match.group(3)}"

                    # Busca cada card de notÃ­cia dentro desta seÃ§Ã£o
                    cards = secao.find_all('div', class_='news-card')
                    for card in cards:
                        a_tag = card.find('a', class_='news-card-link')
                        if not a_tag: continue
                        
                        link = a_tag['href']
                        h3_titulo = card.find('h3', class_='news-card-title')
                        titulo = h3_titulo.get_text(strip=True) if h3_titulo else a_tag.get('title', 'Sem tÃ­tulo')

                        if not link.startswith('http'):
                            link = "https://www.assembleia.pr.leg.br" + (link if link.startswith('/') else '/' + link)

                        noticias.append([
                            data_secao, 
                            titulo[:200], 
                            f'=HYPERLINK("{link}";"{link}")', 
                            origem, 
                            datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                        ])
                        
                        if limite_noticias_atingido(noticias): break
                    if limite_noticias_atingido(noticias): break
                if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: ALE RR (al.rr.leg.br) ---
        if "al.rr.leg.br" in url:
            links = soup.find_all('a', class_='elementor-post__thumbnail__link', href=True)
            for a in links:
                link = a['href']
                # Find title in the post
                post = a.find_parent('article') or a.find_parent('div', class_='elementor-post')
                titulo = ""
                if post:
                    title_tag = post.find('h3', class_='elementor-post__title') or post.find('h2') or post.find('h1')
                    if title_tag:
                        titulo = title_tag.get_text(strip=True)
                if len(titulo) < 10: continue

                data_publicacao = ''
                if post:
                    data_publicacao = _extrair_data_ptbr(post.get_text(" ", strip=True)) or ''

                if not data_publicacao:
                    data_publicacao = _extrair_data_ptbr(link) or ''

                if not data_publicacao:
                    data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)

                if not link.startswith('http'):
                    link = "https://al.rr.leg.br" + link
                if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                    continue
                noticias.append([data_publicacao, titulo[:200], f'=HYPERLINK("{link}";"{link}")', origem, datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
                if limite_noticias_atingido(noticias): break
            if noticias: return noticias

        # --- LÃ“GICA ESPECÃFICA: RS (SEDUC, ALE e GOVERNO RS / Matriz) ---
        if "educacao.rs.gov.br" in url or "al.rs.gov.br" in url or "estado.rs.gov.br" in url:
            base_rs = "/".join(url.split("/")[:3])
            itens_rs = []
            if "educacao.rs.gov.br" in url or "estado.rs.gov.br" in url:
                seletores_rs = [
                    'section.defaultpagedlist div.matriz-ui-pagedlist-body article.conteudo-lista__item',
                    'div.matriz-ui-pagedlist-body article.conteudo-lista__item',
                    'section.conteudo-lista article.conteudo-lista__item',
                    'article.artigo__pagina__listanoticia--semcolunalateral div.matriz-ui-pagedlist-body article.conteudo-lista__item'
                ]
            else:
                seletores_rs = [
                    'div.matriz-ui-pagedlist-body article.conteudo-lista__item',
                    'section.conteudo-lista article.conteudo-lista__item',
                    'section.lista-publicacoes-imagem li.media',
                    'ul.media-list li.media',
                    'article.media'
                ]
            for seletor in seletores_rs:
                for item in soup.select(seletor):
                    if item not in itens_rs:
                        itens_rs.append(item)

            if itens_rs:
                for item in itens_rs:
                    titulo_tag = (
                        item.select_one('h2.conteudo-lista__item__titulo a[href]')
                        or item.select_one('h3.media-heading a[href]')
                        or item.select_one('h2 a[href]')
                        or item.select_one('h3 a[href]')
                    )
                    if not titulo_tag:
                        continue

                    titulo = titulo_tag.get_text(" ", strip=True)
                    link = titulo_tag.get('href', '').strip()
                    if not link or link.startswith('/#') or link.lower().startswith('javascript:'):
                        continue

                    # Filtros especÃ­ficos para ALE RS: remove links institucionais e mantÃ©m sÃ³ notÃ­cia real.
                    if origem == "ALE" and ("al.rs.gov.br" in base_rs or "ww4.al.rs.gov.br" in base_rs):
                        link_lower = link.lower()
                        titulo_lower = titulo.lower()
                        if (
                            "#main-content" in link_lower
                            or "intranet" in titulo_lower
                            or "esqueci minha senha" in titulo_lower
                            or "consulta" in titulo_lower
                            or "processo administrativo" in titulo_lower
                        ):
                            continue
                        if "/noticia/" not in link_lower and "/noticias/" not in link_lower:
                            continue

                    data_publicacao = ''
                    time_tag = item.select_one('time[datetime]') or item.find('time')
                    if time_tag:
                        if time_tag.has_attr('datetime'):
                            try:
                                data_publicacao = datetime.strptime(time_tag['datetime'][:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                            except:
                                pass
                        else:
                            texto_data = time_tag.get_text(" ", strip=True)
                            match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto_data)
                            if match_data:
                                data_publicacao = f"{match_data.group(1)}/{match_data.group(2)}/{match_data.group(3)}"

                    if not link.startswith('http'):
                        link = base_rs + (link if link.startswith('/') else '/' + link)

                    if len(titulo) < 15:
                        continue

                    if any(n[2] == f'=HYPERLINK("{link}";"{link}")' for n in noticias):
                        continue

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])

                    if limite_noticias_atingido(noticias):
                        break
                if noticias:
                    return noticias

        # --- LÃ“GICA ESPECÃFICA: SEDUC TO (to.gov.br/seduc/noticias) ---
        if "to.gov.br" in url and "/seduc/noticias" in url:
            cards = soup.find_all('div', class_='news-card')
            if cards:
                links_vistos_to = set()
                for card in cards:
                    h4_titulo = card.find('h4', class_='headline')
                    if not h4_titulo:
                        continue

                    titulo = h4_titulo.get_text(" ", strip=True)
                    a_titulo = h4_titulo.find_parent('a', href=True)
                    if not a_titulo:
                        continue

                    link = a_titulo.get('href', '').strip()
                    if not link:
                        continue

                    link_lower = link.lower()
                    if (
                        '/seduc/noticias/' not in link_lower
                        or '/categoria/' in link_lower
                        or '/data/' in link_lower
                    ):
                        continue

                    if not link.startswith('http'):
                        link = "https://www.to.gov.br" + (link if link.startswith('/') else '/' + link)

                    if link in links_vistos_to:
                        continue
                    links_vistos_to.add(link)

                    data_publicacao = ''
                    span_data = card.find('span', class_='news-card--data')
                    if span_data:
                        match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', span_data.get_text(" ", strip=True))
                        if match_data:
                            data_publicacao = f"{match_data.group(1)}/{match_data.group(2)}/{match_data.group(3)}"

                    noticias.append([
                        data_publicacao,
                        titulo[:200],
                        f'=HYPERLINK("{link}";"{link}")',
                        origem,
                        datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    ])

                    if limite_noticias_atingido(noticias):
                        break

                if noticias:
                    return noticias

        # --- AJUSTE PARA ALE AC E OUTROS ---
        if "al.ac.leg.br" in url:
            # Na ALE AC, as notÃ­cias de verdade estÃ£o SEMPRE em H2 ou H3
            elementos = soup.find_all(['h2', 'h3'])
        elif "ba.gov.br" in url:
            # Bahia: foca no conteudo principal para evitar menus de secretarias
            main = soup.find('div', {'id': 'conteudo'}) or soup.find('div', {'id': 'content'}) or soup.find('main') or soup.find('div', class_='view-content') or soup
            elementos = main.find_all(['h2', 'h3', 'a'])
        else:
            elementos = soup.find_all(['h1', 'h2', 'h3', 'h4', 'a'])
        
        links_vistos = set()

        for el in elementos:
            a_tag = el if el.name == 'a' else el.find('a')
            if not a_tag: continue

            link = _sanitizar_href_extraido(a_tag.get('href'))
            titulo = a_tag.get_text(strip=True)

            # --- FIX ALEAM (Data grudada no TÃ­tulo) ---
            data_aleam = None
            if "aleam.gov.br" in url:
                # PadrÃ£o: 24.02.26 11:20hTexto...
                match = re.search(r'(\d{2})\.(\d{2})\.(\d{2})\s+\d{2}:\d{2}h(.*)', titulo)
                if match:
                    dia, mes, ano, resto_titulo = match.groups()
                    data_aleam = f"{dia}/{mes}/20{ano}"
                    titulo = resto_titulo.strip()

            # Ignora o tÃ­tulo institucional da ALE AC
            if "Assembleia Legislativa do Estado do Acre" in titulo:
                continue

            # Filtros especÃ­ficos para Governo do AC (agencia.ac.gov.br)
            if "agencia.ac.gov.br" in url:
                if any(termo in titulo.lower() for termo in ['revista deracre', 'floresta em pÃ©', 'portfÃ³lio do governo']):
                    continue

                link_lower = (link or "").lower()
                if not link_lower:
                    continue

                if not link_lower.startswith('http'):
                    link_lower = "https://agencia.ac.gov.br" + (link_lower if link_lower.startswith('/') else '/' + link_lower)

                if "agencia.ac.gov.br" not in link_lower:
                    continue

                if any(trecho in link_lower for trecho in ["/categoria/", "/tag/", "/author/", "/ultimas-noticias", "/contato", "/sobre"]):
                    continue

            # Filtros especÃ­ficos para ALE AL (al.al.leg.br)
            if "al.al.leg.br" in url:
                if any(termo in titulo.lower() for termo in ['diÃ¡rio oficial', 'emendas Ã  constituiÃ§Ã£o', 'procuradoria especial', 'tribunal de justiÃ§a', 'tavares bastos', 'terra das alagÃ´as', 'catÃ¡logo do parlamento']):
                    continue

            # Filtros especÃ­ficos para ALE RN (al.rn.leg.br)
            if "al.rn.leg.br" in url:
                if not link or "/noticia/" not in link:
                    continue

            # Filtros especÃ­ficos para ALE RO (al.ro.leg.br)
            if "al.ro.leg.br" in url:
                if not link or "/noticias/" not in link:
                    continue

            # Filtros especÃ­ficos para SEDUC AC (see.ac.gov.br)
            if "see.ac.gov.br" in url:
                if any(termo in titulo.lower() for termo in ['pular para o conteÃºdo', 'serviÃ§os ac.gov', 'acesso Ã  informaÃ§Ã£o', 'Ã³rgÃ£os do governo', 'representaÃ§Ãµes da see', 'cartilhas institucionais', 'Ã³rgÃ£os vinculados', 'chamada pÃºblica', 'editor de pdfs', 'vozes na rede', 'jogos estudantis', 'alto acre geral', 'baixo acre geral', 'plÃ¡cido de castro', 'senador guiomard', 'santa rosa do purus', 'cruzeiro do sul', 'marechal thaumaturgo', 'rodrigues alves', 'plano estadual de educaÃ§Ã£o', 'matriculas on-line 2026']):
                    continue

            # Filtros especÃ­ficos para SEDUC PA (seduc.pa.gov.br)
            if "seduc.pa.gov.br" in url:
                if not link or "/noticia/" not in link:
                    continue

            # Filtros especÃ­ficos para Governo AL (alagoas.al.gov.br)
            if "alagoas.al.gov.br" in url:
                if "links-uteis" in link or "Planejamento e PrestaÃ§Ã£o de Contas" in titulo:
                    continue

            # Filtros especÃ­ficos para SEDUC MA (educacao.ma.gov.br)
            if "educacao.ma.gov.br" in url:
                if any(termo in titulo.lower() for termo in ['unidades regionais', 'indicadores educacionais', 'seletivos, concursos', 'editais']):
                    continue

            # Filtros especÃ­ficos para ALE MA (al.ma.leg.br)
            if "al.ma.leg.br" in url:
                if any(termo in titulo.lower() for termo in ['assembleia legislativa', 'sapl', 'defesa da cultura', 'transparÃªncia', 'tv assembleia']):
                    continue
                if link and ("sapl.al.ma.leg.br" in link or link.endswith("/sitealema/")):
                    continue

            # Filtros especÃ­ficos para SEDUC AP (seed.portal.ap.gov.br)
            if "seed.portal.ap.gov.br" in url:
                if "/conteudo/" in link or "/ordem_cronologica" in link:
                    continue

            # Filtros especÃ­ficos para ALE BA (al.ba.gov.br)
            if "al.ba.gov.br" in url:
                if not link or "/midia-center/noticias/" not in link:
                    continue

            # Filtros especÃ­ficos para ALE MG (almg.gov.br)
            if "almg.gov.br" in url:
                if not link or "/comunicacao/noticias/" not in link:
                    continue

            # Filtros especÃ­ficos para ALE MS (al.ms.gov.br)
            if "al.ms.gov.br" in url:
                if "ir para o conteÃºdo" in titulo.lower() or (link and "#content" in link):
                    continue

            # Filtros especÃ­ficos para ALE SE (al.se.leg.br)
            if "al.se.leg.br" in url or "al.se.leg.br" in (link or "").lower():
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()

                if (
                    "/audios-das-sessoes-legislativas" in link_lower
                    or "Ã¡udios das sessÃµes legislativas" in titulo_lower
                    or "audios das sessoes legislativas" in titulo_lower
                ):
                    continue

            # Filtros especÃ­ficos para ALE SP (al.sp.gov.br)
            if "al.sp.gov.br" in url or "al.sp.gov.br" in (link or "").lower():
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()

                if (
                    link_lower.startswith("mailto:")
                    or "/mailto:" in link_lower
                    or "/alesp/" in link_lower
                    or "informaÃ§Ãµes:" in titulo_lower
                    or "informacoes:" in titulo_lower
                    or "ordem cronolÃ³gica" in titulo_lower
                    or "ordem cronologica" in titulo_lower
                    or "pesquisa nas atas" in titulo_lower
                ):
                    continue

                if "/noticia/" not in link_lower:
                    continue

            # Filtros especÃ­ficos para ALE RS (al.rs.gov.br / ww4.al.rs.gov.br)
            if "al.rs.gov.br" in url or "ww4.al.rs.gov.br" in url:
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()

                if (
                    "#main-content" in link_lower
                    or "cloud4biz.com" in link_lower
                    or "consultar-processos-administrativos" in link_lower
                    or "pular para o conteÃºdo" in titulo_lower
                    or "intranet" in titulo_lower
                    or "esqueci minha senha" in titulo_lower
                    or "processo administrativo" in titulo_lower
                    or "consulta" in titulo_lower
                ):
                    continue

                if "/noticia/" not in link_lower and "/noticias/" not in link_lower:
                    continue

            # Filtros especÃ­ficos para SEDUC MT (seduc.mt.gov.br)
            if "seduc.mt.gov.br" in url:
                if any(termo in titulo.lower() for termo in ['telefones Ãºteis', 'ouvidoria', 'proteÃ§Ã£o de dados']):
                    continue

            # Filtros especÃ­ficos para Governo MT (secom.mt.gov.br)
            if "secom.mt.gov.br" in url:
                if "pular para o conteÃºdo" in titulo.lower() or (link and "#main-content" in link):
                    continue

            # Filtros especÃ­ficos para SEDUC CE (seduc.ce.gov.br)
            if "seduc.ce.gov.br" in url:
                if not re.search(r'/\d{4}/\d{2}/', link):
                    continue

            # Filtros especÃ­ficos para SEDUC SP (educacao.sp.gov.br)
            if "educacao.sp.gov.br" in url:
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()

                if any(termo in titulo_lower for termo in [
                    'Ãºltimas notÃ­cias',
                    'notÃ­cias',
                    'destaque',
                    'saiba mais',
                    'pular para o conteÃºdo'
                ]):
                    continue

                if any(trecho in link_lower for trecho in [
                    '/noticias/',
                    '/noticia/',
                    '/destaque-home/',
                    '#',
                    'javascript:'
                ]):
                    continue

            # Filtros especÃ­ficos para SEDUC SC (sed.sc.gov.br)
            if "sed.sc.gov.br" in url:
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()
                if any(termo in titulo_lower for termo in [
                    'sed â€“ secretaria de estado da educaÃ§Ã£o',
                    'secretaria de estado da educaÃ§Ã£o',
                    'etapas e modalidades de ensino',
                    'pular para o conteÃºdo'
                ]):
                    continue
                if link_lower in ['', '/', 'https://www.sed.sc.gov.br', 'https://www.sed.sc.gov.br/']:
                    continue
                if any(trecho in link_lower for trecho in [
                    '/etapas-e-modalidades-de-ensino',
                    '/todas-as-noticias',
                    '#main-content'
                ]):
                    continue

            # Filtros especÃ­ficos para ALE SC (agenciaal.alesc.sc.gov.br)
            if (
                "alesc.sc.gov.br" in url
                or "agenciaal.alesc.sc.gov.br" in (link or "").lower()
                or "alesc.sc.gov.br" in (link or "").lower()
            ):
                titulo_lower = titulo.lower()
                link_lower = (link or "").lower()

                if any(trecho in link_lower for trecho in [
                    '/especiais/',
                    '/gabinetes',
                    '/sala_imprensa',
                    '/sala_imprensa_single'
                ]):
                    continue

                if '/noticia_single/' not in link_lower:
                    continue

                if 'notÃ­cias dos deputados/bancadas' in titulo_lower:
                    continue

            # Filtros especÃ­ficos para GOVERNO SC (estado.sc.gov.br)
            if "estado.sc.gov.br" in url:
                link_lower = (link or "").lower()
                if "/noticias/" not in link_lower:
                    continue
                if "/noticias/categoria/" in link_lower:
                    continue

            # Filtros especÃ­ficos para Governo CE (ceara.gov.br)
            if "ceara.gov.br" in url:
                if not re.search(r'/\d{4}/\d{2}/', link):
                    continue
                if any(termo in titulo.lower() for termo in ['homem Ã© preso', 'drogas', 'pmce', 'pcce', 'polÃ­cia militar', 'arma e muniÃ§Ãµes']):
                    continue

            # Filtros especÃ­ficos para Governo PE (pe.gov.br)
            if "pe.gov.br" in url:
                if any(termo in titulo.lower() for termo in ['inÃ­cio', 'serviÃ§os', 'notÃ­cias', 'governo', 'diÃ¡rio oficial', 'transparÃªncia', 'ouvidoria', 'licitaÃ§Ãµes', 'privacidade', 'mapa do site', 'acessibilidade', 'entrar com gov.br', 'praÃ§a da repÃºblica', 'cep', 'links externos']):
                    continue

            # Filtros especÃ­ficos para ALE TO (al.to.leg.br)
            if "al.to.leg.br" in url or "al.to.leg.br" in (link or "").lower():
                link_lower = (link or "").lower()
                titulo_lower = titulo.lower()

                if (
                    link_lower in ["", "/", "https://www.al.to.leg.br", "https://www.al.to.leg.br/"]
                    or "/documento" in link_lower
                    or "assembleia legislativa do tocantins" in titulo_lower
                    or "constituiÃ§Ã£o / regimento / outros" in titulo_lower
                ):
                    continue

                if "/noticia/" not in link_lower:
                    continue

            # Filtros especÃ­ficos para ALE RJ (alerj.rj.gov.br)
            if "alerj.rj.gov.br" in url:
                if "lotus_notes" in link or "default.asp" in link:
                    continue
                if "/Visualizar/Noticia/" not in link:
                    continue

            # ValidaÃ§Ãµes bÃ¡sicas
            min_len = 10 if ("see.ac.gov.br" in url or "agencia.ac.gov.br" in url) else 30
            if not link or len(titulo) < min_len: continue 
            if any(ext in link.lower() for ext in ['.pdf', '.doc', '.jpg']): continue
            
            # Formata link relativo
            if not link.startswith('http'):
                base = "/".join(url.split("/")[:3])
                link = base + (link if link.startswith('/') else '/' + link)

            if link not in links_vistos:
                # Tenta extrair a data real do contexto (pai ou avÃ´ do elemento)
                data_publicacao = ''
                try:
                    # 1. Tenta achar data na URL (ex: .../2023/10/25/...)
                    data_link = _extrair_data_ptbr(link)
                    if data_link and 2020 <= int(data_link[-4:]) <= 2030:
                        data_publicacao = data_link
                    else:
                        # 2. Procura no texto ao redor e tags <time>
                        contexto = ""
                        if el.parent:
                            contexto += el.parent.get_text(" ", strip=True)
                            # Procura tags <time> especificas no pai
                            times = el.parent.find_all('time')
                            for t in times:
                                if t.has_attr('datetime'): contexto += " " + t['datetime']
                            
                            if el.parent.parent:
                                contexto += " " + el.parent.parent.get_text(" ", strip=True)
                        
                        data_contexto = _extrair_data_ptbr(contexto)
                        if data_contexto:
                            data_publicacao = data_contexto
                except:
                    pass

                # ---  Correção DATA ALEAM (Prioridade se achou no título) ---
                if data_aleam:
                    data_publicacao = data_aleam

                # --- Correção DATA GOVERNO AC (Prioridade sobre o genérico) ---
                if "agencia.ac.gov.br" in url:
                    # Busca tag <time> nos elementos pai (container da notícia)
                    # Adiciona classes comuns do tema usado pelo site (Newspaper) para garantir que ache o container
                    container = el.find_parent('div', class_='td-module-container') or \
                                el.find_parent('div', class_='item-details') or \
                                el.find_parent('div', class_='td_module_wrap') or \
                                el.find_parent('div', class_='td-module-meta-info') or \
                                el.find_parent('div', class_='td-module-thumb') or \
                                el.find_parent('article') or \
                                el.parent.parent
                    
                    if container:
                        # 1. Tenta tag time com datetime ou classe entry-date
                        time_tag = container.find('time', class_='entry-date') or container.find('time')
                        if time_tag and time_tag.has_attr('datetime'):
                            try:
                                data_publicacao = datetime.strptime(time_tag['datetime'][:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                            except: pass
                        
                        # 2. Se nÃ£o achou, tenta buscar pela classe de data visual (td-post-date ou entry-date) e ler o texto
                        if not data_publicacao:
                            date_span = container.find('span', class_='td-post-date') or container.find('span', class_='entry-date') or container.find('time')
                            if date_span:
                                texto_data = date_span.get_text(strip=True).lower()
                                data_span = _extrair_data_ptbr(texto_data)
                                if data_span:
                                    data_publicacao = data_span
                        
                        # 3. ULTIMA TENTATIVA: Busca regex em TODO o texto do container (ForÃ§a Bruta)
                        if not data_publicacao:
                            full_text = container.get_text(" ", strip=True).lower()
                            data_bruta = _extrair_data_ptbr(full_text)
                            if data_bruta:
                                data_publicacao = data_bruta

                # --- CORREÃ‡ÃƒO DATA GOVERNO AL ---
                if "alagoas.al.gov.br" in url:
                    # Tenta buscar data no texto do container (card)
                    container = el.find_parent('div', class_='card-body') or el.find_parent('article') or el.parent.parent
                    if container:
                        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', container.get_text(" ", strip=True))
                        if match:
                            data_publicacao = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                # --- CORREÇÃO DATA GOVERNO SP (Agência SP) ---
                if "agenciasp.sp.gov.br" in url and not data_publicacao:
                    data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)
                    if not data_publicacao:
                        data_publicacao = data_referencia_http or data_hoje_br()

                # --- CORREÇÃO DATA ALE SE ---
                if "al.se.leg.br" in url and not data_publicacao:
                    data_publicacao = extrair_data_da_pagina_noticia(link, headers=headers)
                    if not data_publicacao:
                        data_publicacao = data_hoje_br()

                # --- CORREÇÃO DATA SEDUC RJ ---
                if "seeduc.rj.gov.br" in url and not data_publicacao and data_referencia_http:
                    data_publicacao = data_referencia_http

                noticias.append(montar_linha_noticia(data_publicacao, titulo, link, origem))
                links_vistos.add(link)
 

            if limite_noticias_atingido(noticias): break

        return noticias
    except Exception as e:
        erro_curto = str(e).splitlines()[0].strip() if str(e).strip() else e.__class__.__name__
        if erro_curto.lower().startswith("message:"):
            erro_curto = erro_curto.split(":", 1)[1].strip()
        print(f"[DEBUG] Erro em {url}: {erro_curto}")
        return noticias

def main():
    print(f"\n{'='*50}\nNova Execucao: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n{'='*50}")

    spreadsheet_id = os.getenv("SPREADSHEET_ID", "13tjE6nsoh6uBwZhb6mhyP-ogEK3xJ8wWFzvxSc9IIMk")
    pausa_google_api = float(os.getenv("GOOGLE_API_PAUSE_SECONDS", "1.0"))
    ufs_filtro = {
        u.strip().upper()
        for u in os.getenv("UF_FILTER", "").split(",")
        if u and u.strip()
    }

    client = executar_com_retry(setup_gspread, "autenticaÃ§Ã£o Google Sheets")
    sh = executar_com_retry(lambda: client.open_by_key(spreadsheet_id), "abertura da planilha")
    
    # Pega a primeira aba onde estão os links
    ws_main = executar_com_retry(lambda: sh.get_worksheet(0), "leitura da aba principal")
    lista_estados = executar_com_retry(lambda: ws_main.get_all_records(), "leitura dos registros")
    
    colunas = ["Data Not\u00edcia", "T\u00edtulo", "Link Direto", "Origem", "Data Coleta", "Estado"]

    total_coletado = 0

    for row in lista_estados:
        # Tenta pegar UF de qualquer coluna que pareÃ§a com isso
        uf = str(row.get('UF') or row.get('Estado') or row.get('uf')).strip()
        if not uf or uf == "None": continue
        if ufs_filtro and uf.upper() not in ufs_filtro:
            continue

        try:
            print(f"\n>>> PROCESSANDO: {uf}")

            # Mapeia as colunas exatas da sua planilha
            urls = {
                'SEDUC': row.get('Site SEDUC'),
                'ALE': row.get('Site ALE'),
                'GOVERNO': row.get('Site GOVERNO')
            }

            noticias_uf = []
            detalhes_sites = []
            noticias_por_site_raw = {}
            log_sites_ativo = os.getenv("LOG_STATUS_SITES", "0").strip().lower() not in {"0", "false", "no", "off"}
            for origem, url in urls.items():
                origem_upper = str(origem or '').strip().upper()
                if origem_upper not in noticias_por_site_raw:
                    noticias_por_site_raw[origem_upper] = []

                url = str(url).strip() if url else ""
                if url.startswith('http'):
                    try:
                        res = scraping_noticias(url, origem)
                    except Exception as e_site:
                        print(f"[AVISO] Falha no site {uf}/{origem}: {e_site}")
                        res = []

                    coletadas = len(res)
                    noticias_uf.extend(res)
                    noticias_por_site_raw[origem_upper].extend(res)
                    detalhes_sites.append({
                        'origem': origem,
                        'url': url,
                        'coletadas': coletadas
                    })

                    if log_sites_ativo:
                        status_raw = 'ENTROU' if coletadas > 0 else 'FICOU_FORA'
                        print(
                            f"[LOG-SITE-RAW] {uf} | {origem} | {url} | "
                            f"COLETADAS={coletadas} | {status_raw}"
                        )
                else:
                    detalhes_sites.append({
                        'origem': origem,
                        'url': url or 'SEM_URL',
                        'coletadas': 0
                    })

                    if log_sites_ativo:
                        print(
                            f"[LOG-SITE-RAW] {uf} | {origem} | {url or 'SEM_URL'} | "
                            f"COLETADAS=0 | FICOU_FORA"
                        )

            log_status_noticias(uf, noticias_uf, etapa="RAW")
            noticias_uf = filtrar_noticias_reais(noticias_uf)
            noticias_uf = enriquecer_datas_por_link(noticias_uf)

            log_site_noticias_ativo = os.getenv("LOG_STATUS_SITE_NOTICIAS", "0").strip().lower() not in {"0", "false", "no", "off"}
            if log_site_noticias_ativo:
                for site in detalhes_sites:
                    origem_site = str(site.get('origem') or '').strip().upper()
                    noticias_site = [
                        linha for linha in noticias_uf
                        if len(linha) >= 4 and str(linha[3] or '').strip().upper() == origem_site
                    ]
                    noticias_site_raw = noticias_por_site_raw.get(origem_site, [])

                    if noticias_site:
                        log_status_noticias(uf, noticias_site, etapa="SITE", somente_entrou=False)
                    elif noticias_site_raw:
                        log_status_noticias(uf, noticias_site_raw, etapa="SITE", somente_entrou=False)
                    else:
                        print(f"[LOG-SITE-NOTICIA] {uf} | {site.get('origem')} | SEM_NOTICIAS | SEM_DATA | SEM_DATA | FICOU_FORA")

            noticias_selecionadas = selecionar_primeiras_noticias_por_site(noticias_uf, limite_por_site=5)

            if log_sites_ativo:
                selecionadas_por_origem = {}
                for linha in noticias_selecionadas:
                    if len(linha) < 4:
                        continue
                    origem_linha = str(linha[3] or '').strip().upper()
                    if not origem_linha:
                        continue
                    selecionadas_por_origem[origem_linha] = selecionadas_por_origem.get(origem_linha, 0) + 1

                for site in detalhes_sites:
                    origem_site = str(site.get('origem') or '').strip().upper()
                    qtd_selecionadas = selecionadas_por_origem.get(origem_site, 0)
                    status_site = 'ENTROU' if qtd_selecionadas > 0 else 'FICOU_FORA'
                    print(
                        f"[LOG-SITE] {uf} | {site.get('origem')} | {site.get('url')} | "
                        f"COLETADAS={site.get('coletadas', 0)} | SELECIONADAS={qtd_selecionadas} | {status_site}"
                    )

            try:
                ws_estado = executar_com_retry(lambda: sh.worksheet(uf), f"acesso Ã  aba {uf}")
            except gspread.exceptions.WorksheetNotFound:
                ws_estado = executar_com_retry(
                    lambda: sh.add_worksheet(title=uf, rows="2000", cols="6"),
                    f"criaÃ§Ã£o da aba {uf}"
                )

            valores_existentes = executar_com_retry(lambda: ws_estado.get_all_values(), f"leitura da aba {uf}")

            if not valores_existentes:
                executar_com_retry(
                    lambda: ws_estado.update(values=[colunas], range_name='A1', value_input_option='USER_ENTERED'),
                    f"escrita de cabeÃ§alho na aba {uf}"
                )
                valores_existentes = [colunas]
            elif len(valores_existentes[0]) < 6 or valores_existentes[0][:6] != colunas:
                executar_com_retry(
                    lambda: ws_estado.update(values=[colunas], range_name='A1:F1', value_input_option='USER_ENTERED'),
                    f"ajuste de cabeÃ§alho na aba {uf}"
                )

            if len(valores_existentes) > 1:
                executar_com_retry(
                    lambda: ws_estado.update(
                        values=[[uf] for _ in valores_existentes[1:]],
                        range_name=f'F2:F{len(valores_existentes)}',
                        value_input_option='USER_ENTERED'
                    ),
                    f"preenchimento da coluna Estado na aba {uf}"
                )

            chaves_existentes = set()
            for linha in valores_existentes[1:]:
                if len(linha) >= 4:
                    link_existente = extrair_url_da_formula_hyperlink(linha[2])
                    origem_existente = str(linha[3] or '').strip().upper()
                    if link_existente and origem_existente:
                        chaves_existentes.add((origem_existente, link_existente.strip().lower()))

            novas_noticias = []
            for linha in noticias_selecionadas:
                link_novo = extrair_url_da_formula_hyperlink(linha[2])
                origem_nova = str(linha[3] or '').strip().upper()
                if not link_novo or not origem_nova:
                    continue

                chave = (origem_nova, link_novo.strip().lower())
                if chave not in chaves_existentes:
                    novas_noticias.append(list(linha) + [uf])
                    chaves_existentes.add(chave)

            if novas_noticias:
                executar_com_retry(
                    lambda: ws_estado.insert_rows(novas_noticias, row=2, value_input_option='USER_ENTERED'),
                    f"inser\u00e7\u00e3o de not\u00edcias no topo da aba {uf}"
                )
                print(f"Sucesso: {len(novas_noticias)} novas not\u00edcias selecionadas em {uf}")
                total_coletado += len(novas_noticias)
            elif noticias_selecionadas:
                print(f"Aviso: not\u00edcias selecionadas j\u00e1 existentes em {uf}; nada novo para adicionar")
            else:
                print(f"Aviso: Nenhuma not\u00edcia selecionada para {uf}")

            time.sleep(max(0.0, pausa_google_api))
        except Exception as e:
            print(f"[ERRO] Falha ao processar {uf}: {e}")
            continue

    print(f"\n{'='*50}\nFim da Execu\u00e7\u00e3o. Total Geral: {total_coletado} not\u00edcias coletadas.\n{'='*50}")

if __name__ == "__main__":
    main()


