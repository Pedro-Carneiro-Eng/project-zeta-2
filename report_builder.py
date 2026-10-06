import pandas as pd
import services
from core_engine import MotorNodalV4 # Se o seu arquivo se chama motor.py, mude para: from motor import MotorNodalV4
import math
import os

def load_busway_data():
    try:
        return pd.read_csv("Novemp_Barramento.csv")
    except:
        data = {
            'Corrente_A': [250, 450, 550, 800, 1000, 1250, 1600, 2000, 2500, 3000, 3500, 4000],
            'R_20C': [0.2218, 0.1344, 0.0685, 0.0732, 0.0525, 0.0416, 0.0348, 0.0266, 0.0214, 0.0171, 0.0158, 0.0132],
            'R_op': [0.2874, 0.1767, 0.1088, 0.0939, 0.0767, 0.0578, 0.0501, 0.0355, 0.0285, 0.0234, 0.0224, 0.0182],
            'X': [0.1651, 0.1290, 0.0952, 0.0205, 0.0168, 0.0132, 0.0118, 0.0095, 0.0112, 0.0074, 0.0080, 0.0057],
            'Icw_kA': [12.0, 15.0, 17.0, 20.0, 25.0, 44.5, 44.5, 44.5, 44.5, 87.0, 87.0, 87.0]
        }
        return pd.DataFrame(data)

df_busway = load_busway_data()

def fmt_cabo(bitola, is_bw=False, cabos=1):
    if is_bw: return f"{bitola:g}A (BW)"
    s_cab = f"{cabos}x " if cabos > 1 else ""
    return f"{s_cab}#{bitola:.1f} mm²".replace('.', ',')
    
def fmt_pe(bitola, cabos=1):
    if bitola <= 0: return "0 (PEN)"
    s_cab = f"{cabos}x " if cabos > 1 else ""
    return f"{s_cab}#{bitola:.1f} mm²".replace('.', ',')

def montar_pacote_relatorio(db, projeto_id, v_linha=220.0, trafo_kva=152.5, tem_trafo=False, perfil_carga='INDUSTRIAL'):
    circuitos_db = services.listar_circuitos_do_projeto(db, projeto_id)
    quadros_db = db.query(services.models.Quadro).filter(
        services.models.Quadro.projeto_id == projeto_id
    ).all()
    
    if not circuitos_db and not quadros_db:
        return None

    filhos_quadro = {None: []}
    mapa_quadros = {}
    for q in quadros_db:
        filhos_quadro[q.id] = []
        mapa_quadros[q.id] = q

    for q in quadros_db:
        pai = q.quadro_pai_id
        if pai not in filhos_quadro:
            filhos_quadro[pai] = []
        filhos_quadro[pai].append(q)

    dados = []
    ordem_interna = 0

    def visitar_noh(quadro_id):
        nonlocal ordem_interna
        subquadros = sorted(filhos_quadro.get(quadro_id, []), key=lambda x: x.nome)
        
        for sq in subquadros:
            quadro_origem = "CEMIG"
            if sq.quadro_pai_id and sq.quadro_pai_id in mapa_quadros:
                quadro_origem = mapa_quadros[sq.quadro_pai_id].nome
                
            dados.append({
                '_ordem_topologica': ordem_interna,
                'id_circuito': sq.nome, 
                'is_panel': True, 
                'quadro_origem': quadro_origem, 
                'fases': sq.fases_alimentador or 'TRIFASICO',
                'comprimento_m': float(sq.comprimento_alimentador_m or 0.0), 
                'ib_A': float(sq.ib_alimentador_A or 0.0), 
                'fp': 0.92, 
                'isolacao': sq.isolacao_alimentador or 'PVC',
                'bitola_mm2': float(sq.bitola_alimentador_mm2 or 0.0), 
                'bitola_neutro_mm2': float(sq.bitola_neutro_alimentador_mm2 or 0.0),
                'bitola_pe_mm2': float(sq.bitola_pe_alimentador_mm2 or 0.0), 
                'condutores_por_fase': int(getattr(sq, 'condutores_por_fase', 1) or 1),
                'in_disj': float(sq.disjuntor_alimentador_A or 0.0), 
                'curva': sq.curva_alimentador or 'C', 
                'icu_disj': float(sq.icu_alimentador_kA * 1000.0) if sq.icu_alimentador_kA else 10000.0
            })
            ordem_interna += 1
            visitar_noh(sq.id)

        circuitos = sorted([c for c in circuitos_db if c.quadro_id == quadro_id], key=lambda x: x.nome)
        for c in circuitos:
            quadro_origem = "CEMIG"
            if c.quadro:
                quadro_origem = c.quadro.nome
                
            dados.append({
                '_ordem_topologica': ordem_interna,
                'id_circuito': c.nome, 
                'is_panel': False,
                'quadro_origem': quadro_origem, 
                'fases': c.fases,
                'comprimento_m': float(c.comprimento_m or 0.0), 
                'ib_A': float(c.ib_A or 0.0), 
                'fp': float(c.fp or 0.92), 
                'isolacao': c.isolacao or 'PVC',
                'bitola_mm2': float(c.bitola_mm2 or 0.0), 
                'bitola_neutro_mm2': float(c.bitola_neutro_mm2 or 0.0),
                'bitola_pe_mm2': float(c.bitola_pe_mm2 or 0.0), 
                'condutores_por_fase': int(getattr(c, 'condutores_por_fase', 1) or 1),
                'in_disj': float(c.in_disj or 0.0), 
                'curva': c.curva_disj or 'C', 
                'icu_disj': float(c.icu_disj or 10000.0)
            })
            ordem_interna += 1

    visitar_noh(None)
    
    df_proj = pd.DataFrame(dados)

    motor = MotorNodalV4(db, perfil_carga=perfil_carga)
    memoria = {
        'TRANSFORMADOR': motor.inicializar_noh_transformador(s_kVA=trafo_kva, z_pct=4.0, v_ll=v_linha, xr_ratio=4.0),
        'CEMIG': motor.inicializar_noh_transformador(s_kVA=trafo_kva, z_pct=4.0, v_ll=v_linha, xr_ratio=4.0)
    }
    
    projetos_dict = df_proj.set_index('id_circuito').to_dict('index')
    for cid, data in projetos_dict.items(): 
        data['id_circuito'] = str(cid).strip()

    def resolver_noh(circ_id, caminho_atual=None):
        if caminho_atual is None: caminho_atual = set()
        if circ_id in caminho_atual: raise ValueError(f"Loop infinito na origem '{circ_id}'.")
        if circ_id in memoria: return memoria[circ_id]
        if circ_id not in projetos_dict: raise ValueError(f"Referência '{circ_id}' não encontrada.")
        
        caminho_atual.add(circ_id)
        linha = projetos_dict[circ_id]
        
        res_pai = resolver_noh(str(linha['quadro_origem']).strip(), caminho_atual)
        estado_pai = res_pai[0] if isinstance(res_pai, tuple) else res_pai

        bitola_efetiva = float(linha['bitola_mm2'])
        if bitola_efetiva == 0.0: bitola_efetiva = 1.0

        bn_val = float(linha.get('bitola_neutro_mm2', 0.0))
        bpe_val = float(linha.get('bitola_pe_mm2', 0.0))

        bn_calculo = bn_val if bn_val > 0.0 else bitola_efetiva
        bpe_calculo = bpe_val if bpe_val > 0.0 else bn_calculo

        estado = motor.propagar_tensao_nodal(
            estado_pai=estado_pai, comprimento_m=float(linha['comprimento_m']),
            bitola=bitola_efetiva, corrente_A=float(linha['ib_A']), fp=float(linha['fp']),
            isolacao=str(linha['isolacao']).strip(), topologia=str(linha['fases']).strip(), 
            bitola_neutro=bn_calculo, bitola_pe=bpe_calculo,
            n_condutores=int(linha.get('condutores_por_fase', 1))
        )

        if linha.get('is_panel', False): 
            memoria[str(linha['id_circuito']).strip()] = estado

        caminho_atual.remove(circ_id)
        return estado, linha

    linhas_relatorio = []
    linhas_memorial = []
    
    ordenados_id = sorted(projetos_dict.keys(), key=lambda x: projetos_dict[x]['_ordem_topologica'])

    for circ_id in ordenados_id:
        retorno_noh = resolver_noh(circ_id)
        estado, row = retorno_noh if isinstance(retorno_noh, tuple) else (retorno_noh, projetos_dict[circ_id])
        
        bitola_exibicao = float(row['bitola_mm2'])
        bn_ex = float(row.get('bitola_neutro_mm2', 0.0))
        bpe_ex = float(row.get('bitola_pe_mm2', 0.0))
        bn_real = bn_ex if bn_ex > 0 else (bitola_exibicao if bitola_exibicao > 0 else 0)
        
        qtd_cabos = int(row.get('condutores_por_fase', 1) or 1)

        v_fase_noh = abs(estado['v_nodal_fasor'])
        v_laudo = v_fase_noh * math.sqrt(3) if str(row['fases']).strip().upper() in ['3F', '3F+N', 'TRIFASICO', 'F-F', 'BIFASICO'] else v_fase_noh
        q_acum = estado['queda_acumulada_pct']
        q_trecho = estado['queda_trecho_pct']

        # --- RADAR DE TOPOLOGIA: LAÇO BIPOLAR ATIVO ---
        fases_tipo = str(row['fases']).strip().upper()
        
        if fases_tipo in ['F-N', 'MONOFASICO']:
            t_max = 'FN_METALICO'
            t_min = 'FN_METALICO'
        elif fases_tipo in ['F-F', 'BIFASICO']:
            t_max = 'FF'
            t_min = 'FF'
        else: # TRIFASICO (3F)
            t_max = '3F'
            t_min = 'FN_METALICO' if bn_ex > 0 else 'FF'

        icc_min = motor.calcular_icc(estado, v_linha, t_min, 'MIN')
        icc_max = motor.calcular_icc(estado, v_linha, t_max, 'MAX')
        
        xr = estado['z1_acumulado'].imag / max(estado['z1_acumulado'].real, 1e-9)
        ip = motor.calcular_ip(icc_max, xr)
        
        in_disj_val = float(row['in_disj'])
        is_busway = str(row['isolacao']).strip().upper() == 'BARRAMENTO'
        
        curva_raw = str(row['curva']).strip()
        qtd_disj = 1
        if '|' in curva_raw:
            parts = curva_raw.split('|')
            curva_original = parts[0]
            try: qtd_disj = int(parts[1])
            except: pass
        else:
            curva_original = curva_raw
            
        is_casc = 'CASC' in curva_original.upper()
        curva_motor = curva_original.upper().replace('(CASC.)', '').replace('(CASC)', '').strip()
        if not curva_motor: curva_motor = 'C'
        
        if in_disj_val == 0.0:
            disj_str_display = f"0.0A ({curva_original})"
        else:
            s_disj = f"{qtd_disj}x " if qtd_disj > 1 else ""
            disj_str_display = f"{s_disj}{in_disj_val:g}A ({curva_original})"
        
        cabo_exibicao = fmt_cabo(bitola_exibicao, is_busway, qtd_cabos)
        neutro_exibicao = "-" if is_busway else fmt_cabo(bn_real, False, qtd_cabos)
        str_cabo_memorial = fmt_cabo(bitola_exibicao, True, 1) if is_busway else f"{fmt_cabo(bitola_exibicao, False, qtd_cabos)} / {fmt_cabo(bn_real, False, qtd_cabos)} / {fmt_pe(bpe_ex, qtd_cabos)}"
        
        # --- AVALIAÇÃO DE PROTEÇÃO E QUEDA DE TENSÃO ---
        if in_disj_val == 0.0:
            res_prot = {'status_geral': 'OK', 'magnetico': {'status': 'N/A'}, 'termico': {'status': 'N/A'}, 'poder_de_corte': {'status': 'N/A'}}
            i_mag, t_atuacao, i2t_suportado, i2t_curto = 0.0, 0.0, 0.0, 0.0
            status_termico = 'N/A'
        else:
            res_prot = motor.validar_protecao(icc_min, icc_max, in_disj_val, curva_motor, float(row.get('icu_disj', 10000)), bitola_exibicao if bitola_exibicao > 0 else 1.0, str(row['isolacao']).strip(), 0.4, n_condutores=qtd_cabos)
            
            if is_casc:
                res_prot['termico']['status'] = 'OK'
                res_prot['termico']['t_suportado_s'] = 999.0
                res_prot['poder_de_corte']['status'] = 'OK'
                if res_prot['magnetico']['status'] == 'OK':
                    res_prot['status_geral'] = 'OK'

        res_qdt = motor.validar_queda_tensao(q_acum, q_trecho, 'ALIMENTADOR' if row.get('is_panel') else 'TERMINAL', tem_trafo)
        
        # Correção: Aceita "OK" ou "N/A" (para nós de passagem) como aprovação do Icu
        if res_qdt['status'] == 'OK' and res_prot['status_geral'] == 'OK' and res_prot['poder_de_corte']['status'] in ['OK', 'N/A']:
            veredito = 'APROV. (CASC.)' if is_casc and in_disj_val != 0.0 else 'APROVADO'
        else:
            veredito = 'REVISAR'
            
        sug = motor.gerar_sugestoes(res_qdt, res_prot, bitola_exibicao if bitola_exibicao > 0 else 1.0, bn_real if bn_real > 0 else 1.0, 'ALIMENTADOR' if row.get('is_panel') else 'TERMINAL')
        
        icu_exibicao = float(row.get('icu_disj', 10000)) / 1000.0
        
        # Formatação do texto de Sugestões Técnicas
        if in_disj_val == 0.0:
            if res_qdt['status'] == 'OK':
                sug_final = f"Nó de Referência (Passagem) -> Queda: {q_acum:.2f}%"
            else:
                sug_final = f"{sug} -> (Queda: {q_acum:.2f}%)"
        else:
            if veredito == 'APROV. (CASC.)':
                sug_final = f"Retaguarda Ativa (Filiação) -> Queda: {q_acum:.2f}% | Icu Nativo: {icu_exibicao:g}kA"
            elif sug == "Conforme":
                sug_final = f"OK -> Queda: {q_acum:.2f}% | Icu: {icu_exibicao:g}kA"
            else:
                sug_final = f"{sug} -> (Queda: {q_acum:.2f}% | Icu: {icu_exibicao:g}kA)"

        curva_multi = {'B': 5, 'C': 10, 'D': 20}.get(curva_motor, 10)
        i_mag = curva_multi * in_disj_val
        t_atuacao = 0.02 if icc_min >= i_mag else 0.4
        
        if is_busway:
            amp_nominal = bitola_exibicao
            linha_bw = df_busway[df_busway['Corrente_A'] == amp_nominal]
            icw_ka = float(linha_bw['Icw_kA'].iloc[0]) if not linha_bw.empty else 12.0
            i2t_suportado = (icw_ka * 1000.0)**2 * 1.0 
        else:
            k_cabo = 115 if str(row['isolacao']).strip().upper() == 'PVC' else 143   
            i2t_suportado = (k_cabo * (bitola_exibicao if bitola_exibicao > 0 else 1.0) * float(qtd_cabos)) ** 2
            
        if is_casc:
            i2t_curto = 0.0 
            status_termico = 'CONFORME (CASC.)'
        else:
            i2t_curto = (icc_max ** 2) * t_atuacao
            if in_disj_val == 0.0:
                status_termico = 'N/A'
            else:
                status_termico = 'CONFORME' if i2t_suportado >= i2t_curto else 'VIOLADO'

        linhas_relatorio.append({
            'Ordem': int(row['_ordem_topologica']),
            'ID Circuito': circ_id, 'Quadro Origem': row['quadro_origem'],
            'Fases': row['fases'], 'Comp. (m)': float(row['comprimento_m']), 
            'Cabo (mm²)': cabo_exibicao,
            'Neutro (mm²)': neutro_exibicao, 
            'Ib (A)': float(row['ib_A']), 'FP': float(row['fp']),
            'Disjuntor': disj_str_display, 'Isolação': str(row['isolacao']).strip(),
            'Tensão (V)': round(v_laudo, 2), 'Queda Acum. (%)': round(q_acum, 2), 'Queda Trecho (%)': round(q_trecho, 2),
            'Icc Mín. (A)': round(icc_min, 1), 'Icc Máx. (A)': round(icc_max, 1), 'Ip Pico (A)': round(ip, 1),
            'Status Mag.': res_prot.get('magnetico', {}).get('status', 'N/A'), 'Status Térm.': res_prot.get('termico', {}).get('status', 'N/A'),
            'Status Icu': res_prot.get('poder_de_corte', {}).get('status', 'N/A'), 'Veredito': veredito, 'Sugestões Técnicas': sug_final
        })

        linhas_memorial.append({
            'Ordem': int(row['_ordem_topologica']),
            'ID Circuito': circ_id, 'L (m)': float(row['comprimento_m']), 'Isolação': str(row['isolacao']).strip(),
            'F/N/PE (mm²)': str_cabo_memorial, 'Tensão (V)': round(v_laudo, 2),
            'Disparo Mag. (A)': round(i_mag, 1), 'Icc Mín (A)': round(icc_min, 1), 'Icc Máx (A)': round(icc_max, 1),
            'Ip Pico (A)': round(ip, 1), 't (s)': round(t_atuacao, 3),
            'k²S² / Icw²t': f"{(i2t_suportado / 1_000_000):.1f}".replace(".", ","),
            'I²t (kA²s)': "Limitado" if is_casc else f"{(i2t_curto / 1_000_000):.1f}".replace(".", ","),
            'Status Térmico': status_termico
        })

    return {
        "projeto_id": projeto_id, "v_linha": v_linha, "trafo_kva": trafo_kva, "tem_trafo": tem_trafo,
        "df_executivo": pd.DataFrame(linhas_relatorio),
        "df_memorial": pd.DataFrame(linhas_memorial)
    }