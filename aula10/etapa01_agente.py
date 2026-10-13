"""
ETAPA 1 -- Primeiro agente com tool local (15 min).

ESQUELETO: implemente as etapas na ordem. Cada uma está marcada com um comentário e um
raise NotImplementedError: troque esse raise pelo código da etapa e rode o arquivo.
  ETAPA 1.1 -- a tool consultar_servidor (SEM o salário)
  ETAPA 1.2 -- o agente AtendenteRH com a tool
  ETAPA 1.3 -- duas perguntas: uma que precisa da tool e uma que não precisa

REFERÊNCIAS NAS AULAS
  aula1/segundo_agente.py                            Agent + @function_tool + Runner.run_sync (o básico)
  exercicios_resolvidos/aula4/ex10_function_tool.py  tool que consulta uma TABELA e devolve JSON  <- o mais parecido
  aula8/exemplos/02_agente_tool/main.py              o agente decide quando chamar a tool (e quando não)

Rodar (a partir de aula10/):
    python etapa01_agente.py

Pronto quando: a tool é chamada só na primeira pergunta (o print dentro dela prova).
"""
import json

from agents import Agent, Runner, function_tool

from dados_rh import carregar_servidores, servidor_publico
from provedor import configurar

MODELO = configurar()  # LLM REAL: PROVEDOR no .env (openai ou ollama)


# ETAPA 1.1 -- a tool
#   - ponha um print("[tool] consultar_servidor", matricula) no começo, para provar quando ela roda;
#   - devolva json.dumps(servidor_publico(matricula), ensure_ascii=False). A consulta servidor_publico() (dados_rh.py)
#     já vem pronta: tira o salário (dado restrito, ver Etapas 5 e 9) e trata matrícula inexistente;
#   - capriche na DOCSTRING (com Args:): é o que o LLM lê para decidir chamar a tool. Esse é o ponto da etapa.
#   Referência: exercicios_resolvidos/aula4/ex10_function_tool.py (consultar_protocolo)
@function_tool
def consultar_servidor(matricula: str) -> str:
    """Consulta o cadastro de UM servidor pela matrícula.

    Devolve um JSON com matrícula, nome, cargo, equipe, saldo de férias (dias) e abonos
    restantes. Use quando a pergunta for sobre os dados ou saldos de um servidor específico.
    Não devolve remuneração.

    Args:
        matricula: matrícula do servidor, só números (ex.: "1002").
    """
    print(f"[tool] consultar_servidor {matricula}")

    servidor = carregar_servidores().get(str(matricula).strip())
    if servidor is None:
        return "matrícula não encontrada"

    # Lista do que PODE sair: o salário fica de fora (dado restrito, Etapas 5 e 9)
    campos = ["matricula", "nome", "cargo", "equipe", "saldo_ferias_dias", "abonos_restantes"]
    return json.dumps({c: servidor[c] for c in campos}, ensure_ascii=False)


def criar_atendente() -> Agent:

    agente = Agent(
    name="AtendenteRH",
    instructions="Atende servidores, responde em português e de forma breve. " \
                 "Usa a tool quando a pergunta for sobre dados de um servidor. " \
                 "não inventa saldo de cabeça.",
    tools=[consultar_servidor],
)
    return agente


def main() -> None:
    agente = criar_atendente()
    for pergunta in ("Qual o saldo de férias do servidor 1002?", "O que é abono pecuniário?"):
        print(f"\n> {pergunta}")
        print(Runner.run_sync(agente, pergunta).final_output)


if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    main()
