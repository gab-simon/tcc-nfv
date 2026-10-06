# NFV-MANO

Implementação simples de um NFV-MANO em Python, baseada na arquitetura da ETSI. O foco é só o funcionamento do MANO.

## Componentes

- NFVO: orquestra os Network Services e mantém os catálogos.
- VNFM: gerencia o ciclo de vida das VNFs.
- VIM: gerencia os recursos da infraestrutura NFVI.
- Também existem os repositórios com informações sobre NSs, VNFs, instâncias e recursos da infraestrutura.

## Requisitos

- [uv](https://docs.astral.sh/uv/)
- Python 3.12+

## Como usar

```bash
uv sync
uv run ruff check .
uv run nfv-mano --help

# iniciar um componente
uv run nfv-mano serve vim

# executar uma demonstração completa
uv run nfv-mano demo
```

Por padrão o estado fica em memória e o VIM é simulado (driver `mock`).

Para usar Docker e salvar o estado em arquivo:

```bash
export NFV_MANO_REPOSITORY_BACKEND=file
export NFV_MANO_VIM_DRIVER=docker
```

## Documentação

- [`docs/arquitetura-etsi.md`](docs/arquitetura-etsi.md): componentes, reference points e configuração.