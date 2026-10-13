# Roda tudo o que a ficha pede e grava em saida_ficha.txt
# Uso (na pasta aula10, com a venv ativa):  powershell -ExecutionPolicy Bypass -File .\rodar_ficha.ps1
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$OUT = "saida_ficha.txt"
Remove-Item $OUT -ErrorAction SilentlyContinue
 
function Rodar([string]$titulo, [string]$cmd) {
    Write-Host ">> $titulo"
    "`n===================== $titulo =====================`n> $cmd" | Out-File $OUT -Append -Encoding utf8
    cmd /c "$cmd 2>&1" | Out-File $OUT -Append -Encoding utf8
}
function Limpar { Remove-Item saidas\*.json, saidas\*.jsonl, saidas\*.db -ErrorAction SilentlyContinue }
 
Limpar
# Etapas 0 a 6
Rodar "E0 dados_rh"            "python dados_rh.py"
Rodar "E1 agente"              "python etapa01_agente.py"
Rodar "E2 extracao"            "python etapa02_extracao.py"
Rodar "E2 votacao (A)"         "python etapa02_extracao.py --votacao"
Rodar "E3 guardrails"          "python etapa03_guardrails.py"
$env:FERIADOS_OFFLINE = "1"
Rodar "E4 OFFLINE"             "python etapa04_ferramentas.py"
Remove-Item Env:FERIADOS_OFFLINE
Rodar "E4 ONLINE"              "python etapa04_ferramentas.py"
Rodar "E5 cliente MCP"         "python etapa05_cliente_mcp.py"
Rodar "E5 cliente MCP agente"  "python etapa05_cliente_mcp.py --agente"
Rodar "E6 regras"              "python etapa06_regras.py"
Rodar "E6 linear"              "python etapa06_linear.py"
 
# Etapa 7
Limpar
Rodar "E7 C1"                  "python etapa07_grafo.py C1_abono_simples"
Rodar "E7 C6"                  "python etapa07_grafo.py C6_conflito_de_escala"
 
# Etapa 8: C2 -> pendentes -> nao:motivo -> sim 1010 ; C11 sim 1011 duas vezes
Rodar "E8 C2"                  "python etapa07_grafo.py C2_ferias_com_venda"
Rodar "E8 pendentes"           "python etapa07_grafo.py --pendentes"
Rodar "E8 C2 nao"              "python etapa07_grafo.py --retomar C2_ferias_com_venda `"nao:venda so 5 dias, nao 10`" 1010"
Rodar "E8 C2 sim 1010"         "python etapa07_grafo.py --retomar C2_ferias_com_venda sim 1010"
Rodar "E8 C11"                 "python etapa07_grafo.py C11_diaria_exterior"
Rodar "E8 C11 sim 1011 (1a)"   "python etapa07_grafo.py --retomar C11_diaria_exterior sim 1011"
Rodar "E8 C11 sim 1011 (2a)"   "python etapa07_grafo.py --retomar C11_diaria_exterior sim 1011"
 
# Etapa 9 (mantem a auditoria; apaga so checkpoints e registros)
Remove-Item saidas\*.db, saidas\registros.json -ErrorAction SilentlyContinue
Rodar "E9 C2"                  "python etapa07_grafo.py C2_ferias_com_venda"
Rodar "E9 autoaprovacao 1002"  "python etapa07_grafo.py --retomar C2_ferias_com_venda sim 1002"
Remove-Item saidas\*.db -ErrorAction SilentlyContinue
Rodar "E9 C2 de novo"          "python etapa07_grafo.py C2_ferias_com_venda"
Rodar "E9 chefia errada 1011"  "python etapa07_grafo.py --retomar C2_ferias_com_venda sim 1011"
Rodar "E9 sem guardrail C7"    "python etapa07_grafo.py --sem-guardrail C7_autoaprovacao"
Rodar "E9 auditoria"           "type saidas\auditoria.jsonl"
 
# Etapa 11 (limpa, todos, retoma C2 e C11) + Etapa 10 + mermaid
Limpar
Rodar "E11 todos"              "python etapa07_grafo.py --todos"
Rodar "E11 C2 sim 1010"        "python etapa07_grafo.py --retomar C2_ferias_com_venda sim 1010"
Rodar "E11 C11 sim 1011"       "python etapa07_grafo.py --retomar C11_diaria_exterior sim 1011"
Rodar "E10 observabilidade C2" "python etapa10_observabilidade.py C2_ferias_com_venda"
Rodar "E11 mermaid"            "python etapa07_grafo.py --mermaid"
Rodar "CONFERIR"               "python conferir.py --opcionais"
Write-Host "`nPronto. Me mande o arquivo $OUT"