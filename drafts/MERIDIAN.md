# Meridian Protocol

`draft-darley-meridian-protocol-01` lives in its own repository:

**https://github.com/propertools/meridian-protocol**

It is included here as a git submodule at `meridian-protocol/`.

To initialise after cloning:

```bash
git submodule update --init --recursive
```

## How Meridian composes with the Crowsong Suite

Meridian is the L5 Content Layer of the Crowsong Suite:

- Meridian manifests MAY be distributed as FDS-FRAME messages
  over any Crowsong channel, including non-binary channels,
  when DNS and HTTPS are unavailable

- Meridian signing keys MAY be distributed via SHARD-BUNDLE
  over physical media

- Meridian failover MAY be verified via MIRROR-ATTESTATION
  when DNS is unavailable

- The SUCCESSION-PACKET (Meridian §3.6) is the primary
  integration point with the Crowsong trust layer (L4)

See `docs/crowsong-suite-overview.md` for the full picture.
