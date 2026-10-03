# ==============================================================================
# 1. IMPORTE DE TODAS AS BIBLIOTECAS NECESSÁRIAS
# ==============================================================================
import os                       # Manipulação de caminhos e leitura de variáveis de ambiente
import streamlit as st          # Framework principal para construção da interface web interativa
import pandas as pd             # Manipulação de DataFrames e leitura estruturada de dados
import numpy as np              # Manipulação de arrays e constantes matemáticas
import plotly.express as px     # Geração de gráficos dinâmicos com suporte a Dark Mode
from sqlalchemy import create_engine # Criação de engine de conexão SQL via SQLAlchemy
from langchain_community.utilities import SQLDatabase # Utilitário LangChain para inspeção de esquemas SQL
from langchain_ollama import ChatOllama               # Integração com o modelo local Ollama
from langchain_core.prompts import PromptTemplate     # Construtor de templates de prompt estruturados
import re                       # Expressões regulares para varredura e extração de blocos de texto
from datetime import datetime   # Manipulação de datas e horários
from dateutil.relativedelta import relativedelta       # Cálculo de intervalos e deslocamento de meses
import urllib.parse             # Codificação segura de strings de conexão URL
import pyodbc                   # Conexão nativa ODBC com o SQL Server
import decimal                  # Manipulação precisa de números decimais
from dotenv import load_dotenv  # Carregador seguro de variáveis de ambiente do arquivo .env
from database import obter_conexao_ia_aplicativos, obter_conexao_ia_dw, obter_conexao_principal # Helpers centrais do portal

# Carrega as variáveis de ambiente para a memória do sistema
load_dotenv()

# ==============================================================================
# 2. CONFIGURAÇÃO VISUAL DA PÁGINA E INJEÇÃO DO DESIGN SYSTEM (STYLES.PY)
# ==============================================================================
st.set_page_config(
    page_title="BI N1 - Modo IA", 
    page_icon="📊", 
    layout="wide"
)

# Importa e injeta a folha de estilos centralizada do portal (substituindo o CSS legado)
from styles import injetar_estilo_global
injetar_estilo_global()

st.title("Chat IA - BI Conversacional")
st.caption("Consulte a base de dados consolidada DW_REPRESS de forma inteligente, validada pelas regras de negócio.")

# ==============================================================================
# 3. AUTENTICAÇÃO E CONTROLE DE ACESSO (ADMIN vs COMUM)
# ==============================================================================
def is_admin_user(email_usuario):
    """Valida se o usuário autenticado na sessão possui privilégios de administrador."""
    if not email_usuario:
        return False
    try:
        conn = obter_conexao_ia_aplicativos()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("SELECT nivel FROM [auth].[Usuarios] WHERE email = ?", (email_usuario,))
        row = cursor.fetchone()
        conn.close()
        if row and str(row[0]).strip().lower() == 'admin':
            return True
        return False
    except Exception:
        return False

# Captura parâmetros da URL para identificar o usuário logado
query_params = st.query_params
email_logado = query_params.get("user", "")

if "is_admin" not in st.session_state:
    st.session_state.is_admin = is_admin_user(email_logado)

# ==============================================================================
# 4. RAG CORPORATIVO: LEITURA EM TEMPO REAL DA TABELA DE REGRAS
# ==============================================================================
@st.cache_data(ttl=300) # Cache de 5 minutos para otimizar a leitura das regras corporativas
def carregar_regras_do_banco():
    """Lê as regras de negócio, fórmulas DAX e instruções SQL da tabela tb_regras_bi_ia."""
    try:
        conn = obter_conexao_ia_aplicativos()
        if not conn:
            return pd.DataFrame()
        query = "SELECT nome_medida, tabela_origem, formula_dax, instrucao_sql, descricao_regra FROM dbo.tb_regras_bi_ia"
        df_regras = pd.read_sql(query, conn)
        conn.close()
        return df_regras
    except Exception:
        try:
            conn = obter_conexao_ia_aplicativos()
            if not conn:
                return pd.DataFrame()
            query_fallback = "SELECT nome_medida, tabela_origem, formula_dax, descricao_regra FROM dbo.tb_regras_bi_ia"
            df_regras = pd.read_sql(query_fallback, conn)
            df_regras['instrucao_sql'] = None
            conn.close()
            return df_regras
        except Exception:
            return pd.DataFrame()

def buscar_regras_dinamicas(pergunta_usuario, df_regras):
    """Filtra as regras da tabela com base nas palavras-chave da pergunta do usuário."""
    if df_regras.empty:
        return "Nenhuma regra cadastrada."
        
    palavras_chave = [p.lower().strip(',.?') for p in pergunta_usuario.split() if len(p) > 3]
    regras_encontradas = []
    
    for _, row in df_regras.iterrows():
        nome = str(row['nome_medida']).lower()
        if any(palavra in nome for palavra in palavras_chave):
            sql_pronto = row.get('instrucao_sql')
            if pd.isna(sql_pronto) or not sql_pronto:
                sql_pronto = "Não especificado"
            regra_fmt = f"- Métrica: {row['nome_medida']} | Tabela Oficial: {row['tabela_origem']} | Instrução SQL Obrigatória: {sql_pronto}"
            regras_encontradas.append(regra_fmt)
            
    if regras_encontradas:
        return "\n".join(regras_encontradas[:10])
    return "Utilize as views disponíveis aplicando filtros padrão."

# ==============================================================================
# 5. SMART SCHEMA: CONEXÃO COM O DATA WAREHOUSE (DW_REPRESS) COM CACHE DE RECURSO
# ==============================================================================
@st.cache_resource
def iniciar_conexao_banco():
    """Estabelece a conexão SQLAlchemy otimizada com o DW_REPRESS e armazena em cache de recurso."""
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME_DW")
    user = os.getenv("DB_USER_IA")
    password = os.getenv("DB_PASS_IA")

    string_conexao_odbc = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
    )
    
    str_conexao_sqlalchemy = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(string_conexao_odbc)}"
    engine = create_engine(str_conexao_sqlalchemy)
    
    tabelas_vitais = [
        'vw_dClientes', 
        'vw_dProdutos', 
        'vw_DW_Faturamento_Cabecalho',
        'vw_fDevolucao', 
        'vw_fEstoque_Fechamento', 
        'vw_fFaturamento', 
        'vw_fMovimento', 
        'vw_fPedidos'
    ]
    
    # IMPORTANTE: sample_rows_in_table_info=0 desativa o SELECT TOP 3 automático em views cross-database (Evita Erro 916)
    db = SQLDatabase(engine, include_tables=tabelas_vitais, view_support=True, sample_rows_in_table_info=0)
    
    with engine.connect() as conexao_teste:
        pass
        
    return db, engine

try:
    db, engine = iniciar_conexao_banco()
except Exception as e:
    st.error(f"❌ Erro crítico ao conectar no SQL Server: {e}")
    st.stop()

# ==============================================================================
# 6. CONFIGURAÇÃO DA IA E PROMPT DE ENGENHARIA BLINDADO
# ==============================================================================
llm = ChatOllama(
    model="llama3", 
    base_url="http://192.168.2.76:11434", 
    temperature=0 
)

prompt_template_texto = """
Você é um Analista Sênior de BI e especialista em SQL Server.
Sua única e exclusiva tarefa é retornar o código T-SQL puro que responde à pergunta do usuário.

DIRETRIZES OBRIGATÓRIAS:
1. Retorne o código SQL estritamente dentro de um bloco de código markdown (usando ```sql no início e ``` no final). NÃO escreva NENHUMA palavra, cumprimento ou explicação fora desse bloco.
2. NUNCA utilize comandos de modificação (DELETE, UPDATE, DROP, INSERT, ALTER). Faça apenas SELECT.
3. SEGUIDOR DE INSTRUÇÕES SQL CADASTRADAS: Utilize obrigatoriamente a 'Instrução SQL Obrigatória' fornecida nas regras abaixo para estruturar a sua query se houver correspondência com o pedido:
{regras_bi}

Esquema das Tabelas Disponíveis (DW_REPRESS):
{table_info}

Pergunta do Usuário: {input}

Query Final em T-SQL dentro do bloco markdown:
"""

prompt_customizado = PromptTemplate(
    input_variables=["input", "table_info"],
    template=prompt_template_texto
)

# ==============================================================================
# 7. FUNÇÕES DE PROCESSAMENTO, PARSER E FORMATAÇÃO DE DADOS
# ==============================================================================
def extrair_sql_do_markdown(texto_resposta):
    """Extrai o código T-SQL de dentro do bloco markdown gerado pela LLM."""
    padrao_md = re.search(r"```(?:sql)?\s*(SELECT.*?)\s*```", texto_resposta, re.IGNORECASE | re.DOTALL)
    if padrao_md:
        return padrao_md.group(1).strip()
    padrao_select = re.search(r"(SELECT\s+.*)", texto_resposta, re.IGNORECASE | re.DOTALL)
    if padrao_select:
        return padrao_select.group(1).strip()
    return texto_resposta.strip()

def aplicar_regra_deterministica_dinamica(pergunta, sql_gerado):
    """Aplica regras determinísticas por Regex para períodos de tempo e faturamento."""
    pergunta_lower = pergunta.lower()
    meses_dict = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12
    }
    
    match_ultimos_meses = re.search(r"últimos?\s*(\d+)\s*meses", pergunta_lower)
    if "faturamento" in pergunta_lower and match_ultimos_meses:
        qtd_meses = int(match_ultimos_meses.group(1))
        data_atual = datetime.now()
        data_inicio = (data_atual - relativedelta(months=qtd_meses)).replace(day=1)
        data_inicio_str = data_inicio.strftime('%Y-%m-%d')
        
        return f"""
        SELECT 
            FORMAT(Emissao, 'yyyy-MM') AS AnoMes,
            SUM(ValorVenda) AS FaturamentoTotal 
        FROM 
            vw_fMovimento 
        WHERE 
            Emissao >= '{data_inicio_str}' 
            AND Bloqueio <> 'Bloqueio'
        GROUP BY 
            FORMAT(Emissao, 'yyyy-MM')
        ORDER BY 
            AnoMes ASC;
        """

    match_ano = re.search(r"\b(20\d{2})\b", pergunta_lower)
    ano = int(match_ano.group(1)) if match_ano else datetime.now().year
    
    mes_encontrado = None
    for nome_mes, num_mes in meses_dict.items():
        if nome_mes in pergunta_lower:
            mes_encontrado = num_mes
            break
            
    if "faturamento" in pergunta_lower and mes_encontrado:
        primeiro_dia = f"{ano}-{mes_encontrado:02d}-01"
        if mes_encontrado == 12:
            proximo_ano = ano + 1
            proximo_mes = 1
        else:
            proximo_ano = ano
            proximo_mes = mes_encontrado + 1
        proximo_dia = f"{proximo_ano}-{proximo_mes:02d}-01"
        
        return f"""
        SELECT 
            SUM(ValorVenda) AS FaturamentoTotal 
        FROM 
            vw_fMovimento 
        WHERE 
            Emissao >= '{primeiro_dia}' 
            AND Emissao < '{proximo_dia}' 
            AND Bloqueio <> 'Bloqueio';
        """
        
    return sql_gerado

def preparar_dados_grafico(df, coluna_alvo='FaturamentoTotal'):
    """Converte e formata valores decimais do Pyodbc em pontos flutuantes para o Plotly."""
    if coluna_alvo not in df.columns:
        return df
    
    def converter_valor(val):
        if pd.isna(val) or val in ['None', 'nan', '', 'NaT']:
            return 0.0
        if isinstance(val, (int, float, decimal.Decimal)):
            return float(val)
        val_str = str(val).strip()
        if '.' in val_str and ',' in val_str:
            if val_str.rfind(',') > val_str.rfind('.'):
                val_str = val_str.replace('.', '').replace(',', '.')
            else:
                val_str = val_str.replace(',', '')
        elif ',' in val_str and '.' not in val_str:
            val_str = val_str.replace(',', '.')
        try:
            return float(val_str)
        except Exception:
            return 0.0

    df['FatGrafico'] = df[coluna_alvo].apply(converter_valor).astype(float)
    return df

# ==============================================================================
# 8. GERENCIAMENTO DE HISTÓRICO E RENDERIZAÇÃO AO VIVO
# ==============================================================================
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [] 

# Re-renderiza o histórico de chat da sessão
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "df" in msg and msg["df"] is not None:
            colunas_usuario = [c for c in msg["df"].columns if c in ['AnoMes', 'FaturamentoTotal']]
            st.dataframe(msg["df"][colunas_usuario], use_container_width=True, hide_index=True)
            
            df_hist = msg["df"].copy()
            if 'AnoMes' in df_hist.columns and 'FaturamentoTotal' in df_hist.columns:
                df_hist = preparar_dados_grafico(df_hist, 'FaturamentoTotal')
                fig_hist = px.bar(
                    df_hist, 
                    x='AnoMes', 
                    y='FatGrafico', 
                    title="Indicador: Faturamento Total por Ano/Mês",
                    template="plotly_dark",
                    color_discrete_sequence=["#00b4d8"]
                )
                fig_hist.update_yaxes(type='linear', title='Faturamento Total (R$)')
                fig_hist.update_xaxes(title='Ano / Mês')
                st.plotly_chart(fig_hist, use_container_width=True)

pergunta = st.chat_input("Pergunte algo sobre Faturamento, Estoque, Devolução ou Pedidos...")

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Consultando regras corporativas e gerando consulta T-SQL..."):
            try:
                df_dicionario_regras = carregar_regras_do_banco()
                regras_injetadas = buscar_regras_dinamicas(pergunta, df_dicionario_regras)
                esquema_tabelas = db.get_table_info()
                
                prompt_formatado = prompt_customizado.format(
                    input=pergunta,
                    table_info=esquema_tabelas,
                    regras_bi=regras_injetadas
                )
                
                resposta_llm = llm.invoke(prompt_formatado)
                texto_gerado = resposta_llm.content if hasattr(resposta_llm, 'content') else str(resposta_llm)
                
                sql_limpo = extrair_sql_do_markdown(texto_gerado)
                sql_limpo = aplicar_regra_deterministica_dinamica(pergunta, sql_limpo)
                
                if st.session_state.is_admin:
                    st.markdown(f"""
                        <div class="admin-query-box">
                            <b>Visão Administrativa - Código Fonte T-SQL Gerado:</b>
                            <pre><code class="language-sql">{sql_limpo}</code></pre>
                        </div>
                    """, unsafe_allow_html=True)

                df_resultado = pd.read_sql(sql_limpo, engine)

                if not df_resultado.empty:
                    st.success(f"Análise concluída com {len(df_resultado)} registros retornados.")
                    
                    colunas_usuario = [c for c in df_resultado.columns if c in ['AnoMes', 'FaturamentoTotal']]
                    st.dataframe(df_resultado[colunas_usuario], use_container_width=True, hide_index=True)

                    if 'AnoMes' in df_resultado.columns and 'FaturamentoTotal' in df_resultado.columns:
                        df_resultado = preparar_dados_grafico(df_resultado, 'FaturamentoTotal')
                        fig = px.bar(
                            df_resultado, 
                            x='AnoMes', 
                            y='FatGrafico', 
                            title="Indicador: Faturamento Total por Ano/Mês",
                            template="plotly_dark",
                            color_discrete_sequence=["#00b4d8"]
                        )
                        fig.update_yaxes(type='linear', title='Faturamento Total (R$)')
                        fig.update_xaxes(title='Ano / Mês')
                        st.plotly_chart(fig, use_container_width=True)

                    st.session_state.mensagens.append({
                        "role": "assistant", 
                        "content": f"Resultado analítico para: *{pergunta}*", 
                        "df": df_resultado
                    })
                else:
                    st.warning("A consulta foi executada com sucesso, mas não retornou registros para o período/filtro.")
            
            except Exception as err:
                st.error(f"Erro Crítico de Infraestrutura / LLM: {err}")
                st.info("Nota técnica: Verifique o status do serviço Ollama na rede local.")