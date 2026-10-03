# ==============================================================================
# IMPORTE DE BIBLIOTECAS E CONFIGURAÇÃO DE CAMINHOS DO SISTEMA
# ==============================================================================
import streamlit as st        # Importa o framework principal Streamlit para criar a interface web interativa
import pyodbc                 # Importa a biblioteca pyodbc para comunicação com o banco de dados SQL Server[cite: 63]
import pandas as pd           # Importa a biblioteca pandas para manipulação e exibição de dados tabulares[cite: 63]
import os                     # Importa funções do sistema operacional para manipulação de caminhos
import sys                    # Importa o módulo sys para gerenciamento de diretórios

# ==============================================================================
# CONFIGURAÇÃO DO CAMINHO RAIZ E INTEGRAÇÃO COM O DATABASE CENTRALIZADO
# ==============================================================================
caminho_atual = os.path.dirname(os.path.abspath(__file__))
caminho_raiz = os.path.dirname(caminho_atual)
if caminho_raiz not in sys.path:
    sys.path.append(caminho_raiz)

try:
    from database import obter_conexao_principal # Importa a função de conexão centralizada[cite: 63]
except ImportError as erro_importacao:
    st.error("Não foi possível importar a função 'obter_conexao_principal' do arquivo database.py.")
    st.stop()

# ==============================================================================
# CONFIGURAÇÃO INICIAL DA PÁGINA NO STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Custo de Reposição - Repress", 
    page_icon="💱", 
    layout="wide"
)

# ==============================================================================
# IMPORTAÇÃO E INJEÇÃO DO DESIGN SYSTEM CENTRALIZADO (styles.py)
# ==============================================================================
try:
    from styles import injetar_estilo_global
    injetar_estilo_global()
except ImportError:
    st.warning("⚠️ Módulo 'styles.py' não encontrado na raiz. Utilizando layout padrão.")

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
# FUNÇÕES DE CONSULTA E PERSISTÊNCIA OTIMIZADAS (VIEWS E PROCEDURES)
# ==============================================================================
def buscar_produto_dw(id_produto):
    """Consulta na tabela oficial do Data Warehouse (DW_dProdutos) os detalhes cadastrais do produto pelo ID."""
    conexao = get_db_connection()
    if not conexao:
        return None
    cursor = conexao.cursor()
    try:
        query = """
            SELECT TOP 1 [IDProd], [Produto], [Fabricante], [EAN], [PrincipioAtivo], [Similaridade]
            FROM [DW_REPRESS].[dbo].[DW_dProdutos]
            WHERE [IDProd] = ?
        """
        cursor.execute(query, (id_produto,))
        resultado = cursor.fetchone()
        
        if resultado:
            return {
                "Id_Produto": resultado[0],
                "Produto": resultado[1],
                "Fabricante": resultado[2],
                "EAN": resultado[3],
                "Principio_Ativo": resultado[4] if resultado[4] is not None else "",
                "Similaridade": resultado[5] if resultado[5] is not None else ""
            }
    except Exception as e:
        st.error(f"Erro ao consultar o DW: {e}")
        return None
    finally:
        cursor.close()
        conexao.close()
    return None 

def verificar_duplicidade(id_produto):
    """Verifica se o produto informado já existe cadastrado na tabela local de Custo de Reposição."""
    conexao = get_db_connection()
    if not conexao:
        return False
    cursor = conexao.cursor()
    try:
        query = "SELECT COUNT(*) FROM aplicativos_db.dbo.Custo_Reposicao WHERE Id_Produto = ?"
        cursor.execute(query, (id_produto,))
        quantidade = cursor.fetchone()[0]
        return quantidade > 0
    except Exception as e:
        return False
    finally:
        cursor.close()
        conexao.close()

def adicionar_produto(dados):
    """Executa a stored procedure sp_InserirCustoReposicao para persistir o produto e limpa o cache."""
    conexao = get_db_connection()
    if not conexao:
        return
    cursor = conexao.cursor()
    try:
        cursor.execute("{CALL dbo.sp_InserirCustoReposicao (?, ?, ?, ?, ?, ?)}", (
            dados["Id_Produto"], 
            dados["Produto"], 
            dados["Fabricante"], 
            dados["EAN"], 
            dados["Principio_Ativo"], 
            dados["Similaridade"]
        ))
        conexao.commit()
        st.cache_data.clear() # Limpa o cache para refletir a inclusão imediatamente
    except Exception as e:
        st.error(f"Erro ao adicionar produto: {e}")
    finally:
        cursor.close()
        conexao.close()

def remover_produto(id_produto):
    """Executa a stored procedure sp_DeletarCustoReposicao para remover o registro e limpa o cache."""
    conexao = get_db_connection()
    if not conexao:
        return
    cursor = conexao.cursor()
    try:
        cursor.execute("{CALL dbo.sp_DeletarCustoReposicao (?)}", (id_produto,))
        conexao.commit()
        st.cache_data.clear() # Limpa o cache para refletir a remoção imediatamente
    except Exception as e:
        st.error(f"Erro ao remover produto: {e}")
    finally:
        cursor.close()
        conexao.close()

@st.cache_data(ttl=60, show_spinner=False)
def listar_todos_produtos():
    """Retorna um DataFrame contendo todos os produtos cadastrados consultando a View corporativa com cache (60s)."""
    conexao = get_db_connection()
    if not conexao:
        return pd.DataFrame()
    try:
        query = "SELECT * FROM aplicativos_db.dbo.vw_CustoReposicaoListagem ORDER BY Data_Inclusao DESC"
        df = pd.read_sql(query, conexao)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conexao.close()

# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO EM MASSA (EXCEL)
# ==============================================================================
def carregar_excel_ids(arquivo):
    """Lê um arquivo Excel carregado via upload, trata e retorna um DataFrame contendo apenas os IDs válidos."""
    df = pd.read_excel(arquivo, header=None)
    df = df.iloc[:, [0]]
    df.columns = ["Id_Produto"]
    df = df.dropna().reset_index(drop=True)
    
    if df.empty:
        return df
        
    primeira_celula = str(df.iloc[0, 0]).strip()
    if not primeira_celula.isdigit():
        df = df.iloc[1:].reset_index(drop=True)
        
    df["Id_Produto"] = pd.to_numeric(df["Id_Produto"], errors="coerce")
    df = df.dropna().reset_index(drop=True)
    df["Id_Produto"] = df["Id_Produto"].astype(int)
    return df

def processar_inclusao_em_massa(df_excel):
    """Processa a importação em lote de produtos a partir da lista de IDs do Excel."""
    coluna_ids = df_excel["Id_Produto"]
    adicionados = 0
    duplicados = 0
    nao_encontrados = 0
    erros = 0
    
    for valor in coluna_ids:
        try:
            id_prod = int(valor)
            if verificar_duplicidade(id_prod):
                duplicados += 1
            else:
                dados_dw = buscar_produto_dw(id_prod)
                if dados_dw:
                    adicionar_produto(dados_dw)
                    adicionados += 1
                else:
                    nao_encontrados += 1
        except Exception:
            erros += 1
            
    st.cache_data.clear()
    return {
        "adicionados": adicionados,
        "duplicados": duplicados,
        "nao_encontrados": nao_encontrados,
        "erros": erros
    }

def processar_remocao_em_massa(df_excel):
    """Processa a remoção em lote de produtos a partir da lista de IDs do Excel."""
    coluna_ids = df_excel["Id_Produto"]
    removidos = 0
    nao_existiam = 0
    erros = 0
    
    for valor in coluna_ids:
        try:
            id_prod = int(valor)
            if verificar_duplicidade(id_prod):
                remover_produto(id_prod)
                removidos += 1
            else:
                nao_existiam += 1
        except Exception:
            erros += 1
            
    st.cache_data.clear()
    return {
        "removidos": removidos,
        "nao_existiam": nao_existiam,
        "erros": erros
    }

# ==============================================================================
# MONTAGEM DA INTERFACE GRÁFICA DO APLICATIVO
# ==============================================================================
st.title("💱 Gestão de Produtos - Custo de Reposição")
st.markdown("Adicione ou remova produtos da base de Custo de Reposição integrada ao BI.")
st.divider()

col1, col2 = st.columns([1, 2], gap="large")

with col1:
    aba_ind, aba_massa_inc, aba_massa_exc = st.tabs([
        "Individual", 
        "Inclusão em Massa", 
        "Remoção em Massa"
    ])
    
    with aba_ind:
        st.subheader("Consultar / Adicionar")
        id_input = st.text_input("Digite o ID do Produto:", key="input_id_ind")
        
        if id_input:
            if id_input.isdigit():
                id_busca = int(id_input)
                dados_dw = buscar_produto_dw(id_busca)
                
                if dados_dw:
                    ja_cadastrado = verificar_duplicidade(id_busca)
                    with st.container(border=True):
                        st.write(f"**Produto:** {dados_dw['Produto']}")
                        st.write(f"**Fabricante:** {dados_dw['Fabricante']}")
                        st.write(f"**EAN:** {dados_dw['EAN']}")
                        st.write(f"**Princípio Ativo:** {dados_dw['Principio_Ativo'] if dados_dw['Principio_Ativo'] else '-'}")
                        st.write(f"**Similaridade:** {dados_dw['Similaridade'] if dados_dw['Similaridade'] else '-'}")
                        
                        if ja_cadastrado:
                            st.warning("⚠️ **Atenção:** Este produto JÁ ESTÁ na lista de Custo de Reposição.")
                            if st.button("Remover da Lista", type="primary", key="btn_rem_ind"):
                                remover_produto(id_busca)
                                st.success("Produto removido com sucesso!")
                                st.rerun() 
                        else:
                            st.info("✅ Este produto ainda **NÃO** está na lista.")
                            if st.button("Adicionar à Lista de Reposição", type="secondary", key="btn_add_ind"):
                                adicionar_produto(dados_dw)
                                st.success("Produto adicionado com sucesso!")
                                st.rerun() 
                else:
                    st.error("❌ Produto não encontrado na base DW_REPRESS.")
            else:
                st.error("Por favor, digite apenas números no ID.")

    with aba_massa_inc:
        st.subheader("Carga em Massa via Excel")
        st.markdown("Envie um arquivo `.xlsx` contendo a lista de IDs na primeira coluna.")
        
        arquivo_inc = st.file_uploader(
            "Selecione o arquivo Excel para Inclusão:", 
            type=["xlsx", "xls"], 
            key="upload_inc_massa"
        )
        
        if arquivo_inc is not None:
            try:
                df_upload_inc = carregar_excel_ids(arquivo_inc)
                st.write("📋 **Prévia do arquivo carregado:**")
                st.dataframe(
                    df_upload_inc.head(), 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Id_Produto": st.column_config.NumberColumn("Id_Produto", format="%d")
                    }
                )
                
                if st.button("Executar Inclusão em Massa", type="primary", key="btn_proc_inc_massa"):
                    with st.spinner("Processando registros e atualizando banco de dados..."):
                        resumo = processar_inclusao_em_massa(df_upload_inc)
                        
                    st.success("🎉 Processamento concluído com sucesso!")
                    st.write(f"- **Novos produtos inseridos:** {resumo['adicionados']}")
                    st.write(f"- **Já existentes (ignorados):** {resumo['duplicados']}")
                    st.write(f"- **Não encontrados no DW:** {resumo['nao_encontrados']}")
                    if resumo['erros'] > 0:
                        st.write(f"- **Linhas inválidas/com erro:** {resumo['erros']}")
                    
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler o arquivo Excel: {e}")

    with aba_massa_exc:
        st.subheader("Remoção em Massa via Excel")
        st.markdown("Envie um arquivo `.xlsx` contendo os IDs a serem **removidos** na primeira coluna.")
        
        arquivo_exc = st.file_uploader(
            "Selecione o arquivo Excel para Exclusão:", 
            type=["xlsx", "xls"], 
            key="upload_exc_massa"
        )
        
        if arquivo_exc is not None:
            try:
                df_upload_exc = carregar_excel_ids(arquivo_exc)
                st.write("📋 **Prévia dos produtos a remover:**")
                st.dataframe(
                    df_upload_exc.head(), 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Id_Produto": st.column_config.NumberColumn("Id_Produto", format="%d")
                    }
                )
                
                if st.button("Confirmar Exclusão em Massa", type="primary", key="btn_proc_exc_massa"):
                    with st.spinner("Excluindo registros da base de dados..."):
                        resumo_exc = processar_remocao_em_massa(df_upload_exc)
                        
                    st.success("🎉 Remoção em massa concluída!")
                    st.write(f"- **Produtos removidos da lista:** {resumo_exc['removidos']}")
                    st.write(f"- **Produtos que não estavam cadastrados:** {resumo_exc['nao_existiam']}")
                    if resumo_exc['erros'] > 0:
                        st.write(f"- **Linhas inválidas/com erro:** {resumo_exc['erros']}")
                        
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao ler o arquivo Excel: {e}")

# ------------------------------------------------------------------------------
# COLUNA DIREITA: LISTAGEM COMPLETA DOS PRODUTOS COM PAGINAÇÃO INTELIGENTE
# ------------------------------------------------------------------------------
with col2:
    st.subheader("Produtos Atuais na Lista")
    
    df_produtos = listar_todos_produtos()
    
    # Aplica o filtro em tempo real caso o usuário tenha digitado um ID na consulta individual
    if 'id_input' in locals() and id_input and id_input.isdigit():
        id_filtro = int(id_input)
        df_produtos_exibicao = df_produtos[df_produtos['Id_Produto'] == id_filtro]
    else:
        df_produtos_exibicao = df_produtos
    
    if not df_produtos_exibicao.empty:
        total_itens = len(df_produtos_exibicao)
        
        if 'id_input' in locals() and id_input and id_input.isdigit():
            st.caption(f"Exibindo resultado para o ID pesquisado: **{id_input}** (Total encontrado: {total_itens} item(ns))")
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
                    key="paginacao_custo_reposicao"
                )
            with col_pag2:
                inicio_item = (pagina_atual - 1) * itens_por_pagina + 1
                fim_item = min(pagina_atual * itens_por_pagina, total_itens)
                st.markdown(f"<div style='padding-top: 28px; font-size: 13px; color: #6B7280;'>Exibindo registros <b>{inicio_item}</b> a <b>{fim_item}</b> de um total de <b>{total_itens}</b></div>", unsafe_allow_html=True)
            
            # Fatiamento do DataFrame para a página selecionada
            inicio = (pagina_atual - 1) * itens_por_pagina
            fim = inicio + itens_por_pagina
            df_exibicao_pagina = df_produtos_exibicao.iloc[inicio:fim]
        else:
            df_exibicao_pagina = df_produtos_exibicao

        st.dataframe(
            df_exibicao_pagina, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Id_Produto": st.column_config.NumberColumn("Id_Produto", format="%d")
            }
        )
    else:
        if 'id_input' in locals() and id_input and id_input.isdigit():
            st.warning(f"O produto ID {id_input} não está cadastrado na lista de Custo de Reposição.")
        else:
            st.info("Nenhum produto cadastrado na lista de Custo de Reposição até o momento.")