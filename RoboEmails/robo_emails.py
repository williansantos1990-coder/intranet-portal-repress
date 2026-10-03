# -*- coding: utf-8 -*-
# =====================================================================
# IMPORTAÇÃO DE BIBLIOTECAS E MÓDULOS DE SUPORTE
# =====================================================================
import os                     # Utilitários do sistema operacional para manipulação de caminhos e arquivos
import sys                    # Módulo do sistema para manipular o caminho de importação de diretórios
import pyodbc                 # Biblioteca pyodbc para conexão e execução de queries no SQL Server
import resend                 # SDK oficial da API Resend para disparo seguro de e-mails corporativos
from datetime import datetime # Classe datetime para manipulação e formatação de datas e horários
from dotenv import load_dotenv # Carregador de variáveis de ambiente do arquivo .env

# =====================================================================
# CONFIGURAÇÃO DE DIRETÓRIOS E IMPORTAÇÃO DO DATABASE.PY DA RAIZ
# =====================================================================
# Obtém o caminho absoluto da pasta atual (C:\Sistemas\PortalIntranet\RoboEmails)
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

# Define o caminho da pasta raiz do Portal (C:\Sistemas\PortalIntranet)
DIRETORIO_RAIZ_PORTAL = os.path.abspath(os.path.join(DIRETORIO_ATUAL, ".."))

# Adiciona temporariamente a raiz do portal ao sistema para permitir importar o database.py
if DIRETORIO_RAIZ_PORTAL not in sys.path:
    sys.path.insert(0, DIRETORIO_RAIZ_PORTAL)

# Importa a função centralizada de conexão com o banco de dados principal do arquivo database.py
from database import obter_conexao_principal

# =====================================================================
# CARREGAMENTO DO ARQUIVO .ENV CENTRALIZADO E CONFIGURAÇÃO DA API RESEND
# =====================================================================
# Define o caminho exato do arquivo .env unificado na raiz do PortalIntranet
CAMINHO_ENV_RAIZ = os.path.join(DIRETORIO_RAIZ_PORTAL, ".env")

# Verifica se o arquivo .env existe fisicamente na raiz do portal antes de carregar
if os.path.exists(CAMINHO_ENV_RAIZ):
    # Carrega as variáveis sensíveis do arquivo .env centralizado para a memória
    load_dotenv(dotenv_path=CAMINHO_ENV_RAIZ, override=True)
else:
    # Caso não encontre na raiz, tenta carregar do diretório corrente por segurança
    load_dotenv(override=True)

# Recupera a chave específica de API do Resend para Compras definida no arquivo .env
chave_api_compras = os.getenv("RESEND_API_KEY_Compras", "").strip()

# Atribui a chave recuperada à propriedade global de autenticação da SDK do Resend
resend.api_key = chave_api_compras

# =====================================================================
# FUNÇÃO GENÉRICA DE EXECUÇÃO DE QUERIES SQL (UTILIZANDO DATABASE.PY)
# =====================================================================
def executar_query(query, parametros=None, fetch=False):
    """
    Executa instruções SQL no banco de dados principal utilizando a conexão 
    padronizada do arquivo database.py e retorna resultados caso solicitado.
    """
    try:
        # Chama a função centralizada do database.py para obter a conexão ODBC ativa
        conn = obter_conexao_principal()
        
        # Verifica se a conexão retornou nula (falha de comunicação)
        if not conn:
            print(f"[{datetime.now()}] Erro: Não foi possível estabelecer conexão com o banco de dados.")
            return None
            
        # Cria o cursor para trafegar e executar os comandos SQL na sessão
        cursor = conn.cursor()
        
        # Executa a query injetando parâmetros seguros se eles forem fornecidos
        if parametros:
            cursor.execute(query, parametros)
        else:
            cursor.execute(query)
            
        # Verifica se a instrução solicitada espera retorno de dados (consultas SELECT)
        if fetch:
            # Captura o nome de cada coluna retornada pela consulta do banco
            colunas = [column[0] for column in cursor.description]
            # Cria uma lista vazia para armazenar as linhas tratadas
            resultados = []
            # Percorre cada linha obtida no banco de dados
            for row in cursor.fetchall():
                # Transforma a tupla de dados em um dicionário associando coluna: valor
                resultados.append(dict(zip(colunas, row)))
            # Encerra o cursor e fecha a conexão com o banco de dados
            cursor.close()
            conn.close()
            # Retorna a lista de dicionários contendo os dados
            return resultados
        else:
            # Confirma as alterações na base de dados para comandos de escrita (INSERT, UPDATE)
            conn.commit()
            # Encerra o cursor e fecha a conexão com o banco de dados
            cursor.close()
            conn.close()
            # Retorna True indicando que a operação foi executada com sucesso
            return True
            
    except Exception as e:
        # Registra no console qualquer erro técnico ocorrido durante a execução do SQL
        print(f"[{datetime.now()}] Erro crítico ao executar query no banco de dados: {e}")
        return None

# =====================================================================
# CONSULTAS DE DADOS DE INTELIGÊNCIA DE NEGÓCIO (BI - COMANDOS DO DIA)
# =====================================================================
def buscar_dados_vendas_dia():
    """Consulta as solicitações de compras realizadas ou atualizadas na data de hoje."""
    query = """
        SELECT 
            codigo, 
            descricao, 
            quantidade, 
            status_solicitacao, 
            ISNULL(qtde_atendida, 0) AS qtde_atendida, 
            previsao_chegada,
            data_solicitacao
        FROM [aplicativos_db].[dbo].[solicitacoes_vendas]
        WHERE CAST(data_solicitacao AS DATE) = CAST(GETDATE() AS DATE)
        ORDER BY id DESC
    """
    # Executa a query buscando os dados ou retorna lista vazia caso ocorra falha
    return executar_query(query, fetch=True) or []

def buscar_dados_novas_faltas_dia():
    """Consulta os novos produtos inseridos como falta na tabela registro_faltas hoje."""
    query = """
        SELECT 
            codigo, 
            produto, 
            fabricante, 
            status, 
            data_ruptura,
            comunicado
        FROM [aplicativos_db].[dbo].[registro_faltas]
        WHERE CAST(data_ruptura AS DATE) = CAST(GETDATE() AS DATE)
          AND (UPPER(status) != 'NORMALIZADO' OR status IS NULL)
        ORDER BY id DESC
    """
    return executar_query(query, fetch=True) or []

def buscar_dados_normalizacoes_dia():
    """Consulta os produtos cujas faltas foram normalizadas (retornaram ao estoque) hoje."""
    query = """
        SELECT 
            codigo, 
            produto, 
            fabricante, 
            data_normalizacao, 
            ISNULL(dias_ruptura, 0) AS dias_ruptura
        FROM [aplicativos_db].[dbo].[registro_faltas]
        WHERE CAST(data_normalizacao AS DATE) = CAST(GETDATE() AS DATE)
          AND UPPER(status) = 'NORMALIZADO'
        ORDER BY id DESC
    """
    return executar_query(query, fetch=True) or []

def buscar_total_faltas_ativas():
    """Calcula a contagem acumulada de todos os produtos que continuam em falta na empresa."""
    query = """
        SELECT COUNT(*) AS total 
        FROM [aplicativos_db].[dbo].[registro_faltas] 
        WHERE UPPER(status) != 'NORMALIZADO' OR status IS NULL
    """
    res = executar_query(query, fetch=True)
    return res[0]['total'] if res else 0

# =====================================================================
# FILTRAGEM RIGOROSA DE DESTINATÁRIOS (REGRA DE PERMISSÃO DE APPS)
# =====================================================================
def buscar_destinatarios():
    """
    Consulta a tabela [auth].[Usuarios] e filtra apenas os usuários ativos que:
    1. Possuem nível igual a 'admin', OU
    2. Possuem nível igual a 'usuario' E contêm liberação para '1_appCompras' ou '2_appVendas' na coluna [acessos].
    """
    # Query SQL para buscar os dados de cadastro de todos os usuários do portal
    query = "SELECT nome, email, nivel, acessos FROM [auth].[Usuarios] WHERE ativo = 1"
    
    # Executa a consulta no banco de dados
    resultados = executar_query(query, fetch=True)
    
    # Lista auxiliar para armazenar os usuários validados pelas regras
    destinatarios_validados = []
    
    # Valida se a consulta retornou registros válidos
    if resultados:
        # Itera sobre cada cadastro de usuário retornado da base
        for usuario in resultados:
            # Captura o nível do usuário, converte para minúsculas e remove espaços vazios
            nivel = str(usuario.get('nivel', '')).strip().lower()
            
            # Captura a string de aplicativos liberados armazenados na coluna acessos do banco
            acessos_db = str(usuario.get('acessos', ''))
            
            # Divide os acessos separados por vírgula em uma lista limpa de strings
            lista_acessos = [app.strip() for app in acessos_db.split(',')]
            
            # -> REGRA 1: Administradores recebem o e-mail obrigatoriamente
            if nivel == 'admin':
                destinatarios_validados.append(usuario)
                
            # -> REGRA 2: Usuários comuns precisam ter acesso explícito a compras ou vendas
            elif nivel == 'usuario':
                # Verifica se '1_appCompras' ou '2_appVendas' está presente na lista de acessos do usuário
                if '1_appCompras' in lista_acessos or '2_appVendas' in lista_acessos:
                    destinatarios_validados.append(usuario)
                    
    # Retorna a lista filtrada contendo exclusivamente os destinatários autorizados
    return destinatarios_validados

# =====================================================================
# MONTAGEM DO MODELO DE E-MAIL EM HTML (RELATÓRIO EXECUTIVO)
# =====================================================================
def montar_corpo_email_inteligente(nome_usuario, solicitacoes, novas_faltas, normalizacoes, total_faltas_ativas):
    """Monta o código HTML estruturado com KPIs visuais, tabelas formatadas e identidade visual do Portal."""
    data_hoje_str = datetime.now().strftime("%d/%m/%Y")
    total_solic_hoje = len(solicitacoes)
    total_atendidas = sum(1 for s in solicitacoes if str(s.get('status_solicitacao', '')).strip().upper() in ['ATENDIDO', 'ATENDIDO PARCIAL'])
    total_novas_faltas = len(novas_faltas)
    total_normalizados = len(normalizacoes)

    # -----------------------------------------------------------------
    # CONSTRUÇÃO DA TABELA 1: SOLICITAÇÕES DE COMPRAS DO DIA
    # -----------------------------------------------------------------
    if solicitacoes:
        html_tabela_solic = """
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px;">
            <thead>
                <tr style="background-color: #164265; color: #ffffff; text-align: left;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Código</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Descrição do Produto</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Qtd. Solic.</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Status Compras</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Qtd. Atendida</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Prev. Chegada</th>
                </tr>
            </thead>
            <tbody>
        """
        for item in solicitacoes:
            st_raw = str(item.get('status_solicitacao', 'PENDENTE')).strip().upper()
            if st_raw == 'ATENDIDO':
                badge_status = '<span style="background-color: #28a745; color: white; padding: 3px 7px; border-radius: 4px; font-weight: bold; font-size: 11px;">ATENDIDO</span>'
            elif st_raw == 'ATENDIDO PARCIAL':
                badge_status = '<span style="background-color: #ffc107; color: #333; padding: 3px 7px; border-radius: 4px; font-weight: bold; font-size: 11px;">PARCIAL</span>'
            else:
                badge_status = '<span style="background-color: #6c757d; color: white; padding: 3px 7px; border-radius: 4px; font-weight: bold; font-size: 11px;">PENDENTE</span>'

            dt_prev = item.get('previsao_chegada')
            dt_prev_str = dt_prev.strftime("%d/%m/%Y") if dt_prev and hasattr(dt_prev, 'strftime') else (str(dt_prev) if dt_prev else "-")

            html_tabela_solic += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{item.get('codigo', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{item.get('descricao', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{int(item.get('quantidade', 0))}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{badge_status}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; color: #28a745; font-weight: bold;">{int(item.get('qtde_atendida', 0))}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{dt_prev_str}</td>
                </tr>
            """
        html_tabela_solic += "</tbody></table>"
    else:
        html_tabela_solic = "<p style='color: #666; font-style: italic; background-color: #f9f9f9; padding: 10px; border-radius: 4px;'>Nenhuma nova solicitação de compra foi registrada na data de hoje.</p>"

    # -----------------------------------------------------------------
    # CONSTRUÇÃO DA TABELA 2: NOVAS RUPTURAS DO DIA
    # -----------------------------------------------------------------
    if novas_faltas:
        html_tabela_novas_faltas = """
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px;">
            <thead>
                <tr style="background-color: #d9534f; color: #ffffff; text-align: left;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Código</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Produto em Falta</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Fabricante</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Status</th>
                </tr>
            </thead>
            <tbody>
        """
        for falta in novas_faltas:
            html_tabela_novas_faltas += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #d9534f;">{falta.get('codigo', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{falta.get('produto', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{falta.get('fabricante', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><span style="background-color: #f8d7da; color: #721c24; padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">RUPTURA</span></td>
                </tr>
            """
        html_tabela_novas_faltas += "</tbody></table>"
    else:
        html_tabela_novas_faltas = "<p style='color: #28a745; font-style: italic; background-color: #eafaf1; padding: 10px; border-radius: 4px;'>Excelente! Nenhum novo produto entrou em falta na data de hoje.</p>"

    # -----------------------------------------------------------------
    # CONSTRUÇÃO DA TABELA 3: PRODUTOS NORMALIZADOS DO DIA
    # -----------------------------------------------------------------
    if normalizacoes:
        html_tabela_norm = """
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px;">
            <thead>
                <tr style="background-color: #28a745; color: #ffffff; text-align: left;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Código</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Produto Normalizado</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Fabricante</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Dias em Ruptura</th>
                </tr>
            </thead>
            <tbody>
        """
        for norm in normalizacoes:
            html_tabela_norm += f"""
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #28a745;">{norm.get('codigo', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{norm.get('produto', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{norm.get('fabricante', '')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold; color: #164265;">{int(norm.get('dias_ruptura', 0))} dia(s)</td>
                </tr>
            """
        html_tabela_norm += "</tbody></table>"
    else:
        html_tabela_norm = "<p style='color: #666; font-style: italic; background-color: #f9f9f9; padding: 10px; border-radius: 4px;'>Nenhuma normalização de produto foi concluída na data de hoje.</p>"

    # -----------------------------------------------------------------
    # ESTRUTURA GERAL DO DOCUMENTO HTML DO E-MAIL
    # -----------------------------------------------------------------
    html_final = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, Helvetica, sans-serif; color: #333333; background-color: #f4f6f9; margin: 0; padding: 20px;">
        <div style="max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-top: 5px solid #164265;">
            
            <div style="text-align: center; border-bottom: 2px solid #eef2f5; padding-bottom: 15px; margin-bottom: 20px;">
                <h2 style="color: #164265; margin: 0; font-size: 22px;">📊 Resumo Executivo - Boletim de Inteligência Diário</h2>
                <p style="color: #666666; margin: 5px 0 0 0; font-size: 13px;">Consolidado de atividades dos aplicativos - <b>{data_hoje_str}</b></p>
            </div>

            <p style="font-size: 15px;">Olá, <b>{nome_usuario}</b>!</p>
            <p style="font-size: 14px; color: #555;">Confira abaixo o balanço dos produtos solicitados, respostas do setor de compras e atualizações do controle de faltas referente ao dia de hoje:</p>

            <div style="background-color: #eef7ff; border-left: 4px solid #0056b3; padding: 14px 16px; margin: 18px 0; border-radius: 4px; color: #004085;">
                <p style="margin: 0; font-size: 13px; line-height: 1.5;">
                    💡 Para consultar o histórico completo dos produtos, verificar prazos em tempo real ou realizar novas solicitações, acesse diretamente o <b>Portal Intranet Repress</b>. 
                </p>
            </div>

            <table style="width: 100%; margin: 20px 0; border-spacing: 10px; border-collapse: separate;">
                <tr>
                    <td style="background-color: #eef5fc; border-left: 4px solid #164265; padding: 12px; border-radius: 4px; text-align: center; width: 25%;">
                        <span style="font-size: 20px; font-weight: bold; color: #164265;">{total_solic_hoje}</span><br>
                        <span style="font-size: 11px; color: #555; text-transform: uppercase; font-weight: bold;">Solicitações Hoje</span>
                    </td>
                    <td style="background-color: #eafaf1; border-left: 4px solid #28a745; padding: 12px; border-radius: 4px; text-align: center; width: 25%;">
                        <span style="font-size: 20px; font-weight: bold; color: #28a745;">{total_atendidas}</span><br>
                        <span style="font-size: 11px; color: #555; text-transform: uppercase; font-weight: bold;">Atendidas Compras</span>
                    </td>
                    <td style="background-color: #fdf2f2; border-left: 4px solid #d9534f; padding: 12px; border-radius: 4px; text-align: center; width: 25%;">
                        <span style="font-size: 20px; font-weight: bold; color: #d9534f;">{total_novas_faltas}</span><br>
                        <span style="font-size: 11px; color: #555; text-transform: uppercase; font-weight: bold;">Novas Rupturas</span>
                    </td>
                    <td style="background-color: #fff8e6; border-left: 4px solid #ffc107; padding: 12px; border-radius: 4px; text-align: center; width: 25%;">
                        <span style="font-size: 20px; font-weight: bold; color: #b78103;">{total_faltas_ativas}</span><br>
                        <span style="font-size: 11px; color: #555; text-transform: uppercase; font-weight: bold;">Total Faltas Ativas</span>
                    </td>
                </tr>
            </table>

            <div style="margin-top: 25px;">
                <h3 style="color: #164265; border-bottom: 1px solid #ddd; padding-bottom: 5px; font-size: 16px;">
                    🛒 1. Produtos Solicitados & Resposta de Compras (Hoje)
                </h3>
                {html_tabela_solic}
            </div>

            <div style="margin-top: 25px;">
                <h3 style="color: #d9534f; border-bottom: 1px solid #ddd; padding-bottom: 5px; font-size: 16px;">
                    🚨 2. Novas Rupturas / Faltas Registradas no Dia
                </h3>
                {html_tabela_novas_faltas}
            </div>

            <div style="margin-top: 25px;">
                <h3 style="color: #28a745; border-bottom: 1px solid #ddd; padding-bottom: 5px; font-size: 16px;">
                    ✅ 3. Produtos Normalizados Hoje (Retorno de Estoque)
                </h3>
                {html_tabela_norm}
            </div>

            <div style="margin-top: 35px; border-top: 1px solid #eeeeee; padding-top: 15px; text-align: center; font-size: 12px; color: #888888;">
                <p style="margin: 0;">Este é um e-mail automático para <b>Controle de Faltas Repress</b>.</p>
                <p style="margin: 5px 0 0 0;">Acesse e gerencie suas demandas em tempo real no <b>Portal Intranet Repress</b>.</p>
            </div>

        </div>
    </body>
    </html>
    """
    return html_final

# =====================================================================
# FUNÇÃO DE DISPARO DE E-MAIL VIA API DO RESEND
# =====================================================================
def enviar_email(destinatario_email, destinatario_nome, html_conteudo):
    """Realiza a chamada HTTP para a API do Resend efetuando o envio da mensagem."""
    try:
        # Monta o dicionário de parâmetros estruturados exigido pela biblioteca Resend
        params = {
            "from": "Portal Repress <nao-responda@compras.repress.com.br>",
            "to": [destinatario_email],
            "subject": f"📊 Relatorio Automatico - Controle de Faltas Repress ({datetime.now().strftime('%d/%m/%Y')})",
            "html": html_conteudo,
        }
        
        # Dispara o envio do e-mail através da API
        resend.Emails.send(params)
        print(f"[{datetime.now()}] E-mail enviado com sucesso para: {destinatario_email}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] Erro ao enviar e-mail para {destinatario_email}: {e}")
        return False

# =====================================================================
# ROTINA PRINCIPAL DE COORDENAÇÃO DO ROBÔ
# =====================================================================
def executar_rotina():
    """Coordena sequencialmente a extração de dados, filtragem e envio dos e-mails."""
    print(f"[{datetime.now()}] Iniciando a rotina de extração de dados e disparos...")
    
    # Valida se a chave de API foi carregada corretamente do .env da raiz
    if not chave_api_compras:
        print(f"[{datetime.now()}] ERRO CRÍTICO: A chave RESEND_API_KEY_Compras não foi encontrada no arquivo .env da raiz.")
        return

    # Extrai os dados consolidados do banco de dados principal
    solicitacoes_hoje = buscar_dados_vendas_dia()
    novas_faltas_hoje = buscar_dados_novas_faltas_dia()
    normalizacoes_hoje = buscar_dados_normalizacoes_dia()
    total_faltas_ativas = buscar_total_faltas_ativas()

    # Busca a lista de destinatários aplicando as regras de nível e permissão de aplicativos
    destinatarios = buscar_destinatarios()
    
    if not destinatarios:
        print(f"[{datetime.now()}] Nenhum destinatário elegível encontrado. Processo encerrado.")
        return

    # Realiza o envio iterativo para cada usuário autorizado
    for pessoa in destinatarios:
        nome = pessoa['nome']
        email = pessoa['email']
        
        # Monta o HTML customizado com o nome do usuário atual
        corpo_html = montar_corpo_email_inteligente(
            nome_usuario=nome,
            solicitacoes=solicitacoes_hoje,
            novas_faltas=novas_faltas_hoje,
            normalizacoes=normalizacoes_hoje,
            total_faltas_ativas=total_faltas_ativas
        )
        
        # Dispara o e-mail individual
        enviar_email(email, nome, corpo_html)
        
    print(f"[{datetime.now()}] Rotina de e-mails executada com sucesso.")

# =====================================================================
# PONTO DE ENTRADA DO SCRIPT PYTHON
# =====================================================================
if __name__ == "__main__":
    executar_rotina()