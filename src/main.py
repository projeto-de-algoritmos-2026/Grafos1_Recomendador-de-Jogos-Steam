from dotenv import load_dotenv

from steam_client import SteamProfileError, resolve_steam_id

PUBLIC_PROFILE_WARNING = (
    "Aviso: seu perfil Steam precisa estar público "
    "(Configurações -> Privacidade -> Detalhes do jogo), "
    "senão a busca da biblioteca retorna vazia."
)


def prompt_steam_id() -> str:
    print(PUBLIC_PROFILE_WARNING)
    user_input = input("Informe seu SteamID64 ou vanity URL: ")
    try:
        return resolve_steam_id(user_input)
    except SteamProfileError as exc:
        print(f"Erro: {exc}")
        raise SystemExit(1)


def main():
    load_dotenv()
    steam_id = prompt_steam_id()
    print(f"SteamID64 resolvido: {steam_id}")


if __name__ == "__main__":
    main()
