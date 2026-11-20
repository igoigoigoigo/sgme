"""Garante que um banco criado pela Entrega 1 continua funcionando."""
import sqlite3

from sgme.container import montar, repositorios_sqlite
from sgme.domain.sla import Criticidade
from sgme.domain.status_os import StatusOS

ESQUEMA_ENTREGA1 = """
CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
    perfil TEXT NOT NULL, status TEXT DEFAULT 'Disponível');
CREATE TABLE equipamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
    descricao TEXT, ativo INTEGER DEFAULT 1);
CREATE TABLE ordens_servico (id INTEGER PRIMARY KEY AUTOINCREMENT, equipamento_id INTEGER,
    criador_id INTEGER, tecnico_id INTEGER, falha_apontada TEXT, criticidade TEXT,
    status TEXT DEFAULT 'Aberta', diagnostico TEXT, horas_trabalhadas REAL DEFAULT 0.0,
    pecas_utilizadas TEXT, parecer_gestor TEXT);
CREATE TABLE historico (id INTEGER PRIMARY KEY AUTOINCREMENT, os_id INTEGER,
    descricao TEXT, data_hora TEXT);
INSERT INTO usuarios (nome, perfil) VALUES ('Gestor Admin', 'Gestor'), ('Tecnico Joao', 'Técnico');
INSERT INTO equipamentos (nome, descricao) VALUES ('Torno Mecânico CNC', 'Setor A');
INSERT INTO ordens_servico (equipamento_id, criador_id, tecnico_id, falha_apontada, criticidade, status)
    VALUES (1, 1, 2, 'Ruído', 'Media', 'Em Andamento'), (1, 1, NULL, '', 'urgente', 'Aberta');
INSERT INTO historico (os_id, descricao, data_hora) VALUES (1, 'OS Aberta.', '2025-05-01 10:00:00');
"""


def test_migra_banco_da_entrega1(tmp_path):
    caminho = tmp_path / "manutencao.db"
    conn = sqlite3.connect(caminho)
    conn.executescript(ESQUEMA_ENTREGA1)
    conn.close()

    c = montar(repositorios_sqlite(str(caminho)))
    os1, os2 = c.repositorios.ordens.obter(1), c.repositorios.ordens.obter(2)

    assert os1.criticidade is Criticidade.MEDIA
    assert os1.status is StatusOS.EM_ANDAMENTO
    assert os1.data_abertura.year == 2025          # herdada do histórico
    assert os2.criticidade is Criticidade.MEDIA     # valor livre inválido normalizado
    assert os2.falha_apontada == "(não informada)"
    # E o fluxo novo funciona sobre os dados antigos
    joao = c.usuarios.obter(2)
    c.ordens.alterar_status(joao, 1, StatusOS.REPARO_FINALIZADO)
    assert len(c.ordens.detalhar(1).historico) == 2
