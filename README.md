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

Os nós do grafo são a **biblioteca do usuário + um catálogo externo** da loja
Steam, e a recomendação sempre aponta para um jogo que ele **ainda não tem**.
O caminho até lá pode passar por jogos da biblioteca — é isso que dá sentido
ao Dijkstra em vez de só olhar o vizinho mais parecido.

Aresta entre dois jogos existe se `jaccard(tags_a, tags_b) > 0.1`, com peso
`1 - jaccard` (peso baixo = jogos parecidos).

Duas decisões que a qualidade da recomendação exigiu:

- **Catálogo externo limitado por gênero e vendas.** Buscar os ~200k apps da
  loja é inviável pelo rate limit do `appdetails` (~200 chamadas/5min). O pool
  vem da busca da loja filtrada pelos gêneros do jogo de origem e ordenada por
  mais vendidos. Ordenar por avaliação enche o pool de indie nichado de nota
  alta, que não serve como recomendação.
- **Nem toda tag entra no Jaccard.** O `appdetails` mistura, em `categories`,
  modo de jogo (`Co-op`, `PvP`) com recurso de plataforma e acessibilidade
  (`Steam Trading Cards`, `Remote Play on TV`, `Stereo Sound`). Só o primeiro
  grupo indica semelhança: sem esse filtro o CS2 casava com um jogo casual de
  culinária por ambos terem `Camera Comfort` e `Custom Volume Controls`.
