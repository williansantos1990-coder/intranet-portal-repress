# =====================================================================
# APLICATIVO: GESTÃO DE COMUNICADOS - MURAL RH (8_appMuralRH.py)
# =====================================================================

import streamlit as st              # Importa o framework principal para aplicações web
import pandas as pd                 # Importa biblioteca para manipulação de DataFrames
import base64                       # Importa codificação em base64 para imagens e anexos
from PIL import Image               # Importa biblioteca para processamento de imagens
import io                           # Importa manipulação de fluxos de bytes em memória
import os                           # Importa funções de interatividade com o sistema operacional
import uuid                         # Importa gerador de identificadores únicos universais
import pyodbc                       # Importa conector ODBC para comunicação com SQL Server
import re                           # Importa expressões regulares para manipulação de textos e links
from datetime import datetime, date, time, timedelta # Importa classes para tratamento de datas e horários
from database import obter_conexao_principal # Importa função de conexão com banco de dados central
from dotenv import load_dotenv      # Importa carregador de variáveis de ambiente (.env)
import resend                       # Importa biblioteca oficial da API do Resend para envio de e-mails

# Bloco protegido para importar o editor de texto rico visual (Quill), com fallback seguro
try:
    from streamlit_quill import st_quill
    TEM_QUILL = True
except ImportError:
    TEM_QUILL = False

# Carrega as variáveis de ambiente do arquivo .env com prioridade de sobrescrita
load_dotenv(override=True)
resend.api_key = os.getenv("RESEND_API_KEY_Muralrh") # Define a chave da API do Resend específica para o Mural RH

# Definição dos metadados de exibição da página no Streamlit
page_title = "Gestão Mural RH"
page_icon = "📢"

# Configuração inicial da página com layout amplo (wide)
st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")

# Bloco protegido para importação e injeção do arquivo de estilos visuais globais
try:
    from styles import injetar_estilo_global
    injetar_estilo_global()
except ImportError:
    pass

# Função para estabelecer conexão com o banco de dados com suporte a UTF-8 (permite emojis e acentuação correta)
def conectar_banco_rh():
    conn = obter_conexao_principal()
    if not conn: return None
    try:
        conn.setencoding(encoding='utf-8')
    except Exception:
        pass
    return conn

# Função genérica para execução de comandos SQL no contexto do Mural
def executar_query_rh(query, parametros=None, fetch=False):
    conn = conectar_banco_rh()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor()
        if parametros: cursor.execute(query, parametros)
        else: cursor.execute(query)
        if fetch:
            colunas = [column[0] for column in cursor.description]
            resultados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
            return resultados
        else:
            conn.commit()
            st.cache_data.clear() # Limpa o cache de dados global após alterações
            return True
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        st.error(f"Erro SQL: {e}")
        return None if fetch else False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Função otimizada para buscar os dados cadastrais do usuário conectado via autenticação do portal
@st.cache_data(ttl=30, show_spinner=False)
def buscar_dados_usuario_rh(email_usuario):
    conn = conectar_banco_rh()
    if not conn:
        return {"id_usuario": 1, "nome": "Willian Santos", "email": email_usuario, "nivel": "admin"}
    try:
        query = "SELECT id_usuario, nome, email, nivel FROM [aplicativos_db].[auth].[Usuarios] WHERE email = ?"
        df = pd.read_sql(query, conn, params=[email_usuario])
        if not df.empty:
            return df.iloc[0].to_dict()
        else:
            return {"id_usuario": 1, "nome": "Willian Santos", "email": email_usuario, "nivel": "admin"}
    except Exception:
        return {"id_usuario": 1, "nome": "Willian Santos", "email": email_usuario, "nivel": "admin"}
    finally:
        if conn:
            try: conn.close()
            except: pass

# Função para redimensionar e converter imagens principais do comunicado em base64
def processar_imagem(upload_foto):
    if upload_foto is not None:
        img = Image.open(upload_foto)
        img.thumbnail((800, 800))
        if img.mode != 'RGB': img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    return None

# Função para redimensionar e converter imagens de assinatura em base64
def processar_imagem_assinatura(upload_assinatura):
    if upload_assinatura is not None:
        img = Image.open(upload_assinatura)
        img.thumbnail((400, 400))
        if img.mode != 'RGB': img = img.convert('RGB')
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    return None

# Função para processar e garantir que o HTML do editor de texto ou texto puro seja renderizado corretamente no e-mail
def processar_html_mensagem(mensagem_bruta):
    if not mensagem_bruta: return ""
    if "<p>" in mensagem_bruta or "<span>" in mensagem_bruta or "<strong>" in mensagem_bruta:
        return mensagem_bruta
    texto_formatado = mensagem_bruta.replace("\n", "<br>")
    padrao_url = re.compile(r'(https?://[^\s<]+)')
    return padrao_url.sub(r'<a href="\1" target="_blank" style="color: #002B50; text-decoration: underline;">\1</a>', texto_formatado)

# Função auxiliar robusta para converter valores de data vindos do banco
def para_objeto_date(val):
    if isinstance(val, datetime): return val.date()
    if isinstance(val, date): return val
    if isinstance(val, str):
        try: return datetime.strptime(val.split()[0], "%Y-%m-%d").date()
        except: pass
    return val

# Função para buscar a foto/avatar do autor cadastrado consultando a view otimizada de usuários ativos
@st.cache_data(ttl=60, show_spinner=False)
def obter_foto_usuario(nome_autor):
    if not nome_autor: return None
    conn = conectar_banco_rh()
    if not conn: return None
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT foto_perfil FROM [auth].[vw_UsuariosAtivos] WHERE nome = ?", (nome_autor,))
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return None
    except Exception:
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Função para buscar e-mails de destinatários permitidos cadastrados no sistema
@st.cache_data(ttl=60, show_spinner=False)
def obter_emails_permitidos():
    conn = conectar_banco_rh()
    if not conn: return []
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM [auth].[Usuarios] WHERE ativo = 1 AND (nivel = 'admin' OR acessos LIKE '%appMuralRH%')")
        resultados = cursor.fetchall()
        return [row[0] for row in resultados if row[0] and '@' in row[0]]
    except Exception:
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Recupera o usuário conectado da query string (sessão do portal) e busca seus dados cadastrais corretos
query_params_rh = st.query_params
email_sessao_rh = query_params_rh.get("user", "willian.santos@repress.com.br")
dados_usuario_logado = buscar_dados_usuario_rh(email_sessao_rh)

# Inicializa variável de estado para reset de formulários se não existir
if "reset_rh" not in st.session_state: st.session_state.reset_rh = 0

# Títulos principais da interface do aplicativo
st.markdown("<h1>📢 Gestão de Comunicados - Mural RH</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>Gerencie as publicações do portal corporativo com alta performance.</p>", unsafe_allow_html=True)

# Criação de abas para separar a criação de novas postagens e a gestão das existentes
aba_novo, aba_gerenciar = st.tabs(["Novo Comunicado", "Gerenciar Publicações"])

with aba_novo:
    with st.container(border=True):
        # 1º: Campo de Título do Comunicado
        titulo = st.text_input("Título do Comunicado *", key=f"titulo_{st.session_state.reset_rh}")
        
        # 2º: Checkbox e Campo de Definir Validade alinhados abaixo do título
        tem_expiracao = st.checkbox("Definir Validade", key=f"chk_exp_{st.session_state.reset_rh}")
        data_expiracao = None
        if tem_expiracao:
            data_expiracao = st.date_input("Validade", min_value=date.today(), format="DD/MM/YYYY", key=f"data_exp_{st.session_state.reset_rh}")

        # 3º: Campo de Mensagem com suporte a editor rico visual (ou text_area de fallback)
        st.markdown("<label style='font-size: 14px; font-weight: 600;'>Mensagem *</label>", unsafe_allow_html=True)
        if TEM_QUILL:
            mensagem = st_quill(placeholder="Digite ou cole aqui sua mensagem formatada (Ctrl+V suporta estilos, cores, fontes e emojis)...", key=f"msg_quill_{st.session_state.reset_rh}")
        else:
            mensagem = st.text_area("Mensagem *", height=150, key=f"msg_{st.session_state.reset_rh}", label_visibility="collapsed", help="Cole seus textos formatados, emojis ou links.")
        
        # Demais campos do formulário (Imagem opcional e configurações de e-mail)
        imagem_upload = st.file_uploader("Imagem (Opcional)", type=["jpg", "jpeg", "png"], key=f"img_{st.session_state.reset_rh}")
        enviar_email = st.checkbox("Disparar por E-mail", key=f"chk_email_{st.session_state.reset_rh}")
        
        assinatura_texto, assinatura_upload = "", None
        
        if enviar_email:
            with st.container(border=True):
                c_ass1, c_ass2 = st.columns(2)
                with c_ass1: assinatura_texto = st.text_area("Assinatura (Texto)", key=f"ass_txt_{st.session_state.reset_rh}")
                with c_ass2: assinatura_upload = st.file_uploader("Assinatura (Imagem)", type=["jpg", "jpeg", "png"], key=f"ass_img_{st.session_state.reset_rh}")

        # Botão de submissão do formulário com validação transacional
        if st.button("Publicar Comunicado", type="primary", key=f"btn_pub_{st.session_state.reset_rh}"):
            if titulo and mensagem:
                info_progresso = st.info("⏳ Processando publicação e gravando dados no banco...")
                
                uid_gerado = str(uuid.uuid4())
                
                img_b64 = processar_imagem(imagem_upload)
                
                autor = dados_usuario_logado.get('nome', 'Equipe RH')
                mensagem_limpa = mensagem.strip()
                
                # Insere o comunicado na base de dados SQL Server chamando a Stored Procedure corporativa
                sucesso_db = executar_query_rh(
                    "EXEC dbo.sp_CriarComunicado ?, ?, ?, ?, ?, ?, ?",
                    (titulo, mensagem_limpa, autor, img_b64, data_expiracao, None, uid_gerado)
                )

                if not sucesso_db:
                    info_progresso.empty()
                    st.error("⚠️ Erro ao gravar o comunicado no banco de dados. Publicação cancelada.")
                    st.toast(" Erro ao salvar comunicado.", icon="⚠️")
                    st.stop()

                if enviar_email:
                    destinatarios = obter_emails_permitidos()
                    if destinatarios:
                        msg_html_body = processar_html_mensagem(mensagem_limpa)
                        html_email = f"""
                        <div style="font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
                            <div style="margin-bottom: 25px;">
                                {msg_html_body}
                            </div>
                        """
                        
                        if assinatura_upload is not None:
                            ass_b64 = processar_imagem_assinatura(assinatura_upload)
                            if ass_b64:
                                html_email += f"""
                                <div style="margin-top: 25px; margin-bottom: 15px;">
                                    <img src="{ass_b64}" alt="Assinatura" style="max-width: 100%; height: auto; display: block;">
                                </div>
                                """
                        elif assinatura_texto:
                            html_email += f"<div style='margin-top: 20px; color: #475569;'>{processar_html_mensagem(assinatura_texto)}</div>"
                            
                        html_email += """
                            <br>
                            <hr style="border: none; border-top: 1px solid #E2E8F0; margin-top: 25px; margin-bottom: 15px;">
                            <p style="font-size: 11px; color: #64748B; margin: 0;">
                                <i>Esta é uma mensagem automática enviada diretamente pelo <b>Portal Repress</b>.</i>
                            </p>
                        </div>
                        """
                        
                        anexos_resend = []
                        if imagem_upload is not None:
                            imagem_upload.seek(0)
                            anexos_resend.append({
                                "filename": f"comunicado_{imagem_upload.name}",
                                "content": list(imagem_upload.read())
                            })
                            
                        params = {
                            "from": "Mural RH - Repress <nao-responda@rh.repress.com.br>",
                            "to": ["willian.santos@repress.com.br"],
                            "bcc": destinatarios,
                            "subject": titulo,
                            "html": html_email,
                        }
                        if anexos_resend:
                            params["attachments"] = anexos_resend
                            
                        resend.Emails.send(params)
                        
                info_progresso.empty()
                st.session_state.reset_rh += 1
                st.toast("✅ Comunicado publicado com sucesso!", icon="🎉")
                st.success("Comunicado publicado e processado com sucesso!")
                st.rerun()
            else: 
                st.warning("⚠️ Por favor, preencha o Título e A Mensagem do comunicado.")
                st.toast(" Preencha os campos obrigatórios.", icon="⚠️")

with aba_gerenciar:
    edit_id = st.session_state.get("editando_id")
    if edit_id:
        aviso_edit_list = executar_query_rh("SELECT * FROM dbo.MuralRH WHERE id_aviso = ?", (edit_id,), fetch=True)
        if aviso_edit_list:
            aviso_e = aviso_edit_list[0]

            with st.container(border=True):
                st.markdown(f"#### Editando Comunicado: {aviso_e['titulo']}")
                
                e_titulo = st.text_input("Título do Comunicado *", value=aviso_e['titulo'], key="edit_titulo")
                
                tem_exp_atual = bool(aviso_e.get('data_expiracao'))
                e_tem_exp = st.checkbox("Definir Validade", value=tem_exp_atual, key="edit_chk_exp")
                e_data_exp = None
                if e_tem_exp:
                    val_init_exp = para_objeto_date(aviso_e['data_expiracao']) if aviso_e.get('data_expiracao') else date.today()
                    e_data_exp = st.date_input("Validade", value=val_init_exp, min_value=date.today(), format="DD/MM/YYYY", key="edit_data_exp")

                st.markdown("<label style='font-size: 14px; font-weight: 600;'>Mensagem *</label>", unsafe_allow_html=True)
                if TEM_QUILL:
                    e_mensagem = st_quill(value=aviso_e['mensagem'], placeholder="Edite sua mensagem...", key=f"edit_msg_quill_{edit_id}")
                else:
                    e_mensagem = st.text_area("Mensagem *", value=aviso_e['mensagem'], height=150, key="edit_msg", label_visibility="collapsed")
                
                st.markdown("**Imagem Atual / Anexo**")
                tem_img_atual = bool(aviso_e.get('imagem'))
                if tem_img_atual:
                    st.info("Este comunicado possui uma imagem anexada.")
                    remover_img = st.checkbox("Remover imagem anexada atual", key="edit_rem_img")
                else:
                    remover_img = False
                    st.caption("Nenhuma imagem anexada atualmente.")
                
                e_nova_imagem = st.file_uploader("Substituir / Inserir Nova Imagem", type=["jpg", "jpeg", "png"], key="edit_img_upload")

                e_disparar_email = st.checkbox("Disparar E-mail de Atualização aos Participantes", key="edit_chk_email")
                
                e_ass_texto, e_ass_upload = "", None

                if e_disparar_email:
                    with st.container(border=True):
                        c_ea1, c_ea2 = st.columns(2)
                        with c_ea1: e_ass_texto = st.text_area("Assinatura (Texto)", key="edit_ass_txt")
                        with c_ea2: e_ass_upload = st.file_uploader("Assinatura (Imagem)", type=["jpg", "jpeg", "png"], key="edit_ass_img")

                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    if st.button(" Salvar Alterações", type="primary", key="save_edit_btn"):
                        if e_titulo and e_mensagem:
                            info_edit_prog = st.info("⏳ Salvando alterações...")
                            
                            img_final_b64 = aviso_e.get('imagem')
                            if remover_img:
                                img_final_b64 = None
                            if e_nova_imagem is not None:
                                img_final_b64 = processar_imagem(e_nova_imagem)

                            uid_atual = aviso_e.get('uid_invite') or str(uuid.uuid4())

                            sucesso_edit_db = executar_query_rh(
                                "EXEC dbo.sp_AtualizarComunicado ?, ?, ?, ?, ?, ?, ?",
                                (edit_id, e_titulo, e_mensagem.strip(), img_final_b64, e_data_exp, None, uid_atual)
                            )

                            if not sucesso_edit_db:
                                info_edit_prog.empty()
                                st.error("⚠️ Erro ao atualizar o comunicado no banco de dados.")
                                st.toast(" Erro ao atualizar.", icon="⚠️")
                                st.stop()

                            if e_disparar_email:
                                destinatarios = obter_emails_permitidos()
                                if destinatarios:
                                    msg_html_body = processar_html_mensagem(e_mensagem.strip())
                                    html_email = f"""
                                    <div style="font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.6;">
                                        <h3 style="color: #002B50; margin-top: 0;">Comunicado Atualizado: {e_titulo}</h3>
                                        <div style="margin-bottom: 25px;">
                                            {msg_html_body}
                                        </div>
                                    """
                                    
                                    if e_ass_upload is not None:
                                        ass_b64 = processar_imagem_assinatura(e_ass_upload)
                                        if ass_b64:
                                            html_email += f"""
                                            <div style="margin-top: 25px; margin-bottom: 15px;">
                                                <img src="{ass_b64}" alt="Assinatura" style="max-width: 100%; height: auto; display: block;">
                                            </div>
                                            """
                                    elif e_ass_texto:
                                        html_email += f"<div style='margin-top: 20px; color: #475569;'>{processar_html_mensagem(e_ass_texto)}</div>"
                                        
                                    html_email += """
                                        <br>
                                        <hr style="border: none; border-top: 1px solid #E2E8F0; margin-top: 25px; margin-bottom: 15px;">
                                        <p style="font-size: 11px; color: #64748B; margin: 0;">
                                            <i>Esta é uma mensagem automática enviada diretamente pelo <b>Portal Repress</b>.</i>
                                        </p>
                                    </div>
                                    """
                                    
                                    anexos_resend = []
                                    if e_nova_imagem is not None:
                                        e_nova_imagem.seek(0)
                                        anexos_resend.append({
                                            "filename": f"comunicado_{e_nova_imagem.name}",
                                            "content": list(e_nova_imagem.read())
                                        })
                                        
                                    params = {
                                        "from": "Mural RH - Repress <nao-responda@rh.repress.com.br>",
                                        "to": ["willian.santos@repress.com.br"],
                                        "bcc": destinatarios,
                                        "subject": f"ATUALIZADO: {e_titulo}",
                                        "html": html_email,
                                    }
                                    if anexos_resend:
                                        params["attachments"] = anexos_resend
                                        
                                    resend.Emails.send(params)

                            info_edit_prog.empty()
                            st.session_state.pop("editando_id", None)
                            st.toast(" Alterações salvas com sucesso!", icon="💾")
                            st.success("Alterações salvas com sucesso!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Preencha Título e Mensagem.")
                            st.toast(" Preencha os campos obrigatórios.", icon="⚠️")
                with col_e2:
                    if st.button("Cancelar Edição", type="secondary", key="cancel_edit_btn"):
                        st.session_state.pop("editando_id", None)
                        st.rerun()
        else:
            st.session_state.pop("editando_id", None)

    comunicados = executar_query_rh("SELECT * FROM [dbo].[vw_MuralAtivo] ORDER BY data_publicacao DESC", fetch=True)
    
    if comunicados:
        st.markdown(f"Exibindo **{len(comunicados)}** comunicado(s) ativo(s).")
        st.markdown("<br>", unsafe_allow_html=True)
        
        hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([3.0, 1.5, 1.5, 1.5, 1.0, 1.0])
        hc1.markdown("**Título**")
        hc2.markdown("**Data Publicação**")
        hc3.markdown("**Data Expiração**")
        hc4.markdown("**Autor**")
        hc5.markdown("**Editar**")
        hc6.markdown("**Excluir**")
        st.markdown("<hr style='margin: 4px 0px 12px 0px; border-color: #CBD5E1;'>", unsafe_allow_html=True)
        
        for aviso in comunicados:
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([3.0, 1.5, 1.5, 1.5, 1.0, 1.0])
                
                c1.write(aviso['titulo'])
                
                dt_pub = aviso['data_publicacao']
                dt_pub_fmt = dt_pub.strftime('%d/%m/%Y %H:%M') if isinstance(dt_pub, datetime) else str(dt_pub)[:16]
                c2.write(dt_pub_fmt)
                
                dt_exp = aviso.get('data_expiracao')
                if dt_exp:
                    dt_exp_fmt = dt_exp.strftime('%d/%m/%Y') if isinstance(dt_exp, (datetime, date)) else str(dt_exp)[:10]
                else:
                    dt_exp_fmt = "Indeterminada"
                c3.write(dt_exp_fmt)
                
                autor_nome = aviso.get('autor', 'RH')
                foto_autor_b64 = obter_foto_usuario(autor_nome)
                if foto_autor_b64:
                    src_f = foto_autor_b64 if foto_autor_b64.startswith("data:") else f"data:image/jpeg;base64,{foto_autor_b64}"
                    c4.markdown(f"<div style='display: flex; align-items: center; gap: 8px;'><img src='{src_f}' style='width: 26px; height: 26px; border-radius: 50%; object-fit: cover;'><span>{autor_nome}</span></div>", unsafe_allow_html=True)
                else:
                    c4.markdown(f"<div style='display: flex; align-items: center; gap: 8px;'><span style='font-size: 16px;'>👤</span><span>{autor_nome}</span></div>", unsafe_allow_html=True)
                
                if c5.button("Editar", key=f"edit_btn_{aviso['id_aviso']}", use_container_width=True):
                    st.session_state["editando_id"] = aviso['id_aviso']
                    st.rerun()
                    
                if c6.button("Excluir", key=f"del_btn_{aviso['id_aviso']}", use_container_width=True):
                    id_aviso_atual = aviso['id_aviso']
                    executar_query_rh("EXEC dbo.sp_ExcluirComunicado ?", (id_aviso_atual,))
                    st.toast(" Comunicado excluído com sucesso!", icon="🗑️")
                    st.success("Comunicado excluído com sucesso!")
                    st.rerun()
    else:
        st.info("Nenhum comunicado ativo no momento.")