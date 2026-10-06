from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    cpf_cnpj = Column(String, unique=True, index=True)
    telefone = Column(String)
    email = Column(String)
    observacoes = Column(String)
    projetos = relationship("Projeto", back_populates="cliente", cascade="all, delete-orphan")

class Projeto(Base):
    __tablename__ = "projetos"
    
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    nome_projeto = Column(String, nullable=False)
    descricao = Column(String)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_modificacao = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tensao_secundaria = Column(Float, default=220.0)
    potencia_transformador = Column(Float, default=152.5)
    concessionaria = Column(String, default="CEMIG")
    cliente = relationship("Cliente", back_populates="projetos")
    quadros = relationship("Quadro", back_populates="projeto", cascade="all, delete-orphan")

class Quadro(Base):
    __tablename__ = "quadros"

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"))
    quadro_pai_id = Column(Integer, ForeignKey("quadros.id"), nullable=True)
    nome = Column(String, nullable=False)
    tipo = Column(String)
    localizacao = Column(String)
    tensao_operacao = Column(Float, default=220.0)
    capacidade_nominal_A = Column(Float, default=0.0)
    comprimento_alimentador_m = Column(Float, default=0.0)
    fases_alimentador = Column(String, default="TRIFASICO")
    ib_alimentador_A = Column(Float, default=0.0) 
    bitola_alimentador_mm2 = Column(Float, default=10.0)
    condutores_por_fase = Column(Integer, default=1)
    bitola_neutro_alimentador_mm2 = Column(Float, default=10.0)
    bitola_pe_alimentador_mm2 = Column(Float, default=10.0)
    isolacao_alimentador = Column(String, default="PVC")
    disjuntor_alimentador_A = Column(Float, default=50.0)
    curva_alimentador = Column(String, default="C")
    icu_alimentador_kA = Column(Float, default=10.0)
    projeto = relationship("Projeto", back_populates="quadros")
    subquadros = relationship("Quadro", backref="quadro_pai", remote_side=[id])
    circuitos = relationship("Circuito", back_populates="quadro", cascade="all, delete-orphan")

class Circuito(Base):
    __tablename__ = "circuitos"

    id = Column(Integer, primary_key=True, index=True)
    quadro_id = Column(Integer, ForeignKey("quadros.id"))
    nome = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    fases = Column(String)
    comprimento_m = Column(Float)
    ib_A = Column(Float)
    fp = Column(Float, default=0.92)
    isolacao = Column(String)
    condutores_por_fase = Column(Integer, default=1)
    bitola_mm2 = Column(Float)
    bitola_neutro_mm2 = Column(Float)
    bitola_pe_mm2 = Column(Float)
    in_disj = Column(Float)
    curva_disj = Column(String)
    icu_disj = Column(Float)
    quadro = relationship("Quadro", back_populates="circuitos")
    resultado = relationship("Resultado", back_populates="circuito", uselist=False, cascade="all, delete-orphan")

class Resultado(Base):
    __tablename__ = "resultados"

    id = Column(Integer, primary_key=True, index=True)
    circuito_id = Column(Integer, ForeignKey("circuitos.id"), unique=True)
    z_malha_ohm = Column(Float)
    v_nodal_v = Column(Float)
    queda_acum_pct = Column(Float)
    queda_trecho_pct = Column(Float)
    icc_min_a = Column(Float)
    icc_max_a = Column(Float)
    ip_pico_a = Column(Float)
    tempo_atuacao_s = Column(Float)
    i2t_cabo = Column(Float)
    i2t_curto = Column(Float)
    status_qdt = Column(String)
    status_mag = Column(String)
    status_termico = Column(String)
    status_icu = Column(String)
    veredito_final = Column(String)
    circuito = relationship("Circuito", back_populates="resultado")

class CaboCatalogo(Base):
    __tablename__ = "catalogo_cabos"

    id = Column(Integer, primary_key=True, index=True)
    fabricante = Column(String, default="Prysmian")
    isolacao = Column(String)
    bitola_mm2 = Column(Float)
    r_ca_ohm_km = Column(Float)
    x_ohm_km = Column(Float)