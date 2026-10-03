# 🏢 Intranet Portal Repress

<p align="center">
  <b>Uma central corporativa robusta desenvolvida em Python para otimização de processos de TI, Compras, RH, Reserva de salas para reuniões e Inteligência de Negócios (BI).</b>
</p>

---

## 📌 Sobre o Projeto
O **Portal Repress** foi arquitetado para centralizar e automatizar operações críticas de uma empresa. O sistema substitui fluxos manuais por uma interface web intuitiva e responsiva, conectada diretamente a um banco de dados relacional corporativo altamente estruturado.

## 🚀 Módulos e Funcionalidades do Portal

1. **📦 Controle de Faltas de Produtos (`1_appCompras.py` / `3_appCustoReposicao.py`):**
   - Gestão de rupturas e normalizações de estoque.
   - Atualização em lote com validações inteligentes.
   - Integração direta com Views e Procedures em SQL Server.

2. **🛒 Solicitações de Vendas (`2_appVendas.py`):**
   - Centralização de pedidos e demandas comerciais.

3. **🤖 BI com Inteligência Artificial (`5_appModoIA.py`):**
   - Consultas inteligentes baseadas em IA utilizando **Llama** e tradução dinâmica para **T-SQL**.
   - Interface conversacional para extração rápida de indicadores corporativos.

4. **✉️ Automação de E-mails (`RoboEmails/`):**
   - Robôs de disparos transacionais automatizados integrados em background.

5. **🛠️ Outros Módulos Integrados:**
   - Help Desk (`4_appHelpDesk.py`), Reserva de Salas (`6_appReservaSalas.py`), Tabela de Canais (`7_appTabCanal.py`) e Mural do RH (`8_appMuralRH.py`).

---

## 🛠️ Tecnologias e Arquitetura

* **Linguagem:** Python
* **Interface Web:** Streamlit
* **Banco de Dados:** SQL Server (`pyodbc`, Stored Procedures, Views otimizadas)
* **IA & LLM:** Llama (processamento de linguagem natural para geração de queries)
* **Manipulação de Dados:** Pandas

---

## ⚙️ Arquitetura de Banco de Dados
O projeto utiliza uma camada de dados robusta e segura:
* **Views Otimizadas:** Consultas desacopladas para alta performance.
* **Stored Procedures:** Procedimentos em T-SQL para controle transacional seguro de inserções e atualizações.