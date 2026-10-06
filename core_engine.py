import math
import cmath
from sqlalchemy.orm import Session
import catalog_manager

FATOR_CATALOGO_20C = {'PVC': 1.197, 'HEPR': 1.275, 'XLPE': 1.275} # Operação a 70°C / 90°C (Industrial)
FATOR_RESIDENCIAL  = {'PVC': 1.098, 'HEPR': 1.138, 'XLPE': 1.138} # Operação a 45°C / 55°C (Residencial)

class MotorNodalV4:

    def __init__(self, db: Session, perfil_carga: str = 'INDUSTRIAL'):
        self.db = db
        self.perfil_carga = perfil_carga.upper()

    def obter_impedancia_cabo(self, bitola: float, isolacao: str, cenario: str = 'CARGA') -> complex:
        iso = isolacao.upper().strip()
        
        # --- INTERCEPTAÇÃO DE BARRAMENTO BLINDADO ---
        if iso == 'BARRAMENTO':
            amp = float(bitola)
            # Matriz Novemp MBM/MBC embarcada: Amperagem -> (R_20C, R_op, X) em Ohms/km
            tabela_bw = {
                250:  (0.2218, 0.2874, 0.1651), 450:  (0.1344, 0.1767, 0.1290),
                550:  (0.0685, 0.1088, 0.0952), 800:  (0.0732, 0.0939, 0.0205),
                1000: (0.0525, 0.0767, 0.0168), 1250: (0.0416, 0.0578, 0.0132),
                1600: (0.0348, 0.0501, 0.0118), 2000: (0.0266, 0.0355, 0.0095),
                2500: (0.0214, 0.0285, 0.0112), 3000: (0.0171, 0.0234, 0.0074),
                3500: (0.0158, 0.0224, 0.0080), 4000: (0.0132, 0.0182, 0.0057)
            }
            
            if amp in tabela_bw:
                r_20c, r_op, x_base = tabela_bw[amp]
            else:
                raise ValueError(f"Corrente nominal de {amp}A para Barramento não mapeada na matriz Novemp.")
                
            r_final = r_20c if cenario.upper() == 'ICC_MAX' else r_op
            return complex(r_final, x_base)
        # --------------------------------------------

        r_cat_hot, x_base = catalog_manager.consultar_impedancia(self.db, bitola, iso)
        
        # Descompactação da resistência real a frio (20°C)
        fator_ind = FATOR_CATALOGO_20C.get(iso, 1.0)
        r_20c = r_cat_hot / fator_ind
        
        if cenario.upper() == 'ICC_MAX':
            r_final = r_20c
        else:
            # Aplicação do Abrandamento Térmico Dinâmico da Instância
            if 'RESIDENCIAL' in self.perfil_carga:
                r_final = r_20c * FATOR_RESIDENCIAL.get(iso, 1.0)
            else:
                r_final = r_cat_hot
                
        return complex(r_final, x_base)

    def obter_impedancia_neutro(self, bitola_n: float, isolacao: str, cenario: str = 'CARGA') -> complex:
        return self.obter_impedancia_cabo(bitola_n, isolacao, cenario)

    def inicializar_noh_transformador(self, s_kVA: float, z_pct: float, v_ll: float = 220.0, xr_ratio: float = 4.0) -> dict:
        v_fn    = v_ll / math.sqrt(3)
        z_base  = (v_ll ** 2) / (s_kVA * 1000.0)
        z_mag   = z_base * (z_pct / 100.0)
        theta   = math.atan(xr_ratio)
        z1      = complex(z_mag * math.cos(theta), z_mag * math.sin(theta))
        return {
            'v_nodal_fasor':       cmath.rect(v_fn, 0.0),
            'z1_acumulado':        z1,
            'z1_frio_acumulado':   z1, 
            'z_retorno_acumulado': z1,
            'isolacao':            None,
            'queda_acumulada_pct': 0.0,
            'queda_trecho_pct':    0.0,
            'v_ll_nominal':        v_ll,
        }

    def propagar_tensao_nodal(self, estado_pai: dict, comprimento_m: float, bitola: float, corrente_A: float, fp: float, isolacao: str, topologia: str, bitola_neutro: float = None, bitola_pe: float = None, n_condutores: int = 1) -> dict:
        
        n_cond = float(max(1, n_condutores))
        
        z1_km_single      = self.obter_impedancia_cabo(bitola, isolacao, cenario='CARGA')
        z1_frio_km_single = self.obter_impedancia_cabo(bitola, isolacao, cenario='ICC_MAX')
        
        z1_km      = z1_km_single / n_cond
        z1_frio_km = z1_frio_km_single / n_cond
        
        dist_km = comprimento_m / 1000.0
        fp_clamped = max(-1.0, min(1.0, float(fp)))
        i_fasor    = cmath.rect(corrente_A, -math.acos(fp_clamped))
        topo       = topologia.upper()
        v_ll_nom   = estado_pai.get('v_ll_nominal', 220.0)
        v_fn_nom   = v_ll_nom / math.sqrt(3)
        bn = bitola_neutro if bitola_neutro is not None else bitola
        bpe = bitola_pe if bitola_pe is not None else bn 
        
        z_n_km_single  = self.obter_impedancia_neutro(bn, isolacao, cenario='CARGA')
        z_n_km         = z_n_km_single / n_cond
        
        z_pe_km_single = self.obter_impedancia_cabo(bpe, isolacao, cenario='ICC_MAX')
        z_pe_km        = z_pe_km_single / n_cond
        
        if topo in ['3F', '3F+N', 'TRIFASICO']:
            dv = (z1_km * dist_km) * i_fasor
        elif topo in ['F-N', 'MONOFASICO']:
            dv = ((z1_km + z_n_km) * dist_km) * i_fasor
        elif topo in ['F-F', 'BIFASICO']:
            dv = ((z1_km * 2.0 * dist_km) * i_fasor) / math.sqrt(3)
        else:
            dv = (z1_km * dist_km) * i_fasor
            
        v_novo = estado_pai['v_nodal_fasor'] - dv
        queda_acum = ((v_fn_nom - abs(v_novo)) / v_fn_nom) * 100.0
        queda_trecho = queda_acum - estado_pai.get('queda_acumulada_pct', 0.0)
        
        z1_frio_pai = estado_pai.get('z1_frio_acumulado', estado_pai['z1_acumulado'])
        
        return {
            'v_nodal_fasor':       v_novo,
            'z1_acumulado':        estado_pai['z1_acumulado']        + (z1_km      * dist_km),
            'z1_frio_acumulado':   z1_frio_pai                       + (z1_frio_km * dist_km),
            'z_retorno_acumulado': estado_pai['z_retorno_acumulado'] + (z_pe_km    * dist_km), 
            'isolacao':            isolacao.upper(),
            'queda_acumulada_pct': queda_acum,
            'queda_trecho_pct':    queda_trecho,
            'v_ll_nominal':        v_ll_nom,
        }

    def calcular_icc(self, estado_noh: dict, v_ll_nominal: float = 220.0, tipo_curto: str = 'FN_METALICO', modo: str = 'MIN') -> float:
        v_fn    = v_ll_nominal / math.sqrt(3)
        
        if modo.upper() == 'MIN':
            c = 0.95
            z1 = estado_noh['z1_acumulado']
        else:
            c = 1.05
            z1 = estado_noh.get('z1_frio_acumulado', estado_noh['z1_acumulado'])
            
        v_drive = v_fn * c
        zr  = estado_noh['z_retorno_acumulado']
        z2  = z1

        def _div(n, d, lbl):
            if abs(d) < 1e-9:
                raise ZeroDivisionError(f"Impedância '{lbl}' nula — verifique dados.")
            return n / d
            
        t = tipo_curto.upper()
        if   t == 'FN_METALICO': icc = _div(v_drive,               z1 + zr,      'Z1+Zret')
        elif t == 'SLG':         icc = _div(3.0 * v_drive,         z1 + z2 + zr, 'Z1+Z2+Zret')
        elif t == '3F':          icc = _div(v_drive,               z1,           'Z1')
        elif t == 'FF':          icc = _div(v_drive * math.sqrt(3), z1 + z2,     'Z1+Z2')
        else:                    icc = _div(v_drive,               z1,           'fallback')
        return abs(icc)

    def calcular_ip(self, icc_rms_A: float, xr_ratio: float) -> float:
        kappa = 1.02 + 0.98 * math.exp(-3.0 / max(xr_ratio, 0.01))
        return kappa * math.sqrt(2) * icc_rms_A

    def validar_protecao(self, icc_min_A, icc_max_A, in_disj, curva, icu_disj, bitola, isolacao, t_max_s=0.4, n_condutores=1):
        multiplicadores = {'B': 5, 'C': 10, 'D': 20}
        corrente_disparo_mag = multiplicadores.get(curva.upper(), 10) * in_disj
        
        status_mag = "OK" if icc_min_A >= corrente_disparo_mag else "REVISAR"
        status_icu = "OK" if icu_disj >= icc_max_A else "REVISAR"
        
        k = 115 if isolacao.upper() == 'PVC' else 143
        if icc_min_A >= corrente_disparo_mag:
            t_atuacao_disj = 0.02
        else:
            t_atuacao_disj = t_max_s  
            
        bitola_efetiva_total = bitola * max(1, n_condutores)
        
        t_suporta_max = ((k * bitola_efetiva_total) ** 2) / (max(icc_max_A, 1e-9) ** 2)
        t_suporta_min = ((k * bitola_efetiva_total) ** 2) / (max(icc_min_A, 1e-9) ** 2)
        
        tempo_limite_cabo = min(t_suporta_max, t_suporta_min)
        status_term = "OK" if t_atuacao_disj <= tempo_limite_cabo else "PERIGO"
        status_geral = "OK" if all(x == "OK" for x in [status_mag, status_icu, status_term]) else "REVISAR"
        
        return {
            'status_geral': status_geral,
            'magnetico': {'status': status_mag, 'limiar_A': corrente_disparo_mag},
            'poder_de_corte': {'status': status_icu, 'icu_disj_A': icu_disj},
            'termico': {'status': status_term, 't_suportado_s': tempo_limite_cabo}
        }
    
    def validar_queda_tensao(self, queda_acumulada_pct: float, queda_trecho_pct: float, tipo_circuito: str, tem_trafo_proprio: bool = True) -> dict:
        limite_trecho = {
            'ALIMENTADOR':    5.0,
            'TERMINAL':       5.0,
            'MOTOR_PARTIDA':  7.0,
        }.get(tipo_circuito.upper(), 4.0)
        
        limite_global = 7.0 if tem_trafo_proprio else 5.0
        falhas = []
        
        if queda_trecho_pct > limite_trecho:
            falhas.append(('TRECHO', limite_trecho, queda_trecho_pct))
        if queda_acumulada_pct > limite_global:
            falhas.append(('GLOBAL', limite_global, queda_acumulada_pct))
            
        if not falhas:
            return {
                'status': 'OK',
                'motivo': None,
                'limite_trecho_pct':  limite_trecho,
                'limite_global_pct':  limite_global,
            }
            
        motivo, limite, valor = max(falhas, key=lambda x: x[2] - x[1])
        return {
            'status': 'REPROVADO',
            'motivo': motivo,
            'limite_trecho_pct':  limite_trecho,
            'limite_global_pct':  limite_global,
            'valor_violado_pct':  round(valor, 2),
            'limite_violado_pct': limite,
        }

    def gerar_sugestoes(self, res_qdt: dict, res_prot: dict, bitola_fase: float, bitola_neutro: float, tipo_circuito: str) -> str:
        sugs = []
        if res_qdt.get('status') == 'REPROVADO':
            if res_qdt.get('motivo') == 'GLOBAL':
                sugs.append(
                    f"Queda global {res_qdt.get('valor_violado_pct', 0):.1f}% > "
                    f"{res_qdt.get('limite_global_pct', 0):.0f}%: aumente seção do alimentador principal"
                )
            else:
                limite = res_qdt.get('limite_trecho_pct', 0)
                sugs.append(
                    f"Queda no trecho {res_qdt.get('valor_violado_pct','?'):.1f}% > "
                    f"{limite:.0f}%: aumente seção ou reduza comprimento"
                )
                
        if res_prot.get('magnetico', {}).get('status') == 'REVISAR':
            limiar = res_prot['magnetico'].get('limiar_A', 0)
            sugs.append(
                f"Icc_mín não aciona magnético (limiar {limiar:.0f} A): "
                "troque para curva B, reduza In ou aumente bitola"
            )
            
        if res_prot.get('termico', {}).get('status') == 'PERIGO':
            t = res_prot['termico'].get('t_suportado_s', 0)
            sugs.append(
                f"Risco térmico: cabo suporta {t:.3f} s — aumente seção ou use disjuntor mais rápido"
            )
            
        if res_prot.get('poder_de_corte', {}).get('status') == 'REVISAR':
            icu = res_prot['poder_de_corte'].get('icu_disj_A', 0)
            sugs.append(
                f"Icu insuficiente ({icu:.0f} A): "
                "especifique disjuntor com maior ruptura"
            )
            
        if bitola_neutro < bitola_fase * 0.5:
            sugs.append(
                "Neutro < 50% da fase: atenção para cargas não-lineares (NBR 5410 §6.2.2.1)"
            )
            
        return " | ".join(sugs) if sugs else "Conforme"