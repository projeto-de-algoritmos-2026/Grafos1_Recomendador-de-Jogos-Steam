# G22_PA-26.2

## Alunos
|Matrícula | Aluno |
| -- | -- |
| 21/1062179  |  Marcelo de Araújo Lopes |
| 17/0020339  |  Paulo Lucca |

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

Duas decisões que a qualidade e o tempo de execução exigiram:

- **Catálogo externo limitado por gênero e vendas.** Buscar os ~200k apps da
  loja é inviável, então o pool para em 1000 jogos, vindos da busca da loja
  filtrada pelos gêneros do jogo de origem. A ordenação é escolhida no menu;
  o padrão é mais vendidos, porque ordenar por avaliação enche o pool de indie
  nichado de nota alta, que não serve como recomendação.
- **As tags vêm de `IStoreBrowseService/GetItems`, não de `appdetails`.** São
  as tags de usuário (`FPS`, `Souls-like`, `Co-op`), que descrevem o jogo bem
  melhor que os `genres`/`categories` do `appdetails` — lá, recurso de
  plataforma se mistura com gênero, e o CS2 casava com um jogo casual de
  culinária por ambos terem `Stereo Sound` e `Camera Comfort`. O ganho também
  é de tempo: o `appdetails` aceita 1 appid por chamada e corta em ~200
  chamadas/5min (~10min para ~900 jogos), enquanto este aceita 200 appids por
  chamada — o mesmo grafo sai em ~10s.

O resultado de cada consulta fica em `data/cache.json`, gravado de forma
atômica (arquivo temporário + `os.replace`) para uma interrupção no meio da
escrita não corromper o cache.
