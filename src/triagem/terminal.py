"""Chat de triagem pelo terminal."""

import argparse
import asyncio

from triagem.memoria import configurar_conversa
from triagem.runtime import abrir_grafo, executar_turno


async def run_turn(graph, text: str, config: dict) -> None:
    def mostrar_no(node: str, update: dict) -> None:
        details = ""
        if node == "grade_documents":
            details = f"{update['grade']['binary_score']}: {update['grade']['reason']}"
        print(f"  · {node} {details}".rstrip())

    resposta, registro = await executar_turno(graph, text, config, ao_atualizar=mostrar_no)
    if registro.ferramentas:
        print("  · ferramentas:", ", ".join(registro.ferramentas))
    if registro.skills:
        print("  · skills:", ", ".join(registro.skills))
    print()
    print("assistente:", resposta)
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread-id", help="UUID de uma conversa para retomar")
    parser.add_argument("mensagens", nargs="*")
    args = parser.parse_args()
    config = configurar_conversa(args.thread_id)
    async with abrir_grafo() as graph:
        print("Conversa:", config["configurable"]["thread_id"])
        if args.mensagens:
            for text in args.mensagens:
                print("você:", text)
                await run_turn(graph, text, config)
            return
        while text := input("você: ").strip():
            await run_turn(graph, text, config)


if __name__ == "__main__":
    asyncio.run(main())
