"""
ETAPA 4 -- APIs externas com resiliência: feriados, câmbio, idempotência e limites (20 min).

Tudo aqui é Python puro (nenhuma chamada ao LLM, exceto rodar_com_limites): dá para testar sem chave de API.

ESQUELETO: implemente as etapas na ordem (troque cada raise NotImplementedError pelo código da etapa).
  ETAPA 4.1 -- texto_hoje(): a data REAL, para injetar nas instruções dos extratores (extracao.py)
  ETAPA 4.2 -- get_json_com_retry(): timeout + até 3 tentativas + backoff exponencial
  ETAPA 4.3 -- buscar_feriados(): BrasilAPI com plano B (dados/feriados_2027.json)
  ETAPA 4.4 -- dias_uteis(), data_retorno(), inicio_permitido() (regra N3)
  ETAPA 4.5 -- cotacao_usd_brl(): Frankfurter com o mesmo retry; falhou -> None ("a calcular")
  ETAPA 4.6 -- gerar_protocolo(): SHA-256 dos campos normalizados (idempotência)
  ETAPA 4.7 -- rodar_com_limites(): max_turns + asyncio.wait_for, tratando os dois erros separadamente

REFERÊNCIAS NAS AULAS
  aula3/agente_retry.py                    4.1  injetar a data de hoje nas instruções (o modelo não tem relógio)
  aula3/agente_retry2.py                   4.2  retry com backoff; erro de NEGÓCIO (não repete) x erro TÉCNICO (repete)
  aula6/exemplos/11_grafo_real/main.py     4.3  buscar_feriados na MESMA API (BrasilAPI), com User-Agent e plano B local
  aula3/agente_retry4.py                   4.5  a MESMA API de câmbio (Frankfurter)
  aula3/agente_retry3.py                   4.6  idempotência com hash (chave_idempotencia)
  aula3/agente_parada3.py                  4.7  asyncio.wait_for (tempo) x MaxTurnsExceeded (loop)

Rodar:
    python ferramentas.py                  # testes das regras de data e do protocolo
    FERIADOS_OFFLINE=1 python ferramentas.py   # simula a API fora do ar (PowerShell: $env:FERIADOS_OFFLINE="1")

Pronto quando: inicio_permitido("2027-04-30") é False (C12) e inicio_permitido("2027-04-12") é True (C2); offline, os
feriados vêm do arquivo local depois de 3 tentativas visíveis; gerar_protocolo dá o mesmo valor para C1 e C8.
"""
import asyncio
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from agents import Agent, MaxTurnsExceeded, Runner

from dados_rh import carregar_feriados_locais

URL_FERIADOS = "https://brasilapi.com.br/api/feriados/v1/{ano}"
URL_CAMBIO = "https://api.frankfurter.app/latest?from=USD&to=BRL"
DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

# ETAPA 4.1 -- devolva algo como "sexta-feira, 09/10/2026 (2026-10-09)" usando date.today() e DIAS_PT.
    #   Depois, acrescente esse texto a INSTRUCOES_EXTRATOR (extracao.py) e às instruções dos votantes (🆕 A).
    #   Referência: aula3/agente_retry.py
    # raise NotImplementedError("ETAPA 4.1: texto_hoje")
def texto_hoje() -> str:

    hoje = date.today()
    texto_hoje = f"{DIAS_PT[hoje.weekday()]}, {hoje.strftime('%d/%m/%Y')} ({hoje.strftime('%Y-%m-%d')})"
    return texto_hoje
    

# ETAPA 4.2 -- GET com urllib.request (envie o cabeçalho User-Agent: sem ele a BrasilAPI responde 403).
    #   A cada falha TÉCNICA (urllib.error.URLError, TimeoutError, OSError): imprima "[retry] tentativa n falhou",
    #   espere espera_base * 2**(n-1) segundos e tente de novo. Na última, levante a exceção.
    #   Se a variável de ambiente FERIADOS_OFFLINE == "1", trate como falha técnica (para testar sem internet).
    #   Referência: aula3/agente_retry2.py (get_temperatura_resiliente)
    # raise NotImplementedError("ETAPA 4.2: get_json_com_retry")

def get_json_com_retry(url: str, tentativas: int = 3, espera_base: float = 0.5, timeout: float = 5) -> dict | list:
    
    """GET em `url` devolvendo o JSON, com timeout, retry e backoff exponencial."""

    for tentativa in range(1, tentativas + 1):
        try:
            
            if os.getenv("FERIADOS_OFFLINE") == "1":
                raise urllib.error.URLError("modo offline")

            pedido = urllib.request.Request(url, headers={"User-Agent": "curso-pcdf/1.0"})  # sem isso: 403
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                return json.load(resposta)                     # deu certo: sai da função

        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            print(f"[retry] tentativa {tentativa} falhou: {erro}")
            if tentativa == tentativas:
                raise                                          # última: desiste e propaga o erro
            time.sleep(espera_base * 2 ** (tentativa - 1))     # 0.5s, 1s, 2s...
    
    

_CACHE_FERIADOS: dict[int, tuple[dict[str, str], str]] = {}

# ETAPA 4.3 -- devolva ({"2027-04-21": "Tiradentes", ...}, fonte), com fonte "brasilapi" ou "arquivo_local".
    #   Use get_json_com_retry(URL_FERIADOS.format(ano=ano)); se falhar de vez, carregar_feriados_locais()
    #   (o arquivo local só tem 2027: para outro ano, devolva {} e fonte "indisponivel").
    #   Guarde o resultado em _CACHE_FERIADOS[ano] para não chamar a API a cada data.
    #   Referência: aula6/exemplos/11_grafo_real/main.py (buscar_feriados)
    # raise NotImplementedError("ETAPA 4.3: buscar_feriados")

def buscar_feriados(ano: int) -> tuple[dict[str, str], str]:
    
    if ano in _CACHE_FERIADOS:
        return _CACHE_FERIADOS[ano]
    
    try:
        feriados = get_json_com_retry(url=URL_FERIADOS.format(ano=ano))
        resultado = ({f["date"]: f["name"] for f in feriados}, "brasilapi")

    except (OSError, ValueError):
        if ano == 2027:
            resultado = (carregar_feriados_locais(), "arquivo_local")
        else:
            resultado = ({}, "indisponivel")
        
    return resultado


def eh_dia_util(dia: date) -> bool:
    """(PRONTO) Segunda a sexta e não feriado."""
    feriados, _ = buscar_feriados(dia.year)
    return dia.weekday() < 5 and dia.isoformat() not in feriados

# ETAPA 4.4 -- quantos dias úteis entre inicio e fim (AAAA-MM-DD), inclusive. Use eh_dia_util.
# raise NotImplementedError("ETAPA 4.4: dias_uteis")
def dias_uteis(inicio: str, fim: str) -> int:
    dia = date.fromisoformat(inicio)
    ultimo = date.fromisoformat(fim)
    total = 0
    while dia <= ultimo:                 # <= porque o último dia também conta
        if eh_dia_util(dia):
            total += 1
        dia += timedelta(days=1)
    return total
    
# ETAPA 4.4 -- o primeiro dia útil DEPOIS de `fim` (AAAA-MM-DD).
#raise NotImplementedError("ETAPA 4.4: data_retorno")

def data_retorno(fim: str) -> str:
    dia = date.fromisoformat(fim) + timedelta(days=1)   # começa no dia SEGUINTE ao fim
    while not eh_dia_util(dia):                         # pula fim de semana e feriado
        dia += timedelta(days=1)
    return dia.isoformat() 
    
# ETAPA 4.4 -- regra N3: as férias NÃO podem começar nos 2 dias que antecedem um feriado ou fim de semana.
#   Ou seja: o dia de início e os 2 dias seguintes precisam ser dias úteis.
# raise NotImplementedError("ETAPA 4.4: inicio_permitido")
def inicio_permitido(inicio: str) -> bool:
    dia = date.fromisoformat(inicio)
    return all(eh_dia_util(dia + timedelta(days=i)) for i in range(3))   # i = 0, 1, 2
    
# ETAPA 4.5 -- get_json_com_retry(URL_CAMBIO)["rates"]["BRL"]; se falhar de vez, devolva None
#   (o Financeiro escreve "a calcular": o sistema SEGUE e NÃO inventa câmbio).
#   Referência: aula3/agente_retry4.py (consultar_cotacao)
#raise NotImplementedError("ETAPA 4.5: cotacao_usd_brl")

def cotacao_usd_brl() -> float | None:
    
    try:
        
        cotacao = get_json_com_retry(url=URL_CAMBIO)
        return cotacao["rates"]["BRL"]
       
    except (OSError, ValueError, KeyError):
        return None

# ETAPA 4.6 -- normalize (strip, lower, None -> "") e junte com "|"; devolva os 8 primeiros caracteres do
#   sha256 em hexadecimal. O MESMO pedido gera o MESMO protocolo (C1 e C8).
#   Referência: aula3/agente_retry3.py (_chave_idempotencia)
# raise NotImplementedError("ETAPA 4.6: gerar_protocolo")
def gerar_protocolo(matricula: str, tipo: str, data_inicio: str | None, data_fim: str | None) -> str:
    def norm(valor):
        return (valor or "").strip().lower()

    protocolo = "|".join(norm(v) for v in (matricula, tipo, data_inicio, data_fim))
    return hashlib.sha256(protocolo.encode("utf-8")).hexdigest()
    

class TempoEsgotado(Exception):
    """O agente demorou mais que o limite de tempo."""


class LoopExcedido(Exception):
    """O agente passou de max_turns (está em loop)."""

# ETAPA 4.7 -- await asyncio.wait_for(Runner.run(agente, entrada, max_turns=max_turns, **kwargs), timeout=timeout_s)
    #   asyncio.TimeoutError -> levante TempoEsgotado(...)   (o problema é TEMPO)
    #   MaxTurnsExceeded     -> levante LoopExcedido(...)    (o problema é LOOP)
    #   **kwargs repassa hooks=..., context=... (você vai usar hooks no 🆕 B).
    #   Referência: aula3/agente_parada3.py (rodar_com_timeout)
    # raise NotImplementedError("ETAPA 4.7: rodar_com_limites")
async def rodar_com_limites(agente: Agent, entrada: str, max_turns: int = 8, timeout_s: float = 90, **kwargs):
    
    try:
            resultado = await asyncio.wait_for(
                Runner.run(agente, entrada, max_turns=max_turns, **kwargs),
                timeout=timeout_s,
            )
            print("Resposta:", resultado.final_output)
            return resultado
    except asyncio.TimeoutError:
            raise TempoEsgotado(f"{agente.name} passou de {timeout_s}s")
    except MaxTurnsExceeded:
            raise LoopExcedido(f"{agente.name} passou de {max_turns} turnos")
    

def rodar_com_limites_sync(agente: Agent, entrada: str, **kwargs):
    """(PRONTO) Versão síncrona, para usar dentro dos nós do grafo e no fluxo linear."""
    return asyncio.run(rodar_com_limites(agente, entrada, **kwargs))


if __name__ == "__main__":
    inicio = time.perf_counter()
    feriados, fonte = buscar_feriados(2027)
    print(f"feriados 2027: {len(feriados)} (fonte: {fonte}, {time.perf_counter() - inicio:.1f}s)")
    print("hoje:", texto_hoje())
    for dia, esperado in [("2027-04-12", True), ("2027-04-30", False), ("2027-04-15", False), ("2027-05-03", True)]:
        print(f"inicio_permitido({dia}) = {inicio_permitido(dia)}  (esperado {esperado})")
    print("dias úteis 12/04 a 26/04/2027:", dias_uteis("2027-04-12", "2027-04-26"), "| retorno:", data_retorno("2027-04-26"))
    print("cotação USD->BRL:", cotacao_usd_brl())
    p1 = gerar_protocolo("1001", "abono", "2027-04-09", "2027-04-09")
    p8 = gerar_protocolo(" 1001 ", "ABONO", "2027-04-09", "2027-04-09")
    print(f"protocolo C1={p1} C8={p8} iguais={p1 == p8}")
