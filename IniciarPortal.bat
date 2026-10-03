@echo off
:: =====================================================================
:: SCRIPT DE INICIALIZAÇÃO DO PORTAL REPRESS (AMBIENTE DE PRODUÇÃO)
:: =====================================================================

:: Define o diretório atual como a raiz do projeto no drive G:
cd /d G:\Sistemas\PortalIntranet

:: Ativa o ambiente virtual Python isolado
call .venv\Scripts\activate

:: Executa o Streamlit apontando para o script principal Main.py
:: --server.port define a porta lógica (8500)
:: --server.address define o IP de escuta (0.0.0.0 libera para toda a rede local)
streamlit run Main.py --server.port 8500 --server.address 0.0.0.0

pause