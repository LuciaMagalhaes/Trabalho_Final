"""
ETAPA 6 -- O sistema inteiro como um FLUXO LINEAR em Python puro (sem LangGraph) ⇒ Marco mínimo.

ESQUELETO:
  ETAPA 6.3 -- analisar(): o Coordenador junta os pareceres (com os limites da Etapa 4.7)
  ETAPA 6.4 -- processar(): guardrails -> extração -> MCP -> feriados -> regras -> coordenador -> redator
               -> protocolo -> MCP (registrar)
  🆕 B.4    -- passe hooks=Governanca() e trate LimiteExcedido; rode os testes de --governanca

REFERÊNCIAS NAS AULAS
  aula6/exemplos/01_fluxo_linear/main.py     o fluxo linear: funciona, mas sem decisão nem volta (por isso a Etapa 7)
  aula4/ex03_agente_as_tool.py               o Coordenador com especialistas como tools
  aula7/exemplos/02_agentes_especializados/main.py   cada especialista imprime o que fez: dá para saber quem fez o quê

Rodar:
    python etapa6_linear.py                 # C1, C2, C6 e C11
    python etapa6_linear.py --governanca    # 🆕 B: os dois testes de bloqueio

Pronto quando: C1, C2 e C11 são gravados com protocolo, C6 vira indeferimento com sugestão de datas, e você sabe dizer
qual agente escreveu cada parte. No --governanca: a tool restrita NÃO executa e o C2 para no orçamento.
"""
import json
import os
import sys

from agents import RunHooks

import agentes
from cliente_mcp import chamar_mcp
from dados.casos import CASOS
from extracao import extrair
from ferramentas import LoopExcedido, TempoEsgotado, gerar_protocolo, rodar_com_limites_sync
from governanca import Governanca, LimiteExcedido
from guardrails import encontrar_dado_sensivel, nota_escopo, LIMIAR, MENSAGENS
from provedor import configurar
from regras import precisa_chefia, resumo_periodo, violacoes_objetivas

MODELO = configurar()

# ETAPA 6.3 -- monte um texto com o pedido, o servidor (matrícula e equipe), o período e as violações objetivas,
#   e rode criar_coordenador(hooks) com rodar_com_limites_sync(..., hooks=hooks). Devolva final_output.
#    raise NotImplementedError("ETAPA 6.3: analisar")

def analisar(pedido: dict, servidor: dict, periodo: dict, violacoes: list[str], hooks: RunHooks | None = None) -> str:
    entrada = (
        f"PEDIDO: {json.dumps(pedido, ensure_ascii=False)}\n"
        f"SERVIDOR: matrícula {servidor['matricula']}, equipe {servidor['equipe']}\n"
        f"PERÍODO: {json.dumps(periodo, ensure_ascii=False)}\n"
        f"VIOLAÇÕES OBJETIVAS (definitivas, calculadas pelas regras): {violacoes or 'nenhuma'}"
    )
    coordenador = agentes.criar_coordenador(hooks)
    return rodar_com_limites_sync(coordenador, entrada, hooks=hooks).final_output

# ETAPA 6.4 -- encadeie, imprimindo cada passo ("[1/9] guardrails", ...):
#   1. encontrar_dado_sensivel / nota_escopo >= LIMIAR  -> devolva {"resultado": "bloqueado", "mensagem": ...}
#   2. pedido = extrair(texto).model_dump(mode="json")  -> sem matrícula ou datas: {"resultado": "pedir_dados"}
#   3. servidor = chamar_mcp("consultar_servidor", ...) -> não encontrado: {"resultado": "pedir_dados"}
#   4. periodo = resumo_periodo(...)                     (API de feriados, Etapa 4)
#   5. escala = chamar_mcp("consultar_escala", ...); violacoes = violacoes_objetivas(...)
#   6. parecer = analisar(...)
#   7. despacho = rodar_com_limites_sync(agentes.criar_redator(), <fatos + parecer + violações>).final_output
#   8. protocolo = gerar_protocolo(...)
#   9. chamar_mcp("registrar_decisao", {..., "decisao": "indeferido" se houver violação senão "deferido",
#        "aprovador": "pendente_chefia" se precisa_chefia(...) senão "sistema", "token": os.getenv("TOKEN_REGISTRO")})
#      (a aprovação de verdade da chefia entra na Etapa 8; aqui só marcamos que ela será necessária)
#   Devolva {"resultado": ..., "protocolo": ..., "despacho": ..., "parecer": ...}.
# raise NotImplementedError("ETAPA 6.4: processar")


def processar(texto: str, hooks: RunHooks | None = None) -> dict:
    # 1. guardrails (regex sem LLM, depois o classificador)
    print("[1/9] guardrails")
    achado = encontrar_dado_sensivel(texto)
    if achado:
        return {"resultado": "bloqueado", "mensagem": MENSAGENS[achado]}
    nota, motivo = nota_escopo(texto)
    if nota >= LIMIAR:
        return {"resultado": "bloqueado", "mensagem": MENSAGENS["fora_do_escopo"], "nota": nota, "motivo": motivo}
 
    # 2. extração (LLM -> Pedido)
    print("[2/9] extração")
    pedido = extrair(texto).model_dump(mode="json")
    if pedido["tipo"] == "licenca_saude":
        return {"resultado": "bloqueado", "mensagem": MENSAGENS["cid"]}
    faltando = [c for c in ("matricula", "data_inicio", "data_fim") if not pedido.get(c)]
    if pedido["tipo"] == "outro":
        faltando.append("tipo (férias, abono ou diária)")
    if faltando:
        return {"resultado": "pedir_dados", "faltando": faltando}
 
    # 3. cadastro (MCP)
    print("[3/9] MCP: consultar_servidor")
    servidor = chamar_mcp("consultar_servidor", {"matricula": pedido["matricula"]})
    if "erro" in servidor:
        return {"resultado": "pedir_dados", "faltando": ["matrícula válida"], "mensagem": servidor["erro"]}
 
    # 4. feriados (API, com plano B)
    print("[4/9] feriados")
    periodo = resumo_periodo(pedido["data_inicio"], pedido["data_fim"])
 
    # 5. escala (MCP) + regras objetivas (Python decide)
    print("[5/9] MCP: consultar_escala + regras")
    escala = chamar_mcp("consultar_escala", {"equipe": servidor["equipe"],
                                             "inicio": pedido["data_inicio"], "fim": pedido["data_fim"]})
    violacoes = violacoes_objetivas(pedido, servidor, periodo, escala)
    chefia = precisa_chefia(pedido, violacoes)
    decisao = "indeferido" if violacoes else "deferido"
 
    try:
        # 6. coordenador (Normas, Escala e Financeiro como tools)
        print("[6/9] coordenador")
        parecer = analisar(pedido, servidor, periodo, violacoes, hooks)
 
        # 7. redator (só os fatos)
        print("[7/9] redator")
        fatos = (
            f"Matrícula: {servidor['matricula']}\nTipo: {pedido['tipo']}\n"
            f"Período: {pedido['data_inicio']} a {pedido['data_fim']} (retorno {periodo['retorno']})\n"
            f"Decisão: {decisao.upper()}" + (" (sujeito à aprovação da chefia imediata)" if chefia else "") + "\n"
            f"Violações: {violacoes or 'nenhuma'}\n\nPARECER DOS ESPECIALISTAS:\n{parecer}"
        )
        despacho = rodar_com_limites_sync(agentes.criar_redator(), fatos, hooks=hooks).final_output
    except (TempoEsgotado, LoopExcedido) as erro:
        return {"resultado": "erro_tecnico", "mensagem": str(erro)}
 
    # 8. protocolo idempotente
    print("[8/9] protocolo")
    protocolo = gerar_protocolo(pedido["matricula"], pedido["tipo"], pedido["data_inicio"], pedido["data_fim"])
 
    # 9. registrar (MCP, escrita)
    print("[9/9] MCP: registrar_decisao")
    registro = chamar_mcp("registrar_decisao", {
        "protocolo": protocolo, "matricula": pedido["matricula"], "tipo": pedido["tipo"],
        "inicio": pedido["data_inicio"], "fim": pedido["data_fim"], "decisao": decisao,
        "aprovador": "pendente_chefia" if chefia else "sistema",
        "despacho": despacho, "token": os.getenv("TOKEN_REGISTRO", ""), "thread_id": protocolo,
    })
    return {"resultado": decisao, "precisa_chefia": chefia, "protocolo": protocolo, "violacoes": violacoes,
            "registro": registro, "parecer": parecer, "despacho": despacho}

# 🆕 B.4 -- dois testes, cada um tratando LimiteExcedido e imprimindo o motivo:
#   a) coordenador = agentes.criar_coordenador(hooks=Governanca(), tools_extras=[agentes.consultar_remuneracao])
#      pergunte "Qual o salário da matrícula 1002?" -> deve ser BARRADO e o print da tool NÃO pode aparecer.
#   b) processar(CASOS["C2_ferias_com_venda"]["pedido"], hooks=Governanca(max_tools=1))
#      -> deve parar ANTES do segundo especialista.
# raise NotImplementedError("🆕 B.4: testar_governanca")

def testar_governanca() -> None:
    print("\n=== 🆕 B (a): Coordenador tentando ler o salário direto")
    gov = Governanca()
    coordenador = agentes.criar_coordenador(hooks=gov, tools_extras=[agentes.consultar_remuneracao])
    try:
        resposta = rodar_com_limites_sync(coordenador, "Qual o salário da matrícula 1002?", hooks=gov)
        print("NÃO foi barrado (o modelo não tentou a tool). Resposta:", resposta.final_output)
    except LimiteExcedido as erro:
        print(f"BARRADO: {erro}  (repare: o print '[tool] consultar_remuneracao EXECUTOU' não apareceu)")
 
    # b) orçamento de 1 tool: o C2 para antes do segundo especialista
    print("\n=== 🆕 B (b): C2 com MAX_TOOLS = 1")
    try:
        processar(CASOS["C2_ferias_com_venda"]["pedido"], hooks=Governanca(max_tools=1))
        print("NÃO foi barrado")
    except LimiteExcedido as erro:
        print(f"BARRADO: {erro}")



if __name__ == "__main__":
    print(f"[modelo] {MODELO}")
    if "--governanca" in sys.argv:
        testar_governanca()
    else:
        for nome in ("C1_abono_simples", "C2_ferias_com_venda", "C6_conflito_de_escala", "C11_diaria_exterior"):
            print(f"\n=============== {nome}")
            print(json.dumps(processar(CASOS[nome]["pedido"]), ensure_ascii=False, indent=2))
