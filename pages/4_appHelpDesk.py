# ==============================================================================
# APLICATIVO: GESTÃO DE CHAMADOS TI (4_appHelpDesk.py) - OTIMIZADO COM VIEWS E PROCS
# ==============================================================================
import os                          # Importa utilitários do sistema operacional para caminhos e variáveis
import base64                      # Importa codificação Base64 para manipulação de imagens em anexo
import pandas as pd                # Importa Pandas para manipulação de DataFrames e dados tabulares
import pyodbc                      # Importa PyODBC para conexão com o Microsoft SQL Server
import streamlit as st             # Importa Streamlit para construção da interface web interativa
from datetime import datetime, timedelta # Importa manipulação de datas e intervalos de tempo
import streamlit.components.v1 as components # Importa componentes HTML customizados (iframes para cronômetros e cards)
import requests                    # Importa Requests para requisições HTTP à API do Resend
from dotenv import load_dotenv, find_dotenv # Importa gerenciadores de variáveis de ambiente (.env)
from database import obter_conexao_principal # Importa a função centralizada de conexão ODBC do Portal Repress

# Bloco protegido para importar o editor de texto rico visual (Quill), com fallback seguro para text_area padrão
try:
    from streamlit_quill import st_quill
    TEM_QUILL = True
except ImportError:
    TEM_QUILL = False

# ==============================================================================
# 2. CONFIGURAÇÕES INICIAIS DA PÁGINA E DESIGN SYSTEM (STYLES.PY)
# ==============================================================================
st.set_page_config(
    page_title="🖥️ Gestão de Chamados TI", 
    layout="wide"
)

# Importa e injeta a folha de estilos centralizada do portal
from styles import injetar_estilo_global
injetar_estilo_global()

# ==============================================================================
# 3. VARIÁVEIS DE SESSÃO (SESSION STATE)
# ==============================================================================
if "alertas_sistema" not in st.session_state:
    st.session_state.alertas_sistema = [] # Inicializa lista de alertas globais do sistema

if "chamado_selecionado" not in st.session_state:
    st.session_state.chamado_selecionado = None # Inicializa ID do chamado atualmente em foco na tela de detalhes

if "form_reset_counter" not in st.session_state:
    st.session_state.form_reset_counter = 0 # Contador numérico para limpeza de formulário de abertura de chamados

if "comment_reset_counter" not in st.session_state:
    st.session_state.comment_reset_counter = 0 # Contador numérico para limpeza de campo de comentários na linha do tempo

if "mostrar_sucesso_abertura" not in st.session_state:
    st.session_state.mostrar_sucesso_abertura = False # Flag booleana de controle de sucesso na abertura de chamados

# ==============================================================================
# 4. EXIBIÇÃO DE NOTIFICAÇÕES GLOBAIS (TOASTS E ERROS)
# ==============================================================================
if st.session_state.alertas_sistema:
    for alerta in st.session_state.alertas_sistema:
        if alerta['tipo'] == 'erro':
            st.error(alerta['msg'])
        else:
            st.toast(alerta['msg'], icon="📩")
    st.session_state.alertas_sistema.clear()

# ==============================================================================
# 5. CARREGAMENTO DE VARIÁVEIS DE AMBIENTE (.ENV) PARA O RESEND API
# ==============================================================================
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(diretorio_atual, ".env")
caminho_env_txt = os.path.join(diretorio_atual, ".env.txt")

# Limpa variáveis de ambiente pré-existentes para garantir leitura limpa
for k in ["RESEND_API_KEY", "RESEND_API_KEY_Chamados"]:
    if k in os.environ:
        del os.environ[k]

load_dotenv(dotenv_path=caminho_env, override=True)
if not os.getenv("RESEND_API_KEY") and not os.getenv("RESEND_API_KEY_Chamados"):
    load_dotenv(dotenv_path=caminho_env_txt, override=True)
if not os.getenv("RESEND_API_KEY") and not os.getenv("RESEND_API_KEY_Chamados"):
    load_dotenv(find_dotenv(usecwd=True), override=True)

RESEND_API_KEY = (
    os.getenv("RESEND_API_KEY_Chamados") or 
    os.getenv("RESEND_API_KEY", "")
).strip()

EMAIL_REMETENTE = "Suporte TI <suporte@ti.repress.com.br>"

# ==============================================================================
# 6. FUNÇÃO DE DISPARO DE E-MAILS (RESEND API REST COM SUPORTE A BCC)
# ==============================================================================
def enviar_email_resend(destinatarios, assunto, corpo_html, bcc=None):
    """Função responsável por enviar e-mails via API REST do Resend com suporte a BCC e tratamento de erros."""
    if not RESEND_API_KEY or RESEND_API_KEY.strip() == "":
        st.session_state.alertas_sistema.append({
            'tipo': 'erro', 
            'msg': "⚠️ Arquivo .env não carregou ou 'RESEND_API_KEY_Chamados' está vazia/ausente."
        })
        return

    # Normaliza destinatários para lista e remove vazios/duplicados
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    destinatarios = list(set([email for email in destinatarios if email and str(email).strip() != ""]))
    if not destinatarios:
        return

    url_resend = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": EMAIL_REMETENTE,
        "to": destinatarios,
        "subject": assunto,
        "html": corpo_html
    }

    # Adiciona suporte otimizado a cópia oculta (BCC) para notificações em lote (ex: equipe administrativa)
    if bcc:
        if isinstance(bcc, str):
            bcc = [bcc]
        bcc = list(set([email for email in bcc if email and str(email).strip() != ""]))
        if bcc:
            payload["bcc"] = bcc

    try:
        resposta = requests.post(url_resend, json=payload, headers=headers, timeout=10)
        if resposta.status_code == 403:
            st.session_state.alertas_sistema.append({
                'tipo': 'erro', 
                'msg': f"❌ ERRO 403: A API Key configurada não tem permissão para disparar em nome do domínio 'ti.repress.com.br'."
            })
        elif resposta.status_code not in [200, 201]:
            st.session_state.alertas_sistema.append({
                'tipo': 'erro', 
                'msg': f"❌ Erro da API Resend ({resposta.status_code}): {resposta.text}"
            })
        else:
            st.session_state.alertas_sistema.append({
                'tipo': 'sucesso', 
                'msg': f"E-mail enviado com sucesso!"
            })
    except requests.exceptions.RequestException as erro_conexao:
        st.session_state.alertas_sistema.append({
            'tipo': 'erro', 
            'msg': f"❌ Falha de Conexão com o Resend: {erro_conexao}"
        })

# ==============================================================================
# 7. PROCESSAMENTO DE IMAGENS E CÁLCULO DE ALTURA DE CONTAINER
# ==============================================================================
def converter_imagem_para_base64_html(arquivo_upload):
    """Converte a imagem enviada via uploader para Base64 e constrói a tag HTML com classe de thumbnail."""
    if arquivo_upload is not None:
        bytes_imagem = arquivo_upload.read()
        base64_encoded = base64.b64encode(bytes_imagem).decode('utf-8')
        mime_type = arquivo_upload.type
        html_thumb = f'<br/><img src="data:{mime_type};base64,{base64_encoded}" class="img-anexo-thumb" alt="Anexo (Clique para ampliar)"/>'
        return html_thumb, f"data:{mime_type};base64,{base64_encoded}"
    return "", None

def calcular_altura_html(conteudo_html):
    """Estipula a altura dinâmica do iframe do Streamlit evitando barras de rolagem desnecessárias."""
    if "<img" in str(conteudo_html):
        return 260
    return 130

# ==============================================================================
# 8. FUNÇÕES DE BANCO DE DADOS (COM CACHE E PROCEDURES OTIMIZADAS)
# ==============================================================================
def conectar_banco():
    """Conecta ao SQL Server utilizando a função centralizada do database.py com codificação latin1."""
    conn = obter_conexao_principal()
    if not conn:
        return None
    try:
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin1')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='latin1')
        conn.setencoding(encoding='latin1')
    except Exception:
        pass
    return conn

@st.cache_data(ttl=60, show_spinner=False)
def buscar_emails_atendentes():
    """Busca o e-mail de todos os administradores ativos com cache de 60 segundos."""
    conn = conectar_banco()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        query = "SELECT email FROM auth.Usuarios WHERE nivel = 'admin' AND ativo = 1"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()

def buscar_email_atendente_por_nome(nome_atendente):
    """Busca o e-mail de um administrador específico pelo seu nome cadastrado."""
    conn = conectar_banco()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        query = "SELECT email FROM auth.Usuarios WHERE nome = ? AND nivel = 'admin' AND ativo = 1"
        cursor.execute(query, (nome_atendente,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return None
    except Exception:
        return None
    finally:
        cursor.close()
        conn.close()

def garantir_tabela_sla():
    """Cria as tabelas necessárias de SLA, setores e tipos de serviço caso não existam no banco."""
    conn = conectar_banco()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        cursor.execute("""
            IF NOT OBJECT_ID('dbo.Politicas_SLA', 'U') IS NOT NULL
            BEGIN
                CREATE TABLE dbo.Politicas_SLA (
                    ID INT IDENTITY(1,1) PRIMARY KEY,
                    Prioridade VARCHAR(50) NOT NULL,
                    SLA_Resposta_Horas INT NOT NULL,
                    SLA_Solucao_Horas INT NOT NULL,
                    Descricao VARCHAR(255) NULL
                );
                INSERT INTO dbo.Politicas_SLA (Prioridade, SLA_Resposta_Horas, SLA_Solucao_Horas, Descricao) VALUES 
                ('Crítica', 1, 4, 'Chamados críticos com impacto total'),
                ('Alta', 2, 8, 'Chamados de alta prioridade'),
                ('Média', 4, 24, 'Chamados de prioridade padrão'),
                ('Baixa', 8, 48, 'Chamados de baixa urgência');
            END
        """)
        cursor.execute("""
            IF NOT EXISTS (
                SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'Chamados' AND COLUMN_NAME = 'Data_Primeira_Resposta'
            )
            BEGIN
                ALTER TABLE dbo.Chamados ADD Data_Primeira_Resposta DATETIME NULL;
            END
        """)
        cursor.execute("""
            IF NOT OBJECT_ID('dbo.Chamados_Setores', 'U') IS NOT NULL
            BEGIN
                CREATE TABLE dbo.Chamados_Setores (
                    ID INT IDENTITY(1,1) PRIMARY KEY,
                    Nome VARCHAR(100) NOT NULL UNIQUE
                );
                INSERT INTO dbo.Chamados_Setores (Nome) VALUES 
                ('Tecnologia e Dados'), ('RH'), ('Financeiro'), ('Operações');
            END
        """)
        cursor.execute("""
            IF NOT OBJECT_ID('dbo.Chamados_Tipos_Servico', 'U') IS NOT NULL
            BEGIN
                CREATE TABLE dbo.Chamados_Tipos_Servico (
                    ID INT IDENTITY(1,1) PRIMARY KEY,
                    Nome VARCHAR(100) NOT NULL UNIQUE
                );
                INSERT INTO dbo.Chamados_Tipos_Servico (Nome) VALUES 
                ('Suporte Técnico'), ('Nova Funcionalidade'), ('Dúvida'), ('Acesso');
            END
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        cursor.close()
        conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def obter_matriz_sla():
    """Busca as regras de SLA do banco com cache de 60 segundos."""
    garantir_tabela_sla()
    conn = conectar_banco()
    if not conn:
        return pd.DataFrame({
            'Prioridade': ['Crítica', 'Alta', 'Média', 'Baixa'],
            'SLA_Resposta_Horas': [1, 2, 4, 8],
            'SLA_Solucao_Horas': [4, 8, 24, 48],
            'Descricao': ['Crítico', 'Alta', 'Média', 'Baixa']
        })
    try:
        query = "SELECT Prioridade, SLA_Resposta_Horas, SLA_Solucao_Horas, Descricao FROM dbo.Politicas_SLA"
        df_sla = pd.read_sql(query, conn)
        if not df_sla.empty:
            return df_sla
    except Exception:
        pass
    finally:
        conn.close()
    return pd.DataFrame({
        'Prioridade': ['Crítica', 'Alta', 'Média', 'Baixa'],
        'SLA_Resposta_Horas': [1, 2, 4, 8],
        'SLA_Solucao_Horas': [4, 8, 24, 48],
        'Descricao': ['Crítico', 'Alta', 'Média', 'Baixa']
    })

@st.cache_data(ttl=60, show_spinner=False)
def obter_lista_setores():
    """Busca a lista de setores ativos no banco com cache."""
    garantir_tabela_sla()
    conn = conectar_banco()
    if not conn:
        return ["Tecnologia e Dados", "RH", "Financeiro", "Operações"]
    try:
        query = "SELECT Nome FROM dbo.Chamados_Setores ORDER BY ID ASC"
        df_setores = pd.read_sql(query, conn)
        if not df_setores.empty:
            return df_setores['Nome'].tolist()
    except Exception:
        pass
    finally:
        conn.close()
    return ["Tecnologia e Dados", "RH", "Financeiro", "Operações"]

@st.cache_data(ttl=60, show_spinner=False)
def obter_lista_tipos_servico():
    """Busca a lista de tipos de serviço ativos com cache."""
    garantir_tabela_sla()
    conn = conectar_banco()
    if not conn:
        return ["Suporte Técnico", "Nova Funcionalidade", "Dúvida", "Acesso"]
    try:
        query = "SELECT Nome FROM dbo.Chamados_Tipos_Servico ORDER BY ID ASC"
        df_tipos = pd.read_sql(query, conn)
        if not df_tipos.empty:
            return df_tipos['Nome'].tolist()
    except Exception:
        pass
    finally:
        conn.close()
    return ["Suporte Técnico", "Nova Funcionalidade", "Dúvida", "Acesso"]

def validar_usuario_banco(email_usuario):
    """Valida o nível de permissão e status do usuário fornecido na URL."""
    if not email_usuario:
        return False, False, "Usuário não identificado na URL"
    conn = conectar_banco()
    if not conn:
        return False, False, "Erro ao conectar ao banco de dados"
    cursor = conn.cursor()
    try:
        query = "SELECT ativo, nivel, nome FROM auth.Usuarios WHERE email = ?"
        cursor.execute(query, (email_usuario,))
        usuario = cursor.fetchone()
        if usuario:
            ativo = usuario[0] == 1
            eh_admin = usuario[1] == "admin"
            nome = usuario[2]
            return ativo, eh_admin, nome
        else:
            return False, False, "Usuário não cadastrado na base"
    except Exception as erro:
        return False, False, f"Erro na verificação de permissões: {erro}"
    finally:
        cursor.close()
        conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def buscar_atendentes_admin():
    """Retorna lista com nomes de todos os administradores ativos com cache."""
    conn = conectar_banco()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        query = "SELECT nome FROM auth.Usuarios WHERE nivel = 'admin' AND ativo = 1"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()

def atualizar_todos_os_caches():
    """Invalida todos os caches da aplicação para refletir alterações instantaneamente (Garante consistência pós-mutação na Aba 3)."""
    buscar_emails_atendentes.clear()
    obter_matriz_sla.clear()
    obter_lista_setores.clear()
    obter_lista_tipos_servico.clear()
    buscar_atendentes_admin.clear()

# ==============================================================================
# 9. COMPONENTE DE CRONÔMETRO JS (SUPORTE A DARK MODE)
# ==============================================================================
def renderizar_cronometro_js(dt_limite, status_atual, status_fechados, tipo_sla, dt_resposta=None):
    """Renderiza cronômetro em tempo real via JavaScript para monitoramento de SLA."""
    titulo_display = f" Tempo de {tipo_sla}"

    css_reset_iframe = """
    <style>
        html, body {
            background-color: transparent !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .card-sla-box {
            padding: 12px;
            border-radius: 4px;
            box-sizing: border-box;
            width: 100%;
        }
    </style>
    """

    if status_atual == "Cancelado":
        html_codigo_cancelado = f"""
        {css_reset_iframe}
        <div class="card-sla-box" style="background-color: #f8d7da; border-left: 5px solid #dc3545;">
            <span style="font-weight: bold; color: #721c24; font-size: 14px;">{titulo_display}</span>
            <div style="font-size: 18px; font-weight: bold; color: #dc3545; margin-top: 4px;">⛔ Chamado Cancelado</div>
            <div style="font-size: 11px; color: #721c24; margin-top: 2px;">Prazo limite era: {dt_limite.strftime('%d/%m/%Y %H:%M:%S')}</div>
        </div>
        """
        components.html(html_codigo_cancelado, height=90)
        return

    if tipo_sla == "Resposta" and dt_resposta is not None and pd.notna(dt_resposta):
        dt_resp_obj = pd.to_datetime(dt_resposta)
        if dt_resp_obj <= dt_limite:
            html_codigo_resposta = f"""
            {css_reset_iframe}
            <div class="card-sla-box" style="background-color: #d4edda; border-left: 5px solid #28a745;">
                <span style="font-weight: bold; color: #155724; font-size: 14px;">{titulo_display}</span>
                <div style="font-size: 18px; font-weight: bold; color: #28a745; margin-top: 4px;">✅ Atendido no Prazo</div>
                <div style="font-size: 11px; color: #155724; margin-top: 2px;">Respondido em: {dt_resp_obj.strftime('%d/%m/%Y %H:%M:%S')}</div>
            </div>
            """
        else:
            html_codigo_resposta = f"""
            {css_reset_iframe}
            <div class="card-sla-box" style="background-color: #f8d7da; border-left: 5px solid #dc3545;">
                <span style="font-weight: bold; color: #721c24; font-size: 14px;">{titulo_display}</span>
                <div style="font-size: 18px; font-weight: bold; color: #dc3545; margin-top: 4px;">❌ Expirado (Fora do Prazo)</div>
                <div style="font-size: 11px; color: #721c24; margin-top: 2px;">Respondido em: {dt_resp_obj.strftime('%d/%m/%Y %H:%M:%S')} (Limite: {dt_limite.strftime('%d/%m/%Y %H:%M:%S')})</div>
            </div>
            """
        components.html(html_codigo_resposta, height=90)
        return

    if status_atual in status_fechados:
        agora = datetime.now()
        if agora > dt_limite and tipo_sla == "Solução":
            html_codigo_fora_prazo = f"""
            {css_reset_iframe}
            <div class="card-sla-box" style="background-color: #f8d7da; border-left: 5px solid #dc3545;">
                <span style="font-weight: bold; color: #721c24; font-size: 14px;">{titulo_display}</span>
                <div style="font-size: 18px; font-weight: bold; color: #dc3545; margin-top: 4px;">❌ Atendido (Fora do Prazo)</div>
                <div style="font-size: 11px; color: #721c24; margin-top: 2px;">Prazo limite era: {dt_limite.strftime('%d/%m/%Y %H:%M:%S')}</div>
            </div>
            """
            components.html(html_codigo_fora_prazo, height=90)
            return

        html_codigo_verde = f"""
        {css_reset_iframe}
        <div class="card-sla-box" style="background-color: #d4edda; border-left: 5px solid #28a745;">
            <span style="font-weight: bold; color: #155724; font-size: 14px;">{titulo_display}</span>
            <div style="font-size: 18px; font-weight: bold; color: #28a745; margin-top: 4px;">✅ Atendido no Prazo</div>
            <div style="font-size: 11px; color: #155724; margin-top: 2px;">Prazo limite era: {dt_limite.strftime('%d/%m/%Y %H:%M:%S')}</div>
        </div>
        """
        components.html(html_codigo_verde, height=90)
        return

    data_limite_str = dt_limite.strftime('%Y-%m-%dT%H:%M:%S')
    div_id = f"timer_{int(dt_limite.timestamp())}_{abs(hash(tipo_sla))}"
    card_id = f"card_{div_id}"

    html_codigo = f"""
    {css_reset_iframe}
    <div id="{card_id}" class="card-sla-box" style="background-color: #fff3cd; border-left: 5px solid #ffc107; transition: background-color 0.3s, border-left 0.3s;">
        <span id="title_{div_id}" style="font-weight: bold; color: #856404; font-size: 14px;">{titulo_display}</span>
        <div id="{div_id}" style="font-size: 18px; font-weight: bold; color: #856404; margin-top: 4px;">Carregando...</div>
        <div id="subtitle_{div_id}" style="font-size: 11px; color: #6c757d; margin-top: 2px;">Prazo limite: {dt_limite.strftime('%d/%m/%Y %H:%M:%S')}</div>
    </div>

    <script>
        var countDownDate = new Date("{data_limite_str}").getTime();
        var x = setInterval(function() {{
            var agora = new Date().getTime();
            var distancia = countDownDate - agora;
            var card = document.getElementById("{card_id}");
            var timer = document.getElementById("{div_id}");
            var title = document.getElementById("title_{div_id}");

            if (distancia > 0) {{
                var horas = Math.floor(distancia / (1000 * 60 * 60));
                var minutos = Math.floor((distancia % (1000 * 60 * 60)) / (1000 * 60));
                var segundos = Math.floor((distancia % (1000 * 60)) / 1000);

                horas = (horas < 10 ? "0" : "") + horas;
                minutos = (minutos < 10 ? "0" : "") + minutos;
                segundos = (segundos < 10 ? "0" : "") + segundos;

                timer.innerHTML = "Restam " + horas + ":" + minutos + ":" + segundos;
                card.style.backgroundColor = "#fff3cd";
                card.style.borderLeft = "5px solid #ffc107";
                title.style.color = "#856404";
                timer.style.color = "#856404";

            }} else {{
                clearInterval(x);
                timer.innerHTML = "❌ Expirado (Prazo Atingido)";
                card.style.backgroundColor = "#f8d7da";
                card.style.borderLeft = "5px solid #dc3545";
                title.style.color = "#721c24";
                timer.style.color = "#dc3545";
            }}
        }}, 1000);
    </script>
    """
    components.html(html_codigo, height=90)

# ==============================================================================
# 10. AUTENTICAÇÃO E LOGINS VIA PARÂMETRO DA URL
# ==============================================================================
parametros_url = st.query_params
email_logado = parametros_url.get("user", "")

usuario_ativo, eh_admin, nome_usuario = validar_usuario_banco(email_logado)

if not usuario_ativo:
    st.error(f"Acesso Negado: O e-mail '{email_logado}' não tem permissão de acesso.")
    st.stop()

st.title("🖥️ Gestão de Chamados TI")
st.caption(f"Usuário Conectado: **{nome_usuario}** ({email_logado}) — Perfil: **{'Administrador' if eh_admin else 'Usuário'}**")

# ==============================================================================
# 11. CRIAÇÃO DAS ABAS DE NAVEGAÇÃO DO HELP DESK
# ==============================================================================
if eh_admin:
    titulos_abas = ["Abertura de Chamados", "Acompanhamento", "Políticas de SLA"]
else:
    titulos_abas = ["📋 Abertura de Chamados", "📊 Acompanhamento"]

abas = st.tabs(titulos_abas)

# ==============================================================================
# ABA 1: FORMULÁRIO DE ABERTURA DE CHAMADOS (COM EDITOR RICO)
# ==============================================================================
with abas[0]:
    if st.session_state.mostrar_sucesso_abertura:
        st.toast("🚀 Chamado aberto com sucesso! Seu atendimento foi registrado.", icon="✅")
        st.session_state.mostrar_sucesso_abertura = False

    df_matriz_sla_abertura = obter_matriz_sla()
    lista_prioridades_disponiveis = df_matriz_sla_abertura['Prioridade'].tolist()
    lista_setores_disponiveis = obter_lista_setores()
    lista_servicos_disponiveis = obter_lista_tipos_servico()
    
    with st.container():
        col1_l1, col2_l1 = st.columns(2)
        with col1_l1:
            titulo = st.text_input("Título do Incidente / Solicitação", key=f"titulo_{st.session_state.form_reset_counter}")
        with col2_l1:
            prioridade = st.selectbox("Prioridade", lista_prioridades_disponiveis, key=f"prio_{st.session_state.form_reset_counter}")

        col1_l2, col2_l2 = st.columns(2)
        with col1_l2:
            setor = st.selectbox("Setor Afetado", lista_setores_disponiveis, key=f"setor_{st.session_state.form_reset_counter}")
        with col2_l2:
            linha_prio_sel = df_matriz_sla_abertura[df_matriz_sla_abertura['Prioridade'] == prioridade]
            sla_horas = int(linha_prio_sel['SLA_Solucao_Horas'].values[0]) if not linha_prio_sel.empty else 24
            st.number_input("SLA Estimado (Horas de Solução)", value=sla_horas, disabled=True, key=f"sla_input_{prioridade}_{st.session_state.form_reset_counter}")

        col1_l3, col2_l3 = st.columns(2)
        with col1_l3:
            tipo_servico = st.selectbox("Tipo de Serviço", lista_servicos_disponiveis, key=f"serv_{st.session_state.form_reset_counter}")
        with col2_l3:
            st.text_input("Nome do Solicitante", value=nome_usuario, disabled=True, key=f"solic_{st.session_state.form_reset_counter}")

        st.markdown("**Descrição Detalhada do Problema:**")
        # Substituído por st_quill para suportar Ctrl+V, fontes, cores, negrito, etc., com fallback seguro
        if TEM_QUILL:
            descricao_texto = st_quill(placeholder="Descreva o problema em detalhes (suporta Ctrl+V, estilos, cores e formatações)...", key=f"quill_desc_{st.session_state.form_reset_counter}")
        else:
            descricao_texto = st.text_area(
                label="Descrição Detalhada do Problema",
                placeholder="Descreva o problema em detalhes...",
                label_visibility="collapsed",
                key=f"textarea_desc_{st.session_state.form_reset_counter}"
            )

        imagem_anexo = st.file_uploader("📎 Anexar Imagem ao chamado (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key=f"file_abertura_{st.session_state.form_reset_counter}")
        
        botao_enviar_chamado = st.button("Abrir Chamado", type="primary", key=f"btn_enviar_{st.session_state.form_reset_counter}")

    if botao_enviar_chamado:
        if titulo.strip() != "" and descricao_texto and descricao_texto.strip() != "":
            conn = conectar_banco()
            if not conn:
                st.error("Erro ao conectar ao banco de dados.")
            else:
                cursor = conn.cursor()
                try:
                    html_img, raw_base64 = converter_imagem_para_base64_html(imagem_anexo)
                    # Se o quill for usado, ele já traz tags HTML; caso contrário, formatamos quebras
                    if TEM_QUILL and ("<p>" in descricao_texto or "<span>" in descricao_texto):
                        descricao_formatada = descricao_texto
                    else:
                        descricao_formatada = descricao_texto.replace('\n', '<br/>')
                    descricao_final = descricao_formatada + html_img  

                    # Execução otimizada via Stored Procedure sp_CriarChamado (Corrigido para SQL Server)
                    output_id = cursor.execute("DECLARE @NewID INT; EXEC dbo.sp_CriarChamado ?, ?, ?, ?, ?, ?, ?, ?, @NewID OUTPUT; SELECT @NewID;", (
                        titulo, 
                        descricao_final, 
                        sla_horas, 
                        nome_usuario, 
                        email_logado, 
                        setor, 
                        tipo_servico, 
                        prioridade
                    ))
                    
                    row_id_res = cursor.fetchone()
                    novo_id_chamado = int(row_id_res[0]) if row_id_res and row_id_res[0] is not None else 1
                    
                    conn.commit()
                    
                    # Disparo de e-mail de confirmação para o solicitante
                    assunto_solicitante = f"✅ Confirmação de Abertura: Chamado #{novo_id_chamado} - {titulo}"
                    corpo_solicitante = f"""
                    <h3>Olá, {nome_usuario}!</h3>
                    <p>Seu chamado foi aberto com sucesso em nosso sistema de HelpDesk.</p>
                    <ul>
                        <li><b>ID do Chamado:</b> #{novo_id_chamado}</li>
                        <li><b>Título:</b> {titulo}</li>
                        <li><b>Prioridade:</b> {prioridade}</li>
                        <li><b>Setor:</b> {setor}</li>
                        <li><b>Tipo de Serviço:</b> {tipo_servico}</li>
                    </ul>
                    <p>Nossa equipe de suporte analisará a sua solicitação em breve.</p>
                    <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                    """
                    enviar_email_resend(email_logado, assunto_solicitante, corpo_solicitante)

                    # Disparo otimizado de alerta para os atendentes admin utilizando BCC em lote
                    emails_atendentes = buscar_emails_atendentes()
                    if emails_atendentes:
                        assunto_atendentes = f"🚨 Novo Chamado Aberto: #{novo_id_chamado} - {titulo}"
                        corpo_atendentes = f"""
                        <h3>Novo chamado registrado no HelpDesk!</h3>
                        <p>Um novo chamado necessita de atenção da equipe de TI.</p>
                        <ul>
                            <li><b>ID do Chamado:</b> #{novo_id_chamado}</li>
                            <li><b>Solicitante:</b> {nome_usuario} ({email_logado})</li>
                            <li><b>Título:</b> {titulo}</li>
                            <li><b>Prioridade:</b> {prioridade}</li>
                            <li><b>Setor:</b> {setor}</li>
                        </ul>
                        <p>Acesse o painel para atribuir um responsável e iniciar o atendimento.</p>
                        <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                        """
                        # Utiliza o primeiro administrador no 'to' e os demais em 'bcc' para otimizar requisições e preservar cotas da API Resend
                        to_admin = [emails_atendentes[0]]
                        bcc_admins = emails_atendentes[1:] if len(emails_atendentes) > 1 else None
                        enviar_email_resend(to_admin, assunto_atendentes, corpo_atendentes, bcc=bcc_admins)

                    st.session_state.mostrar_sucesso_abertura = True
                    st.session_state.form_reset_counter += 1
                    st.rerun() 
                except Exception as ex:
                    st.error(f"Erro ao salvar chamado no banco: {ex}")
                finally:
                    cursor.close()
                    conn.close()
        else:
            st.warning("Por favor, preencha o Título e a Descrição Detalhada do Problema.")

# ==============================================================================
# ABA 2: ACOMPANHAMENTO DE CHAMADOS (UTILIZANDO VIEW OTIMIZADA)
# ==============================================================================
with abas[1]:
    
    if st.session_state.chamado_selecionado is None:
        
        col_tit_fila, col_btn_atualizar_fila = st.columns([4, 1])
        with col_btn_atualizar_fila:
            if st.button("Atualizar Fila", use_container_width=True):
                st.rerun()
        
        conn = conectar_banco()
        if not conn:
            st.error("Falha na conexão com o banco de dados.")
        else:
            try:
                garantir_tabela_sla()
                
                # Consulta otimizada utilizando a View dbo.vw_ChamadosFila
                if eh_admin:
                    query_sel = """
                    SELECT ID, Titulo, Solicitante AS Solicitante, Solicitante_Email, Responsavel, Setor, Tipo_Servico, Prioridade, Status, Data_Abertura, SLA_Horas, Data_Primeira_Resposta 
                    FROM dbo.vw_ChamadosFila ORDER BY ID DESC
                    """
                    df = pd.read_sql(query_sel, conn)
                else:
                    query_sel = """
                    SELECT ID, Titulo, Solicitante AS Solicitante, Solicitante_Email, Responsavel, Setor, Tipo_Servico, Prioridade, Status, Data_Abertura, SLA_Horas, Data_Primeira_Resposta 
                    FROM dbo.vw_ChamadosFila WHERE Solicitante_Email = ? ORDER BY ID DESC
                    """
                    df = pd.read_sql(query_sel, conn, params=(email_logado,))
                
                if not df.empty:
                    if eh_admin:
                        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                        with f_col1:
                            filtro_id = st.text_input("Filtrar por ID do Chamado")
                        with f_col2:
                            lista_solicitantes = ["Todos"] + list(df['Solicitante'].dropna().unique())
                            filtro_solicitante = st.selectbox("Filtrar por Solicitante", lista_solicitantes)
                        with f_col3:
                            lista_status = ["Todos"] + list(df['Status'].dropna().unique())
                            filtro_status = st.selectbox("Filtrar por Status", lista_status)
                        with f_col4:
                            lista_prioridades = ["Todas"] + list(df['Prioridade'].dropna().unique())
                            filtro_prioridade = st.selectbox("Filtrar por Prioridade", lista_prioridades)
                    else:
                        f_col1, f_col2, f_col3 = st.columns(3)
                        with f_col1:
                            filtro_id = st.text_input("Filtrar por ID do Chamado")
                        with f_col2:
                            lista_status = ["Todos"] + list(df['Status'].dropna().unique())
                            filtro_status = st.selectbox("Filtrar por Status", lista_status)
                        with f_col3:
                            lista_prioridades = ["Todas"] + list(df['Prioridade'].dropna().unique())
                            filtro_prioridade = st.selectbox("Filtrar por Prioridade", lista_prioridades)
                        filtro_solicitante = "Todos"

                    usar_data = st.checkbox("Ativar Filtro por Período de Data")
                    if usar_data:
                        c_data1, c_data2 = st.columns(2)
                        with c_data1:
                            data_inicio = st.date_input("De:")
                        with c_data2:
                            data_fim = st.date_input("Até:")

                    df_filtrado = df.copy()
                    if filtro_id.strip() != "" and filtro_id.isnumeric():
                        df_filtrado = df_filtrado[df_filtrado['ID'] == int(filtro_id)]
                    if filtro_solicitante != "Todos":
                        df_filtrado = df_filtrado[df_filtrado['Solicitante'] == filtro_solicitante]
                    if filtro_status != "Todos":
                        df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_status]
                    if filtro_prioridade != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Prioridade'] == filtro_prioridade]
                    if usar_data:
                        df_filtrado = df_filtrado[(df_filtrado['Data_Abertura'].dt.date >= data_inicio) & (df_filtrado['Data_Abertura'].dt.date <= data_fim)]

                    st.divider()
                    st.caption(f"Exibindo {len(df_filtrado)} chamado(s) encontrado(s).")

                    status_fechados = ['Resolvido', 'Encerrado']
                    df_exibicao = df_filtrado.copy()
                    df_exibicao['Data'] = df_exibicao['Data_Abertura'].dt.strftime('%d/%m/%Y %H:%M')
                    df_exibicao['Responsável'] = df_exibicao['Responsavel'].fillna('Não atribuído')
                    
                    col_h_id, col_h_tit, col_h_sol, col_h_resp, col_h_set, col_h_srv, col_h_pri, col_h_stat, col_h_dat, col_h_sla, col_h_det = st.columns([0.4, 1.4, 1.3, 1.3, 1.1, 1.1, 1.2, 0.9, 1.1, 1.5, 0.9])
                    col_h_id.markdown("**ID**")
                    col_h_tit.markdown("**Título**")
                    col_h_sol.markdown("**Solicitante**")
                    col_h_resp.markdown("**Responsável**")
                    col_h_set.markdown("**Setor**")
                    col_h_srv.markdown("**Serviço**")
                    col_h_pri.markdown("**Prioridade**")
                    col_h_stat.markdown("**Status**")
                    col_h_dat.markdown("**Data**")
                    col_h_sla.markdown("**SLA de Atendimento**")
                    col_h_det.markdown("**Detalhes**")
                    
                    df_matriz_vigente = obter_matriz_sla()

                    for _, row in df_exibicao.iterrows():
                        with st.container(border=True):
                            c_id, c_tit, c_sol, c_resp, c_set, c_srv, c_pri, c_stat, c_dat, c_sla, c_det = st.columns([0.4, 1.4, 1.3, 1.3, 1.1, 1.1, 1.2, 0.9, 1.1, 1.5, 0.9])
                            
                            c_id.write(row['ID'])
                            c_tit.write(row['Titulo'])
                            c_sol.write(row['Solicitante'])
                            c_resp.write(row['Responsável'])
                            c_set.write(row['Setor'])
                            c_srv.write(row['Tipo_Servico'])
                            c_pri.write(row['Prioridade'])
                            c_stat.write(row['Status'])
                            c_dat.write(row['Data'])
                            
                            with c_sla:
                                data_abertura_chamado = row['Data_Abertura']
                                horas_sla = int(row['SLA_Horas']) if pd.notna(row['SLA_Horas']) else 24
                                status_atual = row['Status']
                                dt_primeira_resp = row.get('Data_Primeira_Resposta', None)
                                
                                match_matriz = df_matriz_vigente[df_matriz_vigente['Prioridade'] == row['Prioridade']]
                                horas_resposta = int(match_matriz['SLA_Resposta_Horas'].values[0]) if not match_matriz.empty else max(1, int(horas_sla * 0.10))

                                data_limite_resposta = data_abertura_chamado + timedelta(hours=horas_resposta)
                                data_limite_solucao = data_abertura_chamado + timedelta(hours=horas_sla)
                                agora = datetime.now()

                                if status_atual == "Cancelado":
                                    st.markdown("🔴 **Cancelado**")
                                else:
                                    if pd.notna(dt_primeira_resp):
                                        dt_resp_obj = pd.to_datetime(dt_primeira_resp)
                                        if dt_resp_obj <= data_limite_resposta:
                                            st.markdown("✅ **Resp. OK**")
                                        else:
                                            st.markdown("🔴 **Resp. Atrasada**")
                                    else:
                                        sla_resp_vencido = (agora > data_limite_resposta) and (status_atual not in status_fechados)
                                        if sla_resp_vencido:
                                            st.markdown("🔴 **Resp. Atrasada**")
                                        else:
                                            st.markdown("⚠️ **Resp. Correndo**")

                                    if status_atual in status_fechados:
                                        if agora > data_limite_solucao:
                                            st.markdown("🔴 **Sol. Fora do Prazo**")
                                        else:
                                            st.markdown("✅ **Sol. Concluída**")
                                    else:
                                        sla_sol_vencido = (agora > data_limite_solucao)
                                        if sla_sol_vencido:
                                            st.markdown("🔴 **Sol. Atrasada**")
                                        else:
                                            st.markdown("⏳ **Sol. Correndo**")

                            with c_det:
                                if st.button("Abrir", key=f"btn_detalhes_{row['ID']}", use_container_width=True):
                                    st.session_state.chamado_selecionado = row['ID']
                                    st.rerun()

                    st.divider()
                else:
                    st.info("Nenhum chamado encontrado.")
            except Exception as e:
                st.error(f"Erro ao buscar chamados: {e}")
            finally:
                conn.close()

    else:
        id_selecionado = st.session_state.chamado_selecionado
        
        col_btn_voltar, col_btn_atualizar_ticket = st.columns([4, 1])
        with col_btn_voltar:
            if st.button("Voltar para a Fila", type="secondary"):
                st.session_state.chamado_selecionado = None
                st.rerun()
        with col_btn_atualizar_ticket:
            if st.button("Atualizar Ticket", type="secondary", use_container_width=True):
                st.rerun()
            
        conn = conectar_banco()
        if not conn:
            st.error("Falha na conexão com o banco de dados.")
        else:
            try:
                garantir_tabela_sla()
                
                if eh_admin:
                    query_det = "SELECT * FROM dbo.Chamados WHERE ID = ?"
                    df_det = pd.read_sql(query_det, conn, params=(id_selecionado,))
                else:
                    query_det = "SELECT * FROM dbo.Chamados WHERE ID = ? AND Solicitante_Email = ?"
                    df_det = pd.read_sql(query_det, conn, params=(id_selecionado, email_logado))
                
                if not df_det.empty:
                    row_det = df_det.iloc[0]
                    st.header(f"Chamado #{row_det['ID']} - {row_det['Titulo']}")
                    
                    c_badges_1, c_badges_2, _ = st.columns([1, 1, 6])
                    c_badges_1.info(f"**Prioridade:** {row_det['Prioridade']}")
                    
                    status_atual_det = row_det['Status']
                    status_fechados = ['Resolvido', 'Encerrado']

                    if status_atual_det == "Cancelado":
                        c_badges_2.error(f"**Status:** {status_atual_det}")
                    elif status_atual_det in status_fechados:
                        c_badges_2.success(f"**Status:** {status_atual_det}")
                    else:
                        c_badges_2.warning(f"**Status:** {status_atual_det}")

                    if eh_admin:
                        st.markdown("### Atualizar Chamado (Ações do Administrador)")
                        with st.expander("Abrir Controles de Atendimento", expanded=True):
                            with st.form(key=f"form_atualiza_chamado_{id_selecionado}"):
                                c_att1, c_att2 = st.columns(2)
                                with c_att1:
                                    admins_lista = buscar_atendentes_admin()
                                    resp_atual = row_det['Responsavel']
                                    resp_atual_str = resp_atual if pd.notna(resp_atual) else "Não atribuído"
                                    admins_opcoes = ["Não atribuído"] + admins_lista
                                    idx_resp_final = admins_opcoes.index(resp_atual_str) if resp_atual_str in admins_opcoes else 0
                                    novo_resp = st.selectbox("Atribuir/Alterar Responsável", admins_opcoes, index=idx_resp_final)
                                    
                                with c_att2:
                                    status_opcoes = ['Aberto', 'Em Atendimento', 'Aguardando Terceiros', 'Resolvido', 'Cancelado', 'Encerrado']
                                    idx_status = status_opcoes.index(status_atual_det) if status_atual_det in status_opcoes else 0
                                    novo_status = st.selectbox("Alterar Status", status_opcoes, index=idx_status)

                                st.markdown("**Mensagem ao Solicitante / Justificativa (Opcional):**")
                                # Substituído por st_quill para suporte a rich text moderno com fallback seguro
                                if TEM_QUILL:
                                    mensagem_atendente = st_quill(placeholder="Digite uma mensagem, justificativa da alteração ou detalhes...", key=f"quill_msg_atendente_{id_selecionado}")
                                else:
                                    mensagem_atendente = st.text_area(
                                        label="Mensagem ao Solicitante / Justificativa (Opcional)",
                                        placeholder="Digite uma mensagem, justificativa da alteração de status ou detalhes do atendimento...",
                                        label_visibility="collapsed",
                                        key=f"msg_atendente_{id_selecionado}"
                                    )

                                btn_salvar_att = st.form_submit_button("Salvar Alterações", type="primary")
                                
                                if btn_salvar_att:
                                    cursor_upd = conn.cursor()
                                    try:
                                        valor_resp = novo_resp if novo_resp != "Não atribuído" else None
                                        
                                        # MELHORIA SOLICITADA: Se um responsável válido foi atribuído e o status selecionado for 'Aberto' (ou se o atendente esqueceu de mudar),
                                        # o sistema automaticamente converte o status para 'Em Atendimento' para proteger os indicadores operacionais.
                                        if valor_resp is not None and (novo_status == 'Aberto' or status_atual_det == 'Aberto'):
                                            novo_status = 'Em Atendimento'

                                        dt_primeira_resposta_existente = row_det.get('Data_Primeira_Resposta', None)
                                        atualizar_resp_flag = 1 if (valor_resp is not None and (pd.isna(dt_primeira_resposta_existente) or dt_primeira_resposta_existente is None)) else 0

                                        # Executa Stored Procedure sp_AtualizarChamado
                                        cursor_upd.execute("{CALL dbo.sp_AtualizarChamado (?, ?, ?, ?)}", (
                                            id_selecionado, 
                                            valor_resp, 
                                            novo_status, 
                                            atualizar_resp_flag
                                        ))

                                        msg_texto_limpo = mensagem_atendente.strip() if mensagem_atendente else ""
                                        if msg_texto_limpo != "":
                                            if TEM_QUILL and ("<p>" in mensagem_atendente or "<span>" in mensagem_atendente):
                                                msg_formatada = mensagem_atendente
                                            else:
                                                msg_formatada = msg_texto_limpo.replace('\n', '<br/>')
                                            
                                            # Executa Stored Procedure sp_InserirComentario para registrar a justificativa na linha do tempo
                                            cursor_upd.execute("{CALL dbo.sp_InserirComentario (?, ?, ?, ?)}", (
                                                id_selecionado, 
                                                msg_formatada, 
                                                nome_usuario, 
                                                None
                                            ))

                                        conn.commit()

                                        resp_anterior_str = resp_atual if pd.notna(resp_atual) else None
                                        houve_mudanca_status = (novo_status != status_atual_det)
                                        houve_mudanca_resp = (valor_resp != resp_anterior_str)
                                        tem_mensagem = (msg_texto_limpo != "")

                                        if houve_mudanca_status or houve_mudanca_resp or tem_mensagem:
                                            email_solic_dest = row_det['Solicitante_Email']
                                            nome_solic_dest = row_det['Solicitante_Nome']
                                            titulo_ticket = row_det['Titulo']

                                            assunto_atualizacao = f"🔔 Atualização no Chamado #{id_selecionado}: {titulo_ticket}"
                                            bloco_mensagem_html = ""
                                            if tem_mensagem:
                                                msg_html_atendente = mensagem_atendente if (TEM_QUILL and "<p>" in mensagem_atendente) else msg_texto_limpo.replace('\n', '<br/>')
                                                bloco_mensagem_html = f"""
                                                <p style="margin-top: 15px; font-weight: bold; color: #333;">Mensagem / Justificativa do Atendente:</p>
                                                <blockquote style="background: #f8f9fa; border-left: 4px solid #053B6D; padding: 12px; margin: 10px 0; color: #212529;">
                                                    {msg_html_atendente}
                                                </blockquote>
                                                """

                                            corpo_atualizacao = f"""
                                            <h3>Olá, {nome_solic_dest}!</h3>
                                            <p>Seu chamado <b>#{id_selecionado} - {titulo_ticket}</b> recebeu uma atualização da equipe de suporte.</p>
                                            <ul>
                                                <li><b>Status Atual:</b> <span style="font-size:15px; font-weight:bold; color:#053B6D;">{novo_status}</span></li>
                                                <li><b>Atendente Responsável:</b> {valor_resp if valor_resp else 'Não atribuído'}</li>
                                            </ul>
                                            {bloco_mensagem_html}
                                            <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                                            """
                                            enviar_email_resend(email_solic_dest, assunto_atualizacao, corpo_atualizacao)

                                        st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': "✅ Chamado atualizado com sucesso!"})
                                        st.rerun() 
                                    except Exception as e:
                                        st.error(f"Erro ao atualizar chamado: {e}")
                                    finally:
                                        cursor_upd.close()

                    elif row_det['Solicitante_Email'] == email_logado and status_atual_det not in status_fechados and status_atual_det != "Cancelado":
                        st.markdown("### 🚫 Ações do Solicitante")
                        with st.expander("Cancelar este Chamado", expanded=False):
                            st.warning("Tem certeza de que deseja cancelar esta solicitação?")
                            if st.button("Confirmar Cancelamento do Chamado", type="primary"):
                                cursor_can = conn.cursor()
                                try:
                                    query_cancel = "UPDATE dbo.Chamados SET Status = 'Cancelado' WHERE ID = ? AND Solicitante_Email = ?"
                                    cursor_can.execute(query_cancel, (id_selecionado, email_logado))
                                    conn.commit()

                                    # 1. Notifica o solicitante sobre o cancelamento
                                    assunto_cancel = f"🔔 Chamado #{id_selecionado} Cancelado"
                                    corpo_cancel = f"""
                                    <h3>Olá, {row_det['Solicitante_Nome']}!</h3>
                                    <p>Confirmamos o cancelamento do chamado <b>#{id_selecionado} - {row_det['Titulo']}</b> solicitado por você.</p>
                                    <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                                    """
                                    enviar_email_resend(row_det['Solicitante_Email'], assunto_cancel, corpo_cancel)

                                    # 2. Notifica também o administrador responsável, caso o chamado estivesse em atendimento
                                    resp_atribuido_atual = row_det['Responsavel']
                                    if pd.notna(resp_atribuido_atual) and resp_atribuido_atual and resp_atribuido_atual != "Não atribuído":
                                        email_resp_atribuido_cancel = buscar_email_atendente_por_nome(resp_atribuido_atual)
                                        if email_resp_atribuido_cancel:
                                            assunto_cancel_resp = f"🔔 Chamado #{id_selecionado} Cancelado pelo Solicitante"
                                            corpo_cancel_resp = f"""
                                            <h3>Olá, {resp_atribuido_atual}!</h3>
                                            <p>O chamado <b>#{id_selecionado} - {row_det['Titulo']}</b> que estava sob sua responsabilidade foi cancelado pelo solicitante ({row_det['Solicitante_Nome']}).</p>
                                            <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                                            """
                                            enviar_email_resend(email_resp_atribuido_cancel, assunto_cancel_resp, corpo_cancel_resp)

                                    st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': "✅ Chamado cancelado com sucesso!"})
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao cancelar chamado: {e}")
                                finally:
                                    cursor_can.close()

                    st.markdown("---")

                    col_timer_resp, col_timer_sol = st.columns(2)
                    dt_abertura = pd.to_datetime(row_det['Data_Abertura'])
                    h_sla = int(row_det['SLA_Horas']) if pd.notna(row_det['SLA_Horas']) else 24
                    
                    df_matriz_vigente_det = obter_matriz_sla()
                    match_matriz_det = df_matriz_vigente_det[df_matriz_vigente_det['Prioridade'] == row_det['Prioridade']]
                    h_resposta = int(match_matriz_det['SLA_Resposta_Horas'].values[0]) if not match_matriz_det.empty else max(1, int(h_sla * 0.10))

                    dt_lim_resposta = dt_abertura + timedelta(hours=h_resposta)
                    dt_lim_solucao = dt_abertura + timedelta(hours=h_sla)
                    dt_primeira_resp_db = row_det.get('Data_Primeira_Resposta', None)

                    with col_timer_resp:
                        renderizar_cronometro_js(dt_lim_resposta, status_atual_det, status_fechados, "Resposta", dt_resposta=dt_primeira_resp_db)
                    with col_timer_sol:
                        renderizar_cronometro_js(dt_lim_solucao, status_atual_det, status_fechados, "Solução")

                    st.markdown("---")
                    
                    c_meta1, c_meta2, c_meta3 = st.columns(3)
                    c_meta1.markdown(f"**Solicitante:** {row_det['Solicitante_Nome']}")
                    c_meta1.markdown(f"**Email:** {row_det['Solicitante_Email']}")
                    c_meta2.markdown(f"**Setor Afetado:** {row_det['Setor']}")
                    c_meta2.markdown(f"**Serviço:** {row_det['Tipo_Servico']}")
                    c_meta3.markdown(f"**Data Abertura:** {dt_abertura.strftime('%d/%m/%Y %H:%M')}")
                    resp_atual = row_det['Responsavel']
                    resp_atual_str = resp_atual if pd.notna(resp_atual) else "Não atribuído"
                    c_meta3.markdown(f"**Responsável:** {resp_atual_str}")

                    st.markdown("---")
                    st.markdown("###  Descrição do Incidente")
                    
                    html_descricao_container = f"""
                    <style>
                        html, body {{
                            background-color: transparent !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            color: #212529;
                        }}
                        .img-anexo-thumb, img {{
                            max-width: 220px !important;
                            max-height: 140px !important;
                            object-fit: contain;
                            border-radius: 5px;
                            border: 1px solid #053B6D;
                            margin: 8px 0;
                            cursor: pointer;
                            transition: transform 0.2s, box-shadow 0.2s;
                            display: block;
                        }}
                        .img-anexo-thumb:hover, img:hover {{
                            transform: scale(1.03);
                            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                        }}
                        #modalZoom {{
                            display: none;
                            position: fixed;
                            z-index: 999999;
                            top: 0; left: 0;
                            width: 100vw; height: 100vh;
                            background-color: rgba(0, 0, 0, 0.85);
                            justify-content: center;
                            align-items: center;
                            cursor: zoom-out;
                        }}
                        #modalZoom img {{
                            max-width: 90vw !important;
                            max-height: 90vh !important;
                            object-fit: contain;
                            border: none !important;
                            box-shadow: 0 0 20px rgba(255,255,255,0.2);
                            cursor: default;
                        }}
                    </style>

                    <div style="font-size: 14px; line-height: 1.5;">
                        {row_det['Descricao']}
                    </div>

                    <div id="modalZoom" onclick="this.style.display='none'">
                        <img id="imgExpandida" src="" onclick="event.stopPropagation()">
                    </div>

                    <script>
                        document.addEventListener("DOMContentLoaded", function() {{
                            var imgs = document.querySelectorAll("img:not(#imgExpandida)");
                            imgs.forEach(function(i) {{
                                i.addEventListener("click", function() {{
                                    document.getElementById("imgExpandida").src = this.src;
                                    document.getElementById("modalZoom").style.display = "flex";
                                }});
                            }});
                        }});
                    </script>
                    """
                    altura_desc = calcular_altura_html(row_det['Descricao'])
                    components.html(html_descricao_container, height=altura_desc, scrolling=True)

                    st.markdown("---")

                    st.markdown("###  Linha do Tempo / Interações")
                    st.markdown("**Adicione um comentário ou nota:**")
                    
                    # Substituído por st_quill para permitir formatação rica em comentários (Ctrl+V, cores, fontes, etc.)
                    if TEM_QUILL:
                        comentario_texto = st_quill(placeholder="Escreva sua resposta ou nota aqui (suporta Ctrl+V, negrito, cores e estilos)...", key=f"quill_comentario_{id_selecionado}_{st.session_state.comment_reset_counter}")
                    else:
                        comentario_texto = st.text_area(
                            label="Adicione um comentário ou nota",
                            placeholder="Escreva sua resposta ou nota aqui...",
                            label_visibility="collapsed",
                            key=f"textarea_comentario_{id_selecionado}_{st.session_state.comment_reset_counter}"
                        )

                    comentario_imagem_anexo = st.file_uploader(
                        "📎 Anexar Imagem ao Comentário (PNG, JPG, JPEG)", 
                        type=["png", "jpg", "jpeg"], 
                        key=f"file_comentario_{id_selecionado}_{st.session_state.comment_reset_counter}"
                    )

                    if st.button("Enviar Comentário", type="primary", key=f"btn_env_com_{id_selecionado}"):
                        if (comentario_texto and comentario_texto.strip() != "") or comentario_imagem_anexo is not None:
                            cursor_com = conn.cursor()
                            try:
                                html_img_com, raw_base64_com = converter_imagem_para_base64_html(comentario_imagem_anexo)
                                
                                if TEM_QUILL and comentario_texto and ("<p>" in comentario_texto or "<span>" in comentario_texto):
                                    comentario_formatado = comentario_texto
                                else:
                                    comentario_formatado = comentario_texto.replace('\n', '<br/>') if comentario_texto else ""
                                
                                com_final = comentario_formatado + html_img_com

                                dt_primeira_resp_existente = row_det.get('Data_Primeira_Resposta', None)
                                if pd.isna(dt_primeira_resp_existente) or dt_primeira_resp_existente is None:
                                    cursor_com.execute("UPDATE dbo.Chamados SET Data_Primeira_Resposta = GETDATE() WHERE ID = ?", (id_selecionado,))

                                # Executa Stored Procedure sp_InserirComentario
                                cursor_com.execute("{CALL dbo.sp_InserirComentario (?, ?, ?, ?)}", (
                                    id_selecionado, 
                                    com_final, 
                                    nome_usuario, 
                                    raw_base64_com
                                ))
                                conn.commit()

                                if eh_admin:
                                    email_solic_dest = row_det['Solicitante_Email']
                                    nome_solic_dest = row_det['Solicitante_Nome']
                                    
                                    assunto_comentario_solic = f"💬 Novo comentário no Chamado #{id_selecionado}: {row_det['Titulo']}"
                                    corpo_comentario_solic = f"""
                                    <h3>Olá, {nome_solic_dest}!</h3>
                                    <p>O atendente <b>{nome_usuario}</b> adicionou um comentário no seu chamado <b>#{id_selecionado}</b>:</p>
                                    <blockquote style="background: #f9f9f9; border-left: 4px solid #007bff; padding: 10px; margin: 10px 0;">
                                        {comentario_texto if comentario_texto else '<i>[Imagem anexa adicionada]</i>'}
                                    </blockquote>
                                    <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                                    """
                                    enviar_email_resend(email_solic_dest, assunto_comentario_solic, corpo_comentario_solic)
                                else:
                                    resp_atribuido_nome = row_det['Responsavel']
                                    if pd.notna(resp_atribuido_nome) and resp_atribuido_nome and resp_atribuido_nome != "Não atribuído":
                                        email_resp_atribuido = buscar_email_atendente_por_nome(resp_atribuido_nome)
                                        if email_resp_atribuido:
                                            assunto_comentario_resp = f"💬 Nova resposta do Solicitante no Chamado #{id_selecionado}"
                                            corpo_comentario_resp = f"""
                                            <h3>Olá, {resp_atribuido_nome}!</h3>
                                            <p>O solicitante <b>{nome_usuario}</b> adicionou uma nova interação no chamado <b>#{id_selecionado} - {row_det['Titulo']}</b>:</p>
                                            <blockquote style="background: #f9f9f9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0;">
                                                {comentario_texto if comentario_texto else '<i>[Imagem anexa adicionada]</i>'}
                                            </blockquote>
                                            <hr/><small>Mensagem automática enviada pelo sistema HelpDesk Repress.</small>
                                            """
                                            enviar_email_resend(email_resp_atribuido, assunto_comentario_resp, corpo_comentario_resp)

                                st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': "✅ Comentário enviado com sucesso!"})
                                st.session_state.comment_reset_counter += 1
                                st.rerun()
                            except Exception as e_com:
                                st.error(f"Erro ao salvar comentário: {e_com}")
                            finally:
                                cursor_com.close()
                        else:
                            st.warning("Por favor, digite uma mensagem ou escolha uma imagem para anexar.")

                    st.markdown("#### Histórico de Mensagens")
                    query_historico = """
                    SELECT Autor, Comentario, Data_Comentario, Anexo 
                    FROM [aplicativos_db].[dbo].[Chamados_Comentarios] 
                    WHERE Chamado_ID = ? ORDER BY Data_Comentario DESC
                    """
                    df_historico = pd.read_sql(query_historico, conn, params=(id_selecionado,))

                    if not df_historico.empty:
                        for _, row_hist in df_historico.iterrows():
                            dt_comentario = pd.to_datetime(row_hist['Data_Comentario']).strftime('%d/%m/%Y %H:%M')
                            conteudo_mensagem = row_hist['Comentario']
                            
                            if pd.notna(row_hist['Anexo']) and row_hist['Anexo'] and "<img" not in conteudo_mensagem:
                                conteudo_mensagem += f'<br/><img src="{row_hist["Anexo"]}" class="img-anexo-thumb" alt="Anexo do Comentário"/>'

                            html_comentario_card = f"""
                            <style>
                                html, body {{
                                    background-color: transparent !important;
                                    margin: 0 !important;
                                    padding: 0 !important;
                                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                }}
                                .img-anexo-thumb, img {{
                                    max-width: 200px !important;
                                    max-height: 130px !important;
                                    object-fit: contain;
                                    border-radius: 5px;
                                    border: 1px solid #ccc;
                                    margin-top: 8px;
                                    cursor: pointer;
                                    transition: transform 0.2s;
                                    display: block;
                                }}
                                .img-anexo-thumb:hover, img:hover {{
                                    transform: scale(1.03);
                                }}
                                #modalZoomCom {{
                                    display: none;
                                    position: fixed;
                                    z-index: 999999;
                                    top: 0; left: 0;
                                    width: 100vw; height: 100vh;
                                    background-color: rgba(0, 0, 0, 0.85);
                                    justify-content: center;
                                    align-items: center;
                                    cursor: zoom-out;
                                }}
                                #modalZoomCom img {{
                                    max-width: 90vw !important;
                                    max-height: 90vh !important;
                                    object-fit: contain;
                                    border: none !important;
                                    cursor: default;
                                }}
                            </style>

                            <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 12px; border-radius: 5px; margin-bottom: 5px;">
                                <div style="font-size: 13px; font-weight: bold; color: #333;">
                                    {row_hist['Autor']} — <span style="color: #6c757d; font-weight: normal;">{dt_comentario}</span>
                                </div>
                                <div style="margin-top: 8px; font-size: 14px; color: #212529;">
                                    {conteudo_mensagem}
                                </div>
                            </div>

                            <div id="modalZoomCom" onclick="this.style.display='none'">
                                <img id="imgComExpandida" src="" onclick="event.stopPropagation()">
                            </div>

                            <script>
                                document.addEventListener("DOMContentLoaded", function() {{
                                    var imgs = document.querySelectorAll("img:not(#imgComExpandida)");
                                    imgs.forEach(function(i) {{
                                        i.addEventListener("click", function() {{
                                            document.getElementById("imgComExpandida").src = this.src;
                                            document.getElementById("modalZoomCom").style.display = "flex";
                                        }});
                                    }});
                                }});
                            </script>
                            """
                            altura_comentario = calcular_altura_html(conteudo_mensagem)
                            components.html(html_comentario_card, height=altura_comentario, scrolling=True)
                    else:
                        st.info("Nenhuma interação registrada até o momento.")
                else:
                    st.warning("Chamado não encontrado ou você não tem permissão para visualizá-lo.")
            except Exception as e:
                 st.error(f"Erro ao buscar detalhes: {e}")
            finally:
                conn.close()

# ==============================================================================
# 12. ABA 3: GESTÃO DE POLÍTICAS DE SLA (APENAS ADMINISTRADORES)
# ==============================================================================
if eh_admin:
    with abas[2]:
        st.header(" Gestão e Políticas de SLA (Service Level Agreement)")
        st.info("Painel exclusivo para administradores gerenciarem a Matriz de Prioridades, Prazos, Setores e Tipos de Serviço.")
        
        st.markdown("""
        O SLA no sistema é dividido em duas etapas fundamentais:
        * **SLA de Resposta:** Prazo máximo para o primeiro contato do analista.
        * **SLA de Solução:** Prazo máximo para a resolução definitiva do chamado.
        """)

        st.divider()
        st.subheader(" Editar ou Atualizar Matriz de SLA Vigente")
        df_matriz_admin = obter_matriz_sla()

        with st.form("form_edicao_matriz_sla"):
            st.markdown("**Altere as horas ou descrições dos níveis atuais:**")
            dados_atualizados = []
            
            for idx, row in df_matriz_admin.iterrows():
                col_p1, col_p2, col_p3, col_p4 = st.columns([1.5, 1, 1, 2.5])
                with col_p1:
                    prio_nome = st.text_input(f"Prioridade #{idx}", value=str(row['Prioridade']), key=f"matriz_prio_{idx}")
                with col_p2:
                    resp_h = st.number_input(f"Resp. (h) #{idx}", value=int(row['SLA_Resposta_Horas']), min_value=1, key=f"matriz_resp_{idx}")
                with col_p3:
                    sol_h = st.number_input(f"Sol. (h) #{idx}", value=int(row['SLA_Solucao_Horas']), min_value=1, key=f"matriz_sol_{idx}")
                with col_p4:
                    desc_txt = st.text_input(f"Descrição #{idx}", value=str(row['Descricao']) if pd.notna(row['Descricao']) else "", key=f"matriz_desc_{idx}")
                
                dados_atualizados.append({"prioridade": prio_nome, "resp": resp_h, "sol": sol_h, "desc": desc_txt})

            btn_salvar_matriz = st.form_submit_button("Salvar Alterações na Matriz", type="primary")

            if btn_salvar_matriz:
                conn_m = conectar_banco()
                if not conn_m:
                    st.error("Falha na conexão com o banco de dados.")
                else:
                    cursor_m = conn_m.cursor()
                    try:
                        cursor_m.execute("DELETE FROM dbo.Politicas_SLA")
                        for item in dados_atualizados:
                            cursor_m.execute(
                                "INSERT INTO dbo.Politicas_SLA (Prioridade, SLA_Resposta_Horas, SLA_Solucao_Horas, Descricao) VALUES (?, ?, ?, ?)",
                                (item["prioridade"], item["resp"], item["sol"], item["desc"])
                            )
                        conn_m.commit()
                        atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                        st.success("✅ Matriz de SLA atualizada com sucesso no banco de dados!")
                        st.rerun()
                    except Exception as ex_matriz:
                        st.error(f"Erro ao salvar matriz de SLA: {ex_matriz}")
                    finally:
                        cursor_m.close()
                        conn_m.close()

        st.divider()
        st.subheader(" Criar Nova Prioridade na Matriz")

        with st.form("form_nova_prioridade_sla"):
            c_np1, c_np2, c_np3, c_np4 = st.columns([1.5, 1, 1, 2.5])
            with c_np1:
                nova_prio_nome = st.text_input("Nome da Prioridade", placeholder="Ex: Urgente")
            with c_np2:
                novo_resp_h = st.number_input("SLA Resposta (h)", value=1, min_value=1)
            with c_np3:
                novo_sol_h = st.number_input("SLA Solução (h)", value=12, min_value=1)
            with c_np4:
                nova_desc = st.text_input("Descrição", placeholder="Descrição detalhada do nível")

            btn_criar_prio = st.form_submit_button("Adicionar Nova Prioridade", type="secondary")

            if btn_criar_prio:
                if nova_prio_nome.strip() != "":
                    conn_n = conectar_banco()
                    if not conn_n:
                        st.error("Falha na conexão com o banco de dados.")
                    else:
                        cursor_n = conn_n.cursor()
                        try:
                            cursor_n.execute(
                                "INSERT INTO dbo.Politicas_SLA (Prioridade, SLA_Resposta_Horas, SLA_Solucao_Horas, Descricao) VALUES (?, ?, ?, ?)",
                                (nova_prio_nome.strip(), novo_resp_h, novo_sol_h, nova_desc.strip())
                            )
                            conn_n.commit()
                            atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                            st.success(f"✅ Nova prioridade '{nova_prio_nome}' criada com sucesso!")
                            st.rerun()
                        except Exception as ex_nova:
                            st.error(f"Erro ao criar nova prioridade: {ex_nova}")
                        finally:
                            cursor_n.close()
                            conn_n.close()
                else:
                    st.warning("Por favor, informe o nome da nova prioridade.")

        st.divider()
        st.subheader(" Gestão de Setores Afetados")
        
        list_setores_admin = obter_lista_setores()
        
        col_sec_add, col_sec_del = st.columns(2)
        with col_sec_add:
            st.markdown("**Adicionar Novo Setor:**")
            with st.form("form_add_setor_admin"):
                novo_setor_input = st.text_input("Nome do Novo Setor", placeholder="Ex: Compras / Suprimentos")
                btn_add_setor_submit = st.form_submit_button("Adicionar Setor", type="primary")
                if btn_add_setor_submit:
                    if novo_setor_input.strip() != "":
                        conn_sec = conectar_banco()
                        if not conn_sec:
                            st.error("Falha na conexão com o banco de dados.")
                        else:
                            cursor_sec = conn_sec.cursor()
                            try:
                                cursor_sec.execute("INSERT INTO dbo.Chamados_Setores (Nome) VALUES (?)", (novo_setor_input.strip(),))
                                conn_sec.commit()
                                atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                                st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': f"✅ Setor '{novo_setor_input.strip()}' cadastrado com sucesso!"})
                                st.rerun()
                            except Exception as ex_sec:
                                st.error(f"Erro ao cadastrar setor (pode já existir): {ex_sec}")
                            finally:
                                cursor_sec.close()
                                conn_sec.close()
                    else:
                        st.warning("Por favor, digite o nome do setor.")

        with col_sec_del:
            st.markdown("**Remover Setor Existente:**")
            with st.form("form_del_setor_admin"):
                setor_del_sel = st.selectbox("Selecione o Setor para Remover", list_setores_admin)
                btn_del_setor_submit = st.form_submit_button("Remover Setor", type="secondary")
                if btn_del_setor_submit:
                    if setor_del_sel:
                        conn_dsec = conectar_banco()
                        if not conn_dsec:
                            st.error("Falha na conexão com o banco de dados.")
                        else:
                            cursor_dsec = conn_dsec.cursor()
                            try:
                                cursor_dsec.execute("DELETE FROM dbo.Chamados_Setores WHERE Nome = ?", (setor_del_sel,))
                                conn_dsec.commit()
                                atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                                st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': f"✅ Setor '{setor_del_sel}' removido com sucesso!"})
                                st.rerun()
                            except Exception as ex_dsec:
                                st.error(f"Erro ao remover setor: {ex_dsec}")
                            finally:
                                cursor_dsec.close()
                                conn_dsec.close()

        st.divider()
        st.subheader(" Gestão de Tipos de Serviço")
        
        list_tipos_admin = obter_lista_tipos_servico()
        
        col_tipo_add, col_tipo_del = st.columns(2)
        with col_tipo_add:
            st.markdown("**Adicionar Novo Tipo de Serviço:**")
            with st.form("form_add_tipo_admin"):
                novo_tipo_input = st.text_input("Nome do Novo Tipo de Serviço", placeholder="Ex: Substituição de Hardware")
                btn_add_tipo_submit = st.form_submit_button("Adicionar Tipo de Serviço", type="primary")
                if btn_add_tipo_submit:
                    if novo_tipo_input.strip() != "":
                        conn_tp = conectar_banco()
                        if not conn_tp:
                            st.error("Falha na conexão com o banco de dados.")
                        else:
                            cursor_tp = conn_tp.cursor()
                            try:
                                cursor_tp.execute("INSERT INTO dbo.Chamados_Tipos_Servico (Nome) VALUES (?)", (novo_tipo_input.strip(),))
                                conn_tp.commit()
                                atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                                st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': f"✅ Tipo de serviço '{novo_tipo_input.strip()}' cadastrado com sucesso!"})
                                st.rerun()
                            except Exception as ex_tp:
                                st.error(f"Erro ao cadastrar tipo de serviço (pode já existir): {ex_tp}")
                            finally:
                                cursor_tp.close()
                                conn_tp.close()
                    else:
                        st.warning("Por favor, digite o nome do tipo de serviço.")

        with col_tipo_del:
            st.markdown("**Remover Tipo de Serviço Existente:**")
            with st.form("form_del_tipo_admin"):
                tipo_del_sel = st.selectbox("Selecione o Tipo de Serviço para Remover", list_tipos_admin)
                btn_del_tipo_submit = st.form_submit_button("Remover Tipo de Serviço", type="secondary")
                if btn_del_tipo_submit:
                    if tipo_del_sel:
                        conn_dtp = conectar_banco()
                        if not conn_dtp:
                            st.error("Falha na conexão com o banco de dados.")
                        else:
                            cursor_dtp = conn_dtp.cursor()
                            try:
                                cursor_dtp.execute("DELETE FROM dbo.Chamados_Tipos_Servico WHERE Nome = ?", (tipo_del_sel,))
                                conn_dtp.commit()
                                atualizar_todos_os_caches() # Invalida e limpa todos os caches instantaneamente
                                st.session_state.alertas_sistema.append({'tipo': 'sucesso', 'msg': f"✅ Tipo de serviço '{tipo_del_sel}' removido com sucesso!"})
                                st.rerun()
                            except Exception as ex_dtp:
                                st.error(f"Erro ao remover tipo de serviço: {ex_dtp}")
                            finally:
                                cursor_dtp.close()
                                conn_dtp.close()