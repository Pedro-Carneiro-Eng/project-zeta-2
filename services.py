from sqlalchemy.orm import Session
import models

def criar_cliente(db: Session, nome: str, cpf_cnpj: str = None, telefone: str = None, email: str = None):
    novo_cliente = models.Cliente(
        nome=nome,
        cpf_cnpj=cpf_cnpj,
        telefone=telefone,
        email=email
    )
    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)
    return novo_cliente

def listar_clientes(db: Session):
    return db.query(models.Cliente).all()

def criar_projeto(db: Session, cliente_id: int, nome_projeto: str, descricao: str = None, v_secundaria: float = 220.0, trafo_kva: float = 152.5):
    novo_projeto = models.Projeto(
        cliente_id=cliente_id,
        nome_projeto=nome_projeto,
        descricao=descricao,
        tensao_secundaria=v_secundaria,
        potencia_transformador=trafo_kva
    )
    db.add(novo_projeto)
    db.commit()
    db.refresh(novo_projeto)
    return novo_projeto

def criar_quadro(db: Session, projeto_id: int, nome: str, tipo: str, quadro_pai_id: int = None, condutores_por_fase: int = 1):
    novo_quadro = models.Quadro(
        projeto_id=projeto_id,
        nome=nome,
        tipo=tipo,
        quadro_pai_id=quadro_pai_id,
        condutores_por_fase=condutores_por_fase
    )
    db.add(novo_quadro)
    db.commit()
    db.refresh(novo_quadro)
    return novo_quadro

def adicionar_circuito(db: Session, quadro_id: int, dados_circuito: dict):
    novo_circuito = models.Circuito(
        quadro_id=quadro_id,
        nome=dados_circuito.get('nome'),
        tipo=dados_circuito.get('tipo'),
        fases=dados_circuito.get('fases'),
        comprimento_m=dados_circuito.get('comprimento_m'),
        ib_A=dados_circuito.get('ib_A'),
        fp=dados_circuito.get('fp', 0.92),
        isolacao=dados_circuito.get('isolacao'),
        bitola_mm2=dados_circuito.get('bitola_mm2'),
        bitola_neutro_mm2=dados_circuito.get('bitola_neutro_mm2'),
        bitola_pe_mm2=dados_circuito.get('bitola_pe_mm2'),
        in_disj=dados_circuito.get('in_disj'),
        curva_disj=dados_circuito.get('curva_disj'),
        icu_disj=dados_circuito.get('icu_disj'),
        condutores_por_fase=dados_circuito.get('condutores_por_fase', 1)
    )
    db.add(novo_circuito)
    db.commit()
    db.refresh(novo_circuito)
    return novo_circuito

def listar_circuitos_do_projeto(db: Session, projeto_id: int):
    return db.query(models.Circuito).join(models.Quadro).filter(models.Quadro.projeto_id == projeto_id).all()