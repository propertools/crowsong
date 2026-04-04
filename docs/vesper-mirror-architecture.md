# Vesper Mirror Architecture

*Local knowledge and package infrastructure for sovereign computing.*

- **Version:** 1.0
- **Classification:** TLP:CLEAR — this document may be shared freely
- **Status:** Active

- Cross-reference: `docs/vesper-archive-protocol.md`,
- `docs/structural-principles.md`

---

## What this is

The Vesper mirror is a reference architecture for a private, air-gapped
knowledge and package infrastructure. It is intended to be reproducible
by any individual, household, small organisation, or community with modest
hardware and a reliable internet connection for the initial fetch.

It applies the same infrastructure resilience principles as the Crowsong
stack: do not assume upstream availability, maintain local continuity,
version everything.

A mirrored corpus is not a pile of files. It is a queryable, auditable,
reproducible knowledge base with:

- Dated snapshots (reproducible state, rollback capability)
- Cryptographic verification before publication
- Consistent internal serving with no upstream dependency for consumers
- Full-text search over key collections
- Local AI inference over the corpus — zero bytes leave the network

**Design principle:** fetch once, verify, freeze, serve locally. The mirror
host is the only node that communicates with the outside world for package
and content fetches. Everything else on the local network talks to
`mirror.local` (or whatever hostname the operator assigns).

This is Structural Principle 13 in practice: availability and integrity
before confidentiality. The mirror is air-gapped for availability, not
secrecy. What you can reach when the internet is gone is what matters.

---

## Reference topology

```
Internet
    ↓
Firewall (egress permitted only to mirror_upstreams alias)
    ↓
Mirror host (fetch + serve — ZFS or equivalent, nginx, rsync, aptly)
    ↓
DMZ or trusted LAN
    ↓
┌─────────────────────────────────────┐
│  Local network consumers            │
│  (workstations, servers, devices)   │
└─────────────────────────────────────┘
```

**Minimum hardware:** a single-board computer or small x86 machine with
500GB+ storage will serve a household or small team. A NAS-class machine
handles a larger organisation. The architecture scales down to a Raspberry
Pi with an external drive for personal use.

**Firewall policy:**

| Rule | Action |
|------|--------|
| Mirror host → mirror_upstreams (80/443/873) | Permit |
| Mirror host → internet (other) | Deny |
| Local network → mirror host:80 | Permit |

---

## Reference hostnames

Adapt to your local DNS. These are illustrative.

| Hostname | Purpose |
|----------|---------|
| `mirror.local` | Packages, standards, content |
| `wiki.local` | Kiwix Wikipedia interface |
| `search.local` | Meilisearch full-text search |
| `maps.local` | OpenStreetMap tile server |
| `ollama.local` | Local AI inference (Open WebUI) |

---

## Storage layout

```
mirror/
├── packages/
│   ├── debian/          # aptly managed
│   ├── openbsd/         # rsync
│   └── freebsd/         # rsync (subset)
├── standards/
│   ├── rfcs/            # rsync from rfc-editor.org
│   └── ietf-drafts/     # rsync from ietf.org
├── knowledge/
│   ├── wikipedia/       # Kiwix ZIM files
│   ├── gutenberg/       # rsync from ibiblio.org
│   ├── standard-ebooks/ # rsync
│   ├── khan-academy/    # Kiwix ZIM files
│   └── arxiv/           # selective by category
├── reference/
│   ├── legal/           # jurisdiction-specific law corpus
│   ├── medical/         # Merck Manual + Medline
│   └── appropriate-tech/ # low-tech and appropriate technology corpus
├── geo/
│   └── osm/             # OpenStreetMap regional extracts
├── source/
│   ├── linux/           # kernel source (git mirror)
│   └── freebsd/         # FreeBSD source tree
├── models/              # GGUF model weights for local inference
└── snapshots/           # snapshot manifests
```

Snapshot naming convention: `DATASET@YYYY-MM-DD`

---

## Tier 1 — Package mirrors

*Highest priority. Get these running before anything else.*

### Debian stable (aptly)

```bash
aptly mirror create debian-stable \
  http://deb.debian.org/debian stable \
  main contrib non-free non-free-firmware

aptly mirror create debian-security \
  http://security.debian.org/debian-security stable-security \
  main contrib non-free non-free-firmware

aptly mirror update debian-stable
aptly snapshot create debian-stable-$(date +%Y-%m-%d) \
  from mirror debian-stable
aptly publish snapshot debian-stable-$(date +%Y-%m-%d) \
  filesystem:mirror/packages/debian:
```

Use a geographically close upstream mirror for the initial fetch.
Size: ~50GB. Schedule: daily sync, weekly snapshot.

### OpenBSD

```bash
rsync -avz --delete \
  rsync://[nearest-mirror]/openbsd/7.x/ \
  /mirror/packages/openbsd/7.x/
```

Size: ~15GB. Schedule: after each release + monthly syspatch sync.

### FreeBSD (subset, amd64)

```bash
rsync -avz --delete \
  rsync://rsync.freebsd.org/FreeBSD/releases/amd64/ \
  /mirror/packages/freebsd/releases/amd64/
```

Size: ~30GB. Schedule: monthly.

---

## Tier 2 — Standards and technical reference

### RFCs

```bash
rsync -avz --delete \
  ftp.rfc-editor.org::rfcs \
  /mirror/standards/rfcs/
```

Size: ~3GB. Schedule: weekly. Post-sync: generate index for Meilisearch.

### IETF drafts

```bash
rsync -avz --delete \
  rsync.ietf.org::internet-drafts \
  /mirror/standards/ietf-drafts/
```

Size: ~10GB. Schedule: weekly.

### arXiv (operator-selected categories)

Select categories relevant to your domain. Common choices:

| Category | Topic |
|----------|-------|
| `cs.NI` | Networking and internet architecture |
| `cs.CR` | Cryptography and security |
| `math.NT` | Number theory |
| `eess.SP` | Signal processing |
| `cs.DC` | Distributed computing |

Size varies by selection: ~5–25GB. Schedule: monthly.
Access via arXiv bulk S3 (see arxiv.org/help/bulk_data_s3).

---

## Tier 3 — Knowledge and library

### Wikipedia (Kiwix)

| File | Size | Language |
|------|------|----------|
| `wikipedia_en_all_nopic` | ~22GB | English (no images) |
| `wikipedia_en_all_maxi` | ~90GB | English (with images) |
| `wikipedia_simple_all` | ~1GB | Simple English |

Add language editions relevant to your community. The `_nopic` variants
are strongly recommended for constrained storage.

```bash
docker run -d \
  --name kiwix \
  -p 8080:8080 \
  -v /mirror/knowledge/wikipedia:/data \
  ghcr.io/kiwix/kiwix-serve \
  --library /data/library.xml
```

Schedule: quarterly (ZIM files are large).

### Project Gutenberg

```bash
rsync -avz --delete \
  ftp.ibiblio.org::gutenberg \
  /mirror/knowledge/gutenberg/ \
  --include="*.txt" --include="*.epub" --exclude="*"
```

Size: ~20GB. Schedule: monthly.

### Standard Ebooks

```bash
rsync -avz --delete \
  standardebooks.org::ebooks \
  /mirror/knowledge/standard-ebooks/
```

Size: ~5GB. Schedule: monthly.

### Khan Academy (Kiwix)

Recommended ZIM files: `khan_academy_en_math`, `khan_academy_en_science`,
`khan_academy_en_computing`. Size: ~15GB. Schedule: quarterly.

### OpenStreetMap (regional extracts)

```bash
# Fetch extracts for your region from Geofabrik
wget https://download.geofabrik.de/[region]-latest.osm.pbf \
  -O /mirror/geo/osm/[region]-latest.osm.pbf
```

Size: varies by region. Schedule: monthly.
Serve via OpenMapTiles or Nominatim Docker.

---

## Tier 4 — Reference and resilience

### Legal corpus

Fetch the primary law corpus for your jurisdiction. For EU operators:

- EUR-Lex bulk XML: `eur-lex.europa.eu`
- National law portals (most EU member states provide bulk access)
- GDPR full text and implementing regulations

Size: ~2–5GB depending on jurisdiction. Schedule: quarterly.

Offline access to applicable law is a professional capability for any
organisation operating under regulatory frameworks.

### Medical reference

- Merck Manual (older public domain editions via Gutenberg)
- Medline abstracts (NLM bulk download: `ftp.ncbi.nlm.nih.gov`)
- WHO technical documents (bulk download available)

Size: ~5GB. Schedule: quarterly.

### Appropriate technology corpus

- Practical Action technical briefs (free download)
- Low-tech Magazine articles (full site archivable via wget)
- Village Earth appropriate technology library

Size: ~3GB. Schedule: annual.

This corpus is particularly relevant for operators supporting communities
with constrained infrastructure — the audience the Crowsong stack is
explicitly designed to serve.

### Source code mirrors

```bash
# Linux kernel
git clone --mirror \
  https://github.com/torvalds/linux \
  /mirror/source/linux.git

# Update
git --git-dir=/mirror/source/linux.git remote update
```

Size: ~10GB. Schedule: weekly.

---

## Tier 5 — Local intelligence layer

*Air-gapped AI inference. No internet dependency at inference time.*

### Model weights

Recommended starting configuration (GGUF format, quantised):

```
mirror/models/
├── mistral-7b-instruct-v0.3.Q4_K_M.gguf      ~4.1GB
├── llama-3.2-3b-instruct.Q4_K_M.gguf         ~2.0GB
├── phi-3.5-mini-instruct.Q4_K_M.gguf         ~2.2GB
└── nomic-embed-text-v1.5.Q4_K_M.gguf         ~270MB
```

Verify all model weights against published SHA256 checksums before use.
Serve via Ollama.

### Inference stack

```bash
# Ollama
docker run -d \
  --name ollama \
  --restart unless-stopped \
  -p 11434:11434 \
  -v /mirror/models:/root/.ollama/models \
  ollama/ollama

# Open WebUI
docker run -d \
  --name open-webui \
  --restart unless-stopped \
  -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  --link ollama \
  open-webui/open-webui
```

### Why this corpus is well-suited for local AI

The Vesper mirror is an unusually high-quality RAG corpus:

- **RFCs + IETF drafts** — technical precision, formal structure, authoritative
- **Gutenberg + Standard Ebooks** — literary breadth, clean text, no SEO noise
- **arXiv selected** — scientific reasoning, domain depth
- **Wikipedia** — encyclopaedic breadth, consistent structure
- **Legal corpus** — formal register, domain vocabulary
- **Appropriate technology corpus** — practical knowledge for constrained environments

Combined: a curated, multi-domain corpus without CommonCrawl's noise.
Considerably higher signal-to-noise than most hobbyist corpora, and
verifiable — every item was fetched from a known source, checksummed,
and snapshotted.

### The sovereign computing demonstration

```
Query submitted at ollama.local
         ↓
Open WebUI → Ollama (local inference, no internet)
         ↓
RAG query → Meilisearch (local index, no internet)
         ↓
Retrieved context from RFC/corpus (local storage, no internet)
         ↓
Answer returned to user

Zero bytes leave the network.
```

This capability is directly relevant to:

- Organisations with data sovereignty requirements under GDPR or
  sector-specific regulation
- Communities operating under unreliable or surveilled internet connectivity
- Emergency operations centres requiring continued function during outages
- Any operator for whom "the cloud is unavailable" is a design condition,
  not an edge case

---

## Serving infrastructure

### nginx

```nginx
server {
    listen 80;
    server_name mirror.local;
    root /mirror;
    autoindex on;
    autoindex_exact_size off;
    autoindex_localtime on;

    location /debian/      { alias /mirror/packages/debian/public/; }
    location /openbsd/     { alias /mirror/packages/openbsd/; }
    location /freebsd/     { alias /mirror/packages/freebsd/; }
    location /rfcs/        { alias /mirror/standards/rfcs/; }
    location /ietf-drafts/ { alias /mirror/standards/ietf-drafts/; }
    location /gutenberg/   { alias /mirror/knowledge/gutenberg/; }
    location /standard-ebooks/ { alias /mirror/knowledge/standard-ebooks/; }
    location /osm/         { alias /mirror/geo/osm/; }

    location /wiki/   { proxy_pass http://127.0.0.1:8080/; }
    location /search/ { proxy_pass http://127.0.0.1:7700/; }
    location /maps/   { proxy_pass http://127.0.0.1:8081/; }
    location /ollama/ { proxy_pass http://127.0.0.1:3000/; }
}
```

### Meilisearch

```bash
docker run -d \
  --name meilisearch \
  -p 7700:7700 \
  -v /mirror/search-index:/meili_data \
  getmeili/meilisearch:latest
```

Index: RFCs, IETF drafts, Gutenberg, arXiv, any local document corpus.

---

## Sync schedule (reference)

| Collection | Frequency | Suggested window |
|------------|-----------|-----------------|
| Debian stable | Daily | 02:00 local |
| Debian security | Daily | 02:30 local |
| OpenBSD syspatch | Weekly | Sunday 03:00 |
| FreeBSD | Monthly | 1st Sunday 04:00 |
| RFCs | Weekly | Sunday 03:30 |
| IETF drafts | Weekly | Sunday 04:00 |
| Wikipedia ZIM | Quarterly | Manual |
| Gutenberg | Monthly | 15th 05:00 |
| Standard Ebooks | Monthly | 15th 05:30 |
| Khan Academy | Quarterly | Manual |
| arXiv | Monthly | 1st Sunday 06:00 |
| OSM extracts | Monthly | 1st Sunday 07:00 |
| Legal corpus | Quarterly | Manual |
| Git mirrors | Weekly | Sunday 05:00 |

All sync jobs should log to syslog or equivalent. Alert on failure.
Take a snapshot after every successful sync.

---

## Snapshot policy (reference)

| Dataset | Frequency | Retention |
|---------|-----------|-----------|
| packages/debian | Weekly | 12 weeks |
| packages/openbsd | Per release | All |
| standards/rfcs | Weekly | 52 weeks |
| knowledge/wikipedia | Quarterly | 4 quarters |
| knowledge/gutenberg | Monthly | 12 months |
| All others | Monthly | 6 months |

Export snapshot manifests to a secondary storage location weekly for
off-mirror verification.

---

## Firewall upstream allowlist

Adjust for your nearest mirrors. This is a reference list for a
European operator:

```
deb.debian.org
security.debian.org
ftp.rfc-editor.org
rsync.ietf.org
rsync.freebsd.org
ftp.ibiblio.org
download.kiwix.org
standardebooks.org
download.geofabrik.de
arxiv.org
eur-lex.europa.eu
ftp.ncbi.nlm.nih.gov
```

Firewall rule: mirror host → allowlist, permit TCP 80/443/873.
All other egress from mirror host: deny.

---

## Storage estimates

| Collection | Size | Growth/year |
|------------|------|-------------|
| Debian stable + security | ~50GB | ~10GB |
| OpenBSD | ~15GB | ~5GB |
| FreeBSD subset | ~30GB | ~5GB |
| RFCs + IETF drafts | ~13GB | ~1GB |
| Wikipedia EN (no images) | ~22GB | ~3GB |
| Project Gutenberg | ~20GB | ~2GB |
| Standard Ebooks | ~5GB | ~1GB |
| Khan Academy | ~15GB | ~2GB |
| arXiv selected | ~25GB | ~5GB |
| OSM regional | ~5GB | ~1GB |
| Legal corpus | ~3GB | ~0.5GB |
| Medical reference | ~5GB | ~0.5GB |
| Appropriate tech | ~3GB | ~0.2GB |
| Source mirrors | ~10GB | ~3GB |
| Model weights | ~9GB | ~3GB |
| Search + embedding indexes | ~25GB | ~5GB |
| Snapshots (6 months) | ~100GB | — |
| **Total** | **~360GB** | **~48GB/year** |

A 1TB drive is sufficient for a comfortable initial deployment.
A 2TB drive provides room for several years of growth and full snapshots.

---

## Consumer configuration

### Debian (`/etc/apt/sources.list`)

```
deb http://mirror.local/debian/ stable main contrib non-free non-free-firmware
deb http://mirror.local/debian/ stable-updates main contrib non-free non-free-firmware
deb http://mirror.local/debian/ stable-security main contrib non-free non-free-firmware
```

### OpenBSD (`/etc/installurl`)

```
http://mirror.local/openbsd/
```

---

## Connection to the Crowsong stack

The Vesper mirror is the Crowsong stack's local knowledge layer. It provides:

- **Availability without upstream dependency** — the stack operates when
  the internet does not
- **Integrity by default** — filesystem checksums, cryptographic verification
  before publication, snapshot audit trail
- **The sovereign computing demonstration** — AI-assisted reasoning over
  a technical corpus, air-gapped, on owned hardware

The RFC and IETF draft corpus provides offline access to the standards the
Crowsong stack implements. The appropriate technology corpus serves the
communities the stack is designed to reach. Together they constitute a
self-contained knowledge base for operating the stack without external
infrastructure.

This is what Structural Principle 13 looks like when instantiated in iron:
availability and integrity before confidentiality, all the way down.

---

- *Vesper Mirror Architecture v1.0*
- *Proper Tools SRL — propertools.be*
- *TLP:CLEAR*
