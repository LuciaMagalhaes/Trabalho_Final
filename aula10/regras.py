"""
ETAPA 6.0 -- As regras OBJETIVAS da norma, em Python puro (sem LLM).

Na Etapa 0 você classificou cada regra N1..N10: função Python, agente ou humano. As que são CONTA (saldo, datas,
limite da escala) ficam aqui: um LLM pode errar uma soma, uma função não. O agente Normas (agentes.py) continua
útil para EXPLICAR as regras no despacho, mas quem decide "violou ou não" é este módulo.

ESQUELETO:
  ETAPA 6.0 -- violacoes_objetivas(): devolve a lista de violações ("N3: ...") de um pedido
  ETAPA 6.0 -- precisa_chefia(): regra N8

REFERÊNCIAS NAS AULAS
  aula6/exemplos/11_grafo_real/main.py   avaliar_risco: "tool local (regra de negócio, sem IA)" dentro do fluxo
  aula6/desafio3/ENUNCIADO.md            "LLM para ESCREVER, [regra/modelo tipado] para DECIDIR"

Rodar:
    python regras.py      # confere as regras nos casos C1, C2, C6 e C12 com pedidos montados à mão (sem LLM)
"""
from datetime import date, timedelta

from ferramentas import buscar_feriados, data_retorno, dias_uteis, eh_dia_util, inicio_permitido


def resumo_periodo(inicio: str, fim: str) -> dict:
    """(PRONTO, usa as suas funções da Etapa 4) Tudo o que os especialistas precisam saber sobre as datas."""
    d1, d2 = date.fromisoformat(inicio), date.fromisoformat(fim)
    feriados, fonte = buscar_feriados(d1.year)
    return {
        "inicio": inicio, "fim": fim,
        "dias_corridos": (d2 - d1).days + 1,
        "dias_uteis": dias_uteis(inicio, fim),
        "feriados_no_periodo": {d: n for d, n in feriados.items() if inicio <= d <= fim},
        "retorno": data_retorno(fim),
        "inicio_permitido_n3": inicio_permitido(inicio),
        "fonte_feriados": fonte,
    }


def _dias_uteis_ate(hoje: date, alvo: date) -> int:
    """(PRONTO) Dias úteis entre amanhã e o dia anterior a `alvo` (antecedência do abono, N4)."""
    return sum(1 for k in range(1, (alvo - hoje).days) if eh_dia_util(hoje + timedelta(k)))


    # ETAPA 6.0 -- confira, conforme o tipo do pedido:
    #   férias: N1 (mínimo 5 dias corridos; dias_corridos <= saldo), N2 (dias_vendidos <= 10 e
    #           dias_corridos + dias_vendidos <= saldo), N3 (periodo["inicio_permitido_n3"]),
    #           N4 (início pelo menos 30 dias depois de hoje), N5 (afastamentos que se sobrepõem >= limite_afastados)
    #   abono:  N6 (1 dia, dia útil, abonos_restantes > 0), N4 (>= 2 dias úteis de antecedência: _dias_uteis_ate),
    #           N5
    #   diária: N4 (pelo menos 10 dias de antecedência)
    #   Atenção na N5: descarte da lista de afastamentos o próprio servidor.
    # raise NotImplementedError("ETAPA 6.0: violacoes_objetivas")

def violacoes_objetivas(pedido: dict, servidor: dict, periodo: dict, escala: dict, hoje: date | None = None) -> list[str]:
    """Lista de violações objetivas, cada uma começando pelo código da regra (ex.: "N3: começa numa sexta...").

    Args:
        pedido: Pedido.model_dump() (tipo, data_inicio, data_fim, dias_vendidos...).
        servidor: o cadastro (consultar_servidor do MCP) -- saldo_ferias_dias, abonos_restantes.
        periodo: resumo_periodo(...).
        escala: consultar_escala do MCP -- limite_afastados e afastamentos (sem contar o próprio servidor).
        hoje: data do pedido (padrão: date.today()).
    """
    hoje = hoje or date.today()
    tipo, data, saldo = pedido["tipo"], pedido["data_inicio"], servidor["saldo_ferias_dias"]
    inicio = date.fromisoformat(data)
    dias, vendidos = periodo["dias_corridos"], pedido.get("dias_vendidos") or 0
    outros = [a for a in escala["afastamentos"] if a["matricula"] != servidor["matricula"]]  # N5: sem o próprio
    conflito = len(outros) >= escala["limite_afastados"]
 
    # (regra, violou?, explicação) -- uma linha por checagem, separadas por tipo de pedido
    checagens = {
        "ferias": [
            ("N1", dias < 5,                         f"período de {dias} dias é menor que o mínimo de 5"),
            ("N1", dias > saldo,                     f"{dias} dias pedidos, saldo de {saldo}"),
            ("N2", vendidos > 10,                    f"venda de {vendidos} dias passa do máximo de 10"),
            ("N2", dias + vendidos > saldo,          f"{dias} gozados + {vendidos} vendidos passam do saldo de {saldo}"),
            ("N3", not periodo["inicio_permitido_n3"], f"as férias não podem começar em {data}"),
            ("N4", inicio < hoje + timedelta(30),    "férias exigem 30 dias de antecedência"),
            ("N5", conflito,                         f"equipe já tem {len(outros)} afastado(s) (limite {escala['limite_afastados']})"),
        ],
        "abono": [
            ("N6", data != pedido["data_fim"],       "abono é de 1 dia só"),
            ("N6", not eh_dia_util(inicio),          f"{data} não é dia útil"),
            ("N6", servidor["abonos_restantes"] <= 0, "sem abonos restantes"),
            ("N4", _dias_uteis_ate(hoje, inicio) < 2, "abono exige 2 dias úteis de antecedência"),
            ("N5", conflito,                         f"equipe já tem {len(outros)} afastado(s) (limite {escala['limite_afastados']})"),
        ],
        "diaria": [
            ("N4", inicio < hoje + timedelta(10),    "diária exige 10 dias de antecedência"),
        ],
    }
    return [f"{regra}: {texto}" for regra, violou, texto in checagens.get(tipo, []) if violou]



def precisa_chefia(pedido: dict, violacoes: list[str]) -> bool:
    #   Indeferimento por violação objetiva também não precisa (é a norma que nega, não a chefia).
    return pedido["tipo"] in ("ferias", "diaria") and not violacoes

    # ETAPA 6.0 -- regra N8: férias e diárias deferíveis precisam da chefia; abono que cumpre as regras, não.
    #   Indeferimento por violação objetiva também não precisa (é a norma que nega, não a chefia).
    raise NotImplementedError("ETAPA 6.0: precisa_chefia")


if __name__ == "__main__":
    hoje = date(2026, 10, 9)
    ana = {"matricula": "1001", "saldo_ferias_dias": 30, "abonos_restantes": 5}
    bruno = {"matricula": "1002", "saldo_ferias_dias": 30, "abonos_restantes": 3}
    carla = {"matricula": "1003", "saldo_ferias_dias": 20, "abonos_restantes": 5}
    diego = {"matricula": "1004", "saldo_ferias_dias": 30, "abonos_restantes": 5}
    sem_conflito = {"limite_afastados": 1, "afastamentos": []}
    conflito = {"limite_afastados": 1, "afastamentos": [{"matricula": "1006", "inicio": "2027-07-05", "fim": "2027-07-19"}]}
    testes = [
        ("C1", {"tipo": "abono", "data_inicio": "2027-04-09", "data_fim": "2027-04-09", "dias_vendidos": 0}, ana, sem_conflito, []),
        ("C2", {"tipo": "ferias", "data_inicio": "2027-04-12", "data_fim": "2027-04-26", "dias_vendidos": 10}, bruno, sem_conflito, []),
        ("C6", {"tipo": "ferias", "data_inicio": "2027-07-12", "data_fim": "2027-07-26", "dias_vendidos": 0}, diego, conflito, ["N5"]),
        ("C12", {"tipo": "ferias", "data_inicio": "2027-04-30", "data_fim": "2027-05-14", "dias_vendidos": 0}, carla, sem_conflito, ["N3"]),
    ]
    for nome, pedido, servidor, escala, esperado in testes:
        periodo = resumo_periodo(pedido["data_inicio"], pedido["data_fim"])
        v = violacoes_objetivas(pedido, servidor, periodo, escala, hoje)
        ok = sorted(x.split(":")[0] for x in v) == esperado
        print(f"{nome}: {v or 'nenhuma violação'}  chefia={precisa_chefia(pedido, v)}  {'OK' if ok else 'ESPERADO ' + str(esperado)}")
