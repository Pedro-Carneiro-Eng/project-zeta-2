from database import SessionLocal
from catalog_manager import importar_catalogo_csv


db = SessionLocal()

caminho_pvc = r"C:\Users\Admin\Documents\Project Zeta 2.0\catalogo\Prysmian_70_PVC.csv"
caminho_hepr = r"C:\Users\Admin\Documents\Project Zeta 2.0\catalogo\Prysmian_90_HEPR.csv"

try:
    qtd_pvc = importar_catalogo_csv(db, caminho_pvc, isolacao="PVC")
    print(f"Sucesso! {qtd_pvc} cabos de PVC foram adicionados ao banco de dados.")
    
    qtd_hepr = importar_catalogo_csv(db, caminho_hepr, isolacao="HEPR")
    print(f"Sucesso! {qtd_hepr} cabos de HEPR foram adicionados ao banco de dados.")
except Exception as e:
    print(f"Erro ao importar: {e}")
finally:
    db.close()