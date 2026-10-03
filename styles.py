# =====================================================================
# MÓDULO CENTRALIZADO DE ESTILIZAÇÃO DO PORTAL REPRESS (styles.py)
# =====================================================================

import streamlit as st        # Importa a biblioteca Streamlit para manipulação de componentes visuais e injeção de HTML/CSS

def injetar_estilo_global():
    """Função responsável por injetar a folha de estilos CSS global em todas as páginas do Portal Repress."""
    estilo_css_oficial = """
    <style>
        /* ========================================================= */
        /* 1. SUPORTE A MODO CLARO E ESCURO NATIVO                    */
        /* ========================================================= */
        @media (prefers-color-scheme: light) { :root { color-scheme: light; } } 
        @media (prefers-color-scheme: dark) { :root { color-scheme: dark; } }   
        
        /* ========================================================= */
        /* 2. REMOÇÃO DE ESPAÇOS E OTIMIZAÇÃO DO TOPO (SLIM HEADER)   */
        /* ========================================================= */
        [data-testid="stSidebar"] { display: none !important; }         
        [data-testid="stHeader"] { display: none !important; }          
        .stApp { background-color: #F4F7FA; }                           
        
        [data-testid="stAppViewBlockContainer"] { 
            padding-top: 0.3rem !important;                             
            padding-bottom: 1.5rem !important;                          
            max-width: 98% !important;                                  
        }
        
        .block-container { 
            padding-top: 0.3rem !important;                             
        }
        
        /* ========================================================= */
        /* 3. PADRONIZAÇÃO TIPOGRÁFICA REFINADA (PADRÃO WEB MODERNO)  */
        /* ========================================================= */
        h1, .stMarkdown h1, [data-testid="stMarkdownContainer"] h1 {
            font-size: 22px !important;        
            font-weight: 600 !important;       
            font-family: 'Segoe UI', Roboto, sans-serif !important; 
            margin-top: 0px !important;
            margin-bottom: 8px !important;
            letter-spacing: -0.3px !important;
        }

        h3 { 
            font-size: 1rem !important; 
            font-weight: 600 !important; 
            margin-bottom: 0.3rem !important; 
            letter-spacing: -0.2px !important;
        }

        h5, .card-widget-repress h5 { 
            font-size: 14px !important; 
            font-weight: 600 !important; 
            margin-bottom: 0px !important;
            letter-spacing: -0.2px !important;
        }

        /* ========================================================= */
        /* 4. SAUDAÇÃO ADAPTATIVA                                    */
        /* ========================================================= */
        .saudacao-texto {
            font-size: 13px !important;
            font-weight: 600 !important;
            color: #002B50 !important;
            letter-spacing: -0.1px !important;
        }

        /* ========================================================= */
        /* 5. DESIGN SYSTEM NATIVO DE BOTÕES GERAIS                  */
        /* ========================================================= */
        div.stButton > button, div.stFormSubmitButton > button, 
        button[data-testid="stBaseButton-secondary"], 
        button[data-testid="stBaseButton-primary"], 
        button[data-testid="stFormSubmitButton-button"] {
            border-radius: 8px !important;
            font-weight: 600 !important;
            font-size: 13px !important;
            transition: all 0.2s ease-in-out !important;
            background-color: #002B50 !important; 
            color: #FFFFFF !important; 
            border: 1px solid #003B70 !important; 
            box-shadow: 0 2px 5px rgba(0, 43, 80, 0.25) !important;
        } 

        div.stButton > button:hover, div.stFormSubmitButton > button:hover, 
        button[data-testid="stBaseButton-secondary"]:hover, 
        button[data-testid="stBaseButton-primary"]:hover { 
            background-color: #003B70 !important; 
            border-color: #004C8C !important;
            color: #FFFFFF !important;
            transform: translateY(-1px) !important;                   
        } 

        /* ========================================================= */
        /* 6. FAIXA SUPERIOR EM HTML5 E CSS FLEXBOX                  */
        /* ========================================================= */
        .acoes-topo-repress-html {
            display: flex !important;
            justify-content: flex-end !important;
            align-items: center !important;
            gap: 6px !important;
            width: 100% !important;
            height: 100% !important;
            padding-top: 6px !important;
        }

        .btn-topo-html {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            background-color: transparent !important;
            color: #003B70 !important;
            font-family: 'Segoe UI', Roboto, sans-serif !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            padding: 5px 12px !important;
            border-radius: 6px !important;
            text-decoration: none !important;
            border: none !important;
            white-space: nowrap !important;
            transition: all 0.2s ease-in-out !important;
        }
        
        .btn-topo-html:hover {
            background-color: rgba(0, 43, 80, 0.08) !important;
            color: #002B50 !important;
        }

        /* ========================================================= */
        /* 7. POSICIONAMENTO DO MODAL NO TOPO E SCROLL INTERNO       */
        /* ========================================================= */
        [data-testid="stModal"] {
            font-family: 'Segoe UI', Roboto, sans-serif !important;
            display: flex !important;
            justify-content: center !important;
            align-items: flex-start !important;
            padding-top: 10px !important;
        }

        [data-testid="stModal"] > div, 
        div[role="dialog"] {
            margin-top: 0px !important;
            margin-bottom: auto !important;
            max-height: 94vh !important;
            overflow-y: auto !important;
        }
        
        [data-testid="stModal"] h2 {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: #1F2937 !important;
        }

        /* ========================================================= */
        /* 8. FLEXIBILIZAÇÃO DE COLUNAS GERAIS                       */
        /* ========================================================= */
        [data-testid="column"] { display: flex !important; align-items: stretch !important; } 
        [data-testid="column"] > div { width: 100% !important; display: flex !important; flex-direction: column !important; }
        [data-testid="column"] > div > [data-testid="stVerticalBlock"] { flex-grow: 1 !important; display: flex !important; flex-direction: column !important; }
        [data-testid="column"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] { flex-grow: 1 !important; display: flex !important; flex-direction: column !important; }

        /* ========================================================= */
        /* 9. COMPONENTE POPOVER "MEU PERFIL" E AVATAR               */
        /* ========================================================= */
        [data-testid="stPopover"] {
            margin-top: -12px !important;
        }
        [data-testid="stPopover"] button {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #002B50 !important;
            font-weight: 600 !important;
            font-size: 13px !important;
        }
        
        .img-perfil-header { 
            width: 32px !important; 
            height: 32px !important; 
            min-width: 32px !important; 
            min-height: 32px !important; 
            border-radius: 50% !important; 
            object-fit: cover !important; 
            border: 2px solid #002B50 !important; 
            display: block !important; 
            margin-top: 4px !important; 
        }

        /* ========================================================= */
        /* 10. CARDS E WIDGETS                                       */
        /* ========================================================= */
        .card-widget-repress { 
            background-color: #FFFFFF; 
            border-radius: 8px; 
            padding: 12px 16px; 
            border: 1px solid #E2E8F0; 
            margin-bottom: 10px; 
        }
        .sub-title { color: #6B7280; font-size: 0.85rem; margin-bottom: 12px; } 

        /* ========================================================= */
        /* 11. DARK MODE (AJUSTES DE CORES CONTRA O SANGRAMENTO)     */
        /* ========================================================= */
        @media (prefers-color-scheme: dark) {
            :root { color-scheme: dark; } 
            
            .stApp { background-color: #121212 !important; } 
            
            /* Títulos e Cabeçalhos com branco suave (#F8F9FA) para evitar alto contraste ofuscante */
            h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { 
                color: #F8F9FA !important; 
            } 
            
            /* Textos correntes principais com cinza claro elegante (#E4E6EB) */
            p, span, label, .stMarkdown p, div[data-testid="stMarkdownContainer"] {
                color: #E4E6EB !important;
            }

            /* Textos secundários, legendas e subtítulos com cinza médio (#B0B3B8) */
            small, .sub-title, [data-testid="stCaptionContainer"] {
                color: #B0B3B8 !important;
            }

            input::placeholder, textarea::placeholder {
                color: #707070 !important;
            }
            
            hr { border-color: #333333 !important; } 
            
            .saudacao-texto { color: #F8F9FA !important; }
            
            [data-testid="stPopover"] button { 
                color: #F8F9FA !important; 
                background-color: transparent !important; 
                border: none !important; 
                box-shadow: none !important; 
            }
            
            .img-perfil-header { 
                border: 2px solid #003B70 !important; 
                background-color: #1E3A5F !important; 
                color: #FFFFFF !important; 
            }
            
            div[data-baseweb="input"], 
            div[data-baseweb="base-input"],
            div[data-baseweb="select"] > div {
                background-color: #1A1D24 !important;
                border-color: #1A1D24 !important;
                border: 1px solid #1A1D24 !important;
                color: #E4E6EB !important;
                font-size: 13px !important;
                box-shadow: none !important;
            }
            
            div[data-baseweb="input"]:hover, 
            div[data-baseweb="input"]:focus-within, 
            div[data-baseweb="base-input"]:hover,
            div[data-baseweb="base-input"]:focus-within,
            div[data-baseweb="select"] > div:hover,
            div[data-baseweb="select"] > div:focus-within {
                border-color: #1A1D24 !important;
                box-shadow: none !important;
            }
            
            .btn-topo-html {
                color: #E4E6EB !important;
                background-color: transparent !important;
                border: none !important;
            }
            
            .btn-topo-html:hover {
                background-color: rgba(255, 255, 255, 0.08) !important;
                color: #FFFFFF !important;
            }

            .ql-toolbar.ql-snow {
                background-color: #1A1D24 !important;
                border-color: #1A1D24 !important;
            }
            .ql-container.ql-snow {
                background-color: #1E222B !important;
                border-color: #1A1D24 !important;
                color: #E4E6EB !important;
            }
            .ql-editor {
                color: #E4E6EB !important;
                font-size: 13px !important;
            }
            .ql-snow .ql-stroke { stroke: #E4E6EB !important; }
            .ql-snow .ql-fill { fill: #E4E6EB !important; }
            .ql-snow .ql-picker { color: #E4E6EB !important; }
            
            span[data-baseweb="tag"], div[data-baseweb="tag"], [data-baseweb="tag"] span {
                color: #FFFFFF !important;
            }
            
            [data-testid="stInfo"] {
                background-color: #1A2634 !important;
                border: 1px solid #28384E !important;
                color: #FFFFFF !important;
                font-size: 13px !important;
            }
            [data-testid="stInfo"] * {
                color: #FFFFFF !important;
            }
            
            .card-widget-repress {
                background-color: #1E1E1E !important; 
                border: 1px solid #333333 !important; 
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3) !important; 
            }
            .card-widget-repress h5 { color: #F8F9FA !important; } 
            
            [data-testid="stContainer"], [data-testid="stVerticalBlock"] > div[data-testid="stExpander"] {
                background-color: #181818 !important; 
                border-color: #2A2A2A !important; 
            }
        }
    </style>
    """
    st.markdown(estilo_css_oficial, unsafe_allow_html=True)