# =====================================================================
# 1. IMPORTAÇÃO DE TODAS AS BIBLIOTECAS NECESSÁRIAS
# =====================================================================
import streamlit as st        # Biblioteca principal para construção da interface web
import os                     # Manipulação de caminhos e diretórios do sistema operacional
import re                     # Expressões regulares para leitura de metadados e limpeza de código
import pyodbc                 # Conexão e manipulação de banco de dados Microsoft SQL Server
import hashlib                # Funções de hash criptográfico (ex: SHA-256 para senhas)
import pandas as pd           # Manipulação e exibição de tabelas de dados (DataFrames)
from datetime import datetime # Manipulação de datas e horários dos logs e avisos
import random                 # Geração de valores aleatórios para senhas temporárias
import string                 # Conjuntos de caracteres para senhas
import base64                 # Codificação de imagens em formato Base64 para persistência
from PIL import Image         # Processamento, redimensionamento e leitura de imagens locais
import io                     # Manipulação de fluxos de bytes em memória
import zlib                   # Compactação/hash numérico para identificação de aplicativos
import resend                 # API de envio de e-mails transacionais (Recuperação de senha/Notificações)
from dotenv import load_dotenv # Carregamento de variáveis de ambiente do arquivo .env
from database import obter_conexao_principal # Função centralizada de conexão com o Banco de Dados SQL Server
from styles import injetar_estilo_global     # Módulo centralizado de estilização CSS global do portal

# =====================================================================
# 2. DEFINIÇÃO DINÂMICA DE CAMINHOS E CARREGAMENTO DE SEGURANÇA (.ENV)
# =====================================================================
DIR_PROJETO = os.path.dirname(os.path.abspath(__file__)) # Define o diretório base onde o Main.py está localizado
CAMINHO_FAVICON = os.path.join(DIR_PROJETO, "Favicon.png") # Caminho absoluto para o ícone da aba do navegador
CAMINHO_LOGO = os.path.join(DIR_PROJETO, "Logo.png")       # Caminho absoluto para o logotipo principal da empresa

# Carrega as variáveis sensíveis do arquivo .env com sobreposição ativa
load_dotenv(os.path.join(DIR_PROJETO, ".env"), override=True)
resend.api_key = os.getenv("RESEND_API_KEY_Portal") # Configuração da chave de API do serviço de e-mail Resend

def carregar_imagem_disco(caminho):
    """Função auxiliar segura para carregar imagens do disco rígido usando a biblioteca PIL."""
    try:
        if os.path.exists(caminho):
            return Image.open(caminho)
    except Exception:
        pass
    return None

def ler_arquivo_seguro(caminho):
    """Lê arquivos de texto em disco alternando codificações para evitar erros de acentuação/Unicode."""
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            with open(caminho, "r", encoding=encoding) as arquivo:
                return arquivo.read().lstrip('\ufeff')
        except UnicodeDecodeError:
            continue
    with open(caminho, "r", encoding="utf-8", errors="replace") as arquivo:
        return arquivo.read().lstrip('\ufeff')

# =====================================================================
# 3. MAPEAMENTO DINÂMICO E AUTOMÁTICO DA PASTA 'pages/'
# =====================================================================
def extrair_metadados_pagina(caminho_arquivo):
    """Extrai o título e ícone personalizados definidos no topo das páginas internas."""
    try:
        conteudo = ler_arquivo_seguro(caminho_arquivo)
        match_title = re.search(r'page_title\s*=\s*["\']([^"\']+)["\']', conteudo)
        match_icon = re.search(r'page_icon\s*=\s*["\']([^"\']+)["\']', conteudo)
        titulo = match_title.group(1) if match_title else None
        icone = match_icon.group(1) if match_icon else ""
        if titulo:
            return f"{icone} {titulo}".strip() if icone else titulo
    except Exception:
        pass
    return None

def carregar_mapa_aplicativos_automatico():
    """Varre automaticamente a pasta 'pages/' mapeando todos os aplicativos disponíveis para os usuários."""
    pasta_pages = os.path.join(DIR_PROJETO, "pages")
    mapa_gerado = {}
    if os.path.exists(pasta_pages):
        for arquivo in os.listdir(pasta_pages):
            if arquivo.endswith(".py"):
                caminho_completo = os.path.join(pasta_pages, arquivo)
                nome_sem_ext = arquivo[:-3]
                partes = nome_sem_ext.split("_", 1)
                chave_id = partes[1] if len(partes) > 1 else nome_sem_ext
                titulo_extraido = extrair_metadados_pagina(caminho_completo)
                if not titulo_extraido:
                    titulo_formatado = " ".join(partes[1:]).replace("app", "").strip()
                    titulo_extraido = f"{titulo_formatado.capitalize()}" if titulo_formatado else f"{chave_id}"
                mapa_gerado[chave_id] = {
                    "titulo": titulo_extraido,
                    "path": f"pages/{arquivo}",
                    "permissao_db": chave_id
                }
    return mapa_gerado

MAPA_APLICATIVOS = carregar_mapa_aplicativos_automatico()

# Configuração global da página do Streamlit (Título, Favicon e Layout Expandido)
icone_favicon = carregar_imagem_disco(CAMINHO_FAVICON) or "🏢"
st.set_page_config(page_title="Portal Repress | Intranet Corporativa", page_icon=icone_favicon, layout="wide")
injetar_estilo_global() # Injeta a folha de estilos CSS centralizada

def executar_query(query, parametros=None, fetch=False):
    """Executa comandos SQL (SELECT, INSERT, UPDATE, DELETE) de forma centralizada e segura no SQL Server."""
    try:
        conn = obter_conexao_principal()
        if not conn: return None
        try:
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
            conn.setencoding(encoding='utf-8')
        except Exception:
            pass
        cursor = conn.cursor()
        if parametros: cursor.execute(query, parametros)
        else: cursor.execute(query)
        if fetch:
            colunas = [column[0] for column in cursor.description]
            resultados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
            cursor.close(); conn.close()
            return resultados
        else:
            conn.commit()
            cursor.close(); conn.close()
            return True
    except Exception as e:
        st.session_state["ultimo_erro_sql"] = str(e)
        return None

def app_key_to_id(chave_app):
    """Gera um hash numérico único para mapear aplicativos na tabela de favoritos do banco de dados."""
    return zlib.crc32(str(chave_app).encode('utf-8')) & 0x7FFFFFFF

def gerar_hash_senha(senha_texto):
    """Converte uma senha em texto plano para o padrão seguro SHA-256."""
    return hashlib.sha256(senha_texto.encode('utf-8')).hexdigest()

def gerar_senha_temporaria(tamanho=8):
    """Gera uma string alfanumérica aleatória para servir como senha temporária de recuperação."""
    return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(tamanho))

def buscar_usuario_por_email_db(email):
    """Busca os dados cadastrais, permissões e status de um usuário ativo no banco de dados corporativo."""
    query = "SELECT id_usuario, nome, email, nivel, acessos, ativo, foto_perfil FROM [auth].[vw_UsuariosAtivos] WHERE email = ?"
    resultado = executar_query(query, (email,), fetch=True)
    if resultado and len(resultado) > 0:
        usuario = resultado[0]
        usuario['acessos'] = usuario['acessos'].split(',') if usuario['acessos'] else []
        return usuario
    return None

def registrar_log_db(email_usuario, acao):
    """Registra uma linha de auditoria na tabela de logs do sistema a cada ação relevante do usuário."""
    executar_query("INSERT INTO [auth].[Logs] (email_usuario, acao, data_hora) VALUES (?, ?, ?)", (email_usuario, acao, datetime.now()))

@st.cache_data(ttl=300, show_spinner=False)
def buscar_favoritos_usuario_cache(id_usuario):
    """Busca em cache (por 5 minutos) a lista de atalhos favoritos salvos pelo usuário logado."""
    if not id_usuario: return []
    query = "SELECT id_app FROM [auth].[Favoritos] WHERE id_usuario = ?"
    resultado = executar_query(query, (id_usuario,), fetch=True)
    if resultado is not None:
        fav_ids = {item['id_app'] for item in resultado}
        return [chave for chave in MAPA_APLICATIVOS if app_key_to_id(chave) in fav_ids]
    return []

def alternar_favorito_db(id_usuario, chave_app):
    """Adiciona ou remove um aplicativo da lista de atalhos favoritos do usuário no banco."""
    if not id_usuario or not chave_app: return False
    id_app_num = app_key_to_id(chave_app)
    query_check = "SELECT id_favorito FROM [auth].[Favoritos] WHERE id_usuario = ? AND id_app = ?"
    check = executar_query(query_check, (id_usuario, id_app_num), fetch=True)
    if check is None: return False
    if len(check) > 0:
        executar_query("DELETE FROM [auth].[Favoritos] WHERE id_usuario = ? AND id_app = ?", (id_usuario, id_app_num))
    else:
        executar_query("INSERT INTO [auth].[Favoritos] (id_usuario, id_app, data_adicao) VALUES (?, ?, ?)", (id_usuario, id_app_num, datetime.now()))
    buscar_favoritos_usuario_cache.clear()
    return True

@st.cache_data(ttl=300, show_spinner=False)
def buscar_mural_rh_cache():
    """Busca em cache os avisos ativos publicados no mural corporativo de RH."""
    query_mural = "SELECT id_aviso, titulo, mensagem, data_publicacao, autor, imagem FROM [dbo].[vw_MuralAtivo] ORDER BY data_publicacao DESC"
    return executar_query(query_mural, fetch=True) or []

def enviar_email_recuperacao_resend(email_destino, nome_usuario, nova_senha_temp):
    """Envia um e-mail transacional automatizado contendo a nova senha temporária via API do Resend."""
    try:
        load_dotenv(os.path.join(DIR_PROJETO, ".env"), override=True)
        resend.api_key = os.getenv("RESEND_API_KEY_Portal")
        params = {
            "from": "Portal Repress <nao-responda@portal.repress.com.br>",
            "to": [email_destino],
            "subject": "Portal Repress - Sua Nova Senha de Acesso",
            "html": f"""
                <div style="font-family: Arial, sans-serif; background-color: #F4F7FA; padding: 20px;">
                    <div style="max-width: 500px; margin: 0 auto; background-color: #FFFFFF; padding: 25px; border-radius: 8px; border: 1px solid #E2E8F0;">
                        <h2 style="color: #003B70; text-align: center; margin-top: 0;">Portal Repress</h2>
                        <hr style="border: 0; border-top: 1px solid #E2E8F0;">
                        <p style="color: #334155; font-size: 14px;">Olá, <b>{nome_usuario}</b>!</p>
                        <p style="color: #334155; font-size: 14px;">Sua nova senha temporária para acessar o portal é:</p>
                        <div style="background-color: #E0F2FE; color: #003B70; font-weight: bold; font-size: 20px; text-align: center; padding: 12px; border-radius: 6px; letter-spacing: 2px; margin: 20px 0;">
                            {nova_senha_temp}
                        </div>
                    </div>
                </div>
            """
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        st.session_state["ultimo_erro_sql"] = str(e)
        return False

# =====================================================================
# GERENCIAMENTO DE ESTADO E URL / LOGOUT
# =====================================================================
for key, val in [("logado", False), ("pagina_atual", "login"), ("usuario_dados", {}), ("user_id", ""), ("tela_auth", "login"), ("app_ativo_atual", "home")]:
    if key not in st.session_state: st.session_state[key] = val

# Tratamento da ação de logout disparada via link HTML da faixa superior
if st.query_params.get("action") == "logout":
    if st.session_state.get("user_id"):
        registrar_log_db(st.session_state["user_id"], "Logout realizado")
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

url_user_param = st.query_params.get("user")
url_pagina_param = st.query_params.get("p")

if not st.session_state["logado"] and url_user_param:
    usuario_recuperado_db = buscar_usuario_por_email_db(url_user_param)
    if usuario_recuperado_db:
        st.session_state["logado"] = True
        st.session_state["user_id"] = url_user_param
        st.session_state["usuario_dados"] = usuario_recuperado_db
        st.session_state["pagina_atual"] = url_pagina_param if url_pagina_param else "home"

def navegar_para(pagina):
    """Atualiza o estado da página atual e recarrega a aplicação."""
    st.session_state["pagina_atual"] = pagina
    if pagina == "home": st.session_state["app_ativo_atual"] = "home"
    st.rerun()

# =====================================================================
# CABEÇALHO GLOBAL (Logo ampliado para width=90px e perfil centralizado)
# =====================================================================
def renderizar_cabecalho_global(exibir_voltar_home=False):
    """Renderiza o cabeçalho unificado com logotipo expandido (90px), perfil centralizado e navegação segura."""
    dados_user = st.session_state.get('usuario_dados', {})
    nivel = dados_user.get('nivel', 'usuario')
    user_email = st.session_state.get('user_id', '')
    
    # Colunas mantidas com espaçamento simétrico para perfil centralizado
    col_hdr_logo, col_espaco, col_hdr_welcome, col_hdr_actions = st.columns([0.8, 1.2, 4.5, 3.5])
    
    with col_hdr_logo:
        logo_img = carregar_imagem_disco(CAMINHO_LOGO)
        if logo_img: 
            # Logotipo ajustado para width=90 para preencher perfeitamente a faixa vertical
            st.image(logo_img, width=90)
        else: 
            st.markdown("<h5 style='color:#003B70; margin:0;'>REPRESS</h5>", unsafe_allow_html=True)
            
    with col_espaco:
        st.write("") # Coluna de espaçamento horizontal controlada
        
    with col_hdr_welcome:
        foto_b64 = dados_user.get('foto_perfil')
        nome_user = dados_user.get('nome', 'Colaborador')
        c_avatar, c_textos = st.columns([0.06, 0.94], gap="small")
        with c_avatar:
            if foto_b64: st.markdown(f"<img src='{foto_b64}' class='img-perfil-header'>", unsafe_allow_html=True)
            else: st.markdown("<div class='img-perfil-header' style='display:flex;align-items:center;justify-content:center;background:#E0F2FE;color:#003B70;font-size:14px;'>👤</div>", unsafe_allow_html=True)
        with c_textos:
            st.markdown(f"<span class='saudacao-texto'>Olá, {nome_user} 👋</span>", unsafe_allow_html=True)
            with st.popover("Meu Perfil"):
                with st.form("form_alterar_senha"):
                    st.markdown("**🔒 Alterar Senha**")
                    senha_atual = st.text_input("Senha Atual", type="password", key="hdr_s_atual")
                    senha_nova = st.text_input("Nova Senha", type="password", key="hdr_s_nova")
                    if st.form_submit_button("Salvar Senha"):
                        if executar_query("SELECT id_usuario FROM [auth].[Usuarios] WHERE email=? AND senha_hash=?", (dados_user['email'], gerar_hash_senha(senha_atual)), fetch=True):
                            executar_query("UPDATE [auth].[Usuarios] SET senha_hash=? WHERE email=?", (gerar_hash_senha(senha_nova), dados_user['email']))
                            st.success("Senha alterada!")
                        else: st.error("Senha atual incorreta.")
                with st.form("form_atualizar_foto"):
                    st.markdown("**Atualizar Foto**")
                    upload_foto = st.file_uploader("Nova foto", type=["jpg", "jpeg", "png"], key="hdr_upload_foto")
                    if upload_foto is not None and st.form_submit_button("Gravar Foto"):
                        img = Image.open(upload_foto)
                        img.thumbnail((150, 150))
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=75)
                        str_img_b64 = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
                        executar_query("UPDATE [auth].[Usuarios] SET foto_perfil=? WHERE email=?", (str_img_b64, dados_user['email']))
                        st.session_state['usuario_dados']['foto_perfil'] = str_img_b64
                        st.success("Foto atualizada!")
                        st.rerun()
                    
    with col_hdr_actions:
        # target="_self" garante abertura estrita na mesma aba
        html_botoes = '<div class="acoes-topo-repress-html">'
        if exibir_voltar_home:
            html_botoes += f'<a href="?user={user_email}&p=home" target="_self" class="btn-topo-html">Portal</a>'
        if nivel == "admin":
            html_botoes += f'<a href="?user={user_email}&p=painel_admin" target="_self" class="btn-topo-html">Admin</a>'
        html_botoes += f'<a href="?action=logout" target="_self" class="btn-topo-html">Sair</a>'
        html_botoes += '</div>'
        st.markdown(html_botoes, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 4px 0px 8px 0px; border-color: #E2E8F0;'>", unsafe_allow_html=True)

# =====================================================================
# EXECUTOR DE APLICATIVOS EXTERNOS
# =====================================================================
def executar_app_externo(chave_app):
    """Carrega e executa dinamicamente os scripts Python localizados na pasta 'pages/'."""
    info_app = MAPA_APLICATIVOS.get(chave_app)
    if not info_app: return st.error("Aplicativo não localizado.")
    renderizar_cabecalho_global(exibir_voltar_home=True)
    caminho_arquivo = os.path.join(DIR_PROJETO, info_app["path"])
    eh_transicao_inicial = st.session_state.get("app_ativo_atual") != chave_app
    try:
        codigo = ler_arquivo_seguro(caminho_arquivo)
        codigo_limpo = re.sub(r'st\.set_page_config\s*\(.*?\)', 'pass', codigo, flags=re.DOTALL)
        namespace = {'__name__': '__main__', '__file__': caminho_arquivo, 'st': st}
        if eh_transicao_inicial:
            with st.spinner(f"Carregando {info_app['titulo']}..."):
                exec(codigo_limpo, namespace)
                st.session_state["app_ativo_atual"] = chave_app
        else:
            exec(codigo_limpo, namespace)
        registrar_log_db(st.session_state["user_id"], f"Acessou app: {info_app['titulo']}")
    except Exception as e:
        st.error(f"Erro técnico ao executar '{info_app['titulo']}': {e}")

# =====================================================================
# TELA DE LOGIN E RECUPERAÇÃO DE SENHA
# =====================================================================
def tela_login():
    """Renderiza a interface de autenticação corporativa."""
    col1, col2, col3 = st.columns([1.8, 1.4, 1.8])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        logo_img = carregar_imagem_disco(CAMINHO_LOGO)
        if logo_img:
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2: st.image(logo_img, use_container_width=True)
        st.markdown("<h1 style='text-align: center; color: #003B70; margin-top: 10px; margin-bottom: 20px;'>Portal Repress</h1>", unsafe_allow_html=True)
        
        if st.session_state["tela_auth"] == "login":
            with st.form("form_login_principal"):
                email = st.text_input("E-mail corporativo")
                senha = st.text_input("Senha", type="password")
                btn_enviar_login = st.form_submit_button("Acessar Intranet", use_container_width=True)
                
                if btn_enviar_login:
                    check_db = executar_query("SELECT id_usuario FROM [auth].[Usuarios] WHERE email = ? AND senha_hash = ? AND ativo = 1", (email, gerar_hash_senha(senha)), fetch=True)
                    if check_db:
                        st.session_state["logado"] = True
                        st.session_state["user_id"] = email
                        st.session_state["usuario_dados"] = buscar_usuario_por_email_db(email)
                        registrar_log_db(email, "Login realizado com sucesso")
                        navegar_para("home")
                    else: st.error("Credenciais incorretas ou conta inativa.")
                        
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Esqueci minha senha", use_container_width=True):
                st.session_state["tela_auth"] = "reset"
                st.rerun()
                
        elif st.session_state["tela_auth"] == "reset":
            with st.form("form_reset_senha"):
                st.markdown("<h4 style='text-align: center; color: #003B70;'>Recuperação de Acesso</h4>", unsafe_allow_html=True)
                email_reset = st.text_input("E-mail corporativo")
                btn_enviar_reset = st.form_submit_button("Enviar Nova Senha", use_container_width=True)
                
                if btn_enviar_reset:
                    check_user = buscar_usuario_por_email_db(email_reset)
                    if check_user:
                        nova_senha = gerar_senha_temporaria()
                        executar_query("UPDATE [auth].[Usuarios] SET senha_hash = ? WHERE email = ?", (gerar_hash_senha(nova_senha), email_reset))
                        if enviar_email_recuperacao_resend(email_reset, check_user['nome'], nova_senha):
                            st.success("E-mail enviado com sucesso! Verifique sua caixa de entrada e spam.")
                            registrar_log_db(email_reset, "Solicitação de reset de senha enviada")
                        else: st.error("Falha ao comunicar com a API do Resend.")
                    else: st.error("O e-mail informado não consta na base de dados.")
                    
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Voltar ao Login", use_container_width=True):
                st.session_state["tela_auth"] = "login"
                st.rerun()

# =====================================================================
# TELA HOME PRINCIPAL
# =====================================================================
def tela_home():
    """Renderiza a página inicial (Home) do portal."""
    dados_user = st.session_state['usuario_dados']
    id_usuario = dados_user.get('id_usuario')
    nivel = dados_user['nivel']
    apps_permitidos = dados_user['acessos']
    renderizar_cabecalho_global(exibir_voltar_home=False)
    
    col_main, col_side = st.columns([2.0, 1.0])
    with col_main:
        avisos = buscar_mural_rh_cache()
        st.markdown("<div class='card-widget-repress' style='margin-bottom:8px;'><h5 style='margin:0;color:#003B70;'>Mural de Comunicados</h5></div>", unsafe_allow_html=True)
        if avisos:
            for aviso in avisos:
                data_f = aviso['data_publicacao'].strftime('%d/%m/%Y %H:%M') if isinstance(aviso['data_publicacao'], datetime) else aviso['data_publicacao']
                with st.expander(f"📢 {aviso['titulo']}  ({data_f})"):
                    html_img = f"<img src='{aviso['imagem']}' style='max-width:100%; max-height:250px; border-radius:8px;'><br><br>" if aviso.get('imagem') else ""
                    st.markdown(f"<div>{html_img}{aviso['mensagem']}</div><small style='color: #94A3B8;'>Publicado por <b>{aviso['autor']}</b> em {data_f}</small>", unsafe_allow_html=True)
        else: st.info("Nenhum aviso ou comunicado novo no mural no momento.")
        
    with col_side:
        lista_favoritos = buscar_favoritos_usuario_cache(id_usuario)
        st.markdown("<div class='card-widget-repress' style='margin-bottom:8px;'><h5 style='margin:0;color:#003B70;'>Atalhos</h5></div>", unsafe_allow_html=True)
        if lista_favoritos:
            for fav_key in lista_favoritos:
                if fav_key in MAPA_APLICATIVOS:
                    info_fav = MAPA_APLICATIVOS[fav_key]
                    c_btn, c_del = st.columns([0.82, 0.18])
                    with c_btn:
                        if st.button(f"{info_fav['titulo']}", key=f"fav_{fav_key}", use_container_width=True): navegar_para(f"rodar_{fav_key}")
                    with c_del:
                        if st.button("❌", key=f"del_{fav_key}", use_container_width=True): alternar_favorito_db(id_usuario, fav_key); st.rerun()
        else: st.caption("Nenhum atalho favoritado.")
        
        st.markdown("<hr style='margin: 8px 0px; border-color: #E2E8F0;'>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: #003B70; margin-bottom: 6px;'>Aplicativos</h5>", unsafe_allow_html=True)
        termo_busca = st.text_input("🔍", placeholder="Buscar app...", label_visibility="collapsed")
        for chave_app, dados_app in MAPA_APLICATIVOS.items():
            liberado = True if nivel == "admin" else (dados_app["permissao_db"] in apps_permitidos)
            if liberado and (not termo_busca or termo_busca.lower() in dados_app['titulo'].lower()):
                eh_fav = chave_app in lista_favoritos
                key_top = f"is_fav_{chave_app}" if eh_fav else f"not_fav_{chave_app}"
                with st.container(border=True):
                    if st.button("ATALHO RÁPIDO" if eh_fav else "Adicionar Atalho", key=f"btn_fav_{key_top}", use_container_width=True):
                        alternar_favorito_db(id_usuario, chave_app); st.rerun()
                    if st.button(f"{dados_app['titulo']}", key=f"btn_app_{chave_app}", use_container_width=True): navegar_para(f"rodar_{chave_app}")

def tela_painel_admin():
    """Renderiza o painel administrativo do sistema."""
    renderizar_cabecalho_global(exibir_voltar_home=True)
    st.title("Painel de Gestão")
    aba_lista, aba_logs = st.tabs(["Usuários", "Logs"])
    lista_usuarios = executar_query("SELECT id_usuario, nome, email, nivel, ativo, acessos FROM [auth].[vw_UsuariosAtivos]", fetch=True) or []
    with aba_lista:
        if lista_usuarios: st.dataframe(pd.DataFrame(lista_usuarios), use_container_width=True, hide_index=True)
    with aba_logs:
        logs = executar_query("SELECT TOP 50 data_hora, email_usuario, acao FROM [auth].[Logs] ORDER BY data_hora DESC", fetch=True)
        if logs: st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)

# =====================================================================
# ROTEADOR PRINCIPAL
# =====================================================================
if not st.session_state.get("logado", False):
    st.query_params.clear()
    tela_login()
else:
    st.query_params["user"] = st.session_state["user_id"]
    st.query_params["p"] = st.session_state["pagina_atual"]
    pagina = st.session_state["pagina_atual"]
    if pagina in ["login", "home"]: tela_home()
    elif pagina == "painel_admin": tela_painel_admin()
    elif pagina.startswith("rodar_"): executar_app_externo(pagina.replace("rodar_", ""))