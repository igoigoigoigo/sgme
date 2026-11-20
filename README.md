# SGME — Sistema de Gestão de Manutenção de Equipamentos

Entrega 2 (versão 2.1). É a evolução arquitetural da aplicação de console da Entrega 1: arquitetura em camadas,
princípios SOLID, padrões de projeto (Repository, State, Strategy, Observer, Factory Method,
Command e Injeção de Dependência), persistência SQLite desacoplada e uma interface de terminal reformulada.

**Especialidades:** usuários e OS podem ter nenhuma, uma ou várias especialidades técnicas. Uma OS só
pode ser atribuída a um técnico que possua **todas** as especialidades que ela exige. OS sem
especialidade aceita qualquer técnico.

O relatório técnico completo está em [docs/RELATORIO.md](docs/RELATORIO.md).

## Requisitos

- Python **3.10 ou superior** (testado com 3.12)
- Nenhuma biblioteca externa para executar o sistema
- `pytest` apenas para rodar os testes

## Como executar

```powershell
git clone <url-do-repositorio> sgme
cd sgme
python main.py
```

Na primeira execução é criado o arquivo `manutencao.db` com dados de demonstração
(1 gestor, 3 técnicos, 4 equipamentos e 3 OS em estados diferentes, uma delas com SLA estourado).
Especialidades da demonstração: João tem Mecânica e Hidráulica; Maria tem Elétrica, Eletrônica e
Mecânica; Carlos não tem nenhuma. A OS #1 exige Hidráulica, a OS #2 exige Mecânica e Elétrica e a
OS #3 não exige nenhuma.

| Comando | Efeito |
|---|---|
| `python main.py` | usa o banco `manutencao.db` (cria se não existir) |
| `python main.py --db outro.db` | usa outro arquivo de banco |
| `python main.py --memoria` | roda sem gravar nada em disco |
| `python main.py --sem-demo` | banco vazio, apenas com o usuário "Gestor Admin" |

> Um `manutencao.db` gerado pela Entrega 1 pode ser reaproveitado: as colunas novas são criadas automaticamente na inicialização.

### Usando a interface

1. Escolha o usuário pelo número (ex.: `1` = Gestor Admin, `2` = Técnico João).
2. O painel com os indicadores aparece logo após o login.
3. No menu, digite o número da opção. As opções exibidas dependem do perfil.
4. Em qualquer pergunta, **Enter vazio cancela** a operação e volta ao menu. A exceção é a seleção
   de especialidades, em que Enter significa "nenhuma" (ou "manter as atuais", na edição).
5. `T` troca de usuário e `0` encerra o sistema.

Dica: use um terminal com cores (Windows Terminal, PowerShell, VS Code). Para desligar as cores, defina a variável `NO_COLOR=1`.

## Testes

```powershell
python -m pip install -r requirements.txt
python -m pytest -v
```

## Estrutura

```
main.py                     ponto de entrada (argumentos de linha de comando)
sgme/
  container.py              raiz de composição (injeção de dependência)
  seed.py                   dados de demonstração
  domain/                   CAMADA DE DOMÍNIO: entidades, estados da OS, SLA, exceções
  repositories/             CAMADA DE PERSISTÊNCIA: contratos + SQLite + memória
  services/                 CAMADA DE SERVIÇOS: casos de uso, eventos, permissões, painel
  cli/                      CAMADA DE APRESENTAÇÃO: console, telas e menu
tests/                      testes automatizados (pytest)
legacy/sgme_entrega1.py     código original da Entrega 1, mantido para comparação
docs/RELATORIO.md           relatório técnico
```
