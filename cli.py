"""Console Interativo OmadaSecOps com Gemini 2.5 Flash e Tool Calling da API Omada.

Execução:
    uv run python cli.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Carrega o arquivo .env de forma explícita com caminho absoluto antes de importar módulos do servidor
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

from google import genai
from google.genai import types

from omada_mcp import server
from omada_mcp.server import (
    _startup,
    call_operation as mcp_call_operation,
    get_lan_networks as mcp_get_lan_networks,
    get_operation_schema as mcp_get_operation_schema,
    get_topology as mcp_get_topology,
    list_clients as mcp_list_clients,
    list_devices as mcp_list_devices,
    list_gateway_acls as mcp_list_gateway_acls,
    list_ip_groups as mcp_list_ip_groups,
    list_sites as mcp_list_sites,
    list_time_range_profiles as mcp_list_time_range_profiles,
    search_operations as mcp_search_operations,
)

# Instruções de Sistema para o especialista OmadaSecOps
SYSTEM_INSTRUCTION = """Você é o OmadaSecOps, um assistente sênior especialista em Engenharia de Redes, Segurança da Informação e Arquitetura de Redes TP-Link Omada SDN.

Sua missão:
1. Auxiliar o administrador de rede na consulta, análise de status, monitoramento de clientes conectados, topologia, subnets/LAN, servidores DNS, grupos de IP, perfis de horário e regras de rede (VLANs, ACLs) do Omada Controller local.
2. Atuar com postura defensiva e transparente. Todas as operações estão protegidas pela política de segurança Read-Only/Allowlist do projeto.
3. Utilizar ativamente as ferramentas integradas (`list_devices`, `list_clients`, `list_sites`, `get_topology`, `get_lan_networks`, `list_ip_groups`, `list_gateway_acls`, `list_time_range_profiles`, `search_operations`, `get_operation_schema`, `call_operation`) para coletar dados empíricos em tempo real antes de responder.
4. Fornecer respostas claras, técnicas e estruturadas em Português do Brasil (PT-BR), destacando modelos de equipamentos (ex: roteador ER605, switches JetStream, APs EAP), IPs, MACs, VLANs, servidores DNS e diagnósticos de rede.
"""


def _to_json_str(val: object) -> str:
    """Helper para converter qualquer resultado de tool para string JSON limpa e serializável."""
    return json.dumps(val, default=str, ensure_ascii=False)


def list_sites() -> str:
    """Lista todos os sites gerenciados pelo Omada Controller."""
    return _to_json_str(mcp_list_sites())


def list_devices(site_id: str = "") -> str:
    """Lista todos os dispositivos gerenciados (roteador ER605, switches, APs) no Omada Controller. Se site_id for fornecido, filtra por esse site."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_list_devices(site_id=s_id))


def list_clients(site_id: str = "") -> str:
    """Lista os clientes/dispositivos conectados na rede. Se site_id for fornecido, filtra por esse site."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_list_clients(site_id=s_id))


def get_topology(site_id: str = "") -> str:
    """Obtém os dados de topologia física e lógica da rede Omada. Se site_id for fornecido, filtra por esse site."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_get_topology(site_id=s_id))


def get_lan_networks(site_id: str = "") -> str:
    """Obtém as configurações de redes LAN (subnets, gateways, servidores DNS) configurados no Omada Controller."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_get_lan_networks(site_id=s_id))


def list_ip_groups(site_id: str = "") -> str:
    """Lista os grupos de IP (IP Group Profiles) cadastrados no Omada Controller."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_list_ip_groups(site_id=s_id))


def list_gateway_acls(site_id: str = "") -> str:
    """Lista as regras de ACL de Gateway (OSG ACLs) configuradas no Omada Controller."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_list_gateway_acls(site_id=s_id))


def list_time_range_profiles(site_id: str = "") -> str:
    """Lista os perfis de horário (Time Range Profiles) configurados no Omada Controller."""
    s_id = site_id if site_id else None
    return _to_json_str(mcp_list_time_range_profiles(site_id=s_id))


def search_operations(query: str = "", limit: int = 20) -> str:
    """Busca operações permitidas na API do Omada por palavra-chave (ex: client, device, vlan, acl, topology)."""
    return _to_json_str(mcp_search_operations(query=query, limit=limit))


def get_operation_schema(operation_id: str = "") -> str:
    """Obtém o schema detalhado de parâmetros de uma operação OpenAPI permitida pelo seu operation_id."""
    return _to_json_str(mcp_get_operation_schema(operation_id=operation_id))


def call_operation(
    operation_id: str = "",
    path_params_json: str = "{}",
    query_params_json: str = "{}",
) -> str:
    """Executa uma operação catalogada e permitida da API do Omada Controller pelo seu operation_id (apenas leitura).

    path_params_json e query_params_json aceitam dicionários em formato string JSON.
    """
    path_params = json.loads(path_params_json) if path_params_json and path_params_json != "{}" else None
    query_params = json.loads(query_params_json) if query_params_json and query_params_json != "{}" else None
    res = mcp_call_operation(
        operation_id=operation_id,
        path_params=path_params,
        query_params=query_params,
    )
    return _to_json_str(res)


def main() -> None:
    # 1. Carrega variáveis de ambiente
    load_dotenv()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Erro: A variável GEMINI_API_KEY não foi encontrada no ambiente ou arquivo .env", file=sys.stderr)
        print("Adicione GEMINI_API_KEY=sua_chave no arquivo .env para utilizar o console interativo.", file=sys.stderr)
        sys.exit(1)

    print("=== OmadaSecOps Interactive CLI (Gemini 2.5 Flash) ===")
    print(f"URL Controller: {server.BASE_URL}")
    print(f"Modo Read-Only: {server.READ_ONLY}")
    print("Inicializando sessão com o Omada Controller...")

    try:
        # 2. Inicializa sessão Omada e constrói o catálogo
        _startup()
        print("✓ Conexão e catálogo do Omada inicializados com sucesso!")
    except Exception as exc:
        print(f"⚠️ Aviso ao conectar ao Omada Controller: {exc}", file=sys.stderr)
        print("Tentando prosseguir com o catálogo em fallback...", file=sys.stderr)

    # 3. Inicializa cliente Gemini
    client = genai.Client(api_key=api_key)

    tools_list = [
        list_sites,
        list_devices,
        list_clients,
        get_topology,
        get_lan_networks,
        list_ip_groups,
        list_gateway_acls,
        list_time_range_profiles,
        search_operations,
        get_operation_schema,
        call_operation,
    ]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=tools_list,
        temperature=0.2,
    )

    print("\nInicializando chat com gemini-2.5-flash...")
    chat = client.chats.create(model="gemini-2.5-flash", config=config)

    print("\n---------------------------------------------------------")
    print(" Console OmadaSecOps Pronto!")
    print(" Digite sua mensagem em linguagem natural (ou 'sair' para encerrar).")
    print("---------------------------------------------------------\n")

    while True:
        try:
            user_input = input("OmadaSecOps > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "sair"):
                print("\nEncerrando sessão OmadaSecOps. Até logo!")
                break

            response = chat.send_message(user_input)
            print(f"\n{response.text}\n")

        except KeyboardInterrupt:
            print("\n\nSessão encerrada pelo usuário.")
            break
        except Exception as exc:
            print(f"\n❌ Erro ao processar requisição: {exc}\n")


if __name__ == "__main__":
    main()
