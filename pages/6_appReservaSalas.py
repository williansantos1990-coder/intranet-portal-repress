# =========================================================================================
# 1. IMPORTAÇÃO DAS BIBLIOTECAS DE INTERFACE E MANIPULAÇÃO DE DADOS
# =========================================================================================
import streamlit as st                      # Framework principal para criação de interfaces web interativas
import streamlit.components.v1 as components # Componentes HTML customizados e iframes
import pyodbc                               # Driver ODBC para conexão com o Microsoft SQL Server
import pandas as pd                         # Manipulação de DataFrames tabulares
import locale                               # Configuração regional de localização e idioma
import base64                               # Codificação de imagens em formato Base64 para persistência
import io                                   # Manipulação de fluxos de bytes em memória
from PIL import Image, ImageOps             # Processamento e redimensionamento de imagens de salas
from datetime import datetime, date, time, timedelta # Manipulação avançada de datas e horários

# =========================================================================================
# 2. IMPORTAÇÕES DO SISTEMA E INTEGRAÇÃO CENTRALIZADA (.ENV E DATABASE)
# =========================================================================================
import os                                   # Utilitários do sistema operacional para caminhos e diretórios
import sys                                  # Manipulação do path do interpretador Python
import uuid                                 # Geração de identificadores únicos universais (UUID/UID)
from dotenv import load_dotenv              # Carregamento seguro de variáveis de ambiente (.env)
import resend                               # Biblioteca oficial da API Resend para envio de e-mails

# Configura o caminho raiz do projeto para garantir importações corretas de módulos irmãos
caminho_app = os.path.dirname(os.path.abspath(__file__))
caminho_raiz = os.path.dirname(caminho_app)

if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

# Importa a função centralizada de conexão ODBC do Portal Repress a partir da raiz
try:
    from database import obter_conexao_principal
except ImportError as e:
    st.error("Não foi possível localizar ou importar o arquivo database.py na pasta raiz do projeto.")
    st.exception(e)
    st.stop()

# Carrega as credenciais e define a API Key do Resend priorizando a chave de reservas
caminho_env = os.path.join(caminho_raiz, '.env')
load_dotenv(dotenv_path=caminho_env, override=True)
resend.api_key = os.getenv("RESEND_API_KEY_Reservas") or os.getenv("RESEND_API_KEY")

# =========================================================================================
# 3. CONFIGURAÇÕES DE LOCALIZAÇÃO (IDIOMA) E VERIFICAÇÃO DE MÓDULOS EXTERNOS
# =========================================================================================
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except Exception:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except Exception:
        pass 

# Verifica se o componente de calendário do Streamlit está instalado no ambiente
try:
    from streamlit_calendar import calendar
    CALENDAR_DISPONIVEL = True
except ImportError:
    CALENDAR_DISPONIVEL = False

# =========================================================================================
# 4. CONFIGURAÇÕES GLOBAIS DA PÁGINA STREAMLIT E CONTROLE DE ESTADOS (SESSION STATE)
# =========================================================================================
st.set_page_config(
    page_title="🗓️ Reserva de Salas",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Importa e injeta a folha de estilos corporativa centralizada do portal
from styles import injetar_estilo_global
injetar_estilo_global()

# Inicializa as variáveis de controle de sessão do aplicativo para evitar perda de estados
if "modal_sala_aberto" not in st.session_state:
    st.session_state["modal_sala_aberto"] = False

if "modal_sala_id" not in st.session_state:
    st.session_state["modal_sala_id"] = None

if "reserva_opcoes_dados" not in st.session_state:
    st.session_state["reserva_opcoes_dados"] = {}

if "abrir_modal_detalhes" not in st.session_state:
    st.session_state["abrir_modal_detalhes"] = False

if "abrir_modal_nova" not in st.session_state:
    st.session_state["abrir_modal_nova"] = False

if "abrir_modal_editar" not in st.session_state:
    st.session_state["abrir_modal_editar"] = False

if "ultimo_cal_sig" not in st.session_state:
    st.session_state["ultimo_cal_sig"] = None

if "edit_id_reserva" not in st.session_state:
    st.session_state["edit_id_reserva"] = None

if "recorrencia_ativo" not in st.session_state:
    st.session_state["recorrencia_ativo"] = False

if "rec_frequencia" not in st.session_state:
    st.session_state["rec_frequencia"] = "Semanal"

if "rec_intervalo_qtd" not in st.session_state:
    st.session_state["rec_intervalo_qtd"] = 1

if "rec_dias_semana" not in st.session_state:
    st.session_state["rec_dias_semana"] = {}

if "rec_tipo_fim" not in st.session_state:
    st.session_state["rec_tipo_fim"] = "Número de ocorrências"

if "rec_termino_apos" not in st.session_state:
    st.session_state["rec_termino_apos"] = 10

if "rec_termino_data" not in st.session_state:
    st.session_state["rec_termino_data"] = date.today()

if "temp_participantes" not in st.session_state:
    st.session_state["temp_participantes"] = ""

# =========================================================================================
# 5. ESTILIZAÇÃO MODERNA DO FULLCALENDAR (CSS COM BORDAS ARREDONDADAS E SOMBRAS)
# =========================================================================================
CSS_CALENDARIO_AZUL = """
    .fc { 
        background-color: #ffffff; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
        border: 1px solid #e5e7eb; 
        overflow: hidden; 
    }
    .fc .fc-button-primary { 
        background-color: #004B87 !important; 
        border-color: #004B87 !important; 
        color: #ffffff !important; 
        box-shadow: none !important; 
        outline: none !important; 
        border-radius: 6px !important; 
        font-weight: 500 !important; 
    }
    .fc .fc-button-primary:hover { 
        background-color: #003366 !important; 
        border-color: #003366 !important; 
    }
    .fc .fc-button-primary:not(:disabled).fc-button-active, .fc .fc-button-primary:not(:disabled):active { 
        background-color: #00A8E8 !important; 
        border-color: #00A8E8 !important; 
        color: #ffffff !important; 
    }
    .fc .fc-timegrid-col.fc-day-today { 
        background-color: rgba(0, 168, 232, 0.04) !important; 
    }
    .fc .fc-col-header-cell.fc-day-today { 
        background-color: rgba(92, 141, 174, 0.12) !important; 
    }
    .fc-col-header-cell { 
        padding-top: 10px !important; 
        padding-bottom: 10px !important; 
        vertical-align: middle !important; 
        font-size: 13px !important; 
        font-weight: bold !important; 
    }
    .fc-col-header-cell-cushion { 
        font-size: 13px !important; 
        font-weight: bold !important; 
        text-decoration: none !important; 
        color: #1f2937 !important; 
    }
    .fc-event-main { 
        padding: 3px 6px !important; 
        border-radius: 6px !important; 
    }
    .fc-event-time { 
        display: block !important; 
        font-weight: 700 !important; 
        font-size: 11px !important; 
        opacity: 0.95 !important; 
        margin-bottom: 1px !important; 
    }
    .fc-event-title { 
        display: block !important; 
        font-weight: 600 !important; 
        white-space: pre-wrap !important; 
        line-height: 1.2 !important; 
        font-size: 11px !important; 
    }
    .fc-timegrid-slot, .fc-timegrid-slot-lane { 
        height: 2.6em !important; 
    }
    .fc .fc-button { 
        font-size: 13px !important; 
        padding: 6px 12px !important; 
    }
    .fc-timegrid-slot-label-cushion, .fc-timegrid-axis-cushion { 
        font-size: 12px !important; 
        font-weight: 500 !important; 
        color: #6b7280 !important; 
    }
    .fc { 
        border-radius: 12px; 
    }
    .fc .fc-header-toolbar { 
        padding: 14px 18px !important; 
        margin-bottom: 0 !important; 
        border-bottom: 1px solid #f3f4f6 !important; 
        background-color: #fafafa !important; 
    }
    .fc .fc-toolbar-title { 
        font-size: 15px !important; 
        font-weight: 600 !important; 
        color: #111827 !important; 
        margin-left: 12px !important; 
        display: inline-block !important; 
        vertical-align: middle !important; 
    }
    .fc-toolbar-chunk:first-child { 
        display: flex !important; 
        align-items: center !important; 
    }
"""

# =========================================================================================
# 6. FUNÇÕES DE BANCO DE DADOS E LÓGICA DE NEGÓCIO (COM CACHE E VIEWS/PROCEDURES)
# =========================================================================================
def conectar_banco():
    """Estabelece conexão ODBC com o SQL Server, ajusta codificação e valida colunas necessárias."""
    try:
        conn = obter_conexao_principal()
        if not conn: return None
        try:
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin1')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='latin1')
            conn.setencoding(encoding='latin1')
        except Exception:
            pass
            
        # Valida colunas essenciais na base caso ainda não existam (incluindo participantes)
        cursor = conn.cursor()
        cursor.execute("IF COL_LENGTH('reservas.Agendamentos', 'uid') IS NULL BEGIN ALTER TABLE reservas.Agendamentos ADD uid VARCHAR(255); END")
        cursor.execute("IF COL_LENGTH('reservas.Agendamentos', 'participantes') IS NULL BEGIN ALTER TABLE reservas.Agendamentos ADD participantes NVARCHAR(MAX); END")
        cursor.execute("IF COL_LENGTH('reservas.Salas', 'cor') IS NULL BEGIN ALTER TABLE reservas.Salas ADD cor VARCHAR(50); END")
        cursor.execute("IF EXISTS(SELECT 1 FROM sys.columns WHERE Name = 'imagem_url' AND Object_ID = Object_ID('reservas.Salas') AND max_length != -1) BEGIN ALTER TABLE reservas.Salas ALTER COLUMN imagem_url VARCHAR(MAX); END")
        conn.commit()
        cursor.close()
        return conn
    except Exception as e:
        st.error("Erro crítico ao tentar conectar ou validar a estrutura do banco de dados SQL Server:")
        st.exception(e)
        return None

@st.cache_data(ttl=30, show_spinner=False)
def buscar_dados_usuario(email_usuario):
    """Busca dados cadastrais do usuário logado com cache otimizado de 30 segundos."""
    conn = conectar_banco()
    if not conn:
        return {"id_usuario": 0, "nome": "Usuário Não Encontrado", "email": email_usuario, "nivel": "usuario"}
    try:
        query = "SELECT id_usuario, nome, email, nivel FROM [aplicativos_db].[auth].[Usuarios] WHERE email = ?"
        df = pd.read_sql(query, conn, params=[email_usuario])
        if not df.empty:
            return df.iloc[0].to_dict()
        else:
            return {"id_usuario": 0, "nome": "Usuário Não Encontrado", "email": email_usuario, "nivel": "usuario"}
    except Exception:
        return {"id_usuario": 0, "nome": "Erro Conexão", "email": email_usuario, "nivel": "usuario"}
    finally:
        if conn:
            try: conn.close()
            except: pass

@st.cache_data(ttl=30, show_spinner=False)
def buscar_salas():
    """Busca as salas ativas cadastradas no sistema com cache otimizado de 30 segundos."""
    conn = conectar_banco()
    if not conn:
        return pd.DataFrame(columns=["id_sala", "nome", "capacidade", "localizacao", "equipamentos", "imagem_url", "cor"])
    try:
        query = "SELECT * FROM reservas.Salas WHERE CAST(ativo AS VARCHAR(10)) = '1' OR ativo IS NULL"
        df = pd.read_sql(query, conn)
        if 'id_sala' not in df.columns:
            df['id_sala'] = range(1, len(df) + 1)
        if 'cor' not in df.columns:
            df['cor'] = '#3788d8'
        return df
    except Exception:
        return pd.DataFrame(columns=["id_sala", "nome", "capacidade", "localizacao", "equipamentos", "imagem_url", "cor"])
    finally:
        if conn:
            try: conn.close()
            except: pass

def salvar_sala_banco(id_sala, nome, capacidade, localizacao, equipamentos, imagem_url=""):
    """Insere ou atualiza uma sala no banco de dados e limpa o cache imediatamente."""
    conn = conectar_banco()
    if not conn: return False
    cursor = None
    try:
        cursor = conn.cursor()
        nome_safe = str(nome)[:250]
        localizacao_safe = str(localizacao)[:250]
        equipamentos_safe = str(equipamentos)[:2000]
        imagem_safe = str(imagem_url)
        
        if id_sala:
            query = "UPDATE reservas.Salas SET nome = ?, capacidade = ?, localizacao = ?, equipamentos = ?, imagem_url = ? WHERE id_sala = ?"
            cursor.execute(query, (nome_safe, capacidade, localizacao_safe, equipamentos_safe, imagem_safe, id_sala))
        else:
            query = "INSERT INTO reservas.Salas (nome, capacidade, localizacao, equipamentos, imagem_url, ativo) VALUES (?, ?, ?, ?, ?, 1)"
            cursor.execute(query, (nome_safe, capacidade, localizacao_safe, equipamentos_safe, imagem_safe))
            
        conn.commit()
        st.cache_data.clear()
        return True
    except Exception as err:
        if conn:
            try: conn.rollback()
            except: pass
        st.error(f"Erro ao salvar sala no banco de dados: {err}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def remover_sala_banco(id_sala):
    """Realiza a exclusão lógica (soft delete) de uma sala e limpa o cache."""
    conn = conectar_banco()
    if not conn: return False
    cursor = None
    try:
        cursor = conn.cursor()
        query = "UPDATE reservas.Salas SET ativo = 0 WHERE id_sala = ?"
        cursor.execute(query, (id_sala,))
        conn.commit()
        st.cache_data.clear()
        return True
    except Exception as err:
        if conn:
            try: conn.rollback()
            except: pass
        st.error(f"Erro ao remover sala no banco de dados: {err}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@st.cache_data(ttl=30, show_spinner=False)
def buscar_agendamentos():
    """Busca todos os agendamentos utilizando exclusivamente a View otimizada [vw_AgendamentosCompletos][cite: 45, 48]."""
    conn = conectar_banco()
    if not conn:
        return pd.DataFrame(columns=["id_reserva", "id_usuario", "titulo", "data_reserva", "hora_inicio", "hora_termino", "descricao", "id_sala", "recorrente", "id_serie", "uid", "participantes", "sala_nome", "cor", "usuario_nome"])
    try:
        query = "SELECT * FROM [aplicativos_db].[reservas].[vw_AgendamentosCompletos]"
        df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame(columns=["id_reserva", "id_usuario", "titulo", "data_reserva", "hora_inicio", "hora_termino", "descricao", "id_sala", "recorrente", "id_serie", "uid", "participantes", "sala_nome", "cor", "usuario_nome"])
    finally:
        if conn:
            try: conn.close()
            except: pass

def contar_itens_serie(id_serie):
    """Conta o número de ocorrências vinculadas a uma determinada série recorrente no banco."""
    if not id_serie: return 0
    conn = conectar_banco()
    if not conn: return 0
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reservas.Agendamentos WHERE id_serie = ?", (id_serie,))
        res = cursor.fetchone()
        return res[0] if res else 0
    except Exception:
        return 0
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def carregar_detalhes_serie(id_serie):
    """Analisa as ocorrências de uma série no banco para reconstruir sua configuração original no modal."""
    if not id_serie:
        return {"ativo": False}
    conn = conectar_banco()
    if not conn:
        return {"ativo": False}
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT data_reserva FROM reservas.Agendamentos WHERE id_serie = ? ORDER BY data_reserva ASC", (int(id_serie),))
        rows = cursor.fetchall()
        if not rows:
            return {"ativo": False}
        
        datas = [r[0] if isinstance(r[0], date) else datetime.strptime(str(r[0])[:10], "%Y-%m-%d").date() for r in rows]
        total_ocorrencias = len(datas)
        
        if total_ocorrencias <= 1:
            return {"ativo": False}
            
        diffs = [(datas[i+1] - datas[i]).days for i in range(len(datas)-1)]
        
        freq = "Semanal"
        interval = 1
        dias_semana = {
            "domingo": False, "segunda-feira": False, "terça-feira": False,
            "quarta-feira": False, "quinta-feira": False, "sexta-feira": False, "sábado": False
        }
        
        for d in datas:
            wd = d.weekday() 
            map_wd_key = {0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira", 3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"}
            dias_semana[map_wd_key[wd]] = True
            
        if all(d == 1 for d in diffs):
            freq = "Diário"
            interval = 1
        elif all(d > 1 and d % 7 == 0 for d in diffs):
            freq = "Semanal"
            interval = diffs[0] // 7
        elif all(d == 7 for d in diffs):
            freq = "Semanal"
            interval = 1
        elif any(d > 28 for d in diffs):
            freq = "Mensal"
            interval = 1
        else:
            freq = "Semanal"
            interval = 1
            
        return {
            "ativo": True,
            "freq": freq,
            "intervalo": max(1, interval),
            "dias_semana": dias_semana,
            "tipo_fim": "Número de ocorrências",
            "termino_apos": total_ocorrencias,
            "termino_data": datas[-1]
        }
    except Exception:
        return {"ativo": False}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def verificar_conflito_edicao(id_sala, data_reserva, hora_ini, hora_fim, id_reserva_atual):
    """Verifica conflito de horário durante a edição de uma reserva existente na base."""
    conn = conectar_banco()
    if not conn: return []
    cursor = None
    try:
        cursor = conn.cursor()
        query = "SELECT data_reserva FROM reservas.Agendamentos WHERE id_sala = ? AND id_reserva != ? AND data_reserva = ? AND (hora_inicio < ?) AND (hora_termino > ?)"
        cursor.execute(query, (id_sala, id_reserva_atual, data_reserva.strftime('%Y-%m-%d'), hora_fim.strftime("%H:%M:%S"), hora_ini.strftime("%H:%M:%S")))
        res = cursor.fetchall()
        return res
    except Exception:
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def escurecer_cor(hex_color, fator=0.3):
    """Ajusta a tonalidade da cor hexadecimal para garantir contraste adequado no texto dos eventos."""
    hex_color = str(hex_color).lstrip('#') 
    if len(hex_color) != 6: return "#111827" 
    try:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r, g, b = max(0, int(r * fator)), max(0, int(g * fator)), max(0, int(b * fator))
        return f"#{r:02x}{g:02x}{g:02x}" 
    except Exception:
        return "#111827"

# =========================================================================================
# 7. MOTOR CENTRALIZADO DE RESEND API + GERAÇÃO VCALENDAR (.ICS INTERNACIONAL OUTLOOK)
# =========================================================================================
def enviar_convite_outlook(
    email_destino, titulo, data_reserva, hora_ini, hora_fim, sala_nome, 
    descricao="", nome_usuario="", method="REQUEST", 
    is_recorrente=False, freq="Semanal", interval=1, dias_semana=None, 
    tipo_fim="Número de ocorrências", termino_apos=10, termino_data=None,
    uid_evento=None, recurrence_id_datetime=None, 
    participantes_bcc=None, is_atualizacao=False
):
    """Gera arquivos iCalendar (.ics) compatíveis com Outlook e envia convites via API Resend."""
    api_key_ativa = os.getenv("RESEND_API_KEY_Reservas") or os.getenv("RESEND_API_KEY")
    if not api_key_ativa:
        return False, "A chave da API (RESEND_API_KEY) não foi encontrada ou está vazia no arquivo .env."
    
    resend.api_key = api_key_ativa

    try:
        # Formata as datas e horários para o padrão internacional do iCalendar
        str_dt_ini = datetime.combine(data_reserva, hora_ini).strftime("%Y%m%dT%H%M%S")
        str_dt_fim = datetime.combine(data_reserva, hora_fim).strftime("%Y%m%dT%H%M%S")
        agora = datetime.now().strftime("%Y%m%dT%H%M%SZ")
        
        uid_final = uid_evento if uid_evento else str(uuid.uuid4())
        status_evento = "CONFIRMED" if method == "REQUEST" else "CANCELLED"
        seq_num = "1" if (method == "CANCEL" or recurrence_id_datetime) else "0"
        
        recurrence_id_line = ""
        if recurrence_id_datetime:
            str_rec_id = recurrence_id_datetime.strftime("%Y%m%dT%H%M%S")
            recurrence_id_line = f"RECURRENCE-ID;TZID=America/Sao_Paulo:{str_rec_id}\n"

        rrule_line = ""
        if is_recorrente and method == "REQUEST" and not recurrence_id_datetime:
            freq_map_ics = {"Diário": "DAILY", "Semanal": "WEEKLY", "Mensal": "MONTHLY", "Anual": "YEARLY"}
            freq_code = freq_map_ics.get(freq, "WEEKLY")
            rrule_parts = [f"FREQ={freq_code}", f"INTERVAL={interval}"]
            
            if freq == "Semanal" and dias_semana:
                dias_map_ics = {
                    "domingo": "SU", "segunda-feira": "MO", "terça-feira": "TU",
                    "quarta-feira": "WE", "quinta-feira": "TH", "sexta-feira": "FR", "sábado": "SA"
                }
                byday_list = [dias_map_ics[d] for d, ativo in dias_semana.items() if ativo]
                if byday_list:
                    rrule_parts.append(f"BYDAY={','.join(byday_list)}")
            
            if tipo_fim == "Número de ocorrências":
                rrule_parts.append(f"COUNT={termino_apos}")
            elif tipo_fim == "Data específica" and termino_data:
                until_str = termino_data.strftime("%Y%m%d") + "T235959Z"
                rrule_parts.append(f"UNTIL={until_str}")
            
            rrule_line = f"RULE:{';'.join(rrule_parts)}\n"

        # Constrói o payload bruto do arquivo .ics compatível com calendários corporativos
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Repress//Reserva de Salas//PT-BR
CALSCALE:GREGORIAN
METHOD:{method}
BEGIN:VEVENT
UID:{uid_final}
{recurrence_id_line}DTSTAMP:{agora}
DTSTART;TZID=America/Sao_Paulo:{str_dt_ini}
DTEND;TZID=America/Sao_Paulo:{str_dt_fim}
SUMMARY:{titulo}
DESCRIPTION:{descricao}
LOCATION:{sala_nome}
STATUS:{status_evento}
SEQUENCE:{seq_num}
ORGANIZER;CN="Reserva de Salas":mailto:nao-responda@reservas.repress.com.br
ATTENDEE;CN="{nome_usuario or 'Usuário'}";ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{email_destino}
{rrule_line}END:VEVENT
END:VCALENDAR"""

        data_fmt_br = data_reserva.strftime("%d/%m/%Y") if hasattr(data_reserva, "strftime") else str(data_reserva)
        hora_ini_fmt = hora_ini.strftime("%H:%M") if hasattr(hora_ini, "strftime") else str(hora_ini)[:5]
        hora_fim_fmt = hora_fim.strftime("%H:%M") if hasattr(hora_fim, "strftime") else str(hora_fim)[:5]

        # Monta o corpo HTML estruturado do e-mail de notificação
        if method == "REQUEST":
            acao_realizada = "atualizada" if is_atualizacao else "agendada"
            assunto = f"{'Atualização' if is_atualizacao else 'Convite de Reunião'}: {titulo}"
            html_corpo = f"""
            <div style="font-family: Arial, sans-serif; color: #1F2937; line-height: 1.5;">
                <p style="font-size: 15px;">Olá <strong>{nome_usuario or 'Usuário'}</strong>, tudo bem?</p>
                <p style="font-size: 15px;">A sua reserva para a sala <strong>{sala_nome}</strong> foi <strong>{acao_realizada}</strong> com sucesso!</p>
                <div style="background-color: #F8FAFC; padding: 15px; border-radius: 6px; border: 1px solid #E2E8F0; margin-bottom: 20px;">
                    <ul style="list-style-type: none; padding-left: 0; margin: 0; font-size: 14px;">
                        <li style="margin-bottom: 8px;">📌 <b>Título:</b> {titulo}</li>
                        <li style="margin-bottom: 8px;">📍 <b>Local:</b> {sala_nome}</li>
                        <li style="margin-bottom: 8px;">📅 <b>Data:</b> {data_fmt_br}</li>
                        <li style="margin-bottom: 8px;">⏰ <b>Horário:</b> das <strong>{hora_ini_fmt} às {hora_fim_fmt}</strong></li>
                        <li style="margin-bottom: 0;">📝 <b>Descrição:</b> {descricao or 'Nenhuma descrição detalhada.'}</li>
                    </ul>
                </div>
            </div>
            """
        else:
            assunto = f"Cancelamento de Reunião: {titulo}"
            html_corpo = f"""
            <div style="font-family: Arial, sans-serif; color: #1F2937; line-height: 1.5;">
                <p style="font-size: 15px;">Olá <strong>{nome_usuario or 'Usuário'}</strong>,</p>
                <p style="font-size: 15px;">Informamos que a sua reserva na sala <strong>{sala_nome}</strong> foi <strong>cancelada</strong>.</p>
            </div>
            """

        # Configura o remetente oficial solicitado com o subdomínio validado no DNS
        parametros = {
            "from": "Reserva de Salas <nao-responda@reservas.repress.com.br>",
            "to": [email_destino],
            "subject": assunto,
            "html": html_corpo,
            "attachments": [{
                "filename": "invite.ics",
                "content": list(ics_content.encode("utf-8")),
                "content_type": "text/calendar; charset=utf-8"
            }]
        }
        
        # Insere os participantes em Cópia Oculta (BCC) para blindar contra respostas em massa e garantir recebimento e sincronização no Outlook
        if participantes_bcc and isinstance(participantes_bcc, list) and len(participantes_bcc) > 0:
            parametros["bcc"] = participantes_bcc

        resend.Emails.send(parametros)
        return True, ""
    except Exception as e:
        return False, str(e)

# =========================================================================================
# 8. AUTENTICAÇÃO E RENDERIZAÇÃO INICIAL DA PÁGINA
# =========================================================================================
query_params = st.query_params
email_conectado = query_params.get("user", "willian.santos@repress.com.br")
dados_usuario = buscar_dados_usuario(email_conectado)

st.title("🗓️️ Reserva de Salas")
perfil_exibicao = "Administrador" if dados_usuario.get("nivel") == "admin" else "Usuário"
st.caption(f"Usuário Conectado: **{dados_usuario['nome']}** ({dados_usuario['email']}) — Perfil: **{perfil_exibicao}**")
st.divider()

# Cria as abas de navegação de acordo com o nível de permissão do usuário logado
if dados_usuario.get("nivel") == "admin":
    aba_calendario, aba_gerenciar = st.tabs(["Calendário", "Gerenciar Salas"])
else:
    aba_calendario, = st.tabs(["📅 Calendário"])
    aba_gerenciar = None

# =========================================================================================
# 9. MODAIS FLUTUANTES NATIVOS (@st.dialog) - DETALHES, CRIAÇÃO E EDIÇÃO
# =========================================================================================

@st.dialog("Detalhes da Reserva")
def modal_detalhes_reserva():
    """Modal nativo para visualização, edição ou cancelamento de uma reserva ou série."""
    dados_res = st.session_state.get("reserva_opcoes_dados", {})
    df_salas_cadastradas = buscar_salas()
    img_mini = ""
    if not df_salas_cadastradas.empty:
        sala_filtrada = df_salas_cadastradas[df_salas_cadastradas["nome"] == dados_res.get('sala', '')]
        if not sala_filtrada.empty:
            r_sala = sala_filtrada.iloc[0].to_dict()
            img_mini = r_sala.get("imagem_url", "") or "https://images.unsplash.com/photo-1497366216548-37526070297c?w=500&q=80"
            
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px; margin-bottom: 12px; display: flex; align-items: center; gap: 10px;">
                    <img src="{img_mini}" style="width: 65px; height: 65px; object-fit: cover; border-radius: 4px; flex-shrink: 0;" />
                    <div style="display: flex; flex-direction: column; justify-content: center; gap: 3px;">
                        <div style="font-size: 11px; color: #475569; font-weight: 500;">{r_sala.get('equipamentos', 'Sem descrição.')}</div>
                        <div><span style="background-color: #FFFFFF; border: 1px solid #CBD5E1; padding: 1px 5px; border-radius: 8px; font-size: 9px; color: #475569;">📍 {r_sala.get('localizacao', 'Não informada')}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True
            )

    is_rec_detalhes = dados_res.get("recorrente") in [1, True, "1"] and dados_res.get("id_serie") is not None
    rec_detalhe_texto = f"**Recorrência:** Série ativa com {contar_itens_serie(dados_res.get('id_serie'))} ocorrências" if is_rec_detalhes else ""

    desc_texto = str(dados_res.get('descricao', 'Nenhuma descrição informada.'))
    titulo_texto = str(dados_res.get('titulo', ''))
    
    # Recupera e formata os participantes salvos para exibição limpa no modal de detalhes
    participantes_salvos = str(dados_res.get('participantes', '')).strip() if pd.notna(dados_res.get('participantes')) else ''
    participantes_linha = f"**Participantes:** {participantes_salvos}  \n" if participantes_salvos else ""

    # Renderiza os detalhes utilizando Markdown nativo do Streamlit para evitar vazamento de tags HTML
    st.markdown(
        f"""
        **Título:** {titulo_texto}  
        **Autor:** {dados_res.get('nome', '')}  
        **Data:** {dados_res.get('data', '')}  
        **Horário:** {dados_res.get('inicio', '')} às {dados_res.get('termino', '')}  
        {participantes_linha}**Descrição:** {desc_texto}  
        {rec_detalhe_texto}
        """
    )
    st.divider()

    id_dono_reserva = dados_res.get("id_usuario")
    usuario_logado_id = dados_usuario.get("id_usuario")
    eh_admin = dados_usuario.get("nivel") == "admin"
    
    if id_dono_reserva == usuario_logado_id or eh_admin:
        if is_rec_detalhes:
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1:
                if st.button("Fechar", type="secondary", use_container_width=True):
                    st.session_state["reserva_opcoes_dados"] = {}
                    st.session_state["abrir_modal_detalhes"] = False
                    st.rerun()
            with col_b2:
                if st.button("Editar", type="primary", use_container_width=True):
                    st.session_state["edit_id_reserva"] = dados_res.get("id")
                    st.session_state["temp_titulo"] = dados_res.get("titulo_puro", "")
                    st.session_state["temp_desc"] = dados_res.get("descricao", "")
                    st.session_state["temp_participantes"] = participantes_salvos
                    st.session_state["recorrencia_ativo"] = is_rec_detalhes
                    st.session_state["temp_id_serie"] = dados_res.get("id_serie")
                    
                    if is_rec_detalhes and dados_res.get("id_serie"):
                        info_serie = carregar_detalhes_serie(dados_res.get("id_serie"))
                        if info_serie.get("ativo"):
                            f_val = info_serie.get("freq", "Semanal")
                            i_val = info_serie.get("intervalo", 1)
                            d_dict = info_serie.get("dias_semana", {})
                            t_fim = info_serie.get("tipo_fim", "Número de ocorrências")
                            t_apos = info_serie.get("termino_apos", 10)
                            t_data = info_serie.get("termino_data", date.today())
                            
                            st.session_state["rec_frequencia"] = f_val
                            st.session_state["rec_intervalo_qtd"] = i_val
                            st.session_state["rec_dias_semana"] = d_dict
                            st.session_state["rec_tipo_fim"] = t_fim
                            st.session_state["rec_termino_apos"] = t_apos
                            st.session_state["rec_termino_data"] = t_data
                            
                            st.session_state["edit_rec_freq"] = f_val
                            st.session_state["edit_rec_intervalo"] = i_val
                            st.session_state["edit_rec_tipo_fim"] = t_fim
                            st.session_state["edit_rec_vezes"] = t_apos
                            st.session_state["edit_rec_te_data"] = t_data
                            for dk, dv in d_dict.items():
                                st.session_state[f"edit_dia_{dk}"] = dv

                    try:
                        st.session_state["temp_data_reserva"] = datetime.strptime(dados_res.get("data_iso"), "%Y-%m-%d").date()
                    except Exception:
                        st.session_state["temp_data_reserva"] = date.today()
                    try:
                        st.session_state["temp_hora_ini"] = datetime.strptime(dados_res.get("hora_ini_iso"), "%H:%M:%S").time()
                    except Exception:
                        st.session_state["temp_hora_ini"] = time(9, 0)
                    try:
                        st.session_state["temp_hora_fim"] = datetime.strptime(dados_res.get("hora_fim_iso"), "%H:%M:%S").time()
                    except Exception:
                        st.session_state["temp_hora_fim"] = time(10, 0)
                    st.session_state["temp_id_sala"] = dados_res.get("id_sala_num")
                    st.session_state["reserva_opcoes_dados"] = {}
                    st.session_state["abrir_modal_detalhes"] = False
                    st.session_state["abrir_modal_editar"] = True
                    st.rerun()
            with col_b3:
                cancelar_esta = st.button("Cancelar Apenas Esta", type="secondary", use_container_width=True)
            with col_b4:
                cancelar_serie = st.button("Cancelar Série Completa", type="primary", use_container_width=True)

            # Executa exclusão de ocorrência única via Stored Procedure corporativa enviando cancelamento para anfitrião e participantes
            if cancelar_esta:
                conn = conectar_banco()
                if conn:
                    cursor = None
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT u.email, u.nome, a.uid, a.data_reserva, a.hora_inicio, a.participantes FROM reservas.Agendamentos a JOIN [aplicativos_db].[auth].[Usuarios] u ON a.id_usuario = u.id_usuario WHERE a.id_reserva = ?", (dados_res.get('id'),))
                        row_dono = cursor.fetchone()
                        email_alvo, nome_alvo, uid_persistido, dt_db, hi_db, part_db = (row_dono[0], row_dono[1], row_dono[2], row_dono[3], row_dono[4], row_dono[5]) if row_dono else (dados_usuario.get("email"), dados_usuario.get("nome"), None, None, None, None)
                        
                        # Chama Stored Procedure de exclusão única
                        cursor.execute("EXEC reservas.sp_ExcluirAgendamento ?", (dados_res.get('id'),))
                        conn.commit()
                        st.cache_data.clear()
                        
                        lista_bcc_cancel = [e.strip() for e in str(part_db or '').replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                        if email_alvo and dt_db and hi_db:
                            enviar_convite_outlook(
                                email_destino=email_alvo, titulo=dados_res.get('titulo_puro'),
                                data_reserva=dt_db, hora_ini=hi_db, hora_fim=datetime.strptime(dados_res.get('hora_fim_iso'), "%H:%M:%S").time(),
                                sala_nome=dados_res.get('sala'), descricao=dados_res.get('descricao'), nome_usuario=nome_alvo,
                                method="CANCEL", uid_evento=uid_persistido, participantes_bcc=lista_bcc_cancel
                            )
                        st.toast("✅ Ocorrência cancelada com sucesso!", icon="🗑️")
                        st.session_state["reserva_opcoes_dados"] = {}
                        st.session_state["abrir_modal_detalhes"] = False
                        st.rerun()
                    except Exception as err:
                        conn.rollback()
                        st.error(f"Erro ao cancelar ocorrência: {err}")
                    finally:
                        if cursor: cursor.close()
                        conn.close()

            # Executa exclusão da série completa via Stored Procedure corporativa enviando cancelamento para todos
            if cancelar_serie:
                conn = conectar_banco()
                if conn:
                    cursor = None
                    try:
                        cursor = conn.cursor()
                        serie_alvo = dados_res.get("id_serie")
                        cursor.execute("SELECT TOP 1 u.email, u.nome, a.uid, a.participantes FROM reservas.Agendamentos a LEFT JOIN [aplicativos_db].[auth].[Usuarios] u ON a.id_usuario = u.id_usuario WHERE a.id_serie = ?", (int(serie_alvo),))
                        row_serie = cursor.fetchone()
                        email_alvo, nome_alvo, uid_persistido, part_db = (row_serie[0], row_serie[1], row_serie[2], row_serie[3]) if row_serie else (dados_usuario.get("email"), dados_usuario.get("nome"), None, None)

                        # Chama Stored Procedure de exclusão da série
                        cursor.execute("EXEC reservas.sp_ExcluirSerie ?", (int(serie_alvo),))
                        conn.commit()
                        st.cache_data.clear()

                        lista_bcc_cancel_serie = [e.strip() for e in str(part_db or '').replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                        if email_alvo:
                            enviar_convite_outlook(
                                email_destino=email_alvo, titulo=dados_res.get('titulo_puro'),
                                data_reserva=datetime.strptime(dados_res.get('data_iso'), "%Y-%m-%d").date(),
                                hora_ini=datetime.strptime(dados_res.get('hora_ini_iso'), "%H:%M:%S").time(),
                                hora_fim=datetime.strptime(dados_res.get('hora_fim_iso'), "%H:%M:%S").time(),
                                sala_nome=dados_res.get('sala'), descricao=dados_res.get('descricao'), nome_usuario=nome_alvo,
                                method="CANCEL", uid_evento=uid_persistido, participantes_bcc=lista_bcc_cancel_serie
                            )
                        st.toast("✅ Série de reservas cancelada com sucesso!", icon="🗑️")
                        st.session_state["reserva_opcoes_dados"] = {}
                        st.session_state["abrir_modal_detalhes"] = False
                        st.rerun()
                    except Exception as err:
                        conn.rollback()
                        st.error(f"Erro ao cancelar série: {err}")
                    finally:
                        if cursor: cursor.close()
                        conn.close()
        else:
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button("Fechar", type="secondary", use_container_width=True):
                    st.session_state["reserva_opcoes_dados"] = {}
                    st.session_state["abrir_modal_detalhes"] = False
                    st.rerun()
            with col_b2:
                if st.button("Editar", type="primary", use_container_width=True):
                    st.session_state["edit_id_reserva"] = dados_res.get("id")
                    st.session_state["temp_titulo"] = dados_res.get("titulo_puro", "")
                    st.session_state["temp_desc"] = dados_res.get("descricao", "")
                    st.session_state["temp_participantes"] = participantes_salvos
                    st.session_state["recorrencia_ativo"] = is_rec_detalhes
                    st.session_state["temp_id_serie"] = dados_res.get("id_serie")
                    try:
                        st.session_state["temp_data_reserva"] = datetime.strptime(dados_res.get("data_iso"), "%Y-%m-%d").date()
                    except Exception:
                        st.session_state["temp_data_reserva"] = date.today()
                    try:
                        st.session_state["temp_hora_ini"] = datetime.strptime(dados_res.get("hora_ini_iso"), "%H:%M:%S").time()
                    except Exception:
                        st.session_state["temp_hora_ini"] = time(9, 0)
                    try:
                        st.session_state["temp_hora_fim"] = datetime.strptime(dados_res.get("hora_fim_iso"), "%H:%M:%S").time()
                    except Exception:
                        st.session_state["temp_hora_fim"] = time(10, 0)
                    st.session_state["temp_id_sala"] = dados_res.get("id_sala_num")
                    st.session_state["reserva_opcoes_dados"] = {}
                    st.session_state["abrir_modal_detalhes"] = False
                    st.session_state["abrir_modal_editar"] = True
                    st.rerun()
            with col_b3:
                if st.button("Cancelar", type="primary", use_container_width=True):
                    conn = conectar_banco()
                    if conn:
                        cursor = None
                        try:
                            cursor = conn.cursor()
                            cursor.execute("SELECT u.email, u.nome, a.uid, a.data_reserva, a.hora_inicio, a.participantes FROM reservas.Agendamentos a JOIN [aplicativos_db].[auth].[Usuarios] u ON a.id_usuario = u.id_usuario WHERE a.id_reserva = ?", (dados_res.get('id'),))
                            row_dono = cursor.fetchone()
                            email_alvo, nome_alvo, uid_persistido, dt_db, hi_db, part_db = (row_dono[0], row_dono[1], row_dono[2], row_dono[3], row_dono[4], row_dono[5]) if row_dono else (dados_usuario.get("email"), dados_usuario.get("nome"), None, None, None, None)
                            
                            # Chama Stored Procedure de exclusão única
                            cursor.execute("EXEC reservas.sp_ExcluirAgendamento ?", (dados_res.get('id'),))
                            conn.commit()
                            st.cache_data.clear()
                            
                            lista_bcc_cancel_simples = [e.strip() for e in str(part_db or '').replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                            if email_alvo and dt_db and hi_db:
                                enviar_convite_outlook(
                                    email_destino=email_alvo, titulo=dados_res.get('titulo_puro'),
                                    data_reserva=dt_db, hora_ini=hi_db, hora_fim=datetime.strptime(dados_res.get('hora_fim_iso'), "%H:%M:%S").time(),
                                    sala_nome=dados_res.get('sala'), descricao=dados_res.get('descricao'), nome_usuario=nome_alvo,
                                    method="CANCEL", uid_evento=uid_persistido, participantes_bcc=lista_bcc_cancel_simples
                                )
                            st.toast("✅ Reserva cancelada com sucesso!", icon="🗑️")
                            st.session_state["reserva_opcoes_dados"] = {}
                            st.session_state["abrir_modal_detalhes"] = False
                            st.rerun()
                        except Exception as err:
                            conn.rollback()
                            st.error(f"Erro ao cancelar: {err}")
                        finally:
                            if cursor: cursor.close()
                            conn.close()
    else:
        if st.button("Fechar", type="secondary", use_container_width=True):
            st.session_state["reserva_opcoes_dados"] = {}
            st.session_state["abrir_modal_detalhes"] = False
            st.rerun()

@st.dialog("Nova Reserva")
def modal_nova_reserva():
    """Modal nativo para criação de nova reserva com opções completas de recorrência e BCC."""
    df_salas = buscar_salas()
    opcoes_salas = {}
    if not df_salas.empty:
        for _, r_sala in df_salas.iterrows():
            opcoes_salas[f"{r_sala['nome']} ({r_sala['capacidade']} pessoas)"] = r_sala.to_dict()

    titulo = st.text_input("Título", value=st.session_state.get("temp_titulo", ""), key="modal_input_titulo")
    sala_selecionada = st.selectbox("Sala", list(opcoes_salas.keys()) if opcoes_salas else ["Sala 2 (4 pessoas)"], key="modal_input_sala")
    info_sala_sel = opcoes_salas.get(sala_selecionada, {"id_sala": 1, "nome": "Sala 2", "capacidade": 4, "localizacao": "", "equipamentos": "", "imagem_url": ""})

    img_mini_card = info_sala_sel.get("imagem_url", "") or "https://images.unsplash.com/photo-1497366216548-37526070297c?w=500&q=80"
    st.markdown(
        f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px; margin-bottom: 8px; display: flex; align-items: center; gap: 10px;">
            <img src="{img_mini_card}" style="width: 55px; height: 55px; object-fit: cover; border-radius: 4px;" />
            <div style="font-size: 10px; color: #475569;">{info_sala_sel.get('equipamentos', '')}</div>
        </div>
        """, unsafe_allow_html=True
    )

    data_padrao = st.session_state.get("temp_data_reserva", date.today())
    data_reserva = st.date_input("Data", value=data_padrao, format="DD/MM/YYYY", key="modal_input_data")
    
    c_inicio, c_fim = st.columns(2)
    hora_inicio = c_inicio.time_input("Início", value=st.session_state.get("temp_hora_ini", time(9, 0)), step=timedelta(minutes=30), key="modal_input_hora_ini")
    hora_termino = c_fim.time_input("Término", value=st.session_state.get("temp_hora_fim", time(10, 0)), step=timedelta(minutes=30), key="modal_input_hora_fim")
    
    # Campo para e-mails de participantes inseridos pelo usuário
    participantes_input = st.text_input("Participantes (E-mails separados por vírgula ou ponto e vírgula)", value="", key="modal_input_participantes", placeholder="ex: email1@repress.com.br, email2@repress.com.br")

    descricao = st.text_area("Descrição", value=st.session_state.get("temp_desc", ""), key="modal_input_desc")
    
    st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)
    recorrente_toggle = st.checkbox("🔄 Compromisso Recorrente (Série)", value=st.session_state.get("recorrencia_ativo", False), key="modal_chk_recorrencia")
    st.session_state["recorrencia_ativo"] = recorrente_toggle

    freq = "Semanal"
    intervalo = 1
    dias_semana_dict = {}
    tipo_fim = "Número de ocorrências"
    termino_apos = 10
    termino_data_val = date.today()

    if recorrente_toggle:
        c_freq1, c_freq2 = st.columns(2)
        freq = c_freq1.selectbox("Frequência", ["Diário", "Semanal", "Mensal", "Anual"], key="modal_rec_freq")
        st.session_state["rec_frequencia"] = freq
        intervalo = c_freq2.number_input("A cada (intervalo)", min_value=1, max_value=30, value=st.session_state.get("rec_intervalo_qtd", 1), key="modal_rec_intervalo")
        st.session_state["rec_intervalo_qtd"] = intervalo

        if freq == "Semanal":
            st.markdown("<div style='font-size:12px; font-weight:600; margin-top:4px;'>Repetir nos dias da semana:</div>", unsafe_allow_html=True)
            dias_labels = [
                ("domingo", "Domingo"), ("segunda-feira", "Segunda"), ("terça-feira", "Terça"),
                ("quarta-feira", "Quarta"), ("quinta-feira", "Quinta"), ("sexta-feira", "Sexta"), ("sábado", "Sábado")
            ]
            cols_dias = st.columns(7)
            for i, (key_d, label_d) in enumerate(dias_labels):
                with cols_dias[i]:
                    ativo_dia = st.checkbox(label_d[:3], value=st.session_state.get("rec_dias_semana", {}).get(key_d, i == 0), key=f"modal_dia_{key_d}")
                    dias_semana_dict[key_d] = ativo_dia
            st.session_state["rec_dias_semana"] = dias_semana_dict

        st.markdown("<div style='font-size:12px; font-weight:600; margin-top:6px;'>Término da Série:</div>", unsafe_allow_html=True)
        c_Fim1, c_Fim2 = st.columns(2)
        tipo_fim = c_Fim1.radio("Fim por", ["Número de ocorrências", "Data específica", "Sem data de término"], label_visibility="collapsed", key="modal_rec_tipo_fim")
        st.session_state["rec_tipo_fim"] = tipo_fim
        
        if tipo_fim == "Número de ocorrências":
            termino_apos = c_Fim2.number_input("Ocorrências", min_value=1, max_value=365, value=st.session_state.get("rec_termino_apos", 10), key="modal_rec_vezes")
            st.session_state["rec_termino_apos"] = termino_apos
        elif tipo_fim == "Data específica":
            termino_data_val = c_Fim2.date_input("Até a data", value=st.session_state.get("rec_termino_data", date.today() + timedelta(days=30)), format="DD/MM/YYYY", key="modal_rec_te_data")
            st.session_state["rec_termino_data"] = termino_data_val

    st.divider()
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        if st.button("Cancelar", type="secondary", use_container_width=True, key="btn_cancel_nova"):
            st.session_state["abrir_modal_nova"] = False
            st.rerun()
    with c_m2:
        if st.button("Salvar Reserva", type="primary", use_container_width=True, key="btn_save_nova"):
            if not titulo:
                st.toast("⚠️ Informe o título.", icon="⚠️")
            elif hora_inicio >= hora_termino:
                st.toast("⚠️ Horário inválido.", icon="⚠️")
            else:
                conn = conectar_banco()
                if conn:
                    cursor = conn.cursor()
                    try:
                        id_sala_escolhida = info_sala_sel.get("id_sala", 1)
                        nome_sala_string = info_sala_sel.get("nome", "Sala Oculta")
                        
                        datas_a_agendar = []
                        if not recorrente_toggle:
                            datas_a_agendar.append(data_reserva)
                        else:
                            atual_d = data_reserva
                            contador_ocorrencias = 0
                            max_seguranca = 500
                            dias_selecionados_map = st.session_state.get("rec_dias_semana", {})
                            nome_para_weekday = {"domingo": 6, "segunda-feira": 0, "terça-feira": 1, "quarta-feira": 2, "quinta-feira": 3, "sexta-feira": 4, "sábado": 5}
                            dias_validos_wd = [nome_para_weekday[d] for d, ativo in dias_selecionados_map.items() if ativo]
                            if not dias_validos_wd:
                                dias_validos_wd = [data_reserva.weekday()]
                            
                            while contador_ocorrencias < max_seguranca:
                                if tipo_fim == "Data específica" and atual_d > termino_data_val:
                                    break
                                if tipo_fim == "Número de ocorrências" and contador_ocorrencias >= termino_apos:
                                    break

                                incluir_data = False
                                dias_passados = (atual_d - data_reserva).days
                                semanas_passadas = dias_passados // 7

                                if freq == "Diário":
                                    if (dias_passados % intervalo) == 0: incluir_data = True
                                elif freq == "Semanal":
                                    if (semanas_passadas % intervalo) == 0 and atual_d.weekday() in dias_validos_wd: incluir_data = True
                                elif freq == "Mensal":
                                    if atual_d.day == data_reserva.day and (contador_ocorrencias % intervalo) == 0: incluir_data = True
                                elif freq == "Anual":
                                    if atual_d.month == data_reserva.month and atual_d.day == data_reserva.day: incluir_data = True

                                if incluir_data:
                                    datas_a_agendar.append(atual_d)
                                    contador_ocorrencias += 1

                                atual_d += timedelta(days=1)

                        conflitos_encontrados = []
                        for dt_teste in datas_a_agendar:
                            cursor.execute("SELECT data_reserva FROM reservas.Agendamentos WHERE id_sala = ? AND data_reserva = ? AND (hora_inicio < ?) AND (hora_termino > ?)", (id_sala_escolhida, dt_teste.strftime('%Y-%m-%d'), hora_termino.strftime("%H:%M:%S"), hora_inicio.strftime("%H:%M:%S")))
                            if cursor.fetchall():
                                conflitos_encontrados.append(dt_teste.strftime('%d/%m/%Y'))

                        if conflitos_encontrados:
                            st.toast(f"⚠️ Conflito de horário nas datas: {', '.join(conflitos_encontrados[:3])}...", icon="⚠️")
                        else:
                            id_serie_gerado = abs(hash(str(uuid.uuid4()))) % 2147483647 if (recorrente_toggle and len(datas_a_agendar) > 1) else None
                            uid_comum = str(uuid.uuid4())

                            # Executa a Procedure corporativa de inserção otimizada no banco de dados salvando os participantes
                            for dt_acao in datas_a_agendar:
                                uid_item = str(uuid.uuid4()) if recorrente_toggle else uid_comum
                                cursor.execute(
                                    "EXEC reservas.sp_InserirAgendamento ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
                                    (
                                        titulo[:255], 
                                        id_sala_escolhida, 
                                        dados_usuario.get("id_usuario", 1), 
                                        dt_acao, 
                                        hora_inicio.strftime("%H:%M:%S"), 
                                        hora_termino.strftime("%H:%M:%S"), 
                                        descricao[:2000], 
                                        1 if recorrente_toggle else 0, 
                                        id_serie_gerado, 
                                        uid_item,
                                        participantes_input
                                    )
                                )
                            conn.commit()
                            st.cache_data.clear()

                            # Processa lista de e-mails participantes para envio em Cópia Oculta (BCC)
                            lista_bcc = [e.strip() for e in participantes_input.replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                            if dados_usuario.get("email") and datas_a_agendar:
                                enviar_convite_outlook(
                                    email_destino=dados_usuario.get("email"), titulo=titulo, data_reserva=datas_a_agendar[0],
                                    hora_ini=hora_inicio, hora_fim=hora_termino, sala_nome=nome_sala_string,
                                    descricao=descricao, nome_usuario=dados_usuario.get("nome"), method="REQUEST", 
                                    is_recorrente=recorrente_toggle, freq=freq, interval=intervalo, dias_semana=dias_semana_dict,
                                    tipo_fim=tipo_fim, termino_apos=termino_apos, termino_data=termino_data_val, uid_evento=uid_comum,
                                    participantes_bcc=lista_bcc
                                )

                            st.toast("✅ Reserva(s) realizada(s) com sucesso!", icon="🎉")
                            st.session_state["abrir_modal_nova"] = False
                            st.rerun()
                    except Exception as err:
                        conn.rollback()
                        st.error(f"Erro: {err}")
                    finally:
                        cursor.close()
                        conn.close()

@st.dialog("Editar Reserva")
def modal_editar_reserva():
    """Modal nativo para edição de reserva existente pré-carregando participantes e dados salvos."""
    res_id = st.session_state.get("edit_id_reserva")
    df_salas = buscar_salas()
    opcoes_salas = {}
    sala_atual_idx = 0
    idx_contador = 0
    if not df_salas.empty:
        for _, r_sala in df_salas.iterrows():
            chave_sala = f"{r_sala['nome']} ({r_sala['capacidade']} pessoas)"
            opcoes_salas[chave_sala] = r_sala.to_dict()
            if r_sala['id_sala'] == st.session_state.get("temp_id_sala"):
                sala_atual_idx = idx_contador
            idx_contador += 1

    titulo = st.text_input("Título", value=st.session_state.get("temp_titulo", ""), key="edit_input_titulo")
    sala_selecionada = st.selectbox("Sala", list(opcoes_salas.keys()) if opcoes_salas else ["Sala 2 (4 pessoas)"], index=sala_atual_idx, key="edit_input_sala")
    info_sala_sel = opcoes_salas.get(sala_selecionada, {"id_sala": 1, "nome": "Sala 2", "capacidade": 4, "localizacao": "", "equipamentos": "", "imagem_url": ""})

    img_mini_card = info_sala_sel.get("imagem_url", "") or "https://images.unsplash.com/photo-1497366216548-37526070297c?w=500&q=80"
    st.markdown(
        f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px; margin-bottom: 8px; display: flex; align-items: center; gap: 10px;">
            <img src="{img_mini_card}" style="width: 55px; height: 55px; object-fit: cover; border-radius: 4px;" />
            <div style="font-size: 10px; color: #475569;">{info_sala_sel.get('equipamentos', '')}</div>
        </div>
        """, unsafe_allow_html=True
    )

    data_reserva = st.date_input("Data", value=st.session_state.get("temp_data_reserva", date.today()), format="DD/MM/YYYY", key="edit_input_data")
    
    c_inicio, c_fim = st.columns(2)
    hora_inicio = c_inicio.time_input("Início", value=st.session_state.get("temp_hora_ini", time(9, 0)), step=timedelta(minutes=30), key="edit_input_hora_ini")
    hora_termino = c_fim.time_input("Término", value=st.session_state.get("temp_hora_fim", time(10, 0)), step=timedelta(minutes=30), key="edit_input_hora_fim")
    
    # Pré-carrega o campo de participantes exatamente com os dados salvos anteriormente
    participantes_precarregados = st.session_state.get("temp_participantes", "")
    participantes_input_edit = st.text_input("Participantes (E-mails separados por vírgula ou ponto e vírgula)", value=participantes_precarregados, key="edit_input_participantes", placeholder="ex: email1@repress.com.br, email2@repress.com.br")

    descricao = st.text_area("Descrição", value=st.session_state.get("temp_desc", ""), key="edit_input_desc")
    
    st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)
    recorrente_toggle = st.checkbox("🔄 Compromisso Recorrente (Série)", value=st.session_state.get("recorrencia_ativo", False), key="edit_chk_recorrencia")
    st.session_state["recorrencia_ativo"] = recorrente_toggle

    freq = st.session_state.get("rec_frequencia", "Semanal")
    intervalo = st.session_state.get("rec_intervalo_qtd", 1)
    dias_semana_dict = st.session_state.get("rec_dias_semana", {})
    tipo_fim = st.session_state.get("rec_tipo_fim", "Número de ocorrências")
    termino_apos = st.session_state.get("rec_termino_apos", 10)
    termino_data_val = st.session_state.get("rec_termino_data", date.today())

    if recorrente_toggle:
        c_freq1, c_freq2 = st.columns(2)
        freq = c_freq1.selectbox("Frequência", ["Diário", "Semanal", "Mensal", "Anual"], index=["Diário", "Semanal", "Mensal", "Anual"].index(freq) if freq in ["Diário", "Semanal", "Mensal", "Anual"] else 1, key="edit_rec_freq")
        st.session_state["rec_frequencia"] = freq
        intervalo = c_freq2.number_input("A cada (intervalo)", min_value=1, max_value=30, value=intervalo, key="edit_rec_intervalo")
        st.session_state["rec_intervalo_qtd"] = intervalo

        if freq == "Semanal":
            st.markdown("<div style='font-size:12px; font-weight:600; margin-top:4px;'>Repetir nos dias da semana:</div>", unsafe_allow_html=True)
            dias_labels = [
                ("domingo", "Domingo"), ("segunda-feira", "Segunda"), ("terça-feira", "Terça"),
                ("quarta-feira", "Quarta"), ("quinta-feira", "Quinta"), ("sexta-feira", "Sexta"), ("sábado", "Sábado")
            ]
            cols_dias = st.columns(7)
            for i, (key_d, label_d) in enumerate(dias_labels):
                with cols_dias[i]:
                    ativo_dia = st.checkbox(label_d[:3], value=dias_semana_dict.get(key_d, i == 0), key=f"edit_dia_{key_d}")
                    dias_semana_dict[key_d] = ativo_dia
            st.session_state["rec_dias_semana"] = dias_semana_dict

        st.markdown("<div style='font-size:12px; font-weight:600; margin-top:6px;'>Término da Série:</div>", unsafe_allow_html=True)
        c_Fim1, c_Fim2 = st.columns(2)
        opcoes_fim_lista = ["Número de ocorrências", "Data específica", "Sem data de término"]
        idx_fim_default = opcoes_fim_lista.index(tipo_fim) if tipo_fim in opcoes_fim_lista else 0
        tipo_fim = c_Fim1.radio("Fim por", opcoes_fim_lista, index=idx_fim_default, label_visibility="collapsed", key="edit_rec_tipo_fim")
        st.session_state["rec_tipo_fim"] = tipo_fim
        
        if tipo_fim == "Número de ocorrências":
            termino_apos = c_Fim2.number_input("Ocorrências", min_value=1, max_value=365, value=termino_apos, key="edit_rec_vezes")
            st.session_state["rec_termino_apos"] = termino_apos
        elif tipo_fim == "Data específica":
            termino_data_val = c_Fim2.date_input("Até a data", value=termino_data_val, format="DD/MM/YYYY", key="edit_rec_te_data")
            st.session_state["rec_termino_data"] = termino_data_val

    st.divider()
    is_serie_ativa = recorrente_toggle and st.session_state.get("temp_id_serie") is not None

    if is_serie_ativa:
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            if st.button("Cancelar", type="secondary", use_container_width=True, key="btn_cancel_edit"):
                st.session_state["edit_id_reserva"] = None
                st.session_state["abrir_modal_editar"] = False
                st.rerun()
        with c_m2:
            salvar_esta = st.button("Salvar Apenas Esta", type="secondary", use_container_width=True, key="btn_save_esta_edit")
        with c_m3:
            salvar_serie = st.button("Salvar Série Completa", type="primary", use_container_width=True, key="btn_save_serie_edit")
        salvar_simples = False
    else:
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            if st.button("Cancelar", type="secondary", use_container_width=True, key="btn_cancel_edit"):
                st.session_state["edit_id_reserva"] = None
                st.session_state["abrir_modal_editar"] = False
                st.rerun()
        with c_m2:
            salvar_simples = st.button("Salvar Alterações", type="primary", use_container_width=True, key="btn_save_edit")
        salvar_esta = False
        salvar_serie = False

    # Executa a Stored Procedure corporativa para atualizar apenas um agendamento único, enviando atualizações para todos
    if salvar_simples or salvar_esta:
        if not titulo:
            st.toast("⚠️ Informe o título.", icon="⚠️")
        elif hora_inicio >= hora_termino:
            st.toast("⚠️ Horário inválido.", icon="⚠️")
        else:
            conflitos = verificar_conflito_edicao(info_sala_sel.get("id_sala"), data_reserva, hora_inicio, hora_termino, res_id)
            if conflitos:
                st.toast("⚠️ A sala já está reservada neste horário por outro agendamento!", icon="⚠️")
            else:
                conn = conectar_banco()
                if conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "EXEC reservas.sp_AtualizarAgendamento ?, ?, ?, ?, ?, ?, ?, ?",
                            (
                                res_id,
                                titulo[:255],
                                info_sala_sel.get("id_sala"),
                                data_reserva,
                                hora_inicio.strftime("%H:%M:%S"),
                                hora_termino.strftime("%H:%M:%S"),
                                descricao[:2000],
                                participantes_input_edit
                            )
                        )
                        conn.commit()
                        st.cache_data.clear()
                        
                        lista_bcc_edit = [e.strip() for e in participantes_input_edit.replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                        cursor.execute("SELECT u.email, u.nome, a.uid FROM reservas.Agendamentos a JOIN [aplicativos_db].[auth].[Usuarios] u ON a.id_usuario = u.id_usuario WHERE a.id_reserva = ?", (res_id,))
                        row_usr = cursor.fetchone()
                        if row_usr:
                            enviar_convite_outlook(
                                email_destino=row_usr[0], titulo=titulo, data_reserva=data_reserva,
                                hora_ini=hora_inicio, hora_fim=hora_termino, sala_nome=info_sala_sel.get("nome"),
                                descricao=descricao, nome_usuario=row_usr[1], method="REQUEST", uid_evento=row_usr[2],
                                participantes_bcc=lista_bcc_edit, is_atualizacao=True
                            )
                        
                        st.toast("✅ Reserva atualizada com sucesso!", icon="🎉")
                        st.session_state["edit_id_reserva"] = None
                        st.session_state["abrir_modal_editar"] = False
                        st.session_state["reserva_opcoes_dados"] = {}
                        st.rerun()
                    except Exception as err:
                        conn.rollback()
                        st.error(f"Erro ao atualizar: {err}")
                    finally:
                        cursor.close()
                        conn.close()

    # Executa a Stored Procedure corporativa para atualizar a série completa, enviando atualizações para todos
    if salvar_serie:
        if not titulo:
            st.toast("⚠️ Informe o título.", icon="⚠️")
        elif hora_inicio >= hora_termino:
            st.toast("⚠️ Horário inválido.", icon="⚠️")
        else:
            conn = conectar_banco()
            if conn:
                cursor = conn.cursor()
                try:
                    serie_alvo = st.session_state.get("temp_id_serie")
                    try:
                        data_original = datetime.strptime(st.session_state.get("reserva_opcoes_dados", {}).get("data_iso", str(data_reserva)), "%Y-%m-%d").date()
                        delta_dias = (data_reserva - data_original).days
                    except Exception:
                        delta_dias = 0

                    cursor.execute(
                        "EXEC reservas.sp_AtualizarSerie ?, ?, ?, ?, ?, ?, ?, ?",
                        (
                            int(serie_alvo),
                            titulo[:255],
                            info_sala_sel.get("id_sala"),
                            delta_dias,
                            hora_inicio.strftime("%H:%M:%S"),
                            hora_termino.strftime("%H:%M:%S"),
                            descricao[:2000],
                            participantes_input_edit
                        )
                    )
                    conn.commit()
                    st.cache_data.clear()

                    lista_bcc_serie = [e.strip() for e in participantes_input_edit.replace(";", ",").replace(" ", ",").split(",") if e.strip() and "@" in e]

                    cursor.execute("SELECT TOP 1 u.email, u.nome, a.uid FROM reservas.Agendamentos a LEFT JOIN [aplicativos_db].[auth].[Usuarios] u ON a.id_usuario = u.id_usuario WHERE id_serie = ?", (int(serie_alvo),))
                    row_usr_serie = cursor.fetchone()
                    if row_usr_serie and row_usr_serie[0]:
                        enviar_convite_outlook(
                            email_destino=row_usr_serie[0], titulo=titulo, data_reserva=data_reserva,
                            hora_ini=hora_inicio, hora_fim=hora_termino, sala_nome=info_sala_sel.get("nome"),
                            descricao=descricao, nome_usuario=row_usr_serie[1] or "Usuário", method="REQUEST",
                            is_recorrente=True, freq=freq, interval=intervalo, dias_semana=dias_semana_dict,
                            tipo_fim=tipo_fim, termino_apos=termino_apos, termino_data=termino_data_val,
                            uid_evento=row_usr_serie[2], participantes_bcc=lista_bcc_serie, is_atualizacao=True
                        )

                    st.toast("✅ Série de reservas atualizada com sucesso!", icon="🎉")
                    st.session_state["edit_id_reserva"] = None
                    st.session_state["abrir_modal_editar"] = False
                    st.session_state["reserva_opcoes_dados"] = {}
                    st.rerun()
                except Exception as err:
                    conn.rollback()
                    st.error(f"Erro ao atualizar série: {err}")
                finally:
                    cursor.close()
                    conn.close()

# =========================================================================================
# 10. ABA 1: CALENDÁRIO E GERENCIAMENTO DE AGENDAMENTOS
# =========================================================================================
with aba_calendario:
    if st.session_state.get("abrir_modal_detalhes", False):
        modal_detalhes_reserva()

    if st.session_state.get("abrir_modal_nova", False):
        modal_nova_reserva()

    if st.session_state.get("abrir_modal_editar", False) or st.session_state.get("edit_id_reserva") is not None:
        modal_editar_reserva()

    if CALENDAR_DISPONIVEL:
        df_salas_legenda = buscar_salas()
        if not df_salas_legenda.empty:
            html_legenda_header = "<div style='display: flex; justify-content: center; gap: 20px; align-items: center; font-size: 13px;'>"
            for _, r in df_salas_legenda.iterrows():
                cor_sala = r.get("cor") if pd.notna(r.get("cor")) and r.get("cor") else "#3788d8"
                nome_sala = r["nome"]
                html_legenda_header += f'<div style="display: flex; align-items: center; gap: 6px;"><span style="width: 9px; height: 9px; background-color: {cor_sala}; border-radius: 50%; display: inline-block;"></span><span style="font-weight: 500; color: #374151;">{nome_sala}</span></div>'
            html_legenda_header += "</div>"

            st.markdown(
                f"""
                <div style="position: relative; margin-bottom: -56px;">
                    <div style="position: absolute; top: 16px; left: 50%; transform: translateX(-50%); z-index: 10; pointer-events: auto; display: flex; align-items: center; justify-content: center; height: 40px;">
                        {html_legenda_header}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        df_agendamentos = buscar_agendamentos()

        eventos_calendario = [] 
        for _, row in df_agendamentos.iterrows():
            cor_fundo = row.get("cor") if pd.notna(row.get("cor")) and row.get("cor") else "#3788d8"
            cor_texto_escura = escurecer_cor(cor_fundo)
            nome_usr = row.get("usuario_nome") if pd.notna(row.get("usuario_nome")) and row.get("usuario_nome") else "Desconhecido"
            
            is_rec_evento = int(row["recorrente"]) in [1, True, "1"] if pd.notna(row["recorrente"]) else False
            prefixo_rec = "🔄 " if is_rec_evento else ""
            
            str_inicio = f"{row['data_reserva']}T{row['hora_inicio']}"
            str_fim = f"{row['data_reserva']}T{row['hora_termino']}"
            
            val_data = row.get("data_reserva")
            data_str_pura = val_data.strftime("%d/%m/%Y") if hasattr(val_data, "strftime") else str(val_data)
            ini_str_puro = row.get("hora_inicio").strftime("%H:%M") if hasattr(row.get("hora_inicio"), "strftime") else str(row.get("hora_inicio"))[:5]
            fim_str_puro = row.get("hora_termino").strftime("%H:%M") if hasattr(row.get("hora_termino"), "strftime") else str(row.get("hora_termino"))[:5]
            participantes_str = str(row.get("participantes", "")) if pd.notna(row.get("participantes")) else ""

            eventos_calendario.append({
                "id": str(row["id_reserva"]), 
                "title": f"{prefixo_rec}{row['titulo']}",
                "start": str_inicio,
                "end": str_fim,
                "backgroundColor": cor_fundo,
                "borderColor": cor_fundo,
                "textColor": cor_texto_escura,
                "extendedProps": { 
                    "sala": row["sala_nome"], "descricao": str(row["descricao"]) if pd.notna(row["descricao"]) else "", 
                    "id_usuario": row["id_usuario"], "titulo_puro": row["titulo"], "nome_usuario": nome_usr, 
                    "data_formatada": data_str_pura, "data_iso": str(row["data_reserva"]), 
                    "hora_ini_formatada": ini_str_puro, "hora_fim_formatada": fim_str_puro,
                    "hora_ini_iso": str(row["hora_inicio"]), "hora_fim_iso": str(row["hora_termino"]), 
                    "id_sala_num": row["id_sala"], "recorrente": int(row["recorrente"]) if pd.notna(row["recorrente"]) else 0,
                    "id_serie": int(row["id_serie"]) if pd.notna(row["id_serie"]) else None, "uid": str(row["uid"]) if pd.notna(row["uid"]) else "",
                    "participantes": participantes_str
                }
            })
        
        calendar_options = {
            "editable": False,
            "selectable": True, 
            "headerToolbar": {"left": "today prev,next title", "center": "", "right": "timeGridDay,timeGridWeek,dayGridMonth"},
            "initialView": "timeGridWeek", 
            "locale": "pt-br", 
            "buttonText": {
                "today": "Hoje",
                "day": "Dia",
                "week": "Semana",
                "month": "Mês"
            },
            "slotLabelFormat": {
                "hour": "2-digit",
                "minute": "2-digit",
                "omitZeroMinute": False,
                "meridiem": False,
                "hour12": False
            },
            "slotMinTime": "07:00:00", 
            "slotMaxTime": "24:00:00",
            "allDaySlot": False, 
            "height": "656px"
        }
        
        cal_result = calendar(
            events=eventos_calendario,
            options=calendar_options,
            custom_css=CSS_CALENDARIO_AZUL,
            key="reserva_calendar_full_width"
        )
        
        if cal_result:
            tipo_acao = cal_result.get("callback")
            sig_atual = str(cal_result)
            
            if tipo_acao and sig_atual != st.session_state.get("ultimo_cal_sig"):
                st.session_state["ultimo_cal_sig"] = sig_atual
                
                if tipo_acao == "eventClick":
                    evt = cal_result.get("eventClick", {}).get("event", {})
                    evt_id = evt.get("id")
                    if evt_id:
                        ext_props = evt.get("extendedProps", {})
                        st.session_state["reserva_opcoes_dados"] = {
                            "id": evt_id, "titulo": ext_props.get("titulo_puro"), "descricao": ext_props.get("descricao"),
                            "nome": ext_props.get("nome_usuario"), "sala": ext_props.get("sala"), "data": ext_props.get("data_formatada"), 
                            "data_iso": ext_props.get("data_iso"), "inicio": ext_props.get("hora_ini_formatada"), "termino": ext_props.get("hora_fim_formatada"), 
                            "hora_ini_iso": ext_props.get("hora_ini_iso"), "hora_fim_iso": ext_props.get("hora_fim_iso"),
                            "id_usuario": ext_props.get("id_usuario"), "titulo_puro": ext_props.get("titulo_puro"),
                            "id_sala_num": ext_props.get("id_sala_num"), "recorrente": ext_props.get("recorrente"),
                            "id_serie": ext_props.get("id_serie"), "uid": ext_props.get("uid"),
                            "participantes": ext_props.get("participantes")
                        }
                        st.session_state["abrir_modal_detalhes"] = True
                        st.session_state["abrir_modal_nova"] = False
                        st.session_state["abrir_modal_editar"] = False
                        st.rerun()
                elif tipo_acao in ["select", "dateClick"]:
                    dados_clique = cal_result.get(tipo_acao, {})
                    start_str = dados_clique.get("start", dados_clique.get("date", ""))
                    if start_str:
                        try:
                            dt_convertido = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            if dt_convertido.tzinfo is not None:
                                dt_convertido = dt_convertido.astimezone().replace(tzinfo=None)
                        except Exception:
                            dt_convertido = datetime.strptime(start_str[:19], "%Y-%m-%dT%H:%M:%S")
                            
                        st.session_state["temp_data_reserva"] = dt_convertido.date()
                        st.session_state["temp_hora_ini"] = dt_convertido.time()
                        st.session_state["temp_hora_fim"] = (dt_convertido + timedelta(hours=1)).time()
                        st.session_state["abrir_modal_nova"] = True
                        st.session_state["abrir_modal_detalhes"] = False
                        st.session_state["abrir_modal_editar"] = False
                        st.rerun()
    else:
        st.warning("⚠️ O módulo 'streamlit-calendar' precisa ser instalado no ambiente virtual do servidor.")

# =========================================================================================
# 11. ABA 2: GERENCIAMENTO DE SALAS (EXCLUSIVO PARA ADMINISTRADORES)
# =========================================================================================
if aba_gerenciar is not None:
    with aba_gerenciar:
        st.markdown("<h2 style='margin:0; padding:0; font-weight:700; color:#111827; font-size: 1.4rem;'>Gerenciamento de Salas</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6B7280; font-size:13px; margin-top:2px; margin-bottom:10px;'>Adicione ou edite os espaços disponíveis para reserva.</p>", unsafe_allow_html=True)
        
        if st.button("+  Adicionar Sala", type="primary", key="btn_abrir_modal_add"):
            st.session_state["modal_sala_id"] = None
            st.session_state["modal_sala_aberto"] = True
            st.rerun()

        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        if st.session_state["modal_sala_aberto"]:
            with st.container(border=True):
                titulo_modal = "Adicionar Nova Sala" if st.session_state["modal_sala_id"] is None else "Editar Sala"
                col_m_head, col_m_close = st.columns([8, 1])
                col_m_head.markdown(f"<h3 style='margin:0;'>{titulo_modal}</h3>", unsafe_allow_html=True)
                if col_m_close.button("✕", key="btn_close_modal"):
                    st.session_state["modal_sala_aberto"] = False
                    st.rerun()
                
                dados_edit = {}
                if st.session_state["modal_sala_id"] is not None:
                    df_temp_salas = buscar_salas()
                    df_temp_filt = df_temp_salas[df_temp_salas["id_sala"] == st.session_state["modal_sala_id"]]
                    if not df_temp_filt.empty: dados_edit = df_temp_filt.iloc[0].to_dict()

                st.markdown("<label style='font-weight:600; font-size:13px; color:#374151;'>Imagem da Sala</label>", unsafe_allow_html=True)
                arquivo_imagem = st.file_uploader("Escolher arquivo", type=["jpg", "jpeg", "png", "webp"], key="upload_img_sala", label_visibility="collapsed")
                
                str_imagem_b64 = dados_edit.get("imagem_url", "")
                if arquivo_imagem is not None:
                    try:
                        img = Image.open(arquivo_imagem)
                        img = ImageOps.exif_transpose(img) 
                        img.thumbnail((400, 400)) 
                        if img.mode != "RGB": img = img.convert("RGB")
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=60, optimize=True) 
                        str_imagem_b64 = f"data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
                    except Exception:
                        str_imagem_b64 = f"data:{arquivo_imagem.type};base64," + base64.b64encode(arquivo_imagem.read()).decode("utf-8")

                nome_sala_val = st.text_input("Nome da Sala", value=dados_edit.get("nome", ""), key="modal_input_nome")
                capacidade_val = st.number_input("Capacidade", min_value=1, max_value=100, value=int(dados_edit.get("capacidade", 4)), key="modal_input_cap")
                localizacao_val = st.text_input("Localização (Opcional)", value=dados_edit.get("localizacao", ""), key="modal_input_loc")
                descricao_val = st.text_area("Descrição (Opcional)", value=dados_edit.get("equipamentos", ""), key="modal_input_desc")

                c_mod_space, c_mod_canc, c_mod_salvar = st.columns([3, 1, 1])
                if c_mod_canc.button("Cancelar", key="btn_cancelar_modal_form", type="secondary"):
                    st.session_state["modal_sala_aberto"] = False
                    st.rerun()
                if c_mod_salvar.button("Salvar Sala", key="btn_salvar_modal_form", type="primary"):
                    if not nome_sala_val.strip():
                        st.toast("⚠️ Informe o nome da sala.", icon="⚠️")
                    else:
                        if salvar_sala_banco(id_sala=st.session_state["modal_sala_id"], nome=nome_sala_val, capacidade=capacidade_val, localizacao=localizacao_val, equipamentos=descricao_val, imagem_url=str_imagem_b64):
                            st.session_state["modal_sala_aberto"] = False
                            st.toast("✅ Sala salva com sucesso!", icon="🎉")
                            st.rerun()
            st.divider()

        df_salas_cadastradas = buscar_salas()
        if not df_salas_cadastradas.empty:
            num_colunas_grade = max(len(df_salas_cadastradas), 6)
            colunas_grade = st.columns(num_colunas_grade)
            for idx_sala, row_sala in df_salas_cadastradas.iterrows():
                coluna_atual = colunas_grade[idx_sala % num_colunas_grade]
                with coluna_atual:
                    with st.container(border=True):
                        img_url = row_sala.get("imagem_url", "") or "https://images.unsplash.com/photo-1497366216548-37526070297c?w=500&q=80"
                        st.image(img_url, use_container_width=True)
                        st.markdown(f"<div class='sala-card-title'>{row_sala['nome']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='sala-card-location'>📍 {row_sala.get('localizacao', 'CPD')}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='capacidade-badge'>👥 {row_sala.get('capacidade', 4)} pessoas</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='sala-card-desc'>{row_sala.get('equipamentos', 'Sem descrição.')}</div>", unsafe_allow_html=True)
                        st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #F3F4F6;' />", unsafe_allow_html=True)
                        
                        col_acc_edit, col_color, col_acc_del = st.columns([1, 1, 1])
                        with col_acc_edit:
                            if st.button("✏️", key=f"btn_edit_card_{row_sala['id_sala']}", help="Editar"):
                                st.session_state["modal_sala_id"] = row_sala['id_sala']
                                st.session_state["modal_sala_aberto"] = True
                                st.rerun()
                        with col_color:
                            cor_banco = row_sala.get("cor") if pd.notna(row_sala.get("cor")) and row_sala.get("cor") else "#3788d8"
                            nova_cor = st.color_picker("Cor", value=cor_banco, key=f"color_picker_{row_sala['id_sala']}", label_visibility="collapsed")
                            if nova_cor.lower() != cor_banco.lower():
                                conn_cor = conectar_banco()
                                if conn_cor:
                                    cursor_cor = None
                                    try:
                                        cursor_cor = conn_cor.cursor()
                                        cursor_cor.execute("UPDATE reservas.Salas SET cor = ? WHERE id_sala = ?", (nova_cor, row_sala['id_sala']))
                                        conn_cor.commit()
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar nova cor: {e}")
                                    finally:
                                        if cursor_cor: cursor_cor.close()
                                        conn_cor.close()
                        with col_acc_del:
                            if st.button("🗑️", key=f"btn_del_card_{row_sala['id_sala']}", help="Remover Sala"):
                                if remover_sala_banco(row_sala['id_sala']):
                                    st.toast(f"🗑️ Sala '{row_sala['nome']}' removida com sucesso.", icon="🗑️")
                                    st.rerun()
        else:
            st.info("Nenhuma sala cadastrada no momento. Clique no botão '+ Adicionar Sala' acima para começar.")