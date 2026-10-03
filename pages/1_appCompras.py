# =====================================================================
# 1. IMPORTACAO DAS BIBLIOTECAS DE SUPORTE E CONEXAO
# =====================================================================
import streamlit as st        # Importa a biblioteca Streamlit para construir a interface web interativa do sistema
import pandas as pd           # Importa o Pandas para manipulacao e estruturacao de dados em dataframes
import pyodbc                 # Importa o PyODBC para realizar a manipulacao de tipos e codificacoes do SQL Server
from datetime import datetime # Importa a classe datetime para lidar com operacoes de data e hora
import re                     # Importa o modulo re (Expressoes Regulares) para buscar e manipular padroes de texto
import io                     # Importa o modulo 'io' para manipular fluxos de bytes em memoria

# =====================================================================
# 2. METADADOS DA PAGINA (Lidos automaticamente pelo Main.py do Portal)
# =====================================================================
page_title = "Controle de Faltas Repress" # Define o título descritivo do aplicativo de compras
page_icon = "📦"                         # Define o ícone representativo do aplicativo

# =====================================================================
# 3. CONFIGURACAO DA PAGINA WEB E INJEÇÃO DO DESIGN SYSTEM
# =====================================================================
st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide") # Configura os metadados da página no Streamlit

# Importa e injeta a folha de estilos centralizada do portal, substituindo o CSS legado
from styles import injetar_estilo_global
injetar_estilo_global()

# =====================================================================
# 4. NOTIFICACAO FLUTUANTE (TOAST DE NOTIFICACAO)
# =====================================================================
if "popup_mensagem" in st.session_state: # Verifica se existe alguma mensagem pendente no session state
    st.toast(st.session_state.pop("popup_mensagem"), icon="🔔") # Exibe a notificação toast na tela e a remove do estado

# =====================================================================
# 5. INTEGRACAO COM O GERENCIADOR CENTRALIZADO DE CONEXOES (database.py)
# =====================================================================
from database import obter_conexao_principal # Importa a função centralizada de conexão ODBC do database.py

def conectar_banco():
    """Funcao unificada que retorna uma conexao segura e tratada com o SQL Server."""
    try: # Inicia bloco try para capturar falhas na abertura da conexão
        conn = obter_conexao_principal() # Retorna a conexão obtida pelo gerenciador central
        if conn:
            try:
                conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin-1')
                conn.setdecoding(pyodbc.SQL_WCHAR, encoding='latin-1')
                conn.setencoding(encoding='latin-1')
            except Exception:
                pass
        return conn
    except Exception as e: # Captura exceções de conectividade
        st.error(f"Erro ao conectar ao banco de dados SQL Server: {e}") # Exibe erro amigável na interface
        return None # Retorna None em caso de falha

# =====================================================================
# 6. FUNÇÕES COM CACHE DE PERFORMANCE OTIMIZADO (TTL 300s) VIA VIEWS
# =====================================================================
@st.cache_data(ttl=300, show_spinner=False)
def carregar_dados_faltas_cache():
    """Carrega dados de faltas consultando as Views otimizadas com cache de 300 segundos."""
    conexao = conectar_banco() # Abre conexão com o banco
    if not conexao: # Se a conexão falhar
        return pd.DataFrame(), pd.DataFrame() # Retorna dataframes vazios
    try: # Inicia bloco de execução de queries nas Views corporativas
        query_faltas = "SELECT id, codigo, produto, fabricante, contrato, data_ruptura, data_retorno, previsao_normalizacao, status, comunicado, link_documento FROM vw_FaltasAtivas ORDER BY data_ruptura DESC"
        df_faltas = pd.read_sql(query_faltas, conexao) # Lê os produtos em falta da view
        
        query_norm = "SELECT codigo, produto, fabricante, contrato, data_ruptura, data_normalizacao, dias_ruptura FROM vw_FaltasNormalizadas ORDER BY data_normalizacao DESC"
        df_norm = pd.read_sql(query_norm, conexao) # Lê os produtos normalizados da view
        return df_faltas, df_norm # Retorna os dois dataframes estruturados
    except Exception as e: # Captura erros de leitura
        st.error(f"Erro ao carregar dados do painel: {e}") # Exibe mensagem de erro
        return pd.DataFrame(), pd.DataFrame() # Retorna dataframes vazios
    finally: # Bloco de garantia de fechamento de recursos
        conexao.close() # Fecha a conexão ODBC com o banco

@st.cache_data(ttl=300, show_spinner=False)
def carregar_solicitacoes_cache():
    """Carrega solicitações de vendas consultando a View com cache estruturado de 300 segundos."""
    conexao = conectar_banco() # Abre conexão
    if not conexao:
        return pd.DataFrame()
    try: # Executa consulta da view de solicitações de vendas
        query_solicitacoes = "SELECT * FROM vw_SolicitacoesVendasListagem ORDER BY id DESC"
        return pd.read_sql(query_solicitacoes, conexao) # Retorna o dataframe com as solicitações
    except Exception as e:
        return pd.DataFrame()
    finally:
        conexao.close() # Fecha a conexão

@st.cache_data(ttl=300, show_spinner=False)
def carregar_entradas_cache():
    """Carrega entradas pendentes consultando a View com cache estruturado de 300 segundos."""
    conexao = conectar_banco() # Abre conexão
    if not conexao:
        return pd.DataFrame()
    try: # Executa consulta da view de entradas pendentes
        query_ler_entradas = "SELECT * FROM vw_EntradasPendentesListagem ORDER BY id DESC"
        return pd.read_sql(query_ler_entradas, conexao) # Retorna dataframe de entradas
    except Exception as e:
        return pd.DataFrame()
    finally:
        conexao.close() # Fecha a conexão

# =====================================================================
# 7. INTERFACE DO SISTEMA (TÍTULO E ABAS DE NAVEGAÇÃO)
# =====================================================================
st.title("📦 Controle de Faltas de Produtos") # Renderiza o título principal da página
st.write("Bem-vindo ao portal da equipe de compras.") # Exibe subtítulo descritivo de boas-vindas

# Cria as 5 abas principais do aplicativo de compras
aba1, aba2, aba3, aba4, aba5 = st.tabs(["Painel Principal", "Registrar Nova Falta", "Normalizar Produto", "Solicitações de Vendas", "Entradas Pendentes"])

# ---------------------------------------------------------------------
# ABA 1: PAINEL DE FALTAS (Tabelas e Edicao em Lote)
# ---------------------------------------------------------------------
with aba1: 
    df_faltas, df_norm = carregar_dados_faltas_cache() # Carrega dados em cache de faltas e normalizados
    
    if not df_faltas.empty or not df_norm.empty: # Se houver registros carregados
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
            
        # Cria a coluna auxiliar de agrupamento de contratos
        df_faltas['grupo_contrato'] = df_faltas['contrato'].apply(extrair_grupo) if 'contrato' in df_faltas.columns else "Sem Contrato"
        df_norm['grupo_contrato'] = df_norm['contrato'].apply(extrair_grupo) if 'contrato' in df_norm.columns else "Sem Contrato"
        
        # Mapeia todos os contratos e grupos únicos para os filtros
        todos_contratos = pd.concat([df_faltas.get('contrato', pd.Series()), df_norm.get('contrato', pd.Series())]).dropna().unique() 
        lista_contratos = sorted(list(todos_contratos)) 
        grupos_unicos = sorted(list(set([extrair_grupo(c) for c in lista_contratos]))) 
        
        col_f1, col_f2, col_f3 = st.columns(3) # Cria 3 colunas para os filtros do painel
        
        with col_f1:
            busca_texto = st.text_input("Buscar por Codigo ou Produto:") # Input de busca textual por código ou nome
        with col_f2:
            grupo_selecionado = st.selectbox("1º Filtrar por Grupo Principal:", ["Todos os Grupos"] + grupos_unicos) # Selectbox de grupo
        with col_f3:
            if grupo_selecionado != "Todos os Grupos":
                opcoes_multi = [c for c in lista_contratos if extrair_grupo(c) == grupo_selecionado] 
            else:
                opcoes_multi = lista_contratos 
            filtro_contrato = st.multiselect("2º Filtrar por Contratos:", opcoes_multi) # Multiselect de contratos específicos
            
        if busca_texto: # Aplica filtro textual se preenchido
            if not df_faltas.empty:
                mask_faltas = df_faltas[['codigo', 'produto']].astype(str).apply(lambda x: x.str.lower().str.contains(busca_texto.lower())).any(axis=1)
                df_faltas = df_faltas[mask_faltas]
            if not df_norm.empty:
                mask_norm = df_norm[['codigo', 'produto']].astype(str).apply(lambda x: x.str.lower().str.contains(busca_texto.lower())).any(axis=1)
                df_norm = df_norm[mask_norm] 
            
        if grupo_selecionado != "Todos os Grupos": # Aplica filtro por grupo de contrato
            if not df_faltas.empty: df_faltas = df_faltas[df_faltas['grupo_contrato'] == grupo_selecionado]
            if not df_norm.empty: df_norm = df_norm[df_norm['grupo_contrato'] == grupo_selecionado]
            
        if filtro_contrato: # Aplica filtro por contratos múltiplos selecionados
            if not df_faltas.empty: df_faltas = df_faltas[df_faltas['contrato'].isin(filtro_contrato)]
            if not df_norm.empty: df_norm = df_norm[df_norm['contrato'].isin(filtro_contrato)]
            
        # Remove a coluna temporária de agrupamento antes da exibição
        if 'grupo_contrato' in df_faltas.columns: df_faltas = df_faltas.drop(columns=['grupo_contrato']) 
        if 'grupo_contrato' in df_norm.columns: df_norm = df_norm.drop(columns=['grupo_contrato'])     

        st.markdown(f"**🔴 Produtos atualmente EM FALTA ({len(df_faltas)} encontrados)**") 
        
        if 'id' in df_faltas.columns and not df_faltas.empty:
            df_faltas.set_index('id', inplace=True) # Define o ID como índice para edição na tabela
            
        # Define a ordem padrão das colunas para exibição
        ordem_colunas = ['codigo', 'produto', 'fabricante', 'contrato', 'data_ruptura', 'data_retorno', 'previsao_normalizacao', 'status', 'comunicado', 'link_documento']
        df_faltas = df_faltas[[c for c in ordem_colunas if c in df_faltas.columns]] 

        # Renderiza o editor de dados interativo para atualização em lote dos produtos em falta
        df_editado = st.data_editor( 
            df_faltas, 
            use_container_width=True, 
            hide_index=True,
            disabled=["codigo", "produto", "fabricante", "contrato", "data_ruptura", "status"], # Desabilita edição de colunas essenciais
            column_config={
                "contrato": st.column_config.TextColumn("Contrato e Reserva"),
                "data_retorno": st.column_config.DateColumn("Data Retorno (Fabr.)", format="DD/MM/YYYY"), 
                "previsao_normalizacao": st.column_config.TextColumn("Prev. Normalizacao"),          
                "comunicado": st.column_config.TextColumn("Comunicado"),
                "link_documento": st.column_config.LinkColumn("Link do Comunicado", help="De um duplo clique para alterar a URL", display_text="🔗 Acessar Documento")
            }
        )
        
        if not df_faltas.empty: # Se houver dados editáveis
            if st.button("Salvar Alterações"): # Botão para efetivar as alterações feitas no data editor
                conexao = conectar_banco() # Abre conexão com o banco
                if conexao:
                    cursor = conexao.cursor() # Cria cursor ODBC
                    alteracoes_feitas = 0     # Contador de modificações
                    try:
                        def tratar_nulo(valor):
                            """Função auxiliar para tratar valores nulos do Pandas."""
                            return None if pd.isna(valor) else valor 

                        for index, row in df_editado.iterrows(): # Itera pelas linhas editadas na tabela
                            linha_original = df_faltas.loc[index] # Obtém a linha original correspondente
                            
                            novo_retorno = tratar_nulo(row['data_retorno'])
                            nova_previsao = tratar_nulo(row['previsao_normalizacao'])
                            novo_comunicado = tratar_nulo(row['comunicado'])
                            novo_link = tratar_nulo(row['link_documento'])
                            
                            orig_retorno = tratar_nulo(linha_original['data_retorno'])
                            orig_previsao = tratar_nulo(linha_original['previsao_normalizacao'])
                            orig_comunicado = tratar_nulo(linha_original['comunicado'])
                            orig_link = tratar_nulo(linha_original['link_documento'])
                            
                            # Compara se houve alteração em qualquer campo editável
                            if (novo_retorno != orig_retorno) or (nova_previsao != orig_previsao) or (novo_comunicado != orig_comunicado) or (novo_link != orig_link):
                                # Executa a Stored Procedure sp_AtualizarRegistroFalta
                                cursor.execute("{CALL dbo.sp_AtualizarRegistroFalta (?, ?, ?, ?, ?)}", 
                                               (novo_retorno, nova_previsao, novo_comunicado, novo_link, index)) 
                                alteracoes_feitas += 1 # Incrementa contador
                                
                        if alteracoes_feitas > 0: # Se houveram modificações efetivas
                            conexao.commit() # Confirma transação no banco
                            st.cache_data.clear() # Limpa o cache para refletir as alterações instantaneamente
                            st.session_state["popup_mensagem"] = f"✅ {alteracoes_feitas} registro(s) alterado(s) e gravado(s) com sucesso na base de dados!"
                            st.rerun()       # Recarrega a aplicação para atualizar a interface
                        else:
                            st.warning("⚠️ Nenhuma alteracao foi detectada.")
                    except Exception as e:
                        st.error(f"Erro ao salvar alterações: {e}")
                    finally:
                        cursor.close()   # Fecha cursor
                        conexao.close()  # Fecha conexão ODBC

        st.divider() # Linha divisória visual
        st.markdown(f"**🟢 Produtos NORMALIZADOS ({len(df_norm)} encontrados)**") # Título da seção de normalizados
        st.dataframe(df_norm, use_container_width=True, hide_index=True) # Exibe grid de produtos normalizados

# ---------------------------------------------------------------------
# ABA 2: REGISTRAR NOVA FALTA
# ---------------------------------------------------------------------
with aba2: 
    aba_manual, aba_massa = st.tabs(["Inserção Manual", "Upload em Massa (Excel)"]) # Subabas de registro manual vs massa
    
    with aba_manual: # Subaba de Inserção Manual de Falta
        codigo_busca = st.text_input("🔍 Codigo do Produto") # Input do código para busca no DW
        
        def_ean, def_prod, def_fab = "", "", "" # Inicializa variáveis padrão
        
        if codigo_busca: # Se um código foi digitado
            conexao = conectar_banco() # Abre conexão
            if conexao:
                cursor = conexao.cursor() # Cria cursor
                try: # Consulta o catálogo oficial no Data Warehouse (DW_REPRESS)
                    cursor.execute("""
                        SELECT TOP 1 [EAN], [Produto], [Fabricante]
                        FROM DW_REPRESS.dbo.vw_dProdutos 
                        WHERE [Id Produto] = ?
                    """, (codigo_busca,)) 
                    resultado_dw = cursor.fetchone() # Obtém o registro do produto
                    
                    if resultado_dw: # Se encontrado no catálogo oficial
                        def_ean = resultado_dw[0] if resultado_dw[0] else ""
                        def_prod = resultado_dw[1] if resultado_dw[1] else ""
                        def_fab = resultado_dw[2] if resultado_dw[2] else ""
                        st.success("✅ Produto localizado no catalogo oficial (DW_REPRESS)!")
                    else:
                        st.warning("⚠️ Codigo nao localizado no catalogo oficial. Verifique o codigo digitado.")
                finally:
                    cursor.close()  # Fecha cursor
                    conexao.close() # Fecha conexão
        
        with st.form("form_nova_falta", clear_on_submit=True): # Formulário de cadastro de nova falta
            col1, col2 = st.columns(2) # Divide o formulário em duas colunas
            with col1: # Coluna esquerda (Dados do produto - desabilitados pois vêm do DW)
                codigo = st.text_input("Confirmar Codigo *", value=codigo_busca, disabled=True) 
                produto = st.text_input("Descricao do Produto *", value=def_prod, disabled=True)    
                fabricante = st.text_input("Fabricante", value=def_fab, disabled=True)             
                ean = st.text_input("EAN", value=def_ean, disabled=True)                           
                
            with col2: # Coluna direita (Datas e informações complementares da falta)
                data_ruptura = st.date_input("Data da Ruptura")                                    
                data_retorno = st.date_input("Data do Retorno (Fabricante) - Opcional", value=None)  
                previsao = st.text_input("Previsao de Normalizacao - Opcional")                      
                comunicado = st.text_area("Comunicado / Observacoes")                              
                link_documento = st.text_input("Link / URL do Comunicado (Opcional)")                
                
            btn_salvar = st.form_submit_button("Salvar Registro") # Botão de submissão do formulário
            
            if btn_salvar: # Ao clicar em salvar
                if not codigo or not produto: # Valida campos obrigatórios
                    st.warning("⚠️ Os campos 'Codigo' e 'Descricao' sao obrigatorios! Certifique-se de buscar um codigo valido.")
                else: # Se válidos, inicia processo de gravação
                    conexao = conectar_banco() 
                    if conexao:
                        cursor = conexao.cursor()
                        try:
                            link_final = link_documento.strip() if link_documento.strip() != "" else None # Trata link opcional
                            if link_final and link_final.startswith("\\\\"): # Se for caminho de rede Windows
                                link_final = "file:" + link_final.replace("\\", "/") # Converte para formato URI seguro
                                
                            # Consulta contratos ativos vinculados ao produto na view de produtos/contratos
                            sql_view_contratos = """
                                SELECT DISTINCT [Contrato], [Nr Reserva]
                                FROM [ST_REPRESS].[dbo].[vw_Produtos_Contrato]
                                WHERE CAST([Id_Produto] AS VARCHAR) = ? AND UPPER([Contrato_Inativo]) = 'ATIVO'
                            """ 
                            cursor.execute(sql_view_contratos, (codigo,))
                            
                            contratos_ativos = [] # Lista para armazenar contratos ativos formatados
                            for row in cursor.fetchall():
                                nome_contrato = row[0]
                                nr_reserva = row[1]
                                if nome_contrato:
                                    if nr_reserva and str(nr_reserva).strip() not in ['', '0', 'None', 'nan']:
                                        contratos_ativos.append(f"{nome_contrato} ({str(nr_reserva).strip()})")
                                    else:
                                        contratos_ativos.append(nome_contrato)
                            
                            contratos_ativos = list(dict.fromkeys(contratos_ativos)) # Remove duplicatas preservando ordem
                            
                            if contratos_ativos: # Se o produto possui contratos ativos vinculados
                                registros_inseridos = 0
                                for nome_contrato in contratos_ativos: # Insere um registro de falta para cada contrato ativo via Stored Procedure
                                    cursor.execute("{CALL dbo.sp_InserirRegistroFalta (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                                                   (codigo, ean, produto, fabricante, nome_contrato, data_ruptura, data_retorno, previsao, comunicado, link_final, 'EM FALTA'))
                                    registros_inseridos += 1
                                
                                conexao.commit() # Confirma transação
                                st.cache_data.clear() # Limpa cache de dados
                                st.session_state["popup_mensagem"] = f"✅ Registro de falta do produto {codigo} inserido com sucesso para os {registros_inseridos} contrato(s) ativo(s)!"
                            else: # Se nenhum contrato ativo foi retornado pela view
                                cursor.execute("{CALL dbo.sp_InserirRegistroFalta (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                                               (codigo, ean, produto, fabricante, None, data_ruptura, data_retorno, previsao, comunicado, link_final, 'EM FALTA'))
                                conexao.commit()
                                st.cache_data.clear()
                                st.session_state["popup_mensagem"] = f"⚠️ Produto {codigo} registrado com sucesso, porem nenhum contrato ativo foi associado na view!"

                            st.rerun()      # Recarrega a aplicação
                        except Exception as e:
                            st.error(f"Erro ao salvar nova falta: {e}")
                        finally:
                            cursor.close()  
                            conexao.close() 

    with aba_massa: # Subaba de Upload em Massa via Excel
        
        # Dicionário estruturado para gerar a planilha modelo para download
        dados_modelo = {
            "Codigo": ["[Obrigatorio] Ex: 12345", ""],
            "Data Ruptura": ["[Opcional] Se vazio, assume a data atual do upload", ""],
            "Data Retorno": ["[Opcional] Se vazio, fica em branco (NULL)", ""],
            "Previsao": ["[Opcional] Ex: 2º Trimestre de 2026 ou DD/MM/AAAA", ""],
            "Comunicado": ["[Opcional] Se vazio, fica em branco (NULL)", ""],
            "Link": ["[Opcional] Se vazio, fica em branco (NULL)", ""]
        }
        df_modelo = pd.DataFrame(dados_modelo) 
        buffer_excel = io.BytesIO()            
        
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_modelo.to_excel(writer, index=False, sheet_name='Modelo') 
            
        buffer_excel.seek(0) 
        
        # Botão para baixar a planilha modelo de upload em massa
        st.download_button(
            label="Baixar Planilha Modelo",
            data=buffer_excel,
            file_name="modelo_upload_faltas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ) 
        st.divider()

        arquivo_excel = st.file_uploader("Selecione a Planilha de Faltas", type=["xlsx", "xls"])
        if arquivo_excel is not None: # Se um arquivo for enviado
            try:
                df_upload = pd.read_excel(arquivo_excel) # Lê o arquivo Excel enviado
                if not df_upload.empty and '[Obrigatorio]' in str(df_upload.iloc[0, 0]):
                    df_upload = df_upload.iloc[1:] # Remove a linha de instrução descritiva se presente

                colunas_lidas = [str(c).strip().lower() for c in df_upload.columns]
                if 'código' not in colunas_lidas and 'codigo' not in colunas_lidas: # Valida coluna obrigatória
                    st.error("⚠️ A planilha deve conter obrigatoriamente uma coluna chamada 'Codigo'. Verifique o arquivo e tente novamente.")
                else:
                    st.write("Previa dos dados carregados:")
                    st.dataframe(df_upload.head(), use_container_width=True) # Exibe prévia dos dados
                    
                    if st.button("🚀 Iniciar Processamento e Registrar Faltas"): # Botão para iniciar processamento em massa
                        conexao = conectar_banco()
                        if conexao:
                            cursor = conexao.cursor()
                            try:
                                sucessos = 0
                                erros = 0
                                barra_progresso = st.progress(0) # Inicializa barra de progresso visual
                                total_linhas = len(df_upload)
                                
                                def obter_valor(linha, col_opcoes):
                                    """Função auxiliar para recuperar valor de colunas com variações de nomenclatura."""
                                    for col in col_opcoes:
                                        if col in df_upload.columns:
                                            if pd.isna(linha[col]):
                                                return None
                                            return linha[col]
                                    return None

                                def tratar_data_excel(valor_data):
                                    """Função para converter datas vindas do Excel com segurança."""
                                    if pd.isna(valor_data):
                                        return None
                                    try:
                                        dt = pd.to_datetime(valor_data)
                                        return dt.date()
                                    except:
                                        return None

                                def tratar_texto_previsao(valor_previsao):
                                    """Função para tratar textos de previsão."""
                                    if pd.isna(valor_previsao) or valor_previsao is None:
                                        return None
                                    texto_limpo = str(valor_previsao).strip()
                                    if texto_limpo == "" or texto_limpo.lower() in ["nan", "none"]:
                                        return None
                                    return texto_limpo
                                
                                for index, row in df_upload.iterrows(): # Itera por cada linha da planilha
                                    cod_massa = str(obter_valor(row, ['Codigo', 'codigo', 'CODIGO'])).strip().replace('.0', '')
                                    if not cod_massa or cod_massa == "None" or cod_massa == "nan":
                                        continue
                                    
                                    # Busca dados do produto no DW
                                    cursor.execute("""
                                        SELECT TOP 1 [EAN], [Produto], [Fabricante]
                                        FROM DW_REPRESS.dbo.vw_dProdutos 
                                        WHERE [Id Produto] = ?
                                    """, (cod_massa,))
                                    res_dw = cursor.fetchone()
                                    
                                    if res_dw: # Se encontrado no DW
                                        ean_massa = res_dw[0] if res_dw[0] else ""
                                        prod_massa = res_dw[1] if res_dw[1] else ""
                                        fab_massa = res_dw[2] if res_dw[2] else ""
                                        
                                        dt_ruptura_raw = obter_valor(row, ['Data Ruptura', 'data ruptura', 'DATA RUPTURA'])
                                        dt_retorno_raw = obter_valor(row, ['Data Retorno', 'data retorno', 'DATA RETORNO'])
                                        dt_prev_raw = obter_valor(row, ['Previsao', 'previsao', 'PREVISAO'])
                                        comunicado_massa = obter_valor(row, ['Comunicado', 'comunicado', 'COMUNICADO'])
                                        link_massa = obter_valor(row, ['Link', 'link', 'LINK'])
                                        
                                        dt_ruptura = tratar_data_excel(dt_ruptura_raw)
                                        if not dt_ruptura:
                                            dt_ruptura = datetime.now().date()
                                            
                                        dt_retorno = tratar_data_excel(dt_retorno_raw)
                                        dt_prev = tratar_texto_previsao(dt_prev_raw)
                                        
                                        # Busca contratos ativos para este produto
                                        sql_view_massa = """
                                            SELECT DISTINCT [Contrato], [Nr Reserva]
                                            FROM [ST_REPRESS].[dbo].[vw_Produtos_Contrato]
                                            WHERE CAST([Id_Produto] AS VARCHAR) = ? AND UPPER([Contrato_Inativo]) = 'ATIVO'
                                        """
                                        cursor.execute(sql_view_massa, (cod_massa,))
                                        
                                        contratos_massa = []
                                        for r in cursor.fetchall():
                                            nome_cont_m, nr_res_m = r[0], r[1]
                                            if nome_cont_m:
                                                if nr_res_m and str(nr_res_m).strip() not in ['', '0', 'None', 'nan']:
                                                    contratos_massa.append(f"{nome_cont_m} ({str(nr_res_m).strip()})")
                                                else:
                                                    contratos_massa.append(nome_cont_m)
                                                    
                                        contratos_massa = list(dict.fromkeys(contratos_massa))
                                        
                                        if contratos_massa: # Insere via SP para cada contrato ativo encontrado
                                            for cont_item in contratos_massa:
                                                cursor.execute("{CALL dbo.sp_InserirRegistroFalta (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                                                               (cod_massa, ean_massa, prod_massa, fab_massa, cont_item, dt_ruptura, dt_retorno, dt_prev, comunicado_massa, link_massa, 'EM FALTA'))
                                        else: # Se não houver contratos ativos, insere sem contrato específico via SP
                                            cursor.execute("{CALL dbo.sp_InserirRegistroFalta (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", 
                                                           (cod_massa, ean_massa, prod_massa, fab_massa, None, dt_ruptura, dt_retorno, dt_prev, comunicado_massa, link_massa, 'EM FALTA'))
                                            
                                        sucessos += 1
                                    else: # Se o produto não consta no DW
                                        erros += 1
                                        
                                    barra_progresso.progress((index + 1) / total_linhas) # Atualiza barra de progresso
                                
                                conexao.commit()
                                st.cache_data.clear()
                                msg_resultado = f"🎉 Processamento concluido! {sucessos} produto(s) registrado(s) em falta."
                                if erros > 0:
                                    msg_resultado += f"\n⚠️ {erros} registro(s) ignorado(s) por nao constarem no catalogo DW_REPRESS."
                                
                                st.session_state["popup_mensagem"] = msg_resultado
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro durante o processamento em massa: {e}")
                            finally:
                                cursor.close()
                                conexao.close()
            except Exception as e:
                st.error(f"Erro ao ler a planilha: {e}")

# ---------------------------------------------------------------------
# ABA 3: NORMALIZAR PRODUTO
# ---------------------------------------------------------------------
with aba3: 
    aba_manual_norm, aba_massa_norm = st.tabs(["Normalização Manual", "Upload em Massa (Excel)"])
    
    with aba_manual_norm: # Normalização Manual
        codigo_busca_norm = st.text_input("🔍 Buscar Codigo para Normalizar")
        
        if codigo_busca_norm:
            conexao = conectar_banco()
            if conexao:
                cursor = conexao.cursor()
                try: # Busca registros pendentes (em falta) para o código informado
                    cursor.execute("""
                        SELECT id, produto, contrato, data_ruptura 
                        FROM registro_faltas 
                        WHERE codigo = ? AND (UPPER(status) != 'NORMALIZADO' OR status IS NULL)
                    """, (codigo_busca_norm,))
                    pendentes = cursor.fetchall()
                    
                    if pendentes: # Se houver pendências
                        st.success(f"Encontrado(s) {len(pendentes)} registro(s) pendente(s) para este produto.")
                        nome_produto = pendentes[0][1] if pendentes[0][1] else "Sem descricao"
                        
                        with st.form("form_normalizar"):
                            st.markdown("**Dados do Produto Selecionado (Somente Leitura):**")
                            st.text_input("Produto", value=nome_produto, disabled=True)
                            data_normalizacao = st.date_input("Qual foi a data de normalizacao? *")
                            btn_normalizar = st.form_submit_button(" Confirmar Normalização")
                            
                            if btn_normalizar: # Efetiva a normalização via Stored Procedure para todos os contratos vinculados
                                registros_atualizados = 0
                                for item in pendentes:
                                    id_reg = item[0]
                                    data_r = item[3]
                                    dias_ruptura = None
                                    if data_r:
                                        if hasattr(data_r, 'date'):
                                            data_r = data_r.date()
                                        dias_ruptura = (data_normalizacao - data_r).days # Calcula dias em ruptura
                                        
                                    # Executa a Stored Procedure sp_NormalizarRegistroFalta
                                    cursor.execute("{CALL dbo.sp_NormalizarRegistroFalta (?, ?, ?)}", 
                                                   (id_reg, data_normalizacao, dias_ruptura))
                                    registros_atualizados += 1
                                    
                                conexao.commit()
                                st.cache_data.clear()
                                st.session_state["popup_mensagem"] = f"🎉 Produto {codigo_busca_norm} normalizado com sucesso! ({registros_atualizados} contrato(s) atualizado(s))."
                                st.rerun()
                    else:
                        st.info("Nenhum registro pendente (em falta) encontrado para este codigo no banco.")
                finally:
                    cursor.close()
                    conexao.close()

    with aba_massa_norm: # Normalização em Massa via Excel
        
        dados_modelo_norm = {
            "Codigo do Produto": ["[Obrigatorio] Ex: 12345", ""],
            "Data de Normalizacao": ["[Opcional] Se vazio, assume a data atual do upload (DD/MM/AAAA)", ""]
        }
        df_modelo_norm = pd.DataFrame(dados_modelo_norm)
        buffer_excel_norm = io.BytesIO()
        
        with pd.ExcelWriter(buffer_excel_norm, engine='openpyxl') as writer:
            df_modelo_norm.to_excel(writer, index=False, sheet_name='Modelo')
            
        buffer_excel_norm.seek(0)
        st.download_button(
            label="Baixar Planilha Modelo Normalizar",
            data=buffer_excel_norm,
            file_name="modelo_upload_normalizar.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.divider()

        arquivo_excel_norm = st.file_uploader("Selecione a Planilha de Normalizacao", type=["xlsx", "xls"], key="uploader_normalizar")
        if arquivo_excel_norm is not None:
            try:
                df_upload_norm = pd.read_excel(arquivo_excel_norm)
                if not df_upload_norm.empty and '[Obrigatorio]' in str(df_upload_norm.iloc[0, 0]):
                    df_upload_norm = df_upload_norm.iloc[1:]

                colunas_lidas_norm = [str(c).strip().lower() for c in df_upload_norm.columns]
                if not any(col in colunas_lidas_norm for col in ['código do produto', 'codigo do produto', 'codigo', 'código']):
                    st.error("⚠️ A planilha deve conter obrigatoriamente a coluna 'Codigo do Produto'. Verifique o arquivo e tente novamente.")
                else:
                    st.write("Previa dos dados de normalizacao carregados:")
                    st.dataframe(df_upload_norm.head(), use_container_width=True)
                    
                    if st.button("🚀 Iniciar Processamento e Normalizar Produtos"):
                        conexao_massa_norm = conectar_banco()
                        if conexao_massa_norm:
                            cursor_massa_norm = conexao_massa_norm.cursor()
                            try:
                                sucessos_norm = 0
                                nao_encontrados_norm = 0
                                barra_progresso_norm = st.progress(0)
                                total_linhas_norm = len(df_upload_norm)
                                
                                def obter_valor_norm(linha, opcoes_nomes):
                                    """Função auxiliar para obter valor de colunas de normalização."""
                                    for nome_col in opcoes_nomes:
                                        for col_atual in df_upload_norm.columns:
                                            if str(col_atual).strip().lower() == nome_col.lower():
                                                if pd.isna(linha[col_atual]):
                                                    return None
                                                return linha[col_atual]
                                    return None

                                def tratar_data_excel_norm(val_data):
                                    """Trata conversão de datas para normalização."""
                                    if pd.isna(val_data) or val_data is None:
                                        return None
                                    try:
                                        dt_conv = pd.to_datetime(val_data)
                                        return dt_conv.date()
                                    except:
                                        return None

                                for index_norm, row_norm in df_upload_norm.iterrows():
                                    cod_raw = obter_valor_norm(row_norm, ['Codigo do Produto', 'codigo do produto', 'codigo', 'código'])
                                    cod_norm = str(cod_raw).strip().replace('.0', '') if cod_raw is not None else ""
                                    
                                    if not cod_norm or cod_norm == "None" or cod_norm == "nan":
                                        continue
                                    
                                    dt_norm_raw = obter_valor_norm(row_norm, ['Data de Normalizacao', 'data de normalizacao', 'data normalizacao', 'data_normalizacao'])
                                    dt_norm = tratar_data_excel_norm(dt_norm_raw)
                                    if not dt_norm:
                                        dt_norm = datetime.now().date()
                                    
                                    cursor_massa_norm.execute("""
                                        SELECT id, data_ruptura 
                                        FROM registro_faltas 
                                        WHERE codigo = ? AND (UPPER(status) != 'NORMALIZADO' OR status IS NULL)
                                    """, (cod_norm,))
                                    pendentes_massa = cursor_massa_norm.fetchall()
                                    
                                    if pendentes_massa:
                                        for item in pendentes_massa:
                                            id_reg = item[0]
                                            data_r = item[1]
                                            dias_ruptura = None
                                            if data_r:
                                                if hasattr(data_r, 'date'):
                                                    data_r = data_r.date()
                                                dias_ruptura = (dt_norm - data_r).days
                                                
                                            # Executa Stored Procedure sp_NormalizarRegistroFalta em lote
                                            cursor_massa_norm.execute("{CALL dbo.sp_NormalizarRegistroFalta (?, ?, ?)}", 
                                                                       (id_reg, dt_norm, dias_ruptura))
                                        sucessos_norm += 1
                                    else:
                                        nao_encontrados_norm += 1
                                        
                                    barra_progresso_norm.progress((index_norm + 1) / total_linhas_norm)
                                
                                conexao_massa_norm.commit()
                                st.cache_data.clear()
                                res_massa_norm = f"🎉 Processamento concluido! {sucessos_norm} produto(s) normalizado(s) com sucesso."
                                if nao_encontrados_norm > 0:
                                    res_massa_norm += f"\n⚠️ {nao_encontrados_norm} codigo(s) ignorado(s) por nao possuirem pendencias ativas."
                                    
                                st.session_state["popup_mensagem"] = res_massa_norm
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao processar normalizações em massa: {e}")
                            finally:
                                cursor_massa_norm.close()
                                conexao_massa_norm.close()
            except Exception as e:
                st.error(f"Erro ao processar a planilha de normalizacao: {e}")

# ---------------------------------------------------------------------
# ABA 4: SOLICITACOES DE VENDAS
# ---------------------------------------------------------------------
with aba4: 
    df_solicitacoes = carregar_solicitacoes_cache() # Carrega solicitações de vendas em cache
    
    if not df_solicitacoes.empty: # Se houver solicitações
        df_solicitacoes.set_index('id', inplace=True) # Define ID como índice

        if 'Status_Compra' in df_solicitacoes.columns:
            df_solicitacoes['Status_Compra_Upper'] = df_solicitacoes['Status_Compra'].fillna('OUTROS').astype(str).str.upper()
        else:
            df_solicitacoes['Status_Compra_Upper'] = 'OUTROS'

        # Filtra solicitações por categoria (Farma, Hospitalar, Descontinuado)
        df_farma = df_solicitacoes[df_solicitacoes['Status_Compra_Upper'].str.contains('FARMA')].copy()
        df_hosp = df_solicitacoes[df_solicitacoes['Status_Compra_Upper'].str.contains('HOSPITALAR')].copy()
        df_desc = df_solicitacoes[df_solicitacoes['Status_Compra_Upper'].str.contains('DESCONTINUADO')].copy()

        colunas_exibicao = [
            "data_solicitacao", "hora_solicitacao", "codigo", "ean", "descricao", "fabricante", 
            "quantidade", "solicitante", "prioridade", "qtde_atendida", "status_solicitacao", 
            "distribuidor", "previsao_chegada", "data_recebida", "numero_nf"
        ]

        df_farma = df_farma[[c for c in colunas_exibicao if c in df_farma.columns]]
        df_hosp = df_hosp[[c for c in colunas_exibicao if c in df_hosp.columns]]
        df_desc = df_desc[[c for c in colunas_exibicao if c in df_desc.columns]]

        col_config = {
            "data_solicitacao": st.column_config.DateColumn("Data Solicit.", format="DD/MM/YYYY"),
            "hora_solicitacao": st.column_config.TimeColumn("Hora Solicit."),
            "codigo": st.column_config.TextColumn("Codigo"),
            "ean": st.column_config.TextColumn("EAN"),
            "descricao": st.column_config.TextColumn("Descricao"),
            "fabricante": st.column_config.TextColumn("Fabricante"),
            "quantidade": st.column_config.NumberColumn("Qtd Solicitada", format="%d"),
            "solicitante": st.column_config.TextColumn("Solicitante"),
            "prioridade": st.column_config.TextColumn("Prioridade"),
            "qtde_atendida": st.column_config.NumberColumn("Qtd Atendida", step=1, format="%d"),
            "status_solicitacao": st.column_config.SelectboxColumn("Status", options=["PENDENTE", "ATENDIDO PARCIAL", "ATENDIDO", "FALTA"]),
            "distribuidor": st.column_config.TextColumn("Distribuidor"),
            "previsao_chegada": st.column_config.DateColumn("Previsao Chegada", format="DD/MM/YYYY"),
            "data_recebida": st.column_config.DateColumn("Data Recebida", format="DD/MM/YYYY"),
            "numero_nf": st.column_config.TextColumn("NFº")
        }
        
        cols_bloqueadas = ["data_solicitacao", "hora_solicitacao", "codigo", "ean", "descricao", "fabricante", "quantidade", "solicitante", "prioridade"]

        # Renderiza editores de dados para cada categoria de solicitações de vendas com o total de registros informativo abaixo
        st.markdown("### Categoria: Farma")
        df_farma_edit = st.data_editor(df_farma, key="editor_farma", use_container_width=True, hide_index=True, disabled=cols_bloqueadas, column_config=col_config)
        st.caption(f"Total de registros na Categoria Farma: **{len(df_farma)}**")

        st.markdown("### Categoria: Hospitalar")
        df_hosp_edit = st.data_editor(df_hosp, key="editor_hosp", use_container_width=True, hide_index=True, disabled=cols_bloqueadas, column_config=col_config)
        st.caption(f"Total de registros na Categoria Hospitalar: **{len(df_hosp)}**")

        st.markdown("### Categoria: Descontinuado")
        df_desc_edit = st.data_editor(df_desc, key="editor_desc", use_container_width=True, hide_index=True, disabled=cols_bloqueadas, column_config=col_config)
        st.caption(f"Total de registros na Categoria Descontinuado: **{len(df_desc)}**")
        
        st.divider()

        if st.button("Salvar Alterações em Solicitações"): # Botão para gravar alterações em lote das solicitações
            conexao = conectar_banco()
            if conexao:
                cursor = conexao.cursor()
                try:
                    modificacoes = 0
                    
                    def tratar_nulo(val):
                        return None if pd.isna(val) else val
                    
                    def tratar_inteiro(val):
                        if pd.isna(val) or val is None or str(val).strip() == "":
                            return None
                        try:
                            return int(float(str(val).strip()))
                        except (ValueError, TypeError):
                            return None
                    
                    # Concatena os dataframes editados de todas as categorias
                    df_solicitacoes_editado = pd.concat([df_farma_edit, df_hosp_edit, df_desc_edit])

                    for id_solic, row_edit in df_solicitacoes_editado.iterrows():
                        row_orig = df_solicitacoes.loc[id_solic]
                        
                        st_novo = tratar_nulo(row_edit['status_solicitacao'])
                        qtd_atendida_novo = tratar_inteiro(row_edit['qtde_atendida'])
                        dist_novo = tratar_nulo(row_edit['distribuidor'])
                        prev_novo = tratar_nulo(row_edit['previsao_chegada'])
                        rec_novo = tratar_nulo(row_edit['data_recebida'])
                        nf_novo = tratar_inteiro(row_edit['numero_nf'])
                        
                        st_orig = tratar_nulo(row_orig['status_solicitacao'])
                        qtd_atendida_orig = tratar_inteiro(row_orig['qtde_atendida'])
                        dist_orig = tratar_nulo(row_orig['distribuidor'])
                        prev_orig = tratar_nulo(row_orig['previsao_chegada'])
                        rec_orig = tratar_nulo(row_orig['data_recebida'])
                        nf_orig = tratar_inteiro(row_orig['numero_nf'])
                        
                        # Verifica se houve alteração nos campos
                        if (st_novo != st_orig) or (qtd_atendida_novo != qtd_atendida_orig) or (dist_novo != dist_orig) or (prev_novo != prev_orig) or (rec_novo != rec_orig) or (nf_novo != nf_orig):
                            # CORREÇÃO APLICADA: Ordem correta dos parâmetros enviando @id (id_solic) primeiro conforme a Stored Procedure
                            cursor.execute("{CALL dbo.sp_AtualizarSolicitacaoVenda (?, ?, ?, ?, ?, ?, ?)}", 
                                           (id_solic, st_novo, qtd_atendida_novo, dist_novo, prev_novo, rec_novo, nf_novo))
                            modificacoes += 1
                            
                    if modificacoes > 0:
                        conexao.commit()
                        st.cache_data.clear()
                        st.session_state["popup_mensagem"] = f"✅ {modificacoes} solicitacao(oes) de venda atualizada(s) com sucesso!"
                        st.rerun()
                    else:
                        st.warning("⚠️ Nenhuma alteracao foi detectada nas solicitacoes.")
                except Exception as e:
                    st.error(f"Erro ao salvar solicitações: {e}")
                finally:
                    cursor.close()
                    conexao.close()
    else:
        st.info("Nenhuma solicitacao de compra foi enviada pela equipe de Vendas ate o momento.")

# ---------------------------------------------------------------------
# ABA 5: ENTRADAS PENDENTES
# ---------------------------------------------------------------------
with aba5: 
    aba_manual_ent, aba_massa_ent = st.tabs(["Inserção Manual", "Upload em Massa (Excel)"])
    
    conexao_global_aba5 = conectar_banco()
    
    with aba_manual_ent: # Inserção Manual de Entradas Pendentes
        if conexao_global_aba5:
            st.markdown("### Inserir Novo Codigo")
            
            codigo_busca_entrada = st.text_input("🔍 Codigo do Produto (Buscar no DW)", key="busca_ent_manual")
            def_ean_ent, def_prod_ent, def_fab_ent = "", "", ""
            
            if codigo_busca_entrada:
                cursor_tmp = conexao_global_aba5.cursor()
                try: # Busca dados do produto no DW para preenchimento automático
                    query_dw_entradas = """
                        SELECT TOP 1 [EAN], [Produto], [Fabricante]
                        FROM DW_REPRESS.dbo.vw_dProdutos 
                        WHERE [Id Produto] = ?
                    """
                    cursor_tmp.execute(query_dw_entradas, (codigo_busca_entrada,))
                    res_dw_entradas = cursor_tmp.fetchone()
                    
                    if res_dw_entradas:
                        def_ean_ent = res_dw_entradas[0] if res_dw_entradas[0] else ""
                        def_prod_ent = res_dw_entradas[1] if res_dw_entradas[1] else ""
                        def_fab_ent = res_dw_entradas[2] if res_dw_entradas[2] else ""
                        st.success("✅ Produto localizado no catalogo oficial (DW_REPRESS)!")
                    else:
                        st.warning("⚠️ Codigo nao localizado no catalogo oficial. Verifique o codigo digitado.")
                finally:
                    cursor_tmp.close()

            with st.form("form_nova_entrada", clear_on_submit=True): # Formulário de nova entrada
                col_in1, col_in2, col_in3 = st.columns(3)
                
                with col_in1:
                    novo_codigo = st.text_input("Confirmar Codigo *", value=codigo_busca_entrada, disabled=True)
                    novo_ean = st.text_input("EAN", value=def_ean_ent, disabled=True)
                    quantidade_comprada = st.number_input(
                        label="Quantidade Comprada",
                        min_value=0,
                        step=1,
                        format="%d",
                        key="input_quantidade_comprada_aba5",
                    )
                
                with col_in2:
                    novo_produto = st.text_input("Descricao do Produto *", value=def_prod_ent, disabled=True)
                    novo_recebido = st.text_input("Recebido Via")
                    nova_previsao = st.date_input("Previsao de Chegada", value=None)
                    
                with col_in3:
                    novo_fabricante = st.text_input("Fabricante", value=def_fab_ent, disabled=True)
                    st.write("") 
                    novo_status = st.selectbox("Status (Entrada)", ["Pendente", "OK"])
                    
                btn_inserir_entrada = st.form_submit_button("Inserir Produto Comprado")
                
                if btn_inserir_entrada: # Efetiva inserção manual de entrada via SP
                    if not novo_codigo or not novo_produto:
                        st.warning("⚠️ Os campos 'Codigo' e 'Descricao' sao obrigatorios! Busque um codigo valido antes de inserir.")
                    else:
                        conn_ins = conectar_banco()
                        if conn_ins:
                            cursor_ins = conn_ins.cursor()
                            try:
                                # Executa Stored Procedure sp_InserirEntradaPendente
                                cursor_ins.execute("{CALL dbo.sp_InserirEntradaPendente (?, ?, ?, ?, ?, ?, ?, ?)}", 
                                                   (novo_codigo, novo_ean, novo_produto, novo_fabricante, quantidade_comprada, novo_recebido, nova_previsao, novo_status))
                                conn_ins.commit()
                                st.cache_data.clear()
                                st.session_state["popup_mensagem"] = f"✅ Entrada do produto {novo_codigo} ({novo_produto}) gravada com sucesso!"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao inserir entrada: {e}")
                            finally:
                                cursor_ins.close()
                                conn_ins.close()

            st.divider()
            st.markdown("### Tabela de Entradas")
            
            df_entradas = carregar_entradas_cache() # Carrega entradas pendentes em cache
            
            if not df_entradas.empty:
                df_entradas.set_index('id', inplace=True)
                
                df_entradas_editado = st.data_editor( # Editor interativo para entradas pendentes
                    df_entradas,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["codigo", "ean", "produto", "fabricante"],
                    column_config={
                       "quantidade": st.column_config.NumberColumn("Quantidade", format="%d"),
                       "recebido_via": st.column_config.TextColumn("Recebido Via"),
                       "previsao_chegada": st.column_config.DateColumn("Prev. Chegada", format="DD/MM/YYYY"),
                       "data_recebida": st.column_config.DateColumn("Data Recebida", format="DD/MM/YYYY"),
                       "numero_nf": st.column_config.TextColumn("NF"),
                       "status_entrada": st.column_config.SelectboxColumn("Entrada", options=["Pendente", "OK"])
                    }
                )
                # Exibe o total de registros da Tabela de Entradas em caráter informativo
                st.caption(f"Total de registros na Tabela de Entradas: **{len(df_entradas)}**")
                
                if st.button("Salvar Alterações de Entradas"): # Salva edições na tabela de entradas
                    conn_upd = conectar_banco()
                    if conn_upd:
                        cursor_upd = conn_upd.cursor()
                        try:
                            total_mods_entrada = 0
                            
                            def converter_nulo_entrada(val):
                                return None if pd.isna(val) else val

                            def tratar_numero_nf(val):
                                if pd.isna(val) or val is None or str(val).strip() == "":
                                    return None
                                try:
                                    return int(float(str(val).strip()))
                                except (ValueError, TypeError):
                                    return None
                                
                            for idx, row in df_entradas_editado.iterrows():
                                row_antiga = df_entradas.loc[idx]
                                
                                q_novo = converter_nulo_entrada(row['quantidade'])
                                rv_novo = converter_nulo_entrada(row['recebido_via'])
                                pc_novo = converter_nulo_entrada(row['previsao_chegada'])
                                dr_novo = converter_nulo_entrada(row['data_recebida'])
                                nf_novo = tratar_numero_nf(row['numero_nf'])
                                st_novo = converter_nulo_entrada(row['status_entrada'])
                                
                                q_antigo = converter_nulo_entrada(row_antiga['quantidade'])
                                rv_antigo = converter_nulo_entrada(row_antiga['recebido_via'])
                                pc_antigo = converter_nulo_entrada(row_antiga['previsao_chegada'])
                                dr_antigo = converter_nulo_entrada(row_antiga['data_recebida'])
                                nf_antigo = tratar_numero_nf(row_antiga['numero_nf'])
                                st_antigo = converter_nulo_entrada(row_antiga['status_entrada'])
                                
                                if (q_novo != q_antigo) or (rv_novo != rv_antigo) or (pc_novo != pc_antigo) or (dr_novo != dr_antigo) or (nf_novo != nf_antigo) or (st_novo != st_antigo):
                                    # Executa Stored Procedure sp_AtualizarEntradaPendente
                                    cursor_upd.execute("{CALL dbo.sp_AtualizarEntradaPendente (?, ?, ?, ?, ?, ?, ?)}", 
                                                       (idx, q_novo, rv_novo, pc_novo, dr_novo, nf_novo, st_novo))
                                    total_mods_entrada += 1
                                    
                            if total_mods_entrada > 0:
                                conn_upd.commit()
                                st.cache_data.clear()
                                st.session_state["popup_mensagem"] = f"✅ {total_mods_entrada} entrada(s) atualizada(s) e gravada(s) no sistema!"
                                st.rerun()
                            else:
                                st.warning("⚠️ Nenhuma edicao detectada na tabela.")
                        except Exception as e:
                            st.error(f"Erro ao salvar entradas: {e}")
                        finally:
                            cursor_upd.close()
                            conn_upd.close()

                st.divider()
                st.markdown("### Higienizar Tabela de Entradas")
                lista_para_exclusao = [f"ID {idx} - Codigo: {row['codigo']} ({row['produto']})" for idx, row in df_entradas.iterrows()]
                itens_selecionados_del = st.multiselect("Selecione um ou mais itens para remover do controle:", lista_para_exclusao, key="del_entradas_multiselect")
                
                if itens_selecionados_del:
                    if st.button("Confirmar Deleção de Entradas"): # Botão para excluir itens selecionados via SP
                        conn_del = conectar_banco()
                        if conn_del:
                            cursor_del = conn_del.cursor()
                            try:
                                lista_de_ids_para_deletar = [int(texto_escolhido.split(" - ")[0].replace("ID ", "")) for texto_escolhido in itens_selecionados_del]
                                for item_id_delete in lista_de_ids_para_deletar:
                                    # Executa Stored Procedure sp_DeletarEntradaPendente
                                    cursor_del.execute("{CALL dbo.sp_DeletarEntradaPendente (?)}", (item_id_delete,))
                                conn_del.commit()
                                st.cache_data.clear()
                                st.session_state["popup_mensagem"] = f"✅ {len(lista_de_ids_para_deletar)} item(ns) removido(s) com sucesso da base de dados!"
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao deletar entradas: {e}")
                            finally:
                                cursor_del.close()
                                conn_del.close()
            else:
                st.info("📦 Não há nenhum registro de entrada pendente armazenado. Inicie cadastrando no formulário acima.")

    if conexao_global_aba5:
        conexao_global_aba5.close()

    with aba_massa_ent: # Upload em Massa de Entradas Pendentes via Excel
        
        dados_modelo_entradas = {
            "Codigo do Produto": ["[Obrigatorio] Ex: 12345", ""],
            "Quantidade Comprada": ["[Opcional] Se vazio, assume 0", ""],
            "Recebido Via": ["[Opcional] Se vazio, fica em branco", ""],
            "Previsao de Chegada": ["[Opcional] Se vazio, fica em branco (NULL)", ""],
            "Data Recebida": ["[Opcional] Formato DD/MM/AAAA, pode aceitar vazio", ""],
            "NF": ["[Opcional] Número da Nota Fiscal, pode aceitar vazio", ""],
            "Status (Entrada)": ["[Opcional] Se vazio, assume 'Pendente'", ""]
        }
        df_modelo_entradas = pd.DataFrame(dados_modelo_entradas)
        buffer_excel_entradas = io.BytesIO()
        
        with pd.ExcelWriter(buffer_excel_entradas, engine='openpyxl') as writer:
            df_modelo_entradas.to_excel(writer, index=False, sheet_name='Modelo')
            
        buffer_excel_entradas.seek(0)
        st.download_button(
            label="Baixar Planilha Modelo de Entradas",
            data=buffer_excel_entradas,
            file_name="modelo_upload_entradas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.divider()

        arquivo_excel_entradas = st.file_uploader("Selecione a Planilha de Entradas Pendentes", type=["xlsx", "xls"], key="uploader_entradas")
        if arquivo_excel_entradas is not None:
            try:
                df_upload_ent = pd.read_excel(arquivo_excel_entradas)
                if not df_upload_ent.empty and '[Obrigatorio]' in str(df_upload_ent.iloc[0, 0]):
                    df_upload_ent = df_upload_ent.iloc[1:]

                colunas_lidas_ent = [str(c).strip().lower() for c in df_upload_ent.columns]
                if not any(col in colunas_lidas_ent for col in ['código do produto', 'codigo do produto', 'codigo', 'código']):
                    st.error("⚠️ A planilha deve conter obrigatoriamente a coluna 'Codigo do Produto'. Verifique o arquivo e tente novamente.")
                else:
                    st.write("Previa dos dados de entrada carregados:")
                    st.dataframe(df_upload_ent.head(), use_container_width=True)
                    
                    if st.button("🚀 Iniciar Processamento e Registrar Entradas"): # Inicia processamento em massa de entradas
                        conexao_massa_ent = conectar_banco()
                        if conexao_massa_ent:
                            cursor_massa_ent = conexao_massa_ent.cursor()
                            try:
                                sucessos_ent = 0
                                erros_ent = 0
                                barra_progresso_ent = st.progress(0)
                                total_linhas_ent = len(df_upload_ent)
                                
                                def obter_valor_ent(linha, opcoes_nomes):
                                    """Obtém valor da linha de upload de entradas."""
                                    for nome_col in opcoes_nomes:
                                        for col_atual in df_upload_ent.columns:
                                            if str(col_atual).strip().lower() == nome_col.lower():
                                                if pd.isna(linha[col_atual]):
                                                    return None
                                                return linha[col_atual]
                                    return None

                                def tratar_data_excel_ent(val_data):
                                    if pd.isna(val_data):
                                        return None
                                    try:
                                        dt_conv = pd.to_datetime(val_data)
                                        return dt_conv.date()
                                    except:
                                        return None

                                def tratar_numero_nf(val):
                                    if pd.isna(val) or val is None or str(val).strip() == "":
                                        return None
                                    try:
                                        return int(float(str(val).strip()))
                                    except (ValueError, TypeError):
                                        return None

                                for index_ent, row_ent in df_upload_ent.iterrows():
                                    codigo_massa_raw = obter_valor_ent(row_ent, ['Codigo do Produto', 'codigo do produto', 'codigo', 'código'])
                                    codigo_massa_ent = str(codigo_massa_raw).strip().replace('.0', '') if not pd.isna(codigo_massa_raw) else ""
                                    
                                    if not codigo_massa_ent or codigo_massa_ent == "None" or codigo_massa_ent == "nan":
                                        continue
                                    
                                    cursor_massa_ent.execute("""
                                        SELECT TOP 1 [EAN], [Produto], [Fabricante]
                                        FROM DW_REPRESS.dbo.vw_dProdutos 
                                        WHERE [Id Produto] = ?
                                    """, (codigo_massa_ent,))
                                    res_dw_ent = cursor_massa_ent.fetchone()
                                    
                                    if res_dw_ent:
                                        ean_massa_ent = res_dw_ent[0] if res_dw_ent[0] else ""
                                        prod_massa_ent = res_dw_ent[1] if res_dw_ent[1] else ""
                                        fab_massa_ent = res_dw_ent[2] if res_dw_ent[2] else ""
                                        
                                        qtd_raw = obter_valor_ent(row_ent, ['Quantidade Comprada', 'quantidade comprada', 'quantidade'])
                                        rec_via_raw = obter_valor_ent(row_ent, ['Recebido Via', 'recebido via'])
                                        prev_cheg_raw = obter_valor_ent(row_ent, ['Previsao de Chegada', 'previsao de chegada', 'previsao'])
                                        status_ent_raw = obter_valor_ent(row_ent, ['Status (Entrada)', 'status (entrada)', 'status'])
                                        data_rec_raw = obter_valor_ent(row_ent, ['Data Recebida', 'data recebida'])
                                        nf_raw = obter_valor_ent(row_ent, ['NF', 'nf', 'Número da NF', 'numero da nf'])
                                        
                                        try:
                                            quantidade_massa = int(qtd_raw) if not pd.isna(qtd_raw) else 0
                                        except:
                                            quantidade_massa = 0
                                            
                                        recebido_via_massa = str(rec_via_raw).strip() if not pd.isna(rec_via_raw) else None
                                        previsao_chegada_massa = tratar_data_excel_ent(prev_cheg_raw)
                                        data_recebida_massa = tratar_data_excel_ent(data_rec_raw)
                                        nf_massa = tratar_numero_nf(nf_raw)
                                        
                                        if pd.isna(status_ent_raw) or str(status_ent_raw).strip() == "":
                                            status_entrada_massa = "Pendente"
                                        else:
                                            status_entrada_massa = str(status_ent_raw).strip()
                                            
                                        # Executa Stored Procedure sp_InserirEntradaPendente em lote
                                        cursor_massa_ent.execute("{CALL dbo.sp_InserirEntradaPendente (?, ?, ?, ?, ?, ?, ?, ?)}", 
                                                                   (codigo_massa_ent, ean_massa_ent, prod_massa_ent, fab_massa_ent, quantidade_massa, recebido_via_massa, previsao_chegada_massa, status_entrada_massa))
                                        sucessos_ent += 1
                                    else:
                                        erros_ent += 1
                                        
                                    barra_progresso_ent.progress((index_ent + 1) / total_linhas_ent)
                                
                                conexao_massa_ent.commit()
                                st.cache_data.clear()
                                res_massa_entradas = f"🎉 Processamento concluido! {sucessos_ent} produto(s) de entrada gravado(s)."
                                if erros_ent > 0:
                                    res_massa_entradas += f"\n⚠️ {erros_ent} registro(s) ignorado(s) por nao constarem no DW_REPRESS."
                                
                                st.session_state["popup_mensagem"] = res_massa_entradas
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao processar entradas em massa: {e}")
                            finally:
                                cursor_massa_ent.close()
                                conexao_massa_ent.close()
            except Exception as e:
                st.error(f"Erro ao processar a planilha de entradas: {e}")