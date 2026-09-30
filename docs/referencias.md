# Referências

## ETSI NFV

- ETSI GS NFV 002 — *Network Functions Virtualisation (NFV); Architectural
  Framework*. Define VNF, NFVI e NFV-MANO, além dos reference points.
- ETSI GS NFV-IFA 010 — *Management and Orchestration; Functional requirements
  specification*.
- ETSI GS NFV-SOL 001 — *VNF Descriptor (VNFD)*.
- ETSI GS NFV-SOL 002 — *Network Service Descriptor (NSD)*.
- ETSI GS NFV-SOL 003 — *VNF Lifecycle Management (VNF LCM)*.
- ETSI GS NFV-SOL 005 — *OS-Ma-Nfvo reference point (NS LCM)*.
- Portal do ISG NFV: <https://www.etsi.org/committee/1425-nfv>

## Tolerância a falhas, consenso e estado distribuído

- Raft — página oficial: <https://raft.github.io/>
- Raft — paper *In Search of an Understandable Consensus Algorithm*:
  <https://raft.github.io/raft.pdf>
- etcd — armazenamento distribuído (Raft): <https://etcd.io/>
- *Fault-Tolerant NFV MANO* (trabalho futuro):
  <https://ieeexplore.ieee.org/abstract/document/9459426>

## Implementações de referência

- `giovannivenancio/nham` — NFV High-Availability Module
  (Python 2, REST/Eve, arquivos, FMS + State Manager):
  <https://github.com/giovannivenancio/nham/tree/master/nfv-mano>
- `aodoan/tcc` — projeto `nfv` (Python 3, RabbitMQ + Docker):
  <https://github.com/aodoan/tcc/tree/main/projeto/nfv>

## Ferramentas

- `uv` — gerenciador de projetos/ambientes Python: <https://docs.astral.sh/uv/>
- FastAPI — framework das APIs dos reference points:
  <https://fastapi.tiangolo.com/>
- Pydantic — modelos e validação: <https://docs.pydantic.dev/>
- Docker SDK for Python — driver `Nf-Vi`:
  <https://docker-py.readthedocs.io/>

## Documentos internos

- [`arquitetura-etsi.md`](./arquitetura-etsi.md) — arquitetura e mapeamento de
  reference points.
- [`mapeamento-implementacoes.md`](./mapeamento-implementacoes.md) — relação com
  as implementações de referência.
- [`requisitos-tolerancia-falhas.md`](./requisitos-tolerancia-falhas.md) —
  Proposta 0.1 e requisitos de tolerância a falhas.
