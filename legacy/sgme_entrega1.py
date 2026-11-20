import sqlite3
import datetime
import os

DB_NAME = 'manutencao.db'

# ==========================================
# 1. CAMADA DE BANCO DE DADOS E SETUP
# ==========================================
def conectar():
    return sqlite3.connect(DB_NAME)

def inicializar_banco():
    banco_existe = os.path.exists(DB_NAME)
    conn = conectar()
    cursor = conn.cursor()

    # Criação das Tabelas
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        perfil TEXT NOT NULL,
                        status TEXT DEFAULT 'Disponível')''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS equipamentos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        descricao TEXT,
                        ativo INTEGER DEFAULT 1)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ordens_servico (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        equipamento_id INTEGER,
                        criador_id INTEGER,
                        tecnico_id INTEGER,
                        falha_apontada TEXT,
                        criticidade TEXT,
                        status TEXT DEFAULT 'Aberta',
                        diagnostico TEXT,
                        horas_trabalhadas REAL DEFAULT 0.0,
                        pecas_utilizadas TEXT,
                        parecer_gestor TEXT,
                        FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id),
                        FOREIGN KEY(criador_id) REFERENCES usuarios(id),
                        FOREIGN KEY(tecnico_id) REFERENCES usuarios(id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS historico (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        os_id INTEGER,
                        descricao TEXT,
                        data_hora TEXT,
                        FOREIGN KEY(os_id) REFERENCES ordens_servico(id))''')

    # Mock Data (Apenas na primeira execução)
    if not banco_existe:
        cursor.execute("INSERT INTO usuarios (nome, perfil) VALUES ('Gestor Admin', 'Gestor')")
        cursor.execute("INSERT INTO usuarios (nome, perfil) VALUES ('Tecnico Joao', 'Técnico')")
        cursor.execute("INSERT INTO equipamentos (nome, descricao) VALUES ('Torno Mecânico CNC', 'Equipamento de usinagem setor A')")
        conn.commit()

    conn.close()

def registrar_historico(os_id, descricao):
    conn = conectar()
    cursor = conn.cursor()
    data_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO historico (os_id, descricao, data_hora) VALUES (?, ?, ?)",
                   (os_id, descricao, data_atual))
    conn.commit()
    conn.close()

# ==========================================
# 2. FUNÇÕES COMPARTILHADAS
# ==========================================
def listar_equipamentos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, descricao, ativo FROM equipamentos")
    for row in cursor.fetchall():
        status = 'Ativo' if row[3] == 1 else 'Inativo'
        print(f"[{row[0]}] {row[1]} - {row[2]} ({status})")
    conn.close()

def listar_os():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, equipamento_id, status, criticidade FROM ordens_servico")
    print("\n--- Ordens de Serviço ---")
    for row in cursor.fetchall():
        print(f"OS [{row[0]}] | Equipamento ID: {row[1]} | Status: {row[2]} | Criticidade: {row[3]}")
    conn.close()

def abrir_chamado(usuario_id):
    listar_equipamentos()
    eq_id = input("ID do Equipamento: ")
    falha = input("Descrição da Falha: ")
    criticidade = input("Criticidade (Baixa/Media/Alta): ")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ordens_servico (equipamento_id, criador_id, falha_apontada, criticidade) VALUES (?, ?, ?, ?)",
                   (eq_id, usuario_id, falha, criticidade))
    os_id = cursor.lastrowid
    conn.commit()
    conn.close()

    registrar_historico(os_id, f"OS Aberta. Falha reportada: {falha}")
    print(f"Chamado aberto com sucesso! OS ID: {os_id}")

def ver_disponibilidade_tecnicos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, status FROM usuarios WHERE perfil = 'Técnico'")
    print("\n--- Status dos Técnicos ---")
    for row in cursor.fetchall():
        print(f"ID: {row[0]} | Nome: {row[1]} | Status: {row[2]}")
    conn.close()

def ver_detalhes_os():
    os_id = input("Digite o ID da OS para ver detalhes: ")
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ordens_servico WHERE id = ?", (os_id,))
    os_data = cursor.fetchone()
    if not os_data:
        print("OS não encontrada.")
        return

    print("\n=== DETALHES DA OS ===")
    print(f"ID: {os_data[0]} | Status: {os_data[6]} | Criticidade: {os_data[5]}")
    print(f"Falha: {os_data[4]}")
    print(f"Diagnóstico Técnico: {os_data[7]}")
    print(f"Horas: {os_data[8]} | Peças: {os_data[9]}")
    print(f"Parecer Gestor: {os_data[10]}")

    print("\n--- Histórico ---")
    cursor.execute("SELECT data_hora, descricao FROM historico WHERE os_id = ? ORDER BY id ASC", (os_id,))
    for hist in cursor.fetchall():
        print(f"[{hist[0]}] {hist[1]}")
    conn.close()

# ==========================================
# 3. FUNÇÕES EXCLUSIVAS DO GESTOR
# ==========================================
def atribuir_os():
    listar_os()
    ver_disponibilidade_tecnicos()
    os_id = input("\nID da OS: ")
    tec_id = input("ID do Técnico para alocar: ")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE ordens_servico SET tecnico_id = ?, status = 'Em Andamento' WHERE id = ?", (tec_id, os_id))
    cursor.execute("UPDATE usuarios SET status = 'Em Atendimento' WHERE id = ?", (tec_id,))
    conn.commit()
    conn.close()

    registrar_historico(os_id, f"OS alocada para o técnico ID {tec_id}")
    print("OS atribuída com sucesso!")

def encerramento_administrativo():
    listar_os()
    os_id = input("\nID da OS para encerramento/aprovação: ")
    acao = input("Ação (1-Aprovar e Fechar, 2-Cancelar): ")
    parecer = input("Parecer administrativo: ")

    novo_status = 'Concluída' if acao == '1' else 'Cancelada'

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE ordens_servico SET status = ?, parecer_gestor = ? WHERE id = ?", (novo_status, parecer, os_id))

    # Libera o técnico
    cursor.execute("SELECT tecnico_id FROM ordens_servico WHERE id = ?", (os_id,))
    tec_id = cursor.fetchone()[0]
    if tec_id:
        cursor.execute("UPDATE usuarios SET status = 'Disponível' WHERE id = ?", (tec_id,))

    conn.commit()
    conn.close()

    registrar_historico(os_id, f"Encerramento Administrativo: {novo_status}. Parecer: {parecer}")
    print(f"OS {novo_status} com sucesso!")

# ==========================================
# 4. FUNÇÕES EXCLUSIVAS DO TÉCNICO
# ==========================================
def registrar_diagnostico(usuario_id):
    os_id = input("ID da OS: ")
    diagnostico = input("Diagnóstico e causa-raiz: ")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE ordens_servico SET diagnostico = ? WHERE id = ? AND tecnico_id = ?", (diagnostico, os_id, usuario_id))
    conn.commit()
    conn.close()
    registrar_historico(os_id, f"Diagnóstico registrado: {diagnostico}")
    print("Diagnóstico salvo.")

def apontamento_reparos(usuario_id):
    os_id = input("ID da OS: ")
    horas = input("Horas trabalhadas (ex: 2.5): ")
    pecas = input("Peças/Materiais utilizados: ")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE ordens_servico SET horas_trabalhadas = horas_trabalhadas + ?, pecas_utilizadas = ? WHERE id = ? AND tecnico_id = ?",
                   (float(horas), pecas, os_id, usuario_id))
    conn.commit()
    conn.close()
    registrar_historico(os_id, f"Apontamento de reparo. Horas: {horas}, Peças: {pecas}")
    print("Reparo apontado com sucesso.")

def alterar_status_os(usuario_id):
    os_id = input("ID da OS: ")
    print("1 - Em Execução | 2 - Aguardando Peça | 3 - Reparo Finalizado")
    op = input("Novo Status: ")
    status_map = {'1': 'Em Execução', '2': 'Aguardando Peça', '3': 'Reparo Finalizado'}
    novo_status = status_map.get(op, 'Em Execução')

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE ordens_servico SET status = ? WHERE id = ? AND tecnico_id = ?", (novo_status, os_id, usuario_id))
    conn.commit()
    conn.close()
    registrar_historico(os_id, f"Status alterado para: {novo_status}")
    print("Status atualizado.")

# ==========================================
# 5. MENUS E FLUXO PRINCIPAL
# ==========================================
def menu_gestor(usuario):
    while True:
        print(f"\n=== PAINEL DO GESTOR: {usuario[1]} ===")
        print("1. Visualizar Equipamentos")
        print("2. Consultar Ordens de Serviço (Geral)")
        print("3. Abrir Novo Chamado (OS)")
        print("4. Ver Disponibilidade de Técnicos")
        print("5. Atribuir OS a Técnico")
        print("6. Aprovar e Encerrar OS")
        print("7. Ver Detalhes e Histórico de uma OS")
        print("0. Sair")

        op = input("Escolha: ")
        if op == '1': listar_equipamentos()
        elif op == '2': listar_os()
        elif op == '3': abrir_chamado(usuario[0])
        elif op == '4': ver_disponibilidade_tecnicos()
        elif op == '5': atribuir_os()
        elif op == '6': encerramento_administrativo()
        elif op == '7': ver_detalhes_os()
        elif op == '0': break

def menu_tecnico(usuario):
    while True:
        print(f"\n=== PAINEL DO TÉCNICO: {usuario[1]} ===")
        print("1. Visualizar Equipamentos")
        print("2. Minhas Ordens de Serviço (Geral)")
        print("3. Abrir Novo Chamado (OS)")
        print("4. Ver Disponibilidade da Equipe")
        print("5. Registrar Diagnóstico")
        print("6. Apontamento de Reparos (Horas/Peças)")
        print("7. Atualizar Status Operacional")
        print("8. Ver Detalhes e Histórico de uma OS")
        print("0. Sair")

        op = input("Escolha: ")
        if op == '1': listar_equipamentos()
        elif op == '2': listar_os()
        elif op == '3': abrir_chamado(usuario[0])
        elif op == '4': ver_disponibilidade_tecnicos()
        elif op == '5': registrar_diagnostico(usuario[0])
        elif op == '6': apontamento_reparos(usuario[0])
        elif op == '7': alterar_status_os(usuario[0])
        elif op == '8': ver_detalhes_os()
        elif op == '0': break

def main():
    inicializar_banco()

    print("=== SISTEMA DE GESTÃO DE MANUTENÇÃO (SGME) ===")
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, perfil FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()

    print("Selecione o usuário para logar:")
    for u in usuarios:
        print(f"[{u[0]}] {u[1]} ({u[2]})")

    user_id = input("\nID do Usuário: ")

    usuario_logado = next((u for u in usuarios if str(u[0]) == user_id), None)

    if not usuario_logado:
        print("Usuário inválido.")
        return

    if usuario_logado[2] == 'Gestor':
        menu_gestor(usuario_logado)
    elif usuario_logado[2] == 'Técnico':
        menu_tecnico(usuario_logado)

if __name__ == "__main__":
    main()
