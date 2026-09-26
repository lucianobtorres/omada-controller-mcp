"""Script de teste para validação de conexão e autenticação com o Omada Controller.

Execução:
    uv run python test_connection.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

from omada_auth.auth import OmadaSession


def main() -> None:
    # Carrega variáveis do arquivo .env
    load_dotenv()

    base_url = os.environ.get("OMADA_BASE_URL", "https://your-controller.local:8043")
    verify_ssl = os.environ.get("OMADA_VERIFY_SSL", "false").lower() == "true"

    print("=== Teste de Conexão com Omada Controller ===")
    print(f"URL Base: {base_url}")
    print(f"Verificar SSL: {verify_ssl}")

    try:
        # Inicializa a sessão com o Omada Controller
        session = OmadaSession(base_url=base_url, verify_ssl=verify_ssl)

        print("\n[1/3] Autenticando com o Omada Controller...")
        omadac_id = session.omadac_id
        print(f"✓ Autenticação bem-sucedida! Omada Controller ID (omadacId): {omadac_id}")

        print("\n[2/3] Listando Sites gerenciados...")
        sites_res = session.request("GET", f"/openapi/v1/{omadac_id}/sites")
        sites = sites_res if isinstance(sites_res, list) else sites_res.get("data", []) if isinstance(sites_res, dict) else []
        
        print(f"Found {len(sites)} site(s):")
        for site in sites:
            site_name = site.get("name") if isinstance(site, dict) else site
            site_id = site.get("id") if isinstance(site, dict) else ""
            print(f" - Site: {site_name} (ID: {site_id})")

        print("\n[3/3] Listando Dispositivos gerenciados (roteadores/switches/APs)...")
        devices_res = session.request("GET", f"/openapi/v1/{omadac_id}/devices")
        
        devices: list[dict[str, Any]] = []
        if isinstance(devices_res, list):
            devices = devices_res
        elif isinstance(devices_res, dict):
            devices = devices_res.get("data", []) or devices_res.get("result", [])

        if not devices:
            print("Nenhum dispositivo encontrado ou resposta vazia.")
        else:
            print(f"Total de dispositivos encontrados: {len(devices)}")
            for idx, dev in enumerate(devices, 1):
                name = dev.get("name", "Sem nome")
                model = dev.get("model", dev.get("type", "Desconhecido"))
                mac = dev.get("mac", "N/A")
                ip = dev.get("ip", "N/A")
                status = dev.get("status", "N/A")
                print(f"  [{idx}] Dispositivo: {name} | Modelo: {model} | MAC: {mac} | IP: {ip} | Status: {status}")

        print("\n✓ Teste concluído com sucesso!")

    except Exception as exc:
        print(f"\n❌ Erro durante o teste de conexão: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
