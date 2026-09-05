# G22_PA-26.2

## Alunos
|Matrícula | Aluno |
| -- | -- |
| 21/1062179  |  Marcelo de Araújo Lopes |
| xx/xxxxxx  |  Paulo Lucca |

## Instalação

1. Clone o repositório.
2. Crie um ambiente virtual: `python -m venv venv` e ative-o.
3. Instale as dependências: `pip install -r requirements.txt`.
4. Copie `.env.example` para `.env` e preencha `STEAM_API_KEY` com sua chave gerada em https://steamcommunity.com/dev/apikey.
5. Execute o projeto: `python src/main.py`.

## Escopo do grafo

O grafo de recomendação é construído **só sobre a biblioteca do usuário**
(jogos que ele já possui), não sobre um catálogo maior externo. Nós = appids
da biblioteca; aresta entre dois jogos existe se `jaccard(tags_a, tags_b) >
0.1`, com peso `1 - jaccard`. Recomendação, portanto, aponta para jogos que
o usuário já tem mas talvez não tenha jogado — não para jogos novos.
