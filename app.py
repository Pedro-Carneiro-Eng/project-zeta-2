import streamlit as st
import pandas as pd
from database import SessionLocal, init_db
import services
import report_builder

st.set_page_config(page_title="Project Zeta", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

init_db()

if 'projeto_ativo_id' not in st.session_state:
    st.session_state.projeto_ativo_id = None

db = SessionLocal()

st.title("Project Zeta - Dashboard")

aba1, aba2, aba3, aba4 = st.tabs(["1. Projetos", "2. Topologia", "3. Análise e Laudo", "4. Memorial de Cálculo"])

with aba1:
    col_lista, col_novo = st.columns(2)
    
    with col_lista:
        st.subheader("Projetos Cadastrados")
        projetos = db.query(services.models.Projeto).all()
        if projetos:
            opcoes = {f"[{p.id}] {p.nome_projeto}": p.id for p in projetos}
            selecao = st.selectbox("Selecione um projeto para trabalhar:", list(opcoes.keys()))
            if st.button("Carregar Projeto Selecionado", use_container_width=True):
                st.session_state.projeto_ativo_id = opcoes[selecao]
                st.success("Projeto ativo alterado.")
                st.rerun()
        else:
            st.info("Nenhum projeto encontrado. Cadastre um novo.")
            
    with col_novo:
        st.subheader("Criar Novo Projeto")
        with st.form("form_projeto"):
            nome_proj = st.text_input("Nome do Projeto / Cliente")
            v_sec = st.number_input("Tensão Secundária (V)", value=220.0)
            trafo = st.number_input("Potência Trafo (kVA)", value=152.5)
            if st.form_submit_button("Salvar Novo Projeto", use_container_width=True):
                cli = services.criar_cliente(db, nome=nome_proj)
                novo_p = services.criar_projeto(db, cliente_id=cli.id, nome_projeto=nome_proj, v_secundaria=v_sec, trafo_kva=trafo)
                st.session_state.projeto_ativo_id = novo_p.id
                st.success(f"Projeto '{nome_proj}' criado com sucesso.")
                st.rerun()

    if st.session_state.projeto_ativo_id:
        st.divider()
        st.subheader("Propriedades do Projeto Ativo")
        p_edit = db.query(services.models.Projeto).filter(services.models.Projeto.id == st.session_state.projeto_ativo_id).first()
        
        if p_edit:
            with st.form("form_edit_projeto"):
                c1, c2, c3 = st.columns(3)
                edit_nome = c1.text_input("Nome do Projeto", value=p_edit.nome_projeto)
                edit_v_sec = c2.number_input("Tensão Secundária (V)", value=float(p_edit.tensao_secundaria))
                edit_trafo = c3.number_input("Potência Trafo (kVA)", value=float(p_edit.potencia_transformador))
                
                b_salvar_proj, b_excluir_proj = st.columns(2)
                
                if b_salvar_proj.form_submit_button("Salvar Alterações do Projeto", type="primary", use_container_width=True):
                    p_edit.nome_projeto = edit_nome
                    p_edit.tensao_secundaria = edit_v_sec
                    p_edit.potencia_transformador = edit_trafo
                    db.commit()
                    st.success("Configurações atualizadas com sucesso.")
                    st.rerun()
                    
                if b_excluir_proj.form_submit_button("Excluir Projeto Definitivamente", use_container_width=True):
                    db.delete(p_edit)
                    db.commit()
                    st.session_state.projeto_ativo_id = None
                    st.success("Projeto excluído com sucesso.")
                    st.rerun()

if st.session_state.projeto_ativo_id:
    projeto_atual = db.query(services.models.Projeto).filter(services.models.Projeto.id == st.session_state.projeto_ativo_id).first()
    
    st.sidebar.success(f"Projeto Ativo:\n{projeto_atual.nome_projeto}")
    st.sidebar.info(
        f"Trafo Equivalente: {projeto_atual.potencia_transformador} kVA\n\n"
        f"Tensão Secundária: {projeto_atual.tensao_secundaria} V"
    )

    st.sidebar.divider()
    st.sidebar.subheader("Parâmetros do Motor Zeta")
    perfil_carga = st.sidebar.radio(
        "Perfil de Carga e Aquecimento:",
        options=["Industrial / Contínuo (Pior Caso)", "Residencial / Intermitente (Abrandado)"],
        index=1
    )

    with aba2:
        st.subheader("Topologia Elétrica")
        
        quadros_disponiveis = db.query(services.models.Quadro).filter(services.models.Quadro.projeto_id == projeto_atual.id).all()
        circuitos_totais = services.listar_circuitos_do_projeto(db, projeto_atual.id)
        
        with st.container(border=True):
            st.markdown("#### Explorador Topológico")
            if not quadros_disponiveis:
                st.info("A rede está vazia. Comece adicionando um Ponto/Quadro abaixo.")
            else:
                import streamlit.components.v1 as components
                
                def build_tree_html(pai_id):
                    filhos = sorted([q for q in quadros_disponiveis if q.quadro_pai_id == pai_id], key=lambda x: x.nome)
                    circs = sorted([c for c in circuitos_totais if c.quadro_id == pai_id], key=lambda x: x.nome) if pai_id else []
                    
                    html_snippet = ""
                    for q in filhos:
                        html_snippet += f"""
                        <details open>
                            <summary>
                                <span class="arrow">▶</span>
                                <span class="icon">[Q]</span> <span class="title">{q.nome}</span>
                                <span class="badge">{q.tipo}</span>
                            </summary>
                            {build_tree_html(q.id)}
                        </details>
                        """
                    
                    for c in circs:
                        icone = "[T]" if c.tipo == "TERMINAL" else "[A]"
                        html_snippet += f"""
                        <div class="circuit-item">
                            <span class="tree-line">└─</span>
                            <span class="icon">{icone}</span> <span class="title-circ">{c.nome}</span>
                            <span class="badge">{c.in_disj:g}A • {c.bitola_mm2:g}mm²</span>
                        </div>
                        """
                    return html_snippet

                html_code = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 10px 20px; color: #212529; background-color: transparent; }}
                        @media (prefers-color-scheme: dark) {{
                            body {{ color: #f8f9fa; }}
                            details {{ border-left: 1px solid #495057 !important; }}
                            .badge {{ background-color: #343a40 !important; color: #adb5bd !important; border: 1px solid #495057; }}
                            .circuit-item {{ color: #ced4da !important; }}
                            .tree-line {{ color: #495057 !important; }}
                            .title {{ color: #63b3ed !important; }}
                        }}
                        details {{ margin-left: 20px; border-left: 1px solid #dee2e6; padding-left: 15px; margin-bottom: 5px; }}
                        details.root {{ border-left: none; margin-left: 0; padding-left: 0; }}
                        summary {{ cursor: pointer; list-style: none; font-size: 15px; padding: 8px 0; display: flex; align-items: center; user-select: none; transition: 0.2s; }}
                        summary::-webkit-details-marker {{ display: none; }}
                        summary:hover {{ opacity: 0.7; }}
                        .arrow {{ font-size: 11px; margin-right: 10px; transition: transform 0.2s; display: inline-block; color: #7f8c8d; }}
                        details[open] > summary > .arrow {{ transform: rotate(90deg); }}
                        .title {{ font-weight: 600; color: #2980b9; letter-spacing: 0.3px; }}
                        .title-circ {{ font-weight: 500; }}
                        .badge {{ font-size: 11px; background-color: #f1f3f5; padding: 3px 10px; border-radius: 12px; margin-left: 12px; color: #6c757d; font-weight: 600; letter-spacing: 0.5px; border: 1px solid #e9ecef; }}
                        .circuit-item {{ margin-left: 20px; padding: 6px 0; font-size: 14px; color: #495057; display: flex; align-items: center; }}
                        .tree-line {{ margin-right: 12px; color: #adb5bd; font-family: monospace; font-size: 16px; }}
                        .icon {{ margin-right: 8px; font-size: 13px; font-weight: bold; color: #7f8c8d; }}
                    </style>
                </head>
                <body>
                    <details class="root" open>
                        <summary>
                            <span class="arrow">▶</span>
                            <span class="icon" style="color: #c0392b !important;">[F]</span> <span class="title" style="color: #c0392b !important;">REDE CEMIG / TRAFO</span>
                            <span class="badge">FONTE</span>
                        </summary>
                        {build_tree_html(None)}
                    </details>
                </body>
                </html>
                """
                
                components.html(html_code, height=450, scrolling=True)

        col_esquerda, col_direita = st.columns(2)
        
        with col_esquerda:
            with st.container(border=True):
                st.markdown("##### Módulo: Inclusão de Novo Ponto / Quadro")
                with st.form("form_add_ponto_v4", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nome_q = c1.text_input("Identificação")
                    tipo_q = c2.selectbox("Tipo de Elemento", ["POSTE", "CAIXA ZC/ZB", "MEDIDOR", "QGBT", "QDC", "CM"])
                    
                    local_q = st.text_input("Localização Física")
                    
                    opcoes_pai = {"[Origem do Projeto / Rede Externa]": None}
                    for q in quadros_disponiveis: opcoes_pai[q.nome] = q.id
                    pai_q = st.selectbox("Alimentado por (Ponto de Origem):", list(opcoes_pai.keys()), key="add_pai_v4")
                    
                    st.caption("Dados do Cabo Alimentador e Proteção Geral:")
                    colA, colB, colC = st.columns(3)
                    comp_alim = colA.number_input("Distância (m)", value=0.0, key="add_dist_v4")
                    fases_alim = colB.selectbox("Fases", ["TRIFASICO", "F-N", "F-F"], key="add_fases_v4")
                    iso_alim = colC.selectbox("Isolação", ["HEPR", "PVC", "BARRAMENTO"], key="add_iso_v4")
                    
                    ib_alim = st.number_input("Corrente de Projeto Ib (A)", value=0.0, key="add_ib_v4")

                    colD, colE, colF, col_N = st.columns(4)
                    bit_alim = colD.number_input("Fase (mm² / A nominal)", value=0.0, key="add_bf_v4")
                    bit_n_alim = colE.number_input("Neutro (mm²)", value=0.0, key="add_bn_v4")
                    bit_pe_alim = colF.number_input("PE (mm²)", value=0.0, key="add_bpe_v4")
                    n_cabos_alim = col_N.number_input("Nº Cabos/Fase", value=1, min_value=1, key="add_nc_v4")

                    colG, colH, colI, colJ = st.columns(4)
                    n_disj_alim = colG.number_input("Nº Disj.", value=1, min_value=1, key="add_ndisj_v4")
                    disj_alim = colH.number_input("In (A)", value=0.0, key="add_disjo_v4")
                    curva_alim = colI.selectbox("Curva", ["C", "B", "D", "CM", "C (Casc.)", "B (Casc.)"], key="add_curvao_v4")
                    icu_alim = colJ.number_input("Icu (kA)", value=10.0, key="add_icuo_v4")
                    
                    if st.form_submit_button("Gravar Quadro na Rede", type="primary", use_container_width=True):
                        if nome_q.strip():
                            services.criar_quadro(db, projeto_id=projeto_atual.id, nome=nome_q.strip().upper(), tipo=tipo_q, quadro_pai_id=opcoes_pai[pai_q], condutores_por_fase=n_cabos_alim)
                            novo_q = db.query(services.models.Quadro).filter(services.models.Quadro.projeto_id == projeto_atual.id, services.models.Quadro.nome == nome_q.strip().upper()).first()
                            if novo_q:
                                novo_q.localizacao = local_q.strip()
                                novo_q.comprimento_alimentador_m = comp_alim 
                                novo_q.capacidade_nominal_A = disj_alim 
                                novo_q.fases_alimentador = fases_alim
                                novo_q.ib_alimentador_A = ib_alim
                                novo_q.isolacao_alimentador = iso_alim
                                novo_q.bitola_alimentador_mm2 = bit_alim
                                novo_q.bitola_neutro_alimentador_mm2 = bit_n_alim
                                novo_q.bitola_pe_alimentador_mm2 = bit_pe_alim
                                novo_q.disjuntor_alimentador_A = disj_alim
                                novo_q.curva_alimentador = f"{curva_alim}|{n_disj_alim}" if n_disj_alim > 1 else curva_alim
                                novo_q.icu_alimentador_kA = icu_alim
                                db.commit()
                            st.rerun()
                        else:
                            st.error("A identificação é obrigatória.")

            with st.container(border=True):
                st.markdown("##### Módulo: Inclusão de Circuito Único")
                if not quadros_disponiveis:
                    st.warning("Cadastre um Quadro para inserir circuitos.")
                else:
                    with st.form("form_add_circuito_v4", clear_on_submit=True):
                        mapa_q_circ = {q.nome: q.id for q in quadros_disponiveis}
                        q_origem_id = st.selectbox("Painel de Origem:", list(mapa_q_circ.keys()), key="circ_orig_v4")
                        
                        c1, c2, c3 = st.columns(3)
                        n_circ = c1.text_input("Identificação")
                        t_circ = c2.selectbox("Tipo de Carga", ["TERMINAL", "ALIMENTADOR"], key="circ_tipo_v4")
                        f_circ = c3.selectbox("Fases", ["TRIFASICO", "F-N", "F-F"], key="circ_fases_v4")
                        
                        c4, c5, c6 = st.columns(3)
                        l_circ = c4.number_input("Comprimento (m)", value=10.0, key="circ_len_v4")
                        ib_circ = c5.number_input("Corrente Ib (A)", value=20.0, key="circ_ib_v4")
                        iso_circ = c6.selectbox("Isolação do Cabo", ["HEPR", "PVC", "BARRAMENTO"], key="circ_iso_v4")
                        
                        c7, c8, c9, c_nc = st.columns(4)
                        sc_fase = c7.number_input("Fase (mm² / A nominal)", value=2.5, key="circ_bf_v4")
                        sc_neutro = c8.number_input("Neutro (mm²)", value=2.5, key="circ_bn_v4")
                        sc_terra = c9.number_input("PE (mm²)", value=2.5, key="circ_bpe_v4")
                        n_cabos_circ = c_nc.number_input("Nº Cabos", value=1, min_value=1, key="circ_nc_v4")
                        
                        c10, c11, c12, c13 = st.columns(4)
                        n_disj_circ = c10.number_input("Nº Disj.", value=1, min_value=1, key="circ_ndisj_v4")
                        in_circ = c11.number_input("In (A)", value=20.0, key="circ_in_v4")
                        curva_circ = c12.selectbox("Curva", ["C", "B", "D", "CM", "C (Casc.)", "B (Casc.)"], key="circ_curva_v4")
                        icu_ka_circ = c13.number_input("Icu (kA)", value=10.0, key="circ_icu_v4")
                        
                        if st.form_submit_button("Gravar Circuito", type="primary", use_container_width=True):
                            if n_circ.strip():
                                dados_insercao = {
                                    'nome': n_circ.strip().upper(), 'tipo': t_circ, 'fases': f_circ,
                                    'comprimento_m': l_circ, 'ib_A': ib_circ, 'fp': 0.92,
                                    'isolacao': iso_circ, 'bitola_mm2': sc_fase, 
                                    'bitola_neutro_mm2': sc_neutro, 'bitola_pe_mm2': sc_terra,
                                    'condutores_por_fase': n_cabos_circ,
                                    'in_disj': in_circ, 'curva_disj': f"{curva_circ}|{n_disj_circ}" if n_disj_circ > 1 else curva_circ, 'icu_disj': icu_ka_circ * 1000.0
                                }
                                services.adicionar_circuito(db, mapa_q_circ[q_origem_id], dados_insercao)
                                st.rerun()

        with col_direita:
            with st.expander("Módulo: Edição de Quadro Existente", expanded=False):
                if quadros_disponiveis:
                    mapa_edicao_q = {q.nome: q for q in quadros_disponiveis}
                    selecionado_q = st.selectbox("Selecione o Quadro/Ponto:", list(mapa_edicao_q.keys()), key="sel_q_mod_v4")
                    q_alvo = mapa_edicao_q[selecionado_q]

                    with st.form(key=f"form_edit_{q_alvo.id}"):
                        c1, c2 = st.columns(2)
                        novo_nome_q = c1.text_input("Alterar Nome:", value=q_alvo.nome)
                        tipos = ["POSTE", "CAIXA ZC/ZB", "MEDIDOR", "QGBT", "QDC", "CM"]
                        novo_tipo_q = c2.selectbox("Alterar Tipo:", tipos, index=tipos.index(q_alvo.tipo) if q_alvo.tipo in tipos else 0)
                        
                        opcoes_novo_pai = {"[Manter Atual]": "MANTER", "[Nó Raiz]": None}
                        for q in quadros_disponiveis:
                            if q.id != q_alvo.id: opcoes_novo_pai[q.nome] = q.id
                        selecao_novo_pai = st.selectbox("Mudar Origem para:", list(opcoes_novo_pai.keys()))
                        
                        st.caption("Modificar Dados do Ramal:")
                        colA, colB, colC = st.columns(3)
                        comp_alim = colA.number_input("Distância (m)", value=float(q_alvo.comprimento_alimentador_m if q_alvo.comprimento_alimentador_m is not None else 0.0))
                        fases_opc = ["TRIFASICO", "F-N", "F-F"]
                        fases_alim = colB.selectbox("Fases", fases_opc, index=fases_opc.index(q_alvo.fases_alimentador) if q_alvo.fases_alimentador in fases_opc else 0)
                        iso_opc = ["HEPR", "PVC", "BARRAMENTO"]
                        iso_alim = colC.selectbox("Isolação", iso_opc, index=iso_opc.index(q_alvo.isolacao_alimentador) if q_alvo.isolacao_alimentador in iso_opc else 0)
                        
                        comp_Ib_edit = st.number_input("Corrente Ib (A)", value=float(q_alvo.ib_alimentador_A if q_alvo.ib_alimentador_A is not None else 0.0))

                        colD, colE, colF, col_N = st.columns(4)
                        bit_alim = colD.number_input("Fase (mm² / A nominal)", value=float(q_alvo.bitola_alimentador_mm2 if q_alvo.bitola_alimentador_mm2 is not None else 0.0))
                        bit_n_alim = colE.number_input("Neutro (mm²)", value=float(q_alvo.bitola_neutro_alimentador_mm2 if q_alvo.bitola_neutro_alimentador_mm2 is not None else 0.0))
                        bit_pe_alim = colF.number_input("PE (mm²)", value=float(q_alvo.bitola_pe_alimentador_mm2 if q_alvo.bitola_pe_alimentador_mm2 is not None else 0.0))
                        n_cabos_edit = col_N.number_input("Nº Cabos", value=int(q_alvo.condutores_por_fase if q_alvo.condutores_por_fase is not None else 1), min_value=1)

                        curva_db = q_alvo.curva_alimentador or "C"
                        n_disj_db = 1
                        if '|' in curva_db:
                            c_part, n_part = curva_db.split('|')
                            curva_val = c_part
                            try: n_disj_db = int(n_part)
                            except: pass
                        else:
                            curva_val = curva_db

                        colG, colH, colI, colJ = st.columns(4)
                        n_disj_alim = colG.number_input("Nº Disjuntores", value=n_disj_db, min_value=1)
                        disj_alim = colH.number_input("In (A)", value=float(q_alvo.disjuntor_alimentador_A if q_alvo.disjuntor_alimentador_A is not None else 0.0))
                        curva_opc = ["C", "B", "D", "CM", "C (Casc.)", "B (Casc.)"]
                        curva_alim = colI.selectbox("Curva", curva_opc, index=curva_opc.index(curva_val) if curva_val in curva_opc else 0)
                        icu_alim = colJ.number_input("Icu (kA)", value=float((q_alvo.icu_alimentador_kA if q_alvo.icu_alimentador_kA is not None else 10.0)))

                        b_salvar, b_deletar = st.columns(2)
                        if b_salvar.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                            q_alvo.nome = novo_nome_q.strip().upper()
                            q_alvo.tipo = novo_tipo_q
                            if opcoes_novo_pai[selecao_novo_pai] != "MANTER": q_alvo.quadro_pai_id = opcoes_novo_pai[selecao_novo_pai]
                            q_alvo.comprimento_alimentador_m = comp_alim
                            q_alvo.fases_alimentador = fases_alim
                            q_alvo.ib_alimentador_A = comp_Ib_edit
                            q_alvo.isolacao_alimentador = iso_alim
                            q_alvo.bitola_alimentador_mm2 = bit_alim
                            q_alvo.bitola_neutro_alimentador_mm2 = bit_n_alim
                            q_alvo.bitola_pe_alimentador_mm2 = bit_pe_alim
                            q_alvo.condutores_por_fase = n_cabos_edit
                            q_alvo.disjuntor_alimentador_A = disj_alim
                            q_alvo.curva_alimentador = f"{curva_alim}|{n_disj_alim}" if n_disj_alim > 1 else curva_alim
                            q_alvo.icu_alimentador_kA = icu_alim
                            db.commit()
                            st.rerun()
                            
                        if b_deletar.form_submit_button("Excluir Quadro", use_container_width=True):
                            db.delete(q_alvo)
                            db.commit()
                            st.rerun()

            with st.expander("Módulo: Geração Rápida em Lote", expanded=False):
                if quadros_disponiveis:
                    prefixos_entrada = st.text_area("Prefixos (Separados por vírgula. Ex: AP 11, AP 12)")
                    with st.form("form_add_lote_v4"):
                        mapa_q_lote = {q.nome: q.id for q in quadros_disponiveis}
                        q_lote_id = st.selectbox("Painel Coletivo de Destino:", list(mapa_q_lote.keys()))
                        sufixo_carga = st.text_input("Sufixo Identificador (ex: Alimentador)")
                        disj_padrao = st.number_input("Disjuntor Padrão (A)", value=40.0)
                        icu_ka_lote = st.number_input("Icu Padrão (kA)", value=10.0)
                        
                        if st.form_submit_button("Processar Lote", type="primary", use_container_width=True):
                            lista_prefixos = [p.strip().upper() for p in prefixos_entrada.split(',') if p.strip()]
                            for pref in lista_prefixos:
                                dados_lote = {
                                    'nome': f"{pref} - {sufixo_carga.strip().upper()}", 'tipo': "ALIMENTADOR", 'fases': "TRIFASICO", 
                                    'comprimento_m': 15.0, 'ib_A': disj_padrao * 0.8, 'fp': 0.92, 'isolacao': "HEPR", 
                                    'bitola_mm2': 10.0, 'bitola_neutro_mm2': 10.0, 'bitola_pe_mm2': 10.0, 'condutores_por_fase': 1,
                                    'in_disj': disj_padrao, 'curva_disj': "C", 'icu_disj': icu_ka_lote * 1000.0
                                }
                                services.adicionar_circuito(db, mapa_q_lote[q_lote_id], dados_lote)
                            st.rerun()
                        
        st.divider()
        st.markdown("### Organização em Massa de Circuitos")
        
        circuitos_totais = services.listar_circuitos_do_projeto(db, projeto_atual.id)
        if circuitos_totais:
            dados_planilha = []
            for c in circuitos_totais:
                curva_db = c.curva_disj or "C"
                n_d = 1
                if '|' in curva_db:
                    c_val, n_p = curva_db.split('|')
                    curva_db = c_val
                    try: n_d = int(n_p)
                    except: pass
                    
                dados_planilha.append({
                    'ID Interno': c.id, 'Identificacao': c.nome, 'Tipo': c.tipo, 'Faseamento': c.fases, 'Isolacao': c.isolacao,
                    'Comprimento (m)': c.comprimento_m, 'Ib (A)': c.ib_A, 'Qtd. Cabos': getattr(c, 'condutores_por_fase', 1) or 1, 
                    'Fase (mm²)': c.bitola_mm2, 'Neutro (mm²)': c.bitola_neutro_mm2, 'Terra (mm²)': c.bitola_pe_mm2,
                    'Qtd. Disj.': n_d, 'In Disjuntor (A)': c.in_disj, 'Curva': curva_db, 
                    'Icu (kA)': (c.icu_disj if c.icu_disj is not None else 10000.0) / 1000.0, 'Remover': False
                })
            
            df_config = pd.DataFrame(dados_planilha)
            df_atualizado = st.data_editor(
                df_config,
                column_config={
                    "ID Interno": st.column_config.NumberColumn("ID Interno", disabled=True),
                    "Tipo": st.column_config.SelectboxColumn("Tipo", options=["ALIMENTADOR", "TERMINAL"]),
                    "Faseamento": st.column_config.SelectboxColumn("Faseamento", options=["TRIFASICO", "F-N", "F-F"]),
                    "Isolacao": st.column_config.SelectboxColumn("Isolacao", options=["HEPR", "PVC", "BARRAMENTO"]),
                    "Qtd. Cabos": st.column_config.NumberColumn("Qtd. Cabos", min_value=1),
                    "Qtd. Disj.": st.column_config.NumberColumn("Qtd. Disj.", min_value=1),
                    "Curva": st.column_config.SelectboxColumn("Curva", options=["C", "B", "D", "CM", "C (Casc.)", "B (Casc.)"]),
                    "Remover": st.column_config.CheckboxColumn("Remover")
                },
                use_container_width=True, hide_index=True
            )
            
            if st.button("Salvar Planilha", type="primary"):
                for _, linha_editada in df_atualizado.iterrows():
                    circ_objeto = db.query(services.models.Circuito).filter(services.models.Circuito.id == int(linha_editada['ID Interno'])).first()
                    if circ_objeto:
                        if linha_editada['Remover']: db.delete(circ_objeto)
                        else:
                            circ_objeto.nome = str(linha_editada['Identificacao']).strip().upper()
                            circ_objeto.tipo = str(linha_editada['Tipo'])
                            circ_objeto.fases = str(linha_editada['Faseamento'])
                            circ_objeto.isolacao = str(linha_editada['Isolacao'])
                            circ_objeto.comprimento_m = float(linha_editada['Comprimento (m)'])
                            circ_objeto.ib_A = float(linha_editada['Ib (A)'])
                            circ_objeto.condutores_por_fase = int(linha_editada['Qtd. Cabos'])
                            circ_objeto.bitola_mm2 = float(linha_editada['Fase (mm²)'])
                            circ_objeto.bitola_neutro_mm2 = float(linha_editada['Neutro (mm²)'])
                            circ_objeto.bitola_pe_mm2 = float(linha_editada['Terra (mm²)'])
                            circ_objeto.in_disj = float(linha_editada['In Disjuntor (A)'])
                            q_disj = int(linha_editada['Qtd. Disj.'])
                            circ_objeto.curva_disj = f"{linha_editada['Curva']}|{q_disj}" if q_disj > 1 else linha_editada['Curva']
                            circ_objeto.icu_disj = float(linha_editada['Icu (kA)']) * 1000.0
                db.commit()
                st.rerun()

    with aba3:
        st.subheader("Auditoria Nodal NBR 5410")
        
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if st.button("Executar Motor Zeta", type="primary", use_container_width=True):
                with st.spinner("Resolvendo matriz de impedâncias..."):
                    perfil_selecionado = "RESIDENCIAL" if "Residencial" in perfil_carga else "INDUSTRIAL"
                    pacote = report_builder.montar_pacote_relatorio(
                        db, 
                        projeto_atual.id, 
                        projeto_atual.tensao_secundaria, 
                        projeto_atual.potencia_transformador, 
                        False,
                        perfil_selecionado
                    )
                    
                    if pacote: 
                        df_bruto = pacote["df_executivo"].copy()
                        
                        arvore = {}
                        for _, row in df_bruto.iterrows():
                            origem = str(row['Quadro Origem']).strip()
                            circ = str(row['ID Circuito']).strip()
                            if origem not in arvore:
                                arvore[origem] = []
                            arvore[origem].append(circ)
                            
                        ordem_final = []
                        visitados = set()
                        
                        def visitar(no):
                            if no in visitados: return
                            visitados.add(no)
                            if no in df_bruto['ID Circuito'].str.strip().values:
                                ordem_final.append(no)
                            if no in arvore:
                                for filho in sorted(arvore[no]):
                                    visitar(filho)
                                    
                        origens = set(df_bruto['Quadro Origem'].str.strip())
                        circuitos = set(df_bruto['ID Circuito'].str.strip())
                        raizes = origens - circuitos
                        
                        for raiz in sorted(raizes):
                            visitar(raiz)
                            
                        for circ in sorted(circuitos):
                            if circ not in visitados:
                                visitar(circ)
                                
                        df_bruto['sort_key'] = pd.Categorical(df_bruto['ID Circuito'].str.strip(), categories=ordem_final, ordered=True)
                        df_sorted = df_bruto.sort_values('sort_key').drop(columns=['sort_key']).reset_index(drop=True)
                        df_sorted['Ordem'] = range(1, len(df_sorted) + 1)
                        
                        st.session_state.ultimo_pacote = pacote
                        st.session_state.df_memoria_tabela = df_sorted
                    else: 
                        st.info("Cadastre os circuitos na aba Topologia para realizar o cálculo.")

        if 'ultimo_pacote' in st.session_state and 'df_memoria_tabela' in st.session_state:
            pacote = st.session_state.ultimo_pacote
            
            st.divider()
            
            with st.expander("Ajuste Fino de Dimensionamento (Recálculo Rápido)", expanded=False):
                st.caption("Altere os fatores críticos de dimensionamento abaixo. Ao clicar em 'Salvar e Recalcular', o motor atualizará a malha instantaneamente.")
                circuitos_ajuste = services.listar_circuitos_do_projeto(db, projeto_atual.id)
                if circuitos_ajuste:
                    dados_ajuste = []
                    for c in circuitos_ajuste:
                        curva_db = c.curva_disj or "C"
                        n_d = 1
                        if '|' in curva_db:
                            c_val, n_p = curva_db.split('|')
                            curva_db = c_val
                            try: n_d = int(n_p)
                            except: pass
                            
                        dados_ajuste.append({
                            'ID Interno': c.id, 
                            'Circuito': c.nome, 
                            'Comprimento (m)': c.comprimento_m, 
                            'Bitola / A Nominal': c.bitola_mm2, 
                            'Qtd. Disj.': n_d,
                            'Disjuntor (A)': c.in_disj,
                            'Curva': curva_db,
                            'Icu (kA)': (c.icu_disj if c.icu_disj is not None else 10000.0) / 1000.0
                        })
                    
                    df_ajuste = pd.DataFrame(dados_ajuste)
                    df_editado_ajuste = st.data_editor(
                        df_ajuste,
                        column_config={
                            "ID Interno": st.column_config.NumberColumn(disabled=True),
                            "Circuito": st.column_config.TextColumn(disabled=True),
                            "Bitola / A Nominal": st.column_config.NumberColumn(format="%.1f"),
                            "Qtd. Disj.": st.column_config.NumberColumn("Qtd. Disj.", min_value=1),
                            "Disjuntor (A)": st.column_config.NumberColumn(format="%.1f"),
                            "Curva": st.column_config.SelectboxColumn(options=["C", "B", "D", "CM", "C (Casc.)", "B (Casc.)"]),
                            "Icu (kA)": st.column_config.NumberColumn(format="%.1f")
                        },
                        use_container_width=True, hide_index=True, key="editor_ajuste_tab3"
                    )
                    
                    if st.button("Salvar e Recalcular", type="secondary"):
                        with st.spinner("Atualizando malha..."):
                            for _, linha_ajuste in df_editado_ajuste.iterrows():
                                circ_obj = db.query(services.models.Circuito).filter(services.models.Circuito.id == int(linha_ajuste['ID Interno'])).first()
                                if circ_obj:
                                    circ_obj.comprimento_m = float(linha_ajuste['Comprimento (m)'])
                                    circ_obj.bitola_mm2 = float(linha_ajuste['Bitola / A Nominal'])
                                    circ_obj.in_disj = float(linha_ajuste['Disjuntor (A)'])
                                    q_disj_ajuste = int(linha_ajuste['Qtd. Disj.'])
                                    circ_obj.curva_disj = f"{linha_ajuste['Curva']}|{q_disj_ajuste}" if q_disj_ajuste > 1 else linha_ajuste['Curva']
                                    if 'Icu (kA)' in linha_ajuste:
                                        circ_obj.icu_disj = float(linha_ajuste['Icu (kA)']) * 1000.0
                            db.commit()
                            
                            perfil_selecionado = "RESIDENCIAL" if "Residencial" in perfil_carga else "INDUSTRIAL"
                            pacote_novo = report_builder.montar_pacote_relatorio(
                                db, 
                                projeto_atual.id, 
                                projeto_atual.tensao_secundaria, 
                                projeto_atual.potencia_transformador, 
                                False,
                                perfil_selecionado
                            )
                            
                            if pacote_novo:
                                df_b = pacote_novo["df_executivo"].copy()
                                arv = {}
                                for _, rw in df_b.iterrows():
                                    ori = str(rw['Quadro Origem']).strip()
                                    crc = str(rw['ID Circuito']).strip()
                                    if ori not in arv: arv[ori] = []
                                    arv[ori].append(crc)
                                ord_fin = []
                                vis = set()
                                def vis_dfs(n):
                                    if n in vis: return
                                    vis.add(n)
                                    if n in df_b['ID Circuito'].str.strip().values: ord_fin.append(n)
                                    if n in arv:
                                        for fl in sorted(arv[n]): vis_dfs(fl)
                                origs = set(df_b['Quadro Origem'].str.strip())
                                circs = set(df_b['ID Circuito'].str.strip())
                                for r in sorted(origs - circs): vis_dfs(r)
                                for c in sorted(circs):
                                    if c not in vis: vis_dfs(c)
                                df_b['s_key'] = pd.Categorical(df_b['ID Circuito'].str.strip(), categories=ord_fin, ordered=True)
                                df_s = df_b.sort_values('s_key').drop(columns=['s_key']).reset_index(drop=True)
                                df_s['Ordem'] = range(1, len(df_s) + 1)
                                
                                st.session_state.ultimo_pacote = pacote_novo
                                st.session_state.df_memoria_tabela = df_s 
                            st.rerun()

            st.markdown("#### Tabela Executiva Consolidada")
            st.caption("A tabela já foi automaticamente estruturada através do algoritmo de busca em profundidade (DFS) do Motor Zeta, partindo da Fonte até os Circuitos Terminais.")
            
            def colorir(val):
                if val == 'APROVADO': return 'background-color: #c6efce; color: #006100; font-weight: bold;'
                if 'CASC' in str(val): return 'background-color: #fdebd0; color: #d35400; font-weight: bold;'
                if val == 'REVISAR': return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold;'
                return ''

            df_editado = st.data_editor(
                st.session_state.df_memoria_tabela.style.map(colorir, subset=['Veredito']).format(precision=2),
                column_config={"Ordem": st.column_config.NumberColumn("Ordem", min_value=0, max_value=9999, step=1)},
                disabled=[col for col in st.session_state.df_memoria_tabela.columns if col != 'Ordem'],
                use_container_width=True, hide_index=True
            )
            
            if st.button("Reaplicar Ordem Manual", type="secondary"):
                st.session_state.df_memoria_tabela = df_editado.data.sort_values(by=['Ordem', 'ID Circuito']).reset_index(drop=True)
                st.rerun()

            col_pdf_booktabs, col_tex, _ = st.columns([2, 2, 4])
            
            tabela_impressao = st.session_state.df_memoria_tabela.drop(columns=['Ordem'])
            
            with col_pdf_booktabs:
                if st.button("Baixar Laudo (PDF Formato Acadêmico)", use_container_width=True):
                    with st.spinner("Compilando Documento PDF..."):
                        from weasyprint import HTML
                        
                        def get_ver_class(v):
                            if 'REVISAR' in v: return 'revisar'
                            if 'CASC' in v: return 'aprovado-casc'
                            return 'aprovado'
                            
                        linhas_tabela = "".join([f"<tr><td>{row['ID Circuito']}</td><td>{row['Quadro Origem']}</td><td>{row['Cabo (mm²)']}</td><td>{row['Queda Acum. (%)']}%</td><td>{row['Icc Máx. (A)']}</td><td>{row['Disjuntor']}</td><td class='{get_ver_class(row['Veredito'])}'>{row['Veredito']}</td><td style='font-size: 8pt;'>{row['Sugestões Técnicas']}</td></tr>" for _, row in tabela_impressao.iterrows()])
                        
                        html_latex_style = f"""
                        <html>
                        <head>
                            <style>
                                @import url('https://fonts.cdnfonts.com/css/latin-modern-roman');
                                @page {{
                                    size: A4 landscape;
                                    margin: 1.5cm;
                                }}
                                body {{ font-family: 'Latin Modern Roman', serif; padding: 0; margin: 0; }}
                                h2 {{ text-align: center; text-transform: uppercase; font-size: 14pt; margin-bottom: 20px; letter-spacing: 1px; color: #2c3e50; }}
                                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 10pt; page-break-inside: auto; }}
                                tr {{ page-break-inside: avoid; page-break-after: auto; }}
                                th {{ border-top: 2px solid black; border-bottom: 1px solid black; padding: 8px 4px; text-align: center; font-weight: bold; background-color: #f8f9fa; }}
                                td {{ border-bottom: 1px solid #eeeeee; padding: 8px 4px; text-align: center; vertical-align: middle; }}
                                table tr:last-child td {{ border-bottom: 2px solid black; }}
                                .revisar {{ color: #c0392b; font-weight: bold; }}
                                .aprovado {{ color: #27ae60; font-weight: bold; }}
                                .aprovado-casc {{ color: #d35400; font-weight: bold; }}
                            </style>
                        </head>
                        <body>
                            <h2>Laudo Executivo de Inspeção Nodal - ABNT NBR 5410<br><span style="font-size: 12pt; color: #7f8c8d;">{projeto_atual.nome_projeto}</span></h2>
                            <table>
                                <thead>
                                    <tr><th>Circuito</th><th>Origem</th><th>Condutor / Barramento</th><th>$\\Delta V$ (%)</th><th>Icc Máx (A)</th><th>Proteção</th><th>Status</th><th>Anotações / Falhas</th></tr>
                                </thead>
                                <tbody>
                                    {linhas_tabela}
                                </tbody>
                            </table>
                        </body>
                        </html>
                        """
                        HTML(string=html_latex_style).write_pdf(f"Laudo_{projeto_atual.nome_projeto}.pdf".replace(" ", "_"))
                        st.success("PDF em formato Acadêmico gerado com sucesso!")

            with col_tex:
                linhas_tex = ""
                for _, row in tabela_impressao.iterrows():
                    linhas_tex += f"{row['ID Circuito']} & {row['Quadro Origem']} & {row['Cabo (mm²)']} & {row['Queda Acum. (%)']}\\% & {row['Icc Máx. (A)']} & {row['Disjuntor']} & {row['Veredito']} \\\\\n"
                
                latex_source = f"""\\documentclass[a4paper,10pt,landscape]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{geometry}}
\\geometry{{margin=1in}}
\\usepackage{{booktabs}}
\\usepackage{{longtable}}

\\begin{{document}}
\\section*{{Laudo Executivo de Inspeção Nodal - {projeto_atual.nome_projeto}}}

\\begin{{longtable}}{{cccccccc}}
\\toprule
\\textbf{{Circuito}} & \\textbf{{Origem}} & \\textbf{{Condutor}} & \\textbf{{$\\Delta V$}} & \\textbf{{Icc Máx (A)}} & \\textbf{{Proteção}} & \\textbf{{Status}} \\\\
\\midrule
\\endhead
{linhas_tex}
\\bottomrule
\\end{{longtable}}
\\end{{document}}
"""
                st.download_button(
                    label="Baixar Tabela para Compilador (.tex)",
                    data=latex_source,
                    file_name=f"Laudo_{projeto_atual.nome_projeto}.tex",
                    mime="text/plain",
                    use_container_width=True
                )

            st.divider()
            
            with st.expander("Diagrama Unifilar Detalhado (Auditoria)", expanded=True):
                st.caption("As fichas exibem os dados reais simulados pela matriz de impedância. Navegue livremente com Pan (arrastar), Zoom (scroll) ou Tela Cheia.")
                
                tabela_final = st.session_state.df_memoria_tabela
                
                dot_code = [
                    'digraph Unifilar {',
                    '    rankdir=TB;',
                    '    splines=polyline;',
                    '    nodesep=0.2;',
                    '    ranksep=0.9;',
                    '    bgcolor="transparent";',
                    '    node [shape=none, fontname="Arial", margin=0];',
                    '    edge [color="#888888", penwidth=1.2, arrowsize=0.6, fontname="Arial", fontsize=10, fontcolor="#555555"];', 
                    '    "CEMIG" [label=<<TABLE BORDER="1" COLOR="#c0392b" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" STYLE="ROUNDED" BGCOLOR="#c0392b"><TR><TD><FONT COLOR="white" POINT-SIZE="11"><B>REDE CEMIG / TRAFO</B></FONT></TD></TR></TABLE>>];'
                ]
                
                for _, row in tabela_final.iterrows():
                    def scape_xml(texto):
                        return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    
                    nid = str(row['ID Circuito']).replace('"', '')
                    nome = scape_xml(row['ID Circuito'])
                    cabo = scape_xml(row['Cabo (mm²)'])
                    
                    ib = f"{float(row['Ib (A)']):.1f}A"
                    disj_bruto = str(row['Disjuntor'])
                    disj_val = "Passagem" if disj_bruto.startswith("0.0A") or disj_bruto.startswith("0A") else disj_bruto
                    disj = scape_xml(disj_val)
                    
                    icc = f"{(float(row['Icc Máx. (A)']) / 1000):.1f} kA"
                    queda = f"{float(row['Queda Acum. (%)']):.2f}%"
                    distancia = float(row['Comp. (m)'])
                    veredito = str(row['Veredito'])
                    
                    nome_str = str(row['ID Circuito']).strip()
                    circ_obj = db.query(services.models.Circuito).join(services.models.Quadro).filter(
                        services.models.Quadro.projeto_id == projeto_atual.id, 
                        services.models.Circuito.nome == nome_str
                    ).first()
                    
                    if circ_obj:
                        icu_val = (circ_obj.icu_disj if circ_obj.icu_disj is not None else 10000.0) / 1000.0
                    else:
                        q_obj = db.query(services.models.Quadro).filter(
                            services.models.Quadro.projeto_id == projeto_atual.id, 
                            services.models.Quadro.nome == nome_str
                        ).first()
                        if q_obj:
                            icu_val = float(q_obj.icu_alimentador_kA if q_obj.icu_alimentador_kA is not None else 10.0)
                        else:
                            icu_val = 10.0
                    icu_str = f"{icu_val:g} kA"
                    
                    is_panel = (tabela_final['Quadro Origem'] == str(row['ID Circuito'])).any()
                    header_bg = "#2c3e50" if is_panel else "#7f8c8d"
                    
                    if veredito == 'APROVADO':
                        status_bg, status_fg, status_icon = "#e8f5e9", "#1b5e20", "CONFORME"
                    elif 'CASC' in veredito:
                        status_bg, status_fg, status_icon = "#fdf2e9", "#d35400", "CONFORME (CASC.)"
                    else:
                        status_bg, status_fg, status_icon = "#ffebee", "#b71c1c", "REVISAR"
                    
                    label = f'''<<TABLE BORDER="1" COLOR="#d2d6de" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" STYLE="ROUNDED" BGCOLOR="#ffffff">
                        <TR><TD COLSPAN="2" BGCOLOR="{header_bg}"><FONT COLOR="white" POINT-SIZE="10"><B>{nome}</B></FONT></TD></TR>
                        <TR><TD ALIGN="LEFT" BGCOLOR="#f8f9fa"><FONT COLOR="#555555" POINT-SIZE="10">Ib / Disj.</FONT></TD><TD ALIGN="RIGHT" BGCOLOR="#f8f9fa"><FONT POINT-SIZE="10"><B>{ib} / {disj}</B></FONT></TD></TR>
                        <TR><TD ALIGN="LEFT" BGCOLOR="#ffffff"><FONT COLOR="#555555" POINT-SIZE="10">Cabo / B.</FONT></TD><TD ALIGN="RIGHT" BGCOLOR="#ffffff"><FONT POINT-SIZE="10"><B>{cabo}</B></FONT></TD></TR>
                        <TR><TD ALIGN="LEFT" BGCOLOR="#f8f9fa"><FONT COLOR="#555555" POINT-SIZE="10">Icc Máx</FONT></TD><TD ALIGN="RIGHT" BGCOLOR="#f8f9fa"><FONT POINT-SIZE="10"><B>{icc}</B></FONT></TD></TR>
                        <TR><TD ALIGN="LEFT" BGCOLOR="#ffffff"><FONT COLOR="#555555" POINT-SIZE="10">Icu</FONT></TD><TD ALIGN="RIGHT" BGCOLOR="#ffffff"><FONT POINT-SIZE="10"><B>{icu_str}</B></FONT></TD></TR>
                        <TR><TD ALIGN="LEFT" BGCOLOR="#f8f9fa"><FONT COLOR="#555555" POINT-SIZE="10">Queda</FONT></TD><TD ALIGN="RIGHT" BGCOLOR="#f8f9fa"><FONT POINT-SIZE="10"><B>{queda}</B></FONT></TD></TR>
                        <TR><TD COLSPAN="2" BGCOLOR="{status_bg}"><FONT COLOR="{status_fg}" POINT-SIZE="9"><B>{status_icon}</B></FONT></TD></TR>
                    </TABLE>>'''
                    
                    dot_code.append(f'    "{nid}" [label={label}];')
                    
                    origem = str(row['Quadro Origem']).replace('"', '')
                    label_seta = f'[label=<<TABLE BORDER="0" CELLPADDING="2" BGCOLOR="#ffffff99"><TR><TD><FONT POINT-SIZE="9" COLOR="#555555">{distancia:g} m</FONT></TD></TR></TABLE>>]'
                    
                    if origem == "CEMIG":
                        dot_code.append(f'    "CEMIG" -> "{nid}" {label_seta};')
                    else:
                        dot_code.append(f'    "{origem}" -> "{nid}" {label_seta};')
                        
                dot_code.append('}')
                
                try:
                    import graphviz
                    import streamlit.components.v1 as components
                    
                    grafico_motor = graphviz.Source('\n'.join(dot_code))
                    
                    col_dl_diag, _ = st.columns([2, 4])
                    with col_dl_diag:
                        pdf_diagrama_bytes = grafico_motor.pipe(format='pdf')
                        st.download_button(
                            label="Baixar Diagrama Unifilar (Alta Resolução - PDF)",
                            data=pdf_diagrama_bytes,
                            file_name=f"Diagrama_Unifilar_{projeto_atual.nome_projeto}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    
                    svg_bytes = grafico_motor.pipe(format='svg')
                    svg_string = svg_bytes.decode('utf-8')
                    
                    if '<svg' in svg_string:
                        svg_string = svg_string[svg_string.find('<svg'):]
                        
                    html_code = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                        <style>
                            body {{ margin: 0; padding: 0; overflow: hidden; background-color: transparent; font-family: sans-serif; }}
                            #svg-container {{ width: 100vw; height: 100vh; }}
                            g.graph > title {{ display: none; }}
                            
                            #btn-fullscreen {{
                                position: absolute;
                                top: 15px;
                                right: 15px;
                                z-index: 1000;
                                background-color: #2c3e50;
                                color: #ecf0f1;
                                border: 1px solid #34495e;
                                padding: 8px 12px;
                                border-radius: 4px;
                                cursor: pointer;
                                font-weight: bold;
                                font-size: 11px;
                                box-shadow: 0 4px 6px rgba(0,0,0,0.2);
                                transition: 0.2s;
                            }}
                            #btn-fullscreen:hover {{ background-color: #34495e; transform: scale(1.05); }}
                        </style>
                    </head>
                    <body>
                        <button id="btn-fullscreen" onclick="toggleFullScreen()">⛶ TELA CHEIA</button>
                        <div id="svg-container">
                            {svg_string}
                        </div>
                        <script>
                            function toggleFullScreen() {{
                                if (!document.fullscreenElement) {{
                                    document.documentElement.requestFullscreen().catch(err => {{
                                        console.log(`Erro ao ativar tela cheia: ${{err.message}}`);
                                    }});
                                    document.getElementById('btn-fullscreen').innerText = "✖ FECHAR";
                                }} else {{
                                    if (document.exitFullscreen) {{
                                        document.exitFullscreen();
                                        document.getElementById('btn-fullscreen').innerText = "⛶ TELA CHEIA";
                                    }}
                                }}
                            }}

                            setTimeout(function() {{
                                var svgElement = document.querySelector('svg');
                                if (svgElement) {{
                                    svgElement.setAttribute('width', '100%');
                                    svgElement.setAttribute('height', '100%');
                                    svgPanZoom(svgElement, {{
                                        zoomEnabled: true,
                                        controlIconsEnabled: true,
                                        fit: true,
                                        center: true,
                                        minZoom: 0.1,
                                        maxZoom: 10,
                                        zoomScaleSensitivity: 0.6
                                    }});
                                }}
                            }}, 100);
                        </script>
                    </body>
                    </html>
                    """
                    components.html(html_code, height=650)
                except Exception as e:
                    st.error(f"Falha ao gerar o diagrama. Detalhes: {e}")

    with aba4:
        st.subheader("Memorial Descritivo e Fundamentação Analítica")
        st.markdown(r"""
        Este documento delineia o arranjo teórico e as formulações matemáticas processadas pelo **Motor Nodal Zeta**, garantindo rigor analítico no dimensionamento das proteções e condutores, em conformidade com as diretrizes da **ABNT NBR 5410** e **IEC 60909**.

        ### 1. Modelagem de Impedância e Condutores Equivalentes
        A atenuação estrutural dos curtos-circuitos e a queda de tensão dependem da impedância física longitudinal dos condutores ($Z$). Em sistemas com arranjo de múltiplos condutores em paralelo ($N_c$), a impedância própria por fase ($Z_{eq}$) é regida pelo equivalente nodal da admitância:
        
        $$Z_{eq} = \frac{R(T)}{N_c} + j\frac{X}{N_c}$$

        Onde $R(T)$ é a resistência efetiva corrigida pelo fator de temperatura operacional (70°C para PVC ou 90°C para HEPR). O fasor de impedância total do trecho ($\vec{Z}_{trecho}$) é extraído integrando-se $Z_{eq}$ ao comprimento real $L$:
        
        $$\vec{Z}_{trecho} = Z_{eq} \cdot \left(\frac{L}{1000}\right)$$

        ### 2. Fluxo de Potência e Equação de Queda de Tensão
        A propagação nodal utiliza a abordagem dos momentos elétricos (fasores). Sendo o Fator de Potência definido por $\cos(\theta)$:
        
        $$\vec{I} = |I_b| \angle -\arccos(fp)$$
        $$\Delta \vec{V} = \vec{Z}_{trecho} \cdot \vec{I}$$

        O registro percentual acumulado atesta que os limites normativos não sejam violados no extremo da malha:
        
        $$\Delta V_{\%} = \left( \frac{V_{nom} - |V_{nodal}|}{V_{nom}} \right) \cdot 100$$

        ### 3. Espectro de Curto-Circuito (Diretriz IEC 60909)
        A matriz nodal simula a pior condição de estresse térmico ($I_{cc,max}$) com a rede a frio (20°C) e a pior condição magnética no extremo da linha ($I_{cc,min}$) a quente, penalizada pelo fator de afundamento.
        
        **3.1. Curto-Circuito Trifásico Simétrico (Estresse Térmico Máximo):**
        $$I_{cc3\phi} = \frac{V_{fase}}{|\vec{Z}_{acum}^{20^\circ C}|}$$
        
        **3.2. Curto-Circuito Fase-Neutro (Verificação Magnética Mínima):**
        $$I_{cc1\phi} = \frac{0,95 \cdot V_{fase}}{|\vec{Z}_{acum,F}^{T_{max}} + \vec{Z}_{acum,N}^{T_{max}}|}$$
        """)

        if 'df_memoria_tabela' in st.session_state:
            st.divider()
            st.markdown("### 4. Resumo Físico Paramétrico da Malha")
            st.caption("Tabela sintética contendo exclusivamente as propriedades físicas e limites elétricos validados.")
            
            df_tab4 = st.session_state.df_memoria_tabela[['ID Circuito', 'Cabo (mm²)', 'Comp. (m)', 'Queda Acum. (%)', 'Icc Mín. (A)', 'Icc Máx. (A)', 'Ip Pico (A)']]
            
            st.dataframe(df_tab4, use_container_width=True, hide_index=True)

            col_pdf_mem, col_tex_mem, _ = st.columns([2, 2, 4])
            
            with col_pdf_mem:
                if st.button("Baixar Memorial (PDF Acadêmico)", use_container_width=True):
                    with st.spinner("Compilando Documento PDF..."):
                        from weasyprint import HTML
                        
                        linhas_tabela_mem = "".join([
                            f"<tr><td>{row['ID Circuito']}</td><td>{row['Cabo (mm²)']}</td><td>{row['Comp. (m)']}</td><td>{row['Queda Acum. (%)']}%</td><td>{row['Icc Mín. (A)']}</td><td>{row['Icc Máx. (A)']}</td><td>{row['Ip Pico (A)']}</td></tr>" 
                            for _, row in df_tab4.iterrows()
                        ])
                        
                        html_memorial = f"""
                        <html>
                        <head>
                            <style>
                                @import url('https://fonts.cdnfonts.com/css/latin-modern-roman');
                                @page {{ size: A4 portrait; margin: 2cm 1.5cm; }}
                                body {{ font-family: 'Latin Modern Roman', serif; font-size: 11pt; padding: 0; margin: 0; color: #111; line-height: 1.5; }}
                                h2 {{ text-align: center; text-transform: uppercase; font-size: 14pt; margin-bottom: 20px; letter-spacing: 1px; }}
                                h3 {{ margin-top: 25px; border-bottom: 1px solid #ccc; padding-bottom: 5px; font-size: 12pt; }}
                                p {{ text-align: justify; margin-bottom: 10px; }}
                                .math-eq {{ text-align: center; font-size: 13pt; margin: 15px 0; font-style: italic; }}
                                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 9pt; page-break-inside: auto; }}
                                tr {{ page-break-inside: avoid; page-break-after: auto; }}
                                th {{ border-top: 2px solid black; border-bottom: 1px solid black; padding: 6px 4px; text-align: center; font-weight: bold; background-color: #f8f9fa; }}
                                td {{ border-bottom: 1px solid #eeeeee; padding: 6px 4px; text-align: center; vertical-align: middle; }}
                                table tr:last-child td {{ border-bottom: 2px solid black; }}
                            </style>
                        </head>
                        <body>
                            <h2>Memorial Descritivo e Fundamentação Analítica<br><span style="font-size: 11pt; color: #555;">Projeto: {projeto_atual.nome_projeto}</span></h2>
                            
                            <p>Este documento delineia o arranjo teórico e as formulações matemáticas processadas pelo <b>Motor Nodal Zeta</b>, garantindo rigor analítico no dimensionamento das proteções e condutores, em conformidade com as diretrizes da <b>ABNT NBR 5410</b> e <b>IEC 60909</b>.</p>

                            <h3>1. Modelagem de Impedância e Condutores Equivalentes</h3>
                            <p>A atenuação estrutural dos curtos-circuitos e a queda de tensão dependem da impedância física longitudinal dos condutores (<i>Z</i>). Em sistemas com arranjo de múltiplos condutores em paralelo (<i>N<sub>c</sub></i>), a impedância própria por fase (<i>Z<sub>eq</sub></i>) é regida pelo equivalente nodal da admitância:</p>
                            <div class="math-eq">Z<sub>eq</sub> = R(T) / N<sub>c</sub> + j (X / N<sub>c</sub>)</div>
                            <p>Onde <i>R(T)</i> é a resistência efetiva corrigida pelo fator de temperatura operacional (70&deg;C ou 90&deg;C). O fasor de impedância total do trecho (<i>Z&#8407;<sub>trecho</sub></i>) é obtido integrando-se <i>Z<sub>eq</sub></i> ao comprimento real <i>L</i> (em metros):</p>
                            <div class="math-eq">Z&#8407;<sub>trecho</sub> = Z<sub>eq</sub> &times; (L / 1000)</div>

                            <h3>2. Fluxo de Potência e Equação de Queda de Tensão</h3>
                            <p>A propagação nodal utiliza a abordagem dos momentos elétricos (fasores). Sendo o Fator de Potência definido por cos(&theta;):</p>
                            <div class="math-eq">I&#8407; = |I<sub>b</sub>| &ang; -arccos(fp)<br><br>&Delta;V&#8407; = Z&#8407;<sub>trecho</sub> &times; I&#8407;</div>
                            <p>O registro percentual acumulado atesta que os limites normativos não sejam violados no extremo da malha:</p>
                            <div class="math-eq">&Delta;V<sub>%</sub> = [ (V<sub>nom</sub> - |V<sub>nodal</sub>|) / V<sub>nom</sub> ] &times; 100</div>

                            <h3>3. Espectro de Curto-Circuito (Diretriz IEC 60909)</h3>
                            <p>A matriz nodal simula a pior condição de estresse térmico a frio (20&deg;C) e a pior condição magnética no extremo da linha sob temperatura máxima e afundamento de tensão (fator c = 0,95).</p>
                            <p><b>Curto-Circuito Trifásico Simétrico (Estresse Térmico Máximo):</b></p>
                            <div class="math-eq">I<sub>cc3&phi;</sub> = V<sub>fase</sub> / |Z&#8407;<sub>acum</sub><sup>20&deg;C</sup>|</div>
                            <p><b>Curto-Circuito Fase-Neutro (Verificação Magnética Mínima):</b></p>
                            <div class="math-eq">I<sub>cc1&phi;</sub> = (0,95 &times; V<sub>fase</sub>) / |Z&#8407;<sub>acum,F</sub><sup>T<sub>max</sub></sup> + Z&#8407;<sub>acum,N</sub><sup>T<sub>max</sub></sup>|</div>

                            <h3>4. Resumo Físico Paramétrico da Malha</h3>
                            <table>
                                <thead>
                                    <tr><th>Circuito</th><th>Cabo (mm²)</th><th>L (m)</th><th>&Delta;V Acum. (%)</th><th>Icc Mín (A)</th><th>Icc Máx (A)</th><th>Ip Pico (A)</th></tr>
                                </thead>
                                <tbody>
                                    {linhas_tabela_mem}
                                </tbody>
                            </table>
                        </body>
                        </html>
                        """
                        HTML(string=html_memorial).write_pdf(f"Memorial_Analitico_{projeto_atual.nome_projeto}.pdf".replace(" ", "_"))
                        st.success("Memorial Analítico (PDF) gerado com sucesso!")

            with col_tex_mem:
                linhas_tex_mem = ""
                for _, row in df_tab4.iterrows():
                    linhas_tex_mem += f"{row['ID Circuito']} & {row['Cabo (mm²)']} & {row['Comp. (m)']} & {row['Queda Acum. (%)']}\\% & {row['Icc Mín. (A)']} & {row['Icc Máx. (A)']} & {row['Ip Pico (A)']} \\\\\n"
                
                latex_mem_source = f"""\\documentclass[a4paper,10pt]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{geometry}}
\\geometry{{margin=1in}}
\\usepackage{{booktabs}}
\\usepackage{{longtable}}
\\usepackage{{amsmath}}

\\begin{{document}}
\\section*{{Memorial Descritivo e Fundamentação Analítica - {projeto_atual.nome_projeto}}}

Este documento delineia o arranjo teórico e as formulações matemáticas processadas pelo \\textbf{{Motor Nodal Zeta}}, garantindo rigor analítico no dimensionamento das proteções e condutores, em conformidade com as diretrizes da \\textbf{{ABNT NBR 5410}} e \\textbf{{IEC 60909}}.

\\subsection*{{1. Modelagem de Impedância e Condutores Equivalentes}}
A atenuação estrutural dos curtos-circuitos e a queda de tensão dependem da impedância física longitudinal dos condutores ($Z$). Em sistemas com arranjo de múltiplos condutores em paralelo ($N_c$), a impedância própria por fase ($Z_{{eq}}$) é regida pelo equivalente nodal da admitância:
\\begin{{equation*}}
Z_{{eq}} = \\frac{{R(T)}}{{N_c}} + j\\frac{{X}}{{N_c}}
\\end{{equation*}}
O fasor de impedância total do trecho ($\\vec{{Z}}_{{trecho}}$) é extraído integrando-se $Z_{{eq}}$ ao comprimento real $L$:
\\begin{{equation*}}
\\vec{{Z}}_{{trecho}} = Z_{{eq}} \\cdot \\left(\\frac{{L}}{{1000}}\\right)
\\end{{equation*}}

\\subsection*{{2. Fluxo de Potência e Equação de Queda de Tensão}}
Sendo o Fator de Potência definido por $\\cos(\\theta)$:
\\begin{{align*}}
\\vec{{I}} &= |I_b| \\angle -\\arccos(fp) \\\\
\\Delta \\vec{{V}} &= \\vec{{Z}}_{{trecho}} \\cdot \\vec{{I}}
\\end{{align*}}
O registro percentual acumulado:
\\begin{{equation*}}
\\Delta V_{{\\%}} = \\left( \\frac{{V_{{nom}} - |V_{{nodal}}|}}{{V_{{nom}}}} \\right) \\cdot 100
\\end{{equation*}}

\\subsection*{{3. Espectro de Curto-Circuito (Diretriz IEC 60909)}}
\\textbf{{Curto-Circuito Trifásico Simétrico (Estresse Térmico Máximo):}}
\\begin{{equation*}}
I_{{cc3\\phi}} = \\frac{{V_{{fase}}}}{{|\\vec{{Z}}_{{acum}}^{{20^\\circ C}}|}}
\\end{{equation*}}
\\textbf{{Curto-Circuito Fase-Neutro (Verificação Magnética Mínima):}}
\\begin{{equation*}}
I_{{cc1\\phi}} = \\frac{{0,95 \\cdot V_{{fase}}}}{{|\\vec{{Z}}_{{acum,F}}^{{T_{{max}}}} + \\vec{{Z}}_{{acum,N}}^{{T_{{max}}}}|}}
\\end{{equation*}}

\\subsection*{{4. Resumo Físico Paramétrico da Malha}}
\\begin{{longtable}}{{ccccccc}}
\\toprule
\\textbf{{Circuito}} & \\textbf{{Cabo (mm²)}} & \\textbf{{L (m)}} & \\textbf{{$\\Delta V$}} & \\textbf{{Icc Mín (A)}} & \\textbf{{Icc Máx (A)}} & \\textbf{{Ip Pico (A)}} \\\\
\\midrule
\\endhead
{linhas_tex_mem}
\\bottomrule
\\end{{longtable}}
\\end{{document}}
"""
                st.download_button(
                    label="Baixar Memorial para Compilador (.tex)",
                    data=latex_mem_source,
                    file_name=f"Memorial_{projeto_atual.nome_projeto}.tex",
                    mime="text/plain",
                    use_container_width=True
                )

db.close()