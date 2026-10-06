import sqlite3

def atualizar_banco():
    # Substitua 'database.db' pelo nome exato do seu arquivo de banco de dados
    conn = sqlite3.connect('zeta.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE quadros ADD COLUMN condutores_por_fase INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE circuitos ADD COLUMN condutores_por_fase INTEGER DEFAULT 1")
        conn.commit()
        print("Migração concluída com sucesso. Colunas adicionadas.")
    except sqlite3.OperationalError as e:
        print(f"Aviso: {e} (As colunas provavelmente já existem).")
    finally:
        conn.close()

if __name__ == "__main__":
    atualizar_banco()