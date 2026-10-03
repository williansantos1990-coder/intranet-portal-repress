# ==============================================================================
# IMPORTE DE BIBLIOTECAS E CONFIGURAÇÃO DE CAMINHOS DO SISTEMA
# ==============================================================================
import streamlit as st          # Importa o framework principal Streamlit para criar a interface web interativa
import pandas as pd             # Importa a biblioteca Pandas para manipulação de tabelas (DataFrames) e arquivos Excel
import pyodbc                   # Importa o driver pyodbc para gerenciar conexões e comandos no SQL Server
import io                       # Importa o módulo io para manipulação de fluxos de dados binários em memória RAM
import os                       # Importa funções do sistema operacional para manipulação de diretórios e caminhos
import sys                      # Importa o módulo sys para gerenciar os caminhos de importação do Python (sys.path)

# ==============================================================================
# CONFIGURAÇÃO DO CAMINHO RAIZ E INTEGRAÇÃO COM O DATABASE CENTRALIZADO
# ==============================================================================
caminho_atual = os.path.dirname(os.path.abspath(__file__))
caminho_raiz = os.path.dirname(caminho_atual)
if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

# Bloco protegido para importar a função de conexão principal do arquivo database.py
try:
    from database import obter_conexao_principal
except ImportError as erro_importacao:
    st.error("Não foi possível importar a função 'obter_conexao_principal' do arquivo database.py.")
    st.stop()

# ==============================================================================
# CONFIGURAÇÃO INICIAL DA PÁGINA NO STREAMLIT
# ==============================================================================
st.set_page_config(page_title="Gestão - Tab Canal", page_icon="🔄", layout="wide")

# ==============================================================================
# IMPORTAÇÃO E INJEÇÃO DO DESIGN SYSTEM CENTRALIZADO (styles.py)
# ==============================================================================
try:
    from styles import injetar_estilo_global
    injetar_estilo_global()
except ImportError:
    st.warning("⚠️ Módulo 'styles.py' não encontrado na raiz. Utilizando layout padrão.")

# ==============================================================================
# GERENCIAMENTO DE ESTADOS DE SESSÃO E CONTROLE DE COMPONENTES DE UPLOAD
# ==============================================================================
if "inc_file_key" not in st.session_state:
    st.session_state["inc_file_key"] = 0

if "del_file_key" not in st.session_state:
    st.session_state["del_file_key"] = 0

if "toast_notification" in st.session_state:
    st.toast(
        st.session_state.toast_notification["mensagem"],
        icon=st.session_state.toast_notification.get("icone", "✅")
    )
    del st.session_state["toast_notification"]

def agendar_toast(mensagem, icone="✅"):
    """Função auxiliar para registrar mensagens na sessão antes de executar uma recarga de página (st.rerun)"""
    st.session_state["toast_notification"] = {"mensagem": mensagem, "icone": icone}

# ==============================================================================
# ADAPTADOR DE CONEXÃO BLINDADO (CORREÇÃO DE ENCODING PARA ACENTOS)
# ==============================================================================
def get_db_connection():
    """Obtém a conexão unificada do database.py e aplica a blindagem de encoding (latin-1)."""
    conn = obter_conexao_principal()
    if conn:
        try:
            conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin-1')
            conn.setdecoding(pyodbc.SQL_WCHAR, encoding='latin-1')
            conn.setencoding(encoding='latin-1')
        except Exception:
            pass
    return conn

# ==============================================================================
# FUNÇÕES DE CONSULTA E PERSISTÊNCIA OTIMIZADAS (UTILIZANDO VIEWS E PROCEDURES)
# ==============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def buscar_produto_dw(id_produto):
    """Consulta as informações detalhadas de um produto específico no Data Warehouse com cache de 60s."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        query = """
            SELECT 
                [Id Produto] AS Id_Produto,
                [Produto],
                [Princípio Ativo] AS Principio_Ativo,
                [Fabricante],
                [Uni Fab],
                [Qtde Uni Pad]
            FROM [DW_REPRESS].[dbo].[vw_dProdutos]
            WHERE [Id Produto] = ?
        """
        df = pd.read_sql(query, conn, params=[id_produto])
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Erro ao buscar produto no DW: {e}")
        return None
    finally:
        if conn:
            try: conn.close()
            except: pass

def buscar_status_canal_existente(id_produto):
    """Verifica se o produto informado já possui um registro gravado na tabela local Tab_Canal"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        query = "SELECT Status_Compra, Canal_Compra FROM [aplicativos_db].[dbo].[Tab_Canal] WHERE Id_Produto = ?"
        df = pd.read_sql(query, conn, params=[id_produto])
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Erro ao consultar Tab_Canal: {e}")
        return None
    finally:
        if conn:
            try: conn.close()
            except: pass

# ==============================================================================
# FUNÇÃO DE CARREGAMENTO OTIMIZADA COM A VIEW (TODOS OS REGISTROS COM CACHE)
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def carregar_todos_produtos_canal(id_filtro=None):
    """
    Carrega todos os registros consultando a view corporativa vw_TabCanalDetalhes com cache de 60s.
    """
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        if id_filtro:
            query = """
                SELECT 
                    Id_Produto,
                    [Produto],
                    [Principio_Ativo],
                    [Fabricante],
                    [Uni Fab],
                    [Qtde Uni Pad],
                    Status_Compra,
                    Canal_Compra,
                    Data_Atualizacao
                FROM [aplicativos_db].[dbo].[vw_TabCanalDetalhes]
                WHERE Id_Produto = ? OR CAST(Id_Produto AS VARCHAR) LIKE ?
                ORDER BY Data_Atualizacao DESC
            """
            df = pd.read_sql(query, conn, params=[id_filtro, f"%{id_filtro}%"])
        else:
            query = """
                SELECT 
                    Id_Produto,
                    [Produto],
                    [Principio_Ativo],
                    [Fabricante],
                    [Uni Fab],
                    [Qtde Uni Pad],
                    Status_Compra,
                    Canal_Compra,
                    Data_Atualizacao
                FROM [aplicativos_db].[dbo].[vw_TabCanalDetalhes]
                ORDER BY Data_Atualizacao DESC
            """
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar produtos da View: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            try: conn.close()
            except: pass

def salvar_ou_atualizar(id_produto, status_compra, canal_compra):
    """Executa a stored procedure sp_SalvarTabCanal para realizar UPSERT no SQL Server e limpa o cache."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("{CALL dbo.sp_SalvarTabCanal (?, ?, ?)}", (id_produto, status_compra, canal_compra))
        conn.commit()
        st.cache_data.clear() # Limpa o cache para refletir atualizações imediatamente
        return True
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        st.error(f"Erro ao salvar dados no banco: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def deletar_produto(id_produto):
    """Executa a stored procedure sp_DeletarTabCanal para remover o registro e limpa o cache."""
    conn = get_db_connection()
    if not conn:
        return False
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("{CALL dbo.sp_DeletarTabCanal (?)}", (id_produto,))
        conn.commit()
        st.cache_data.clear() # Limpa o cache para refletir remoções imediatamente
        return True
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        st.error(f"Erro ao deletar produto: {e}")
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ==============================================================================
# FUNÇÃO PARA GERAÇÃO DA PLANILHA MODELO EM MEMÓRIA (EXCEL .XLSX)
# ==============================================================================
def gerar_planilha_modelo():
    """Gera um arquivo Excel (.xlsx) estruturado em memória RAM contendo dados de exemplo"""
    df_exemplo = pd.DataFrame({
        "Id_Produto": [36840, 36841, 36842],
        "Status_Compra": ["Hospitalar", "Farma", "Descontinuado"],
        "Canal_Compra": ["Direto", "Distribuidor", ""]
    })
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_exemplo.to_excel(writer, index=False, sheet_name='Modelo_Tab_Canal')
    buffer.seek(0)
    return buffer

# ==============================================================================
# CONSTRUÇÃO DA INTERFACE GRÁFICA DO USUÁRIO (LAYOUT STREAMLIT)
# ==============================================================================
st.markdown('<p class="title-header">🔄 Gestão de Produtos - Tab Canal</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Gerencie os status e canais de compra dos produtos diretamente na base integrada ao BI (Modo Preview Otimizado).</p>', unsafe_allow_html=True)

col_esquerda, col_direita = st.columns([1.2, 1.8], gap="large")

id_input_pesquisa = None

# ------------------------------------------------------------------------------
# COLUNA ESQUERDA: PAINEL DE CONTROLE E ABAS DE OPERAÇÃO
# ------------------------------------------------------------------------------
with col_esquerda:
    tab1, tab2, tab3 = st.tabs(["Individual", "Inclusão em Massa", "Remoção em Massa"])

    # --- ABA 1: INDIVIDUAL ---
    with tab1:
        st.subheader("Consultar / Cadastrar Produto")
        
        id_input = st.number_input(
            "Digite o ID / Código do Produto:",
            min_value=1,
            step=1,
            format="%d",
            value=None,
            placeholder="Ex: 36840"
        )

        id_input_pesquisa = id_input

        if id_input:
            produto_dw = buscar_produto_dw(id_input)

            if not produto_dw:
                st.warning(f"⚠️ Produto com ID {id_input} não foi encontrado na view vw_dProdutos.")
            else:
                st.markdown("---")
                st.markdown("**Dados do Produto (vw_dProdutos):**")
                
                st.text_input("Produto", value=str(produto_dw.get('Produto', '')), disabled=True)
                st.text_input("Princípio Ativo", value=str(produto_dw.get('Principio_Ativo', '')), disabled=True)
                st.text_input("Fabricante", value=str(produto_dw.get('Fabricante', '')), disabled=True)
                
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.text_input("Uni Fab", value=str(produto_dw.get('Uni Fab', '')), disabled=True)
                with col_u2:
                    st.text_input("Qtde Uni Pad", value=str(produto_dw.get('Qtde Uni Pad', '')), disabled=True)

                st.markdown("---")

                registro_existente = buscar_status_canal_existente(id_input)
                opcoes_status = ["Descontinuado", "Farma", "Hospitalar"]
                
                val_status = registro_existente['Status_Compra'] if registro_existente and registro_existente['Status_Compra'] in opcoes_status else opcoes_status[0]
                val_canal = registro_existente['Canal_Compra'] if registro_existente and registro_existente['Canal_Compra'] else ""

                if registro_existente:
                    st.info("ℹ️ Este produto **JÁ EXISTE** na Tab Canal. Altere os campos abaixo se desejar atualizar.")
                else:
                    st.success("✨ Este produto **AINDA NÃO ESTÁ** na Tab Canal. Preencha os campos abaixo para adicionar.")

                status_compra = st.selectbox(
                    "Status Compra",
                    options=opcoes_status,
                    index=opcoes_status.index(val_status)
                )

                canal_compra = st.text_input(
                    "Canal Compra",
                    value=val_canal,
                    placeholder="Ex: Direto, Distribuidor... (opcional)"
                )

                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    if st.button("💾 Salvar / Atualizar", type="primary", use_container_width=True):
                        if salvar_ou_atualizar(id_input, status_compra, canal_compra):
                            agendar_toast(f"Produto {id_input} salvo com sucesso!", icone="💾")
                            st.rerun()

                with btn_col2:
                    if registro_existente:
                        if st.button("🗑️ Remover da Lista", type="secondary", use_container_width=True):
                            if deletar_produto(id_input):
                                agendar_toast(f"Produto {id_input} removido da lista!", icone="🗑️")
                                st.rerun()

    # --- ABA 2: INCLUSÃO EM MASSA ---
    with tab2:
        st.subheader("Carga em Massa via Excel")
        
        st.info("""
        **Regras de Preenchimento da Planilha:**
        * **`Id_Produto`**: *(Obrigatório)* Número inteiro do código do produto.
        * **`Status_Compra`**: *(Obrigatório)* Deve ser estritamente um dos 3 valores: `Descontinuado`, `Farma` ou `Hospitalar`.
        * **`Canal_Compra`**: *(Opcional)* Texto livre com o canal de compra (pode ficar em branco).
        """)

        excel_modelo = gerar_planilha_modelo()
        st.download_button(
            label="📄 Baixar Planilha Modelo (.xlsx)",
            data=excel_modelo,
            file_name="Modelo_Carga_TabCanal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.markdown("---")

        file_inc = st.file_uploader(
            "Selecione a planilha preenchida para inclusão:", 
            type=["xlsx", "xls"], 
            key=f"inc_file_{st.session_state['inc_file_key']}"
        )

        if file_inc:
            try:
                df_upload = pd.read_excel(file_inc)
                st.markdown("**Pré-visualização dos dados:**")
                st.dataframe(df_upload.head(), use_container_width=True)
                
                if st.button("Confirmar Carga em Massa", type="primary", use_container_width=True):
                    sucessos = 0
                    erros = []
                    opcoes_validas = ["Descontinuado", "Farma", "Hospitalar"]

                    for idx, row in df_upload.iterrows():
                        try:
                            id_p = int(row['Id_Produto'])
                            st_c = str(row['Status_Compra']).strip() if pd.notna(row['Status_Compra']) else ""
                            cn_c = str(row['Canal_Compra']).strip() if pd.notna(row['Canal_Compra']) else ""

                            if st_c not in opcoes_validas:
                                erros.append(f"Linha {idx + 2}: Status '{st_c}' inválido para ID {id_p}. Deve ser Descontinuado, Farma ou Hospitalar.")
                                continue

                            if salvar_ou_atualizar(id_p, st_c, cn_c):
                                sucessos += 1
                        except Exception as ex_row:
                            erros.append(f"Linha {idx + 2}: Erro ao processar - {ex_row}")

                    if sucessos > 0:
                        agendar_toast(f"{sucessos} produtos importados/atualizados com sucesso!", icone="📥")
                    if erros:
                        for err in erros:
                            st.warning(err)
                    
                    st.session_state["inc_file_key"] += 1
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler o arquivo Excel: {e}")

    # --- ABA 3: REMOÇÃO EM MASSA ---
    with tab3:
        st.subheader("Remoção em Massa via Excel")
        st.caption("Envie um arquivo `.xlsx` contendo a coluna `Id_Produto` para remover os produtos da lista.")
        
        file_del = st.file_uploader(
            "Selecione o arquivo Excel para Remoção:", 
            type=["xlsx", "xls"], 
            key=f"del_file_{st.session_state['del_file_key']}"
        )

        if file_del:
            try:
                df_del = pd.read_excel(file_del)
                st.markdown("**Pré-visualização dos dados:**")
                st.dataframe(df_del.head(), use_container_width=True)
                
                if st.button("Confirmar Remoção em Massa", type="primary", use_container_width=True):
                    removidos = 0
                    for _, row in df_del.iterrows():
                        id_p = int(row['Id_Produto'])
                        if deletar_produto(id_p):
                            removidos += 1
                    if removidos > 0:
                        agendar_toast(f"{removidos} produtos removidos da base com sucesso!", icone="🗑️")
                    
                    st.session_state["del_file_key"] += 1
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar arquivo para exclusão: {e}")

# ------------------------------------------------------------------------------
# COLUNA DIREITA: LISTAGEM COMPLETA DOS PRODUTOS NA TAB CANAL (PAGINADA)
# ------------------------------------------------------------------------------
with col_direita:
    st.subheader("Produtos Atuais na Tab Canal (Lista Completa)")
    
    df_lista = carregar_todos_produtos_canal(id_filtro=id_input_pesquisa)

    if not df_lista.empty:
        total_itens = len(df_lista)
        
        if id_input_pesquisa:
            st.caption(f"Exibindo resultado para o ID pesquisado: **{id_input_pesquisa}** (Total encontrado: {total_itens} item(ns))")
        else:
            st.caption(f"Total de registros cadastrados na base: **{total_itens}**")
        
        # Configuração de Paginação de 50 em 50 itens
        itens_por_pagina = 50
        total_paginas = max(1, (total_itens + itens_por_pagina - 1) // itens_por_pagina)
        
        if total_paginas > 1:
            col_pag1, col_pag2 = st.columns([1, 3])
            with col_pag1:
                pagina_atual = st.selectbox(
                    "Página", 
                    options=list(range(1, total_paginas + 1)), 
                    format_func=lambda x: f"Pág. {x} de {total_paginas}",
                    key="paginacao_tab_canal"
                )
            with col_pag2:
                inicio_item = (pagina_atual - 1) * itens_por_pagina + 1
                fim_item = min(pagina_atual * itens_por_pagina, total_itens)
                st.markdown(f"<div style='padding-top: 28px; font-size: 13px; color: #6B7280;'>Exibindo registros <b>{inicio_item}</b> a <b>{fim_item}</b> de um total de <b>{total_itens}</b></div>", unsafe_allow_html=True)
            
            # Fatiamento do DataFrame para a página selecionada
            inicio = (pagina_atual - 1) * itens_por_pagina
            fim = inicio + itens_por_pagina
            df_exibicao_pagina = df_lista.iloc[inicio:fim]
        else:
            df_exibicao_pagina = df_lista

        st.dataframe(
            df_exibicao_pagina,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Id_Produto": st.column_config.NumberColumn("ID Produto", format="%d"),
                "Qtde Uni Pad": st.column_config.NumberColumn("Qtde Uni Pad", format="%d"),
                "Data_Atualizacao": st.column_config.DatetimeColumn("Última Atualização", format="DD/MM/YYYY HH:mm")
            }
        )
    else:
        st.info("Nenhum produto encontrado na base com o critério informado.")