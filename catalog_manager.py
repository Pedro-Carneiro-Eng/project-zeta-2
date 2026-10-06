import pandas as pd
from sqlalchemy.orm import Session
import models

def importar_catalogo_csv(db: Session, caminho_csv: str, isolacao: str, fabricante: str = "Prysmian"):
    df = pd.read_csv(caminho_csv, sep=',')
    df.columns = df.columns.str.replace(';', '').str.strip()
    isolacao = isolacao.upper().strip()
    db.query(models.CaboCatalogo).filter(
        models.CaboCatalogo.fabricante == fabricante,
        models.CaboCatalogo.isolacao == isolacao
    ).delete()
    novos_cabos = []
    for index, row in df.iterrows():
        cabo = models.CaboCatalogo(
            fabricante=fabricante,
            isolacao=isolacao,
            bitola_mm2=float(row['bitola_mm2']),
            r_ca_ohm_km=float(row['resistencia_ca_ohm_km']),
            x_ohm_km=float(row['reatancia_ohm_km'])
        )
        novos_cabos.append(cabo)
    db.add_all(novos_cabos)
    db.commit()
    return len(novos_cabos)

def consultar_impedancia(db: Session, bitola: float, isolacao: str, fabricante: str = "Prysmian"):
    cabo = db.query(models.CaboCatalogo).filter(
        models.CaboCatalogo.fabricante == fabricante,
        models.CaboCatalogo.isolacao == isolacao.upper().strip(),
        models.CaboCatalogo.bitola_mm2 >= bitola - 0.01,
        models.CaboCatalogo.bitola_mm2 <= bitola + 0.01
    ).first()
    if not cabo:
        raise ValueError(f"Bitola {bitola} mm² ({isolacao}) do fabricante {fabricante} não encontrada no banco.")
    return cabo.r_ca_ohm_km, cabo.x_ohm_km