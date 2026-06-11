# Nexar

Nexar e um sistema Django para pesquisar modelos de veiculos e exibir pecas compativeis cadastradas no catalogo.

## O que esta pronto

- Projeto Django com SQLite.
- Pagina publica de busca por modelo, marca, versao ou ano.
- Cadastro de modelos/aplicacoes de veiculos, sem depender de placa.
- Cadastro de categorias de pecas pelo painel.
- Cadastro de pecas.
- Importacao de pecas por XML de NF-e ou CSV.
- Vinculo de compatibilidade entre pecas e veiculos.
- Painel protegido por senha especial.
- Importacao automatizada de modelos pela FIPE DeividFortuna/Parallelum.

## Rodando o projeto

Instale as dependencias:

```bash
python -m pip install -r requirements.txt
```

Crie/atualize o banco:

```bash
python manage.py migrate
```

Opcionalmente, carregue dados demo do Voyage:

```bash
python manage.py seed_demo
```

Para testar a importacao FIPE com uma amostra pequena:

```bash
python manage.py import_fipe --brand-limit 1 --model-limit 1
```

Para popular rapidamente marcas e modelos sem consultar anos, use:

```bash
python manage.py import_fipe --catalog-only
```

Esse modo evita a maioria dos erros `429`, porque usa poucas requisicoes. Os modelos entram com ano nao especificado, e depois podem ser enriquecidos aos poucos.

Depois de importar o catalogo rapido, voce pode criar os anos somente para modelos ja existentes:

```bash
python manage.py import_fipe --expand-existing-years --brand-code 59 --sleep 0.5
```

Esse comando cria registros especificos por ano, por exemplo uma entrada generica `VW Voyage` pode virar entradas como `VW Voyage 2018`, `VW Voyage 2019` e `VW Voyage 2020`. Se a entrada generica ja tiver pecas vinculadas, os vinculos sao copiados para os anos criados.

Importante: modelos importados antes desta versao talvez ainda nao tenham os codigos internos da FIPE salvos. Nesse caso, rode novamente o catalogo rapido da marca antes de expandir anos:

```bash
python manage.py import_fipe --brand-code 59 --catalog-only --sleep 0.2
python manage.py import_fipe --expand-existing-years --brand-code 59 --sleep 0.5
```

Se voce ja importou muitos modelos antes dos codigos internos existirem, preencha esses codigos primeiro:

```bash
python manage.py import_fipe --brand-code 59 --backfill-codes --sleep 0.2
python manage.py import_fipe --brand-code 59 --expand-existing-years --sleep 0.5
```

Para importar carros sem limitar marca/modelo:

```bash
python manage.py import_fipe
```

Use com cuidado: a API gratuita tem limite diario e a importacao completa pode fazer muitas requisicoes.
O ideal e importar por marcas prioritarias, em vez de puxar o Brasil inteiro de uma vez:

```bash
python manage.py import_fipe --brand-code 59 --catalog-only --sleep 0.2
```

Tambem da para importar varias marcas:

```bash
python manage.py import_fipe --brand-code 59,21,23 --catalog-only --sleep 0.2
```

Na API v1, alguns codigos comuns sao:

- `59`: VW - VolksWagen
- `21`: Fiat
- `23`: GM - Chevrolet
- `25`: Honda
- `56`: Toyota

Se aparecer erro `429 Too Many Requests`, voce atingiu o limite temporario da FIPE. Espere alguns minutos ou rode com uma pausa maior:

```bash
python manage.py import_fipe --sleep 1 --retry-wait 180
```

O comando imprime `Modelo CODIGO - nome` durante a execucao. Se parar no meio, voce pode retomar a partir de uma marca/modelo:

```bash
python manage.py import_fipe --start-brand-code 7 --start-model-code 9785 --sleep 1 --retry-wait 180
```

Inicie o servidor:

```bash
python manage.py runserver
```

Acesse:

```text
http://127.0.0.1:8000/
```

## Acessando por outros dispositivos na mesma rede

Para acessar o Nexar em celulares, notebooks ou outros computadores da mesma rede, deixe o computador principal ligado e rode o servidor aceitando conexoes externas.

1. Descubra o IP do computador que vai hospedar o Nexar:

```powershell
ipconfig
```

Procure por `Endereco IPv4`, por exemplo:

```text
192.168.100.42
```

2. No arquivo `nexar/settings.py`, adicione esse IP em `ALLOWED_HOSTS`:

```python
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "192.168.100.42"]
```

Se outro computador for virar o host depois, troque esse IP pelo IP dele, ou mantenha os dois:

```python
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "192.168.100.42", "192.168.100.55"]
```

3. Rode o Django assim:

```bash
python manage.py runserver 0.0.0.0:8000
```

4. Nos outros dispositivos da mesma rede, acesse:

```text
http://192.168.100.42:8000/
```

Use `http`, nao `https`.

5. Se nao abrir, libere a porta 8000 no firewall do computador host. No PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "Nexar Django 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

Para testar a conexao em outro computador:

```powershell
Test-NetConnection 192.168.100.42 -Port 8000
```

Se `TcpTestSucceeded` for `True`, a rede esta chegando no servidor.

## Painel protegido

O painel fica em:

```text
http://127.0.0.1:8000/painel/
```

Senha inicial:

```text
34260120
```

Essa senha pode ser alterada por variavel de ambiente:

```bash
NEXAR_STAFF_PASSWORD=outra-senha
```

## Como cadastrar pecas e compatibilidades

1. Acesse `/painel/`.
2. Entre com a senha especial.
3. Cadastre um modelo em "Novo modelo", por exemplo Volkswagen Voyage 1.6 MSI Comfortline.
4. Cadastre categorias em "Nova categoria", como Oleo, Filtro de ar ou Bieleta.
5. Cadastre uma peca em "Nova peca".
6. No cadastro da peca, marque os modelos compativeis.

Na pagina publica, pesquise pelo modelo do carro, por exemplo `Voyage 2020`, escolha o resultado exato e o Nexar exibira as pecas vinculadas ao modelo selecionado.

## Importando pecas por XML ou CSV

No painel, use o botao "Importar pecas" para enviar um ou mais arquivos XML de NF-e ou CSV de uma vez.

O Nexar importa somente os itens da nota em `det > prod`, ignorando dados de emitente, destinatario, CNPJ, impostos e cobranca.

Campos aproveitados:

- `cProd`: codigo principal do produto, usado no cadastro da peca.
- `xProd`: usado para separar codigo e nome da peca. Exemplo: `PD60-PASTILHA FREIO`.
- `cEAN`: codigo de barras.
- `NCM`: classificacao fiscal.
- `uCom`: unidade.
- `qCom`: ultima quantidade comprada.
- `vUnCom`: ultimo custo unitario.
- `vProd`: ultimo total comprado.
O codigo que aparece antes do hifen em `xProd`, como `PD60` ou `LX4894`, fica guardado nas observacoes como referencia/modelo do produto. O codigo principal usado pelo Nexar passa a ser o `cProd`, como `124285`.

Se uma peca com o mesmo codigo ja existir, ela sera atualizada. Se nao existir, sera criada.

Para CSV, o Nexar tenta reconhecer colunas comuns, como:

- `codigo`, `cod`, `referencia`, `sku`
- `nome`, `descricao`, `produto`
- `marca`, `fabricante`
- `categoria`, `grupo`, `linha`
- `ean`, `codigo de barras`, `gtin`
- `ncm`
- `unidade`
- `preco`, `valor`, `custo`
- `quantidade`
- `total`

## Vinculando pecas por PDF ou XLSX

No painel, use "Vincular pecas por PDF" para enviar tabelas de aplicacao em `.pdf`, `.xlsx` ou `.xlsm`.

O fluxo recomendado e:

1. Envie a planilha e clique em "Pre-visualizar".
2. Confira quais pecas e modelos foram encontrados.
3. Se estiver certo, envie a mesma planilha e clique em "Aplicar vinculos".

O importador tenta reconhecer colunas comuns de peca e veiculo, como `codigo`, `peca`, `marca`, `modelo`, `versao`, `motor`, `ano`, `ano inicial` e `ano final`. Ele tambem aceita tabelas largas, onde cada linha representa um carro e as colunas seguintes trazem codigos de pecas.

Para PDF, o arquivo precisa ter texto extraivel. Se o PDF for uma imagem escaneada, gere uma versao com OCR ou envie a planilha original.

## Importando modelos pela FIPE

O comando principal e:

```bash
python manage.py import_fipe
```

Por padrao, ele usa a API FIPE v2:

```text
https://fipe.parallelum.com.br/api/v2
```

Tambem e possivel configurar no `.env`:

```bash
NEXAR_FIPE_API_BASE_URL=https://parallelum.com.br/fipe/api/v1
NEXAR_FIPE_API_VERSION=v1
NEXAR_FIPE_API_TOKEN=
```

Configuracao recomendada:

```bash
NEXAR_FIPE_API_BASE_URL=https://fipe.parallelum.com.br/api/v2
NEXAR_FIPE_API_VERSION=v2
NEXAR_FIPE_API_TOKEN=
```

Criando um token gratuito em https://fipe.online, a FIPE informa que o limite sobe de 500 para 1000 requisicoes por 24h. Coloque esse token em `NEXAR_FIPE_API_TOKEN`.

Opcoes uteis:

```bash
python manage.py import_fipe --vehicle-type carros
python manage.py import_fipe --vehicle-type motos
python manage.py import_fipe --vehicle-type caminhoes
python manage.py import_fipe --brand-limit 5 --model-limit 20
python manage.py import_fipe --with-values
```

`--with-values` faz uma consulta extra por ano/modelo para preencher detalhes como `CodigoFipe` e combustivel oficial, entao consome muito mais requisicoes.

Fonte da API FIPE: https://deividfortuna.github.io/fipe/
