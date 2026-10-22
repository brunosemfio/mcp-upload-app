# Upload App MCP Server

Servidor MCP (Model Context Protocol) para enviar um `.aab` para uma faixa de teste da Google Play ou um `.ipa` para o TestFlight e depois promover para produção. O servidor não gera o build: cada projeto de app gera o próprio arquivo, e as ferramentas só recebem o caminho. Por baixo, o servidor roda lanes do [fastlane](https://fastlane.tools) que vêm dentro do pacote.

## Ferramentas expostas

- `upload_android` — envia um `.aab` para uma faixa de teste (`internal`, `alpha`, `beta` ou o nome de uma faixa fechada personalizada; padrão `internal`)
- `promote_android` — promove um version code de uma faixa de teste para produção, com rollout gradual e notas da versão opcionais
- `update_rollout_android` — muda a fração de uma release de produção, completa o rollout com `1` ou para a release com `halt=true`
- `status_android` — lista as releases de cada faixa, com version codes, status e fração do rollout
- `upload_ios` — envia um `.ipa` para o TestFlight, sem esperar o processamento da Apple
- `release_ios` — anexa um build do TestFlight a uma versão da App Store, cria a versão se ela não existir e envia para review, com as novidades da versão opcionais
- `status_ios` — mostra as últimas versões da App Store com o estado de cada uma e os últimos builds com o estado do processamento

`promote_android`, `update_rollout_android` e `release_ios` só publicam com `confirm=true`. Sem ele, as duas ferramentas do Android validam a mudança na Google Play sem publicar nada, e `release_ios` só descreve o que vai fazer.

## Pré-requisitos

Funciona só no macOS, porque o envio para o TestFlight depende do Xcode.

- [uv](https://docs.astral.sh/uv/): baixa e executa o servidor. Se a máquina não tiver Python 3.10 ou mais novo, o `uv` baixa um sozinho.
- [git](https://git-scm.com/): o `uvx` usa o git para baixar o código deste repositório.
- [fastlane](https://fastlane.tools): faz os envios para as lojas.
- [Xcode](https://developer.apple.com/xcode/): necessário para `upload_ios`.

Com [Homebrew](https://brew.sh/):

```bash
brew install uv git fastlane
```

## Configuração

### 1. Google Play

1. No Google Cloud, habilite a [Google Play Android Developer API](https://console.cloud.google.com/apis/library/androidpublisher.googleapis.com), crie uma service account e baixe a chave JSON.
2. No Play Console, em **Usuários e permissões → Convidar novo usuário**, convide o e-mail da service account com as permissões de lançamento em faixas de teste e em produção nos apps desejados.
3. Guarde a chave num local fixo e anote o caminho completo. O caminho vai na variável `GOOGLE_APPLICATION_CREDENTIALS` quando você registrar o servidor no cliente MCP.

Se você já criou o arquivo `~/.config/google-play-console/.env` para o [mcp-google-play-console](https://github.com/brunosemfio/mcp-google-play-console), este servidor lê o mesmo arquivo. Se a chave de publicação for diferente da chave de relatórios daquele servidor, acrescente o caminho dela ao arquivo na variável `SUPPLY_JSON_KEY`:

```bash
echo 'SUPPLY_JSON_KEY=/Users/voce/keys/play-publisher.json' >> ~/.config/google-play-console/.env
```

Com uma service account só para os dois servidores, o `GOOGLE_APPLICATION_CREDENTIALS` do arquivo basta. Para usar outro arquivo, defina `PLAY_CONSOLE_ENV_FILE` com o caminho dele. Variáveis já definidas no ambiente têm prioridade sobre o arquivo, mas o `SUPPLY_JSON_KEY` do arquivo tem prioridade sobre o `GOOGLE_APPLICATION_CREDENTIALS` do ambiente.

### 2. App Store Connect

O servidor usa as mesmas variáveis do [mcp-app-store-connect](https://github.com/brunosemfio/mcp-app-store-connect):

| Variável | Valor |
|---|---|
| `APP_STORE_CONNECT_KEY_ID` | Key ID da chave, ex. `2X9R4HXF34` |
| `APP_STORE_CONNECT_ISSUER_ID` | Issuer ID, ex. `57246542-96fe-1a63-e053-0824d011072a` |
| `APP_STORE_CONNECT_PRIVATE_KEY_PATH` | Caminho completo do `.p8` |

Se você já criou o arquivo `~/.config/app-store-connect/.env` para aquele servidor, este lê o mesmo arquivo e não precisa de mais nada. Para usar outro arquivo, defina `APP_STORE_CONNECT_ENV_FILE` com o caminho dele. Variáveis já definidas no ambiente têm prioridade sobre o arquivo.

A chave precisa da função App Manager ou Admin para enviar builds para review.

## Instalação e uso

### Claude Code

1. Registre o servidor. O `--scope user` deixa o servidor disponível em qualquer pasta.

   ```bash
   claude mcp add --scope user upload-app \
     --env GOOGLE_APPLICATION_CREDENTIALS=/Users/voce/keys/play-publisher.json \
     -- uvx --from git+https://github.com/brunosemfio/mcp-upload-app.git upload-app-mcp
   ```

   Se a chave do Google Play estiver no arquivo `.env`, remova a linha de `--env`.

2. Rode `claude mcp list`. O `upload-app` deve aparecer como conectado.

Para trocar algum valor, remova o servidor com `claude mcp remove --scope user upload-app` e registre de novo.

### Claude Desktop

Abra o arquivo de configuração em **Settings → Developer → Edit Config** e adicione o servidor dentro de `mcpServers`:

```json
{
  "mcpServers": {
    "upload-app": {
      "command": "/opt/homebrew/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/brunosemfio/mcp-upload-app.git",
        "upload-app-mcp"
      ],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/Users/voce/keys/play-publisher.json",
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

- Troque `/opt/homebrew/bin/uvx` pelo resultado de `which uvx`.
- O `PATH` deixa o servidor encontrar o `fastlane`. O Claude Desktop aberto pelo Dock não enxerga o PATH do terminal.
- Se a chave do Google Play estiver no arquivo `.env`, remova a linha do `GOOGLE_APPLICATION_CREDENTIALS`.

Encerre o Claude Desktop com Cmd+Q e abra de novo para carregar a configuração.

O `uvx` faz cache do build: para atualizar após novos commits, rode o comando uma vez com `--refresh`. Para fixar uma versão, aponte para uma tag ou commit: `git+https://...@<tag-ou-sha>`.

### A partir de um clone local (desenvolvimento)

```bash
git clone https://github.com/brunosemfio/mcp-upload-app.git
cd mcp-upload-app
uv sync
uv run upload-app-mcp
```

Para registrar no cliente MCP, use como comando o executável que o `uv sync` cria dentro do clone: `/caminho/do/clone/.venv/bin/upload-app-mcp`.

## Desenvolvimento

```bash
uv sync --extra dev
uv run pytest
uv run ruff check upload_app_mcp tests
uv run mypy upload_app_mcp
```

Os testes não chamam o fastlane nem as lojas. O CI (GitHub Actions, branch `main`) roda ruff, mypy e a suíte com cobertura mínima de 65% em Python 3.10 e 3.12.

## Exemplos de perguntas

- "Envie /caminho/app-release.aab para a faixa internal do com.example.app."
- "Promova o version code 42 do com.example.app para produção com rollout de 20% e a nota 'Correções de bugs'."
- "O crash rate da versão 42 subiu. Pare o rollout."
- "O build 15 do com.example.app já terminou de processar? Se sim, envie a versão 1.2.0 para review."

## Notas

- `upload_ios` não espera o processamento da Apple, que costuma levar de 10 a 30 minutos. Use `status_ios`: o build só pode ir para review quando estiver `VALID`.
- Sem `release_notes`, `release_ios` não altera os metadados da versão, e as novidades precisam estar preenchidas no App Store Connect. Com `release_notes`, o texto vai para todos os idiomas da versão publicada, ou para o idioma principal do app se ainda não houver versão publicada.
- No `promote_android`, `locale` é o código de idioma da Play para as notas da versão, por padrão `pt-BR`.
- O `Info.plist` do app precisa declarar `ITSAppUsesNonExemptEncryption`; sem isso, a Apple pede a conformidade de exportação e o envio para review falha.
- `rollout` aceita valores maiores que 0 e até 1. Abaixo de 1, a release entra em produção como lançamento gradual. Para retomar uma release parada, chame `update_rollout_android` com uma nova fração.
- Cada ferramenta devolve as últimas 40 linhas da saída do fastlane e tem timeout de 30 minutos.
