# NFV-MANO (base ETSI)

Base de um NFV-MANO em Python seguindo a arquitetura padrão da ETSI.
O foco inicial é o **NFV-MANO sem tolerância a falhas**; a tolerância a
falhas (Raft/etcd) é trabalho futuro.

## Componentes ETSI

- **NFVO** — Network Functions Virtualisation Orchestrator (`Os-Ma-nfvo`).
- **VNFM** — VNF Manager (`Or-Vnfm`, `Ve-Vnfm-*`).
- **VIM** — Virtualised Infrastructure Manager (`Vi-Vnfm`, `Nf-Vi`).
- Repositórios ETSI: NS Catalog, VNF Catalog, NS/VNF Instances, NFVI Resources.

## Requisitos

- [uv](https://docs.astral.sh/uv/)
- Python 3.12+ (gerenciado pelo uv)

## Uso

```bash
uv sync                       # cria o ambiente e instala as dependências
uv run pytest                 # testes
uv run ruff check .           # lint
uv run nfv-mano --help        # CLI

# Sobe um componente (nfvo, vnfm ou vim)
uv run nfv-mano serve vim

# Executa um ciclo de vida de Network Service de ponta a ponta (driver mock)
uv run nfv-mano demo
```

Por padrão os componentes usam o backend de repositório em memória e o driver
de VIM simulado. Para usar Docker e persistência em arquivo:

```bash
export NFV_MANO_REPOSITORY_BACKEND=file
export NFV_MANO_VIM_DRIVER=docker
```

## Documentação

- [`docs/arquitetura-etsi.md`](docs/arquitetura-etsi.md) — arquitetura ETSI e
  mapeamento dos reference points para o código.
- [`docs/mapeamento-implementacoes.md`](docs/mapeamento-implementacoes.md) —
  relação com as implementações de referência (`nham` e `aodoan/tcc`).
- [`docs/requisitos-tolerancia-falhas.md`](docs/requisitos-tolerancia-falhas.md)
  — Proposta 0.1 e requisitos de tolerância a falhas (trabalho futuro).
- [`docs/referencias.md`](docs/referencias.md) — referências.
