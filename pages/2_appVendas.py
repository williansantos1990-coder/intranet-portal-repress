# ==============================================================================
# 1. IMPORTAÇÃO DAS BIBLIOTECAS NECESSÁRIAS PARA O FUNCIONAMENTO DA APLICAÇÃO
# ==============================================================================
import streamlit as st        # Importa o framework Streamlit para construção da interface web interativa[cite: 66]
import pandas as pd           # Importa Pandas para manipulação e estruturação de dataframes[cite: 66]
import os                     # Importa utilitários do sistema operacional para manipulação de caminhos
import pyodbc                 # Importa o driver ODBC para suporte a operações no SQL Server[cite: 66]
import sys                    # Importa o módulo sys para gerenciamento de diretórios do sistema
from datetime import datetime # Importa manipulação de datas e horários[cite: 66]
import re                     # Importa expressões regulares para tratamento de strings[cite: 66]

# ==============================================================================
# 2. CONFIGURAÇÃO DO CAMINHO RAIZ E INTEGRAÇÃO COM O DATABASE CENTRALIZADO
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
# 3. CONFIGURAÇÃO INICIAL DA PÁGINA DO STREAMLIT E DESIGN SYSTEM
# ==============================================================================
st.set_page_config(
    page_title="Solicitação de Compras", 
    page_icon="🛒", 
    layout="wide"
)

# Importa e injeta a folha de estilos centralizada do portal, substituindo o CSS legado[cite: 66]
try:
    from styles import injetar_estilo_global
    injetar_estilo_global()
except ImportError:
    st.warning("⚠️ Módulo 'styles.py' não encontrado na raiz. Utilizando layout padrão.")

# ==============================================================================
# 4. ADAPTADOR DE CONEXÃO BLINDADO (CORREÇÃO DE ENCODING PARA ACENTOS)
# ==============================================================================
def conectar_banco():
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
# 5. FUNÇÃO DE VERIFICAÇÃO DE FALTA ATIVA NO SISTEMA (VIA VIEW)
# ==============================================================================
def verificar_falta_sistema(codigo_produto):
    """Consulta na View corporativa vw_FaltasAtivas se um determinado código de produto possui falta ativa."""
    conn = conectar_banco() # Abre conexão
    if not conn:
        return None
    cursor = None
    try:
        cursor = conn.cursor() # Cria cursor ODBC
        sql_falta = """
            SELECT TOP 1 link_documento, comunicado, data_ruptura 
            FROM vw_FaltasAtivas 
            WHERE codigo = ?
            ORDER BY data_ruptura DESC
        """
        cursor.execute(sql_falta, (str(codigo_produto).strip(),)) # Executa query parametrizada
        resultado = cursor.fetchone() # Obtém o registro, se houver
        return resultado
    except Exception as e:
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close() # Fecha a conexão ODBC

# ==============================================================================
# 6. FUNÇÃO DE BUSCA DO NOME DO USUÁRIO LOGADO (COM CACHE)
# ==============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def obter_nome_usuario_logado(email_sessao):
    """Busca o nome completo do colaborador logado na tabela de autenticação com cache de 1 hora."""
    if not email_sessao:
        return "Usuário Desconhecido"
         
    nome_final = email_sessao 
    conn = conectar_banco()
    if not conn:
        return nome_final
        
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nome 
            FROM [aplicativos_db].[auth].[Usuarios] 
            WHERE email = ?
        """, (email_sessao,)) # Busca o nome do usuário pelo e-mail
        resultado = cursor.fetchone()
        if resultado and resultado[0]:
            nome_final = str(resultado[0]).strip()
    except Exception as e:
        pass
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
            
    return nome_final

# ==============================================================================
# 7. FUNÇÕES DE CARREGAMENTO DE DADOS COM CACHE OTIMIZADO (UTILIZANDO VIEWS)
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def carregar_entradas_pendentes_db():
    """Carrega a View vw_EntradasPendentesListagem para análise de compras com cache de 60 segundos."""
    conn = conectar_banco()
    if not conn:
        return None
    try:
        query = """
            SELECT codigo, ean, produto, fabricante, quantidade, recebido_via, previsao_chegada, data_recebida, numero_nf, status_entrada 
            FROM vw_EntradasPendentesListagem
        """
        df_entradas = pd.read_sql(query, conn) # Lê dados da view de entradas pendentes
        return df_entradas
    except Exception as e:
        return None
    finally:
        if conn: conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def carregar_solicitacoes():
    """Carrega todas as solicitações de vendas consultando a View vw_SolicitacoesVendasListagem com cache."""
    conn = conectar_banco()
    if not conn:
        return pd.DataFrame()
    cursor = None
    try:
        query = "SELECT * FROM vw_SolicitacoesVendasListagem ORDER BY data_solicitacao DESC, hora_solicitacao DESC"
        df = pd.read_sql(query, conn) # Lê diretamente para DataFrame Pandas otimizado
        return df
    except Exception as e:
        st.error(f"Erro ao carregar solicitações: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

@st.cache_data(ttl=60, show_spinner=False)
def carregar_produtos_em_falta():
    """Carrega simultaneamente a lista de faltas ativas e normalizadas consultando as Views corporativas com cache."""
    conn = conectar_banco()
    if not conn:
        return pd.DataFrame(), pd.DataFrame()
    try:
        query_faltas = "SELECT id, codigo, produto, fabricante, contrato, data_ruptura, data_retorno, previsao_normalizacao, status, comunicado, link_documento FROM vw_FaltasAtivas ORDER BY data_ruptura DESC"
        df_faltas = pd.read_sql(query_faltas, conn)
        
        query_norm = "SELECT codigo, produto, fabricante, contrato, data_ruptura, data_normalizacao, dias_ruptura FROM vw_FaltasNormalizadas ORDER BY data_normalizacao DESC"
        df_norm = pd.read_sql(query_norm, conn)
        
        return df_faltas, df_norm
    except Exception as e:
        st.error(f"Erro ao carregar lista de faltas: {e}")
        return pd.DataFrame(), pd.DataFrame()
    finally:
        if conn: conn.close()

def atualizar_todos_os_caches():
    """Limpa todos os caches ativos, forçando nova leitura direto das Views do banco de dados."""
    carregar_entradas_pendentes_db.clear()
    carregar_solicitacoes.clear()
    carregar_produtos_em_falta.clear()

# ==============================================================================
# 8. LÓGICA DE INTELIGÊNCIA DE MERCADO (BI - ANÁLISE DE COMPRAS E DEMANDA)
# ==============================================================================
def analisar_bi_produto(codigo_produto):
    """Cruza dados de compras com a fila de espera de vendas para gerar relatório inteligente."""
    mensagem_conselheiro = ""
    qtd_total_pendente = 0.0
    ean_db, desc_db, fab_db = "", "", ""
    
    df_bi = carregar_entradas_pendentes_db()
    if df_bi is None:
        return "⚠️ Poxa, não consegui acessar os dados de Compras no banco agora. Tente novamente em instantes.", 0.0, "", "", ""
        
    try:
        serie_codigos_coluna = df_bi['codigo'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        codigo_busca_limpo = str(codigo_produto).strip().replace('.0', '')
        df_filtrado = df_bi[serie_codigos_coluna == codigo_busca_limpo]
        
        if not df_filtrado.empty:
            primeira_linha = df_filtrado.iloc[0]
            if pd.notna(primeira_linha['ean']):
                ean_db = str(primeira_linha['ean']).strip().replace('.0', '')
            if pd.notna(primeira_linha['produto']):
                desc_db = str(primeira_linha['produto']).strip()
            if pd.notna(primeira_linha['fabricante']):
                fab_db = str(primeira_linha['fabricante']).strip()
            
        datas_previstas = []
        for idx, linha in df_filtrado.iterrows():
            qtd = linha['quantidade'] if pd.notna(linha['quantidade']) else 0
            entrada_status = str(linha['status_entrada']).strip().lower() if pd.notna(linha['status_entrada']) else ""
            nf_num = linha['numero_nf']
            
            try:
                nf_val = float(nf_num) if pd.notna(nf_num) else 0.0
            except ValueError:
                nf_val = 0.0
                
            if entrada_status == "pendente":
                qtd_total_pendente += float(qtd)
                if nf_val > 0:
                    dt_str = pd.to_datetime(linha['data_recebida']).strftime("%d/%m/%Y") if pd.notna(linha['data_recebida']) else "Data N/A"
                    datas_previstas.append(f"{dt_str} (Na Empresa)")
                else:
                    dt_str = pd.to_datetime(linha['previsao_chegada']).strftime("%d/%m/%Y") if pd.notna(linha['previsao_chegada']) else "Data N/A"
                    datas_previstas.append(f"{dt_str}")

        datas_unicas = list(set(datas_previstas))
        datas_str = " e ".join(datas_unicas) if datas_unicas else "Data N/A"

        if qtd_total_pendente > 0:
            texto_compras = f"Há pedido(s) de compra em andamento para este produto! Estão previstas para chegar **{qtd_total_pendente:.2f} unidade(s)** com data-alvo para **{datas_str}**."
        else:
            texto_compras = "No momento, **não há pedido de compra em andamento** ou mercadoria chegando para este produto."

        demanda_vendas_pendente = 0.0
        df_solicitacoes = carregar_solicitacoes()
        
        if not df_solicitacoes.empty:
            serie_codigos_sol = df_solicitacoes['codigo'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_sol_produto = df_solicitacoes[serie_codigos_sol == codigo_busca_limpo]
            
            for idx_sol, linha_sol in df_sol_produto.iterrows():
                status_sol = str(linha_sol['status_solicitacao']).strip().upper() if pd.notna(linha_sol['status_solicitacao']) else ""
                if status_sol in ["ATENDIDO", "ATENDIDO PARCIAL"]:
                    qtd_solicitada = float(linha_sol['quantidade']) if pd.notna(linha_sol['quantidade']) else 0.0
                    qtd_atendida = float(linha_sol['qtde_atendida']) if 'qtde_atendida' in linha_sol and pd.notna(linha_sol['qtde_atendida']) else 0.0
                    falta_atender = qtd_solicitada - qtd_atendida
                    if falta_atender > 0:
                        demanda_vendas_pendente += falta_atender

        if demanda_vendas_pendente > 0:
            texto_demanda = f"Notei também que já existe uma demanda de **{demanda_vendas_pendente:.2f} unidade(s)** em solicitações anteriores aguardando entrega (fila de espera)."
        else:
            texto_demanda = "A boa notícia é que não temos fila de espera ou solicitações pendentes de outros vendedores para este produto."

        sobra_disponivel = qtd_total_pendente - demanda_vendas_pendente

        if sobra_disponivel > 0:
             texto_saldo = f"✅ **Resumo do Saldo Livre:** Fazendo as contas, após atender a fila atual, você terá um saldo livre de **{sobra_disponivel:.2f} unidade(s)** disponível no estoque. Pode seguir com sua solicitação com tranquilidade!"
        elif sobra_disponivel == 0 and qtd_total_pendente > 0:
             texto_saldo = f"**Resumo do Saldo Livre:** Toda a mercadoria que está chegando já está 100% comprometida com a fila atual. Portanto, **não restará saldo livre disponível** para novos pedidos."
        elif sobra_disponivel < 0 and qtd_total_pendente > 0:
             texto_saldo = f"**Resumo do Saldo Livre:** A quantidade de pedidos na fila ({demanda_vendas_pendente:.2f}) é maior que a quantidade que vai chegar ({qtd_total_pendente:.2f}). Ou seja, **mesmo com esse pedido de compra, não restará saldo disponível** para o seu atendimento neste momento (Saldo Previsto: {sobra_disponivel:.2f})."
        elif qtd_total_pendente == 0 and demanda_vendas_pendente > 0:
             texto_saldo = f"**Resumo do Saldo Livre:** Como não há mercadoria chegando e já temos fila, o saldo atual do sistema está negativo em **{sobra_disponivel:.2f} unidade(s)**."
        else: 
             texto_saldo = f"ℹ️ **Resumo:** Como não temos compras chegando e nem fila de espera, a sua solicitação será a primeira a gerar demanda de compra para este item."

        # Monta a mensagem de BI estruturada
        mensagem_conselheiro = (
            f"- **Compras:** {texto_compras}\n"
            f"- **Demanda:** {texto_demanda}\n\n"
            f"{texto_saldo}"
        )
    except Exception as e:
        mensagem_conselheiro = f"⚠️ Ops, ocorreu um erro ao analisar os dados de BI: {e}"
        
    return mensagem_conselheiro, qtd_total_pendente, ean_db, desc_db, fab_db

def extrair_grupo(nome):
    """Função auxiliar para extrair o grupo principal a partir do nome do contrato com regras inteligentes de separador, sigla PE isolada e limpeza de pontuações finais."""
    if pd.isna(nome) or str(nome).strip() == "":
        return "Sem Contrato" 
    
    texto_contrato = str(nome).strip()
    
    # Procura pela sigla "PE" isolada como palavra na string (ex: "NHANDEARA PE. 039/2025")
    match_pe = re.search(r'\bPE\b', texto_contrato)
    if match_pe:
        grupo_extraido = texto_contrato[:match_pe.start()].strip()
    else:
        # Caso contrário, utiliza o separador padrão "-" ou "("
        grupo_extraido = re.split(r'[-|\(]', texto_contrato)[0].strip()
    
    # Remove caracteres de pontuação ou separadores remanescentes no final da string (espaços, traços, sublinhados, vírgulas, pontos, barras)
    grupo_extraido = re.sub(r'[\s\-_,\./]+$', '', grupo_extraido).strip()
    
    return grupo_extraido.upper()

# ==============================================================================
# 9. INTERFACE GRÁFICA PRINCIPAL DO APLICATIVO
# ==============================================================================
st.title("🛒 Solicitação de Compras")
st.write("Acompanhe o status do BI, envie solicitações e consulte a posição das faltas em abas dedicadas.")

# Cria as abas principais do aplicativo de vendas
aba_envio, aba_painel_faltas = st.tabs([
    "Solicitação de Compras e Consulta", 
    "Painel de Produtos EM FALTA"
])

# -----------------------------------------------------------------------------
# ABA 1: ENVIO DE SOLICITAÇÃO + INTELIGÊNCIA BI + CONSULTA DE HISTÓRICO
# -----------------------------------------------------------------------------
with aba_envio:
    codigo_input = st.text_input("🔍 Digite o Código do Produto e pressione Enter para iniciar:")

    ean_auto, prod_auto, fab_auto = "", "", ""
    mensagem_bi = ""
    total_qtd = 0.0

    if codigo_input: # Se o código for digitado
        atualizar_todos_os_caches()
        mensagem_bi, total_qtd, ean_db, desc_db, fab_db = analisar_bi_produto(codigo_input)

        conn = conectar_banco()
        if conn:
            cursor = conn.cursor()
            try: # Busca dados oficiais do produto no DW
                cursor.execute("""
                    SELECT TOP 1 [EAN], [Produto], [Fabricante]
                    FROM DW_REPRESS.dbo.vw_dProdutos 
                    WHERE [Id Produto] = ?
                """, (codigo_input,))
                res = cursor.fetchone()
                
                if res:
                    ean_auto = res[0] if res[0] else ""
                    prod_auto = res[1] if res[1] else ""
                    fab_auto = res[2] if res[2] else ""
                elif desc_db != "":
                    ean_auto = ean_db
                    prod_auto = desc_db
                    fab_auto = fab_db
            finally:
                cursor.close()
                conn.close()

        st.markdown("---")
        st.markdown("### Inteligência de Compras (BI - Entradas Pendentes)")
        
        if mensagem_bi:
            st.info(mensagem_bi)

        registro_falta = verificar_falta_sistema(codigo_input)
        if registro_falta: # Se o produto estiver em falta
            link_comunicado = registro_falta[0]
            st.error("🚨 **Produto atualmente EM FALTA. Acessar Link do Comunicado:**")
            if link_comunicado and str(link_comunicado).strip() != "":
                link_seguro = str(link_comunicado).replace(" ", "%20")
                texto_explicativo = "🔗 Comunicado: Clique com o botão direito do Mouse, depois copiar endereço do link, cole em uma nova aba de Internet"
                st.markdown(f'<a href="{link_seguro}" target="_blank" style="text-decoration: none; color: #1f77b4; font-weight: bold;">{texto_explicativo}</a>', unsafe_allow_html=True)
            else:
                st.info("ℹ️ Produto atualmente EM FALTA no Painel Principal (Sem Link de Comunicado anexado).")

    st.markdown("---")
    st.markdown("### Formulário de Envio de Nova Solicitação")
    
    with st.form("form_solicitacao_vendas", clear_on_submit=True): # Formulário de envio de solicitação
        col1, col2 = st.columns(2)
        
        with col1:
            codigo_form = st.text_input("Código do Produto *", value=codigo_input, disabled=True)
            descricao_form = st.text_input("Descrição do Produto *", value=prod_auto, disabled=True)
            ean_form = st.text_input("EAN", value=ean_auto, disabled=True)
            fabricante_form = st.text_input("Fabricante", value=fab_auto, disabled=True)

        with col2:
            qtd_solicitada = st.number_input("Quantidade Desejada *", min_value=1, step=1, value=1)

            usuario_url = st.query_params.get("user", None)
            login_usuario_atual = usuario_url if usuario_url else st.session_state.get('username', 'usuario_teste') 
            nome_solicitante_auto = obter_nome_usuario_logado(login_usuario_atual)
            
            solicitante_form = st.text_input("Nome do Solicitante (Logado) *", value=nome_solicitante_auto, disabled=True)
            st.text_input("Data da Solicitação", value=datetime.now().strftime("%Y-%m-%d"), disabled=True)
            st.text_input("Hora da Solicitação", value=datetime.now().strftime("%H:%M:%S"), disabled=True)

        # Move o checkbox de prioridade para o final do formulário, mantendo o alinhamento perfeito de 4 itens por coluna
        prioridade_form = st.checkbox("Solicitar Prioridade")

        btn_enviar = st.form_submit_button("Enviar Solicitação de Compra")
        
        if btn_enviar: # Ao submeter solicitação
            if not descricao_form or not solicitante_form or qtd_solicitada <= 0:
                st.error("⚠️ Preencha todos os campos obrigatórios (*): Descrição, Solicitante e Quantidade! Certifique-se de buscar um código válido.")
            else:
                conn = conectar_banco()
                if conn:
                    cursor = conn.cursor()
                    try:
                        resumo_bi_str = mensagem_bi if mensagem_bi else "Sem análise prévia"
                        prioridade_str = "Sim" if prioridade_form else "Não"

                        status_compra = None 
                        try:
                            sql_canal = "SELECT TOP 1 Status_Compra FROM [aplicativos_db].[dbo].[Tab_Canal] WHERE Id_Produto = ?"
                            cursor.execute(sql_canal, (codigo_input,))
                            resultado_canal = cursor.fetchone()
                            if resultado_canal and resultado_canal[0]:
                                status_compra = str(resultado_canal[0]).strip()
                        except Exception as e:
                            pass

                        data_hoje = datetime.now().strftime("%Y-%m-%d")
                        hora_hoje = datetime.now().strftime("%H:%M:%S")
                        
                        # Executa a Stored Procedure corporativa sp_InserirSolicitacaoVenda para gravação otimizada
                        cursor.execute("{CALL dbo.sp_InserirSolicitacaoVenda (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                                       (data_hoje, hora_hoje, codigo_input, ean_form, descricao_form, fabricante_form, int(qtd_solicitada), solicitante_form, resumo_bi_str, 'PENDENTE', status_compra, prioridade_str))
                        conn.commit()
                        
                        atualizar_todos_os_caches()
                        st.success("🎉 Solicitação de compra enviada com sucesso para a equipe de Compras!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao enviar solicitação: {e}")
                    finally:
                        cursor.close()
                        conn.close()

    st.markdown("---")
    
    col_titulo, col_btn = st.columns([4, 1])
    with col_titulo:
        st.subheader("Acompanhamento de Solicitações")
    with col_btn:
        if st.button("Atualizar Solicitações", key="btn_atualizar_solic_aba1", use_container_width=True):
            atualizar_todos_os_caches()
            st.rerun()

    df_consulta = carregar_solicitacoes()

    if not df_consulta.empty: # Se houver solicitações cadastradas
        if 'id' in df_consulta.columns:
            df_consulta = df_consulta.drop('id', axis=1)
        if 'analise_bi_resumo' in df_consulta.columns:
            df_consulta = df_consulta.drop('analise_bi_resumo', axis=1)
        if 'Status_Compra' in df_consulta.columns:
            df_consulta = df_consulta.drop('Status_Compra', axis=1)

        if 'qtde_atendida' in df_consulta.columns:
            df_consulta['qtde_atendida'] = pd.to_numeric(df_consulta['qtde_atendida'], errors='coerce').astype('Int64')
            df_consulta = df_consulta.rename(columns={'qtde_atendida': 'Qtde. Atendida'})
        else:
            df_consulta['Qtde. Atendida'] = pd.Series(dtype='Int64')

        if 'prioridade' in df_consulta.columns:
            df_consulta = df_consulta.rename(columns={'prioridade': 'Prioridade'})

        colunas_ordem = list(df_consulta.columns)
        if 'Qtde. Atendida' in colunas_ordem and 'quantidade' in colunas_ordem:
            colunas_ordem.remove('Qtde. Atendida')
            pos_quantidade = colunas_ordem.index('quantidade') 
            colunas_ordem.insert(pos_quantidade + 1, 'Qtde. Atendida')
            df_consulta = df_consulta[colunas_ordem]

        df_filtrado = df_consulta.copy()

        with st.expander("🔍 Filtros Avançados de Pesquisa"): # Expander para filtros de pesquisa
            fcol1, fcol2, fcol3 = st.columns(3)
            with fcol1:
                opcoes_solicitante = df_filtrado['solicitante'].dropna().unique().tolist()
                filtro_sol = st.multiselect("Filtrar por Solicitante", options=opcoes_solicitante)
            with fcol2:
                if 'status_solicitacao' in df_filtrado.columns:
                    opcoes_status = df_filtrado['status_solicitacao'].dropna().unique().tolist()
                    filtro_status = st.multiselect("Filtrar por Status", options=opcoes_status)
                else:
                    filtro_status = []
            with fcol3:
                texto_busca = st.text_input("Buscar por Código, EAN ou Descrição")

        if filtro_sol:
            df_filtrado = df_filtrado[df_filtrado['solicitante'].isin(filtro_sol)]
        if filtro_status:
            df_filtrado = df_filtrado[df_filtrado['status_solicitacao'].isin(filtro_status)]
        if texto_busca:
            termo = texto_busca.lower()
            mask_cod = df_filtrado['codigo'].astype(str).str.lower().str.contains(termo)
            mask_ean = df_filtrado['ean'].astype(str).str.lower().str.contains(termo)
            mask_desc = df_filtrado['descricao'].astype(str).str.lower().str.contains(termo)
            df_filtrado = df_filtrado[mask_cod | mask_ean | mask_desc]

        st.caption(f"Exibindo {len(df_filtrado)} registro(s) encontrados.")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma solicitação encontrada no banco de dados até o momento.")

# ---------------------------------------------------------------------
# ABA 2: PAINEL DE PRODUTOS EM FALTA (ESPELHO DE COMPRAS)
# ---------------------------------------------------------------------
with aba_painel_faltas:
    col_tit_falta, col_btn_falta = st.columns([4, 1])
    with col_btn_falta:
        if st.button("Atualizar Faltas", key="btn_atualizar_faltas_vendas", use_container_width=True):
            atualizar_todos_os_caches()
            st.rerun()

    df_faltas, df_norm = carregar_produtos_em_falta()

    if not df_faltas.empty:
        df_faltas['grupo_contrato'] = df_faltas['contrato'].apply(extrair_grupo)
        
        if not df_norm.empty:
            df_norm['grupo_contrato'] = df_norm['contrato'].apply(extrair_grupo)
            todos_contratos = pd.concat([df_faltas['contrato'], df_norm['contrato']]).dropna().unique()
        else:
            todos_contratos = df_faltas['contrato'].dropna().unique()
            
        lista_contratos = sorted(list(todos_contratos))
        grupos_unicos = sorted(list(set([extrair_grupo(c) for c in lista_contratos])))

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            busca_texto_falta = st.text_input("Buscar por Código ou Produto:", key="busca_falta_vendas")
        with col_f2:
            grupo_selecionado_falta = st.selectbox("1º Filtrar por Grupo Principal:", ["Todos os Grupos"] + grupos_unicos, key="grupo_falta_vendas")
        with col_f3:
            if grupo_selecionado_falta != "Todos os Grupos":
                opcoes_multi_falta = [c for c in lista_contratos if extrair_grupo(c) == grupo_selecionado_falta]
            else:
                opcoes_multi_falta = lista_contratos
            filtro_contrato_falta = st.multiselect("2º Filtrar por Contratos:", opcoes_multi_falta, key="contrato_falta_vendas")

        if busca_texto_falta:
            mask_faltas = df_faltas[['codigo', 'produto']].astype(str).apply(lambda x: x.str.lower().str.contains(busca_texto_falta.lower())).any(axis=1)
            df_faltas = df_faltas[mask_faltas]

        if grupo_selecionado_falta != "Todos os Grupos":
            df_faltas = df_faltas[df_faltas['grupo_contrato'] == grupo_selecionado_falta]

        if filtro_contrato_falta:
            df_faltas = df_faltas[df_faltas['contrato'].isin(filtro_contrato_falta)]

        if 'grupo_contrato' in df_faltas.columns:
            df_faltas = df_faltas.drop(columns=['grupo_contrato'])

        st.markdown(f"**🔴 Produtos atualmente EM FALTA ({len(df_faltas)} encontrados)**")

        ordem_colunas_falta = ['codigo', 'produto', 'fabricante', 'contrato', 'data_ruptura', 'data_retorno', 'previsao_normalizacao', 'status', 'comunicado', 'link_documento']
        df_exibir_faltas = df_faltas[[c for c in ordem_colunas_falta if c in df_faltas.columns]]

        st.dataframe( # Exibe tabela de produtos em falta para consulta da equipe de vendas
            df_exibir_faltas,
            use_container_width=True,
            hide_index=True,
            column_config={
                "codigo": st.column_config.TextColumn("Código"),
                "produto": st.column_config.TextColumn("Produto"),
                "fabricante": st.column_config.TextColumn("Fabricante"),
                "contrato": st.column_config.TextColumn("Contrato e Reserva"),
                "data_ruptura": st.column_config.DateColumn("Data Ruptura", format="DD/MM/YYYY"),
                "data_retorno": st.column_config.DateColumn("Data Retorno (Fabr.)", format="DD/MM/YYYY"),
                "previsao_normalizacao": st.column_config.TextColumn("Prev. Normalização"),
                "status": st.column_config.TextColumn("Status"),
                "comunicado": st.column_config.TextColumn("Comunicado"),
                "link_documento": st.column_config.LinkColumn(
                    "Link do Comunicado",
                    display_text="🔗 Acessar Documento"
                )
            }
        )
    else:
        st.info("Nenhum produto atualmente em falta foi encontrado no banco de dados.")