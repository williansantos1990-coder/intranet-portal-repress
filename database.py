# =====================================================================
# MÓDULO CENTRALIZADO DE CONEXÃO E SUPORTE AO BANCO DE DADOS (database.py)
# =====================================================================

import streamlit as st          
import pyodbc                   
import os                       
from dotenv import load_dotenv  

DIR_PROJETO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DIR_PROJETO, ".env"), override=True)

SERVER = os.getenv("DB_SERVER")
DB_PRINCIPAL = os.getenv("DB_NAME_PRINCIPAL")

DB_DW = os.getenv("DB_NAME_DW")
USER_IA = os.getenv("DB_USER_IA")
PASS_IA = os.getenv("DB_PASS_IA")

# =====================================================================
# CONEXÃO 1: PORTAL GERAL (Utiliza a Autenticação do Windows do Serviço)
# =====================================================================
def obter_conexao_principal():
    """
    Estabelece conexão utilizando Trusted Connection (Autenticação do Windows).
    Como o serviço do Windows roda como REPRESS\assistente.marketing, 
    o acesso ao SQL Server é concedido de forma segura e nativa.
    """
    try:
        string_conexao = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=" + str(SERVER) + ";"
            "DATABASE=" + str(DB_PRINCIPAL) + ";"
            "Trusted_Connection=yes;"
        )
        conn = pyodbc.connect(string_conexao, timeout=5)
        
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin-1')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        return conn
    except Exception as e:
        st.error(f"Erro crítico de conexão com o Banco de Dados Principal: {e}")
        return None

# =====================================================================
# CONEXÃO 2: MODO IA (Acesso Auth/Rules no aplicativos_db)
# =====================================================================
def obter_conexao_ia_aplicativos():
    try:
        string_conexao_auth = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=" + str(SERVER) + ";"
            "DATABASE=" + str(DB_PRINCIPAL) + ";" 
            "UID=" + str(USER_IA) + ";"
            "PWD=" + str(PASS_IA) + ";"
        )
        conn = pyodbc.connect(string_conexao_auth, timeout=5)
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin-1')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        return conn
    except Exception as e:
        return None

# =====================================================================
# CONEXÃO 3: MODO IA (Acesso de Leitura ao DW_REPRESS)
# =====================================================================
def obter_conexao_ia_dw():
    try:
        string_conexao_odbc = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=" + str(SERVER) + ";"
            "DATABASE=" + str(DB_DW) + ";"
            "UID=" + str(USER_IA) + ";"
            "PWD=" + str(PASS_IA) + ";"
        )
        conn = pyodbc.connect(string_conexao_odbc, timeout=5)
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='latin-1')
        conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        return conn
    except Exception as e:
        return None