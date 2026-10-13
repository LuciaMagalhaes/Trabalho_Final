"""
ETAPA 5 -- MCP Server do RH (30 min). Volta aqui na ETAPA 9 (token, regra N8 e auditoria).

Os dados saem de dentro do agente e passam a morar num PROCESSO SEPARADO, que fala MCP. O agente (Etapa 5.3) e os
nós do grafo (Etapa 7, via cliente_mcp.chamar_mcp) só enxergam as tools abaixo: nunca os CSVs.

ESQUELETO: implemente as etapas na ordem (troque cada raise NotImplementedError pelo código da etapa).
  ETAPA 5.1 -- as 5 tools de LEITURA (docstrings e tipos caprichados: é o "schema" que o LLM lê).
               Convenção deste server: toda tool devolve UM dict (veja o comentário em consultar_normas).
  ETAPA 5.2 -- a tool de ESCRITA registrar_decisao, IDEMPOTENTE (protocolo repetido não duplica)
  ETAPA 9.2 -- autorização NO SERVER: token + regra N8 (chefia certa, nunca o próprio servidor) + decisão num enum
  ETAPA 9.3 -- auditoria: toda tentativa de escrita (ALLOW ou DENY) vira uma linha em saidas/auditoria.jsonl

REFERÊNCIAS NAS AULAS
  aula6/desafio2/mcp_unidades.py               MCP Server que lê um CSV                          <- o mais parecido (5.1)
  aula5/exemplos/03_mcp_parametros/server.py   tool com parâmetros opcionais
  aula5/exemplos/05_multiplas_tools/server.py  várias tools no mesmo server, tool de "descoberta"
  aula3/agente_retry3.py                       idempotência (5.2)
  aula5/exemplos/10_seguranca/server_seguro.py token, enum fechado e auditoria NO SERVER        <- o mais parecido (9.2/9.3)

Testar sem agente (MCP Inspector, precisa de Node.js):
    npx @modelcontextprotocol/inspector python mcp_rh.py

Pronto quando: o Inspector lista as 6 tools; registrar C1 duas vezes gera um único registro.
"""
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from dados_rh import PASTA, SAIDAS, carregar_diarias, carregar_escala, carregar_servidores, normas

# O server roda como SUBPROCESSO: ele não herda o ambiente de quem o chamou. Por isso carrega o .env sozinho
# (mesmo cuidado de aula5/exemplos/02_mcp_basico/database.py).
load_dotenv(PASTA / ".env")

mcp = MCPServer("rh-mcp")

ARQUIVO_REGISTROS = SAIDAS / "registros.json"
ARQUIVO_AUDITORIA = SAIDAS / "auditoria.jsonl"
TOKEN_REGISTRO = os.getenv("TOKEN_REGISTRO", "")
DECISOES_VALIDAS = {"deferido", "indeferido", "indeferido_pela_chefia"}
TIPOS_COM_CHEFIA = {"ferias", "diaria"}  # regra N8


def _ler_registros() -> dict:
    """(PRONTO) {protocolo: registro} gravados até agora."""
    if ARQUIVO_REGISTROS.exists():
        return json.loads(ARQUIVO_REGISTROS.read_text(encoding="utf-8"))
    return {}


def _gravar_registros(registros: dict) -> None:
    """(PRONTO)"""
    ARQUIVO_REGISTROS.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ ETAPA 5.1: leitura
"""TODO ETAPA 5.1: docstring. Cadastro de UM servidor, SEM o salário."""
    # Mesmo conteúdo da tool da Etapa 1, agora no server. Matrícula inexistente: {"erro": "matrícula não encontrada"}.
    # raise NotImplementedError("ETAPA 5.1: consultar_servidor")
@mcp.tool()
def consultar_servidor(matricula: str) -> dict:
    """Cadastro de UM servidor: nome, cargo, equipe, saldo de férias, abonos restantes e chefia imediata.
    NÃO devolve remuneração.

    Args:
        matricula: matrícula do servidor, só números (ex.: "1002").
    """
    servidor = carregar_servidores().get(str(matricula).strip())
    if servidor is None:
        return {"erro": "matrícula não encontrada"}
    campos = ["matricula", "nome", "cargo", "equipe", "saldo_ferias_dias", "abonos_restantes", "chefia"]
    return {c: servidor[c] for c in campos}
    

"""TODO ETAPA 5.1: docstring. Afastamentos da equipe que se sobrepõem ao período e o limite da regra N5."""
    # Devolva {"equipe", "tamanho_equipe", "limite_afastados" (30% arredondado p/ baixo, mínimo 1),
    #          "afastamentos": [...os de carregar_escala() da equipe com sobreposição de datas...]}
    # Duas faixas [a1, a2] e [b1, b2] se sobrepõem quando a1 <= b2 e b1 <= a2 (dá para comparar as strings AAAA-MM-DD).
    # raise NotImplementedError("ETAPA 5.1: consultar_escala")
@mcp.tool()
def consultar_escala(equipe: str, inicio: str, fim: str) -> dict:
    """Afastamentos já marcados de uma equipe que se sobrepõem a um período, e o limite da regra N5.
 
    Use para saber se cabe mais um afastamento: compare len(afastamentos) com limite_afastados
    (30% da equipe, arredondado para baixo, mínimo 1).
 
    Args:
        equipe: nome da equipe, como no cadastro (ex.: "Cartório", "Plantão A", "Inteligência").
        inicio: primeiro dia do período, AAAA-MM-DD.
        fim: último dia do período, AAAA-MM-DD.
    """

    tamanho = sum(1 for s in carregar_servidores().values() if s["equipe"] == equipe)
    limite = max(1, int(tamanho * 0.3))  # N5: 30% arredondado para baixo, mínimo 1
    afastamentos = [a for a in carregar_escala()
                    if a["equipe"] == equipe and a["inicio"] <= fim and inicio <= a["fim"]]  # sobreposição
    return {"equipe": equipe, "tamanho_equipe": tamanho, "limite_afastados": limite, "afastamentos": afastamentos}

   

"""TODO ETAPA 5.1: docstring (diga quais temas existem: férias, prazos, escala, abono, diária, aprovação...)."""
# Devolva {"tema": tema, "regras": normas(tema)} (normas() está em dados_rh.py).
# Por que um dict e não a lista direto? Uma tool MCP que devolve LISTA manda cada item como um conteúdo separado:
# quem chama não distingue "lista com 1 regra" de "1 dict". Neste server, TODA tool devolve UM dict.
# raise NotImplementedError("ETAPA 5.1: consultar_normas")
@mcp.tool()
def consultar_normas(tema: str) -> dict:
    """Regras da Norma Interna nº 1/2026 sobre um tema.
 
    Args:
        tema: um destes: "férias", "prazos", "escala", "abono", "diária", "aprovação", "saúde", "dados".
              Acento e maiúsculas não importam ("ferias" também funciona).
    """

    return {"tema": tema, "regras": normas(tema)}
    

"""TODO ETAPA 5.1: docstring. Moeda e valor da diária para capital, interior ou exterior."""
# raise NotImplementedError("ETAPA 5.1: tabela_diarias")

@mcp.tool()
def tabela_diarias(tipo_destino: str) -> dict:
    """Moeda e valor de UMA diária para o tipo de destino (regra N7).
 
    No exterior o valor vem em USD e precisa ser convertido pela cotação do dia.
 
    Args:
        tipo_destino: "capital", "interior" ou "exterior".
    """

    tabela = carregar_diarias()
    if tipo_destino not in tabela:
        return {"erro": f"tipo_destino inválido: use um de {sorted(tabela)}"}
    return {"tipo_destino": tipo_destino, **tabela[tipo_destino]}


"""[RESTRITA] TODO ETAPA 5.1: docstring. Salário-base de um servidor (só o Financeiro deve usar, ver 🆕 B)."""
# raise NotImplementedError("ETAPA 5.1: consultar_remuneracao")
@mcp.tool()
def consultar_remuneracao(matricula: str) -> dict:
    """[RESTRITA] Salário-base de um servidor. Uso exclusivo do cálculo financeiro (venda de férias, N2).
 
    Args:
        matricula: matrícula do servidor, só números (ex.: "1002").
    """

    servidor = carregar_servidores().get(str(matricula).strip())
    if servidor is None:
        return {"erro": "matrícula não encontrada"}
    return {"matricula": servidor["matricula"], "salario_base": servidor["salario_base"]}



# ------------------------------------------------------------------ ETAPA 5.2 / 9.2 / 9.3: escrita
def _auditar(protocolo: str, decisao_acesso: str, motivo: str, parametros: dict) -> None:
    # ETAPA 9.3 -- acrescente UMA linha JSON em ARQUIVO_AUDITORIA com: quando (datetime.now().isoformat()),
    #   thread_id, quem pediu (aprovador), tool ("registrar_decisao"), protocolo, decisao_acesso ("ALLOW"/"DENY"),
    #   motivo e os parâmetros (SEM o token e SEM o despacho inteiro).
    #   Referência: aula5/exemplos/10_seguranca/server_seguro.py (_registrar_auditoria), aqui em JSON Lines.
    #   Até fazer a 9.3, este pass deixa a escrita funcionar sem auditoria.
    pass

# ETAPA 5.2 -- grave em ARQUIVO_REGISTROS (use _ler_registros/_gravar_registros).
    #   Protocolo já existe -> NÃO grave de novo; devolva {"sucesso": True, "duplicado": True, ...}.
    #   Senão grave {**parametros, "despacho": despacho, "registrado_em": ...} e devolva {"sucesso": True, ...}.
    #   Audite com ALLOW (9.3).
    # raise NotImplementedError("ETAPA 5.2: registrar_decisao")

@mcp.tool()
def registrar_decisao(protocolo: str, matricula: str, tipo: str, inicio: str, fim: str, decisao: str,
                      aprovador: str, despacho: str, token: str, thread_id: str = "") -> dict:
    
    """[ESCRITA -- requer autorização] Grava a decisão final de um pedido. IDEMPOTENTE: se o protocolo já
    existir, NÃO grava de novo e devolve duplicado=True.
 
    Args:
        protocolo: protocolo idempotente do pedido (ferramentas.gerar_protocolo).
        matricula: matrícula do servidor que fez o pedido.
        tipo: "ferias", "abono" ou "diaria".
        inicio: primeiro dia, AAAA-MM-DD.
        fim: último dia, AAAA-MM-DD.
        decisao: "deferido", "indeferido" ou "indeferido_pela_chefia".
        aprovador: matrícula de quem aprovou (a chefia, regra N8) ou "sistema" quando não precisa de chefia.
        despacho: texto do despacho (sem CPF nem dado de saúde, N10).
        token: token de registro. Sem ele, a gravação é negada.
        thread_id: identificador da execução do grafo, para a auditoria.
    """

    parametros = {"matricula": matricula, "tipo": tipo, "inicio": inicio, "fim": fim, "decisao": decisao,
                  "aprovador": aprovador, "thread_id": thread_id}

    # ETAPA 9.2 -- ANTES de gravar, negue (e audite com DENY) quando:
    #   - token != TOKEN_REGISTRO (ou TOKEN_REGISTRO vazio);
    #   - decisao não está em DECISOES_VALIDAS;
    #   - aprovador == matricula (ninguém aprova o próprio pedido, N8);
    #   - decisao == "deferido" e tipo in TIPOS_COM_CHEFIA e aprovador != chefia do servidor no cadastro.
    #   Devolva {"sucesso": False, "erro": "..."} -- quem nega é o SERVER, não o agente.
    #   Referência: aula5/exemplos/10_seguranca/server_seguro.py (alterar_status_ocorrencia)

    
    registros = _ler_registros()
    if protocolo in registros:  # idempotência: o mesmo pedido não grava duas vezes
        return {"sucesso": True, "duplicado": True, "protocolo": protocolo,
                "mensagem": "protocolo já registrado: nada foi gravado de novo"}
    registros[protocolo] = {**parametros, "despacho": despacho, "registrado_em": datetime.now().isoformat()}
    _gravar_registros(registros)
    _auditar(protocolo, "ALLOW", "registrado", parametros)
    return {"sucesso": True, "duplicado": False, "protocolo": protocolo}



if __name__ == "__main__":
    mcp.run(transport="stdio")
