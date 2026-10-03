@echo off
REM =====================================================================
REM SCRIPT DE EXECUÇÃO AUTOMÁTICA DO ROBÔ DE E-MAILS (PORTAL REPRESS)
REM =====================================================================

REM Redireciona a navegação para o diretório raiz do Portal na nova estrutura
cd /d C:\Sistemas\PortalIntranet

REM Ativa o ambiente virtual Python (.venv) localizado na raiz do projeto
call .venv\Scripts\activate.bat

REM Executa o script Python principal do robô apontando para a pasta interna
python RoboEmails\robo_emails.py

REM Desativa o ambiente virtual e encerra o arquivo de lote com segurança
call deactivate