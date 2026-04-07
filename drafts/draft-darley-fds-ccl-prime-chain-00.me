# CCL Prime-Chain Schedule
## Draft specification section for draft-darley-fds-ccl-prime-twist-01

*Status: pre-normative design sketch*
*To be incorporated into §4 (Key Schedule) and §7 (Schedule Variants)*

---

## Abstract

The prime-chain schedule extends the standard CCL ouroboros construction
by allowing the key schedule to walk through a deterministic chain of
primes rather than cycling through a single prime. Digits 0 and 1 in
the active prime's digit sequence trigger hops to adjacent primes; the
hopped-to prime's digit sequence drives the base selection for that
position. The walk is fully deterministic from the seed prime and
requires no additional key material.

---

## 1. Background and motivation

In the standard CCL schedule (§4.1), digits 0 and 1 in the key prime
are degenerate: base 0 and base 1 cannot represent any non-trivial token
value, so positions scheduled to these bases fall back to base 10 and
contribute no twist. Approximately 20% of positions in a typical 77-digit
prime produce no twist under the standard schedule.

The prime-chain schedule eliminates this waste by repurposing digits 0
and 1 as control flow operators. Every digit in the key schedule now
drives real work: either a base-switch twist (digits 2–9) or a prime
hop combined with a base-switch twist drawn from the destination prime
(digits 0 and 1).

The result is a key schedule whose trajectory through prime-space is
determined by the primes themselves. The schedule has memory: the prime
active at position i depends on the full history of hops from position
0 through i−1. This property makes the schedule non-periodic at any
practical message length and renders the twist-map insufficient for
key schedule reconstruction without the seed.

---

## 2. Definitions

**Seed prime P₀:** The prime derived from the key verse via the
standard verse-to-prime construction (§3). This is the starting point
of the prime walk.

**Active prime Pₐ:** The prime currently governing the key schedule.
Initially Pₐ = P₀. Updated at each hop.

**Prime walk:** The sequence of primes visited during encoding, fully
determined by P₀ and the input length.

**Hop:** A transition from the active prime Pₐ to an adjacent prime,
triggered by digit 0 (hop up) or digit 1 (hop down) in Pₐ's digit
sequence.

**Walk floor:** A lower bound on the prime walk, defined as the
smallest prime greater than 2^255. Hops that would cross the floor
are redirected upward (see §4.3).

---

## 3. Schedule construction

### 3.1 Initialisation

```
Pₐ ← P₀           (seed prime, from verse-to-prime)
pos ← 0            (position in input token stream)
walk ← [P₀]        (prime walk log, for verification)
```

### 3.2 Per-token processing

For each input token T at position pos:

```
d ← digits(Pₐ)[pos mod len(digits(Pₐ))]

if d == 0:
    P_next ← next_prime(Pₐ)
    b ← digits(P_next)[pos mod len(digits(P_next))]
    output ← twist(T, b)          # feasibility fallback applies
    Pₐ ← P_next
    append P_next to walk

elif d == 1:
    P_prev ← prev_prime(Pₐ)      # subject to floor rule (§4.3)
    b ← digits(P_prev)[pos mod len(digits(P_prev))]
    output ← twist(T, b)          # feasibility fallback applies
    Pₐ ← P_prev
    append P_prev to walk

else:                              # d in {2, 3, 4, 5, 6, 7, 8, 9}
    b ← d
    output ← twist(T, b)          # feasibility fallback applies
    # Pₐ unchanged

pos ← pos + 1
```

### 3.3 Base twist and feasibility fallback

The twist function is identical to the standard schedule (§4.1):

```
twist(T, b):
    if b^WIDTH > T:
        return repr(T, base=b, width=WIDTH)   # re-express in base b
    else:
        return repr(T, base=10, width=WIDTH)  # fallback: base 10
```

The feasibility fallback applies identically whether b was drawn
from the active prime in-place (d ∈ 2–9) or from the hop destination
prime (d ∈ 0–1). The fallback does not affect the prime walk — if a
hop was triggered, Pₐ is updated regardless of whether the base was
feasible.

### 3.4 Floor rule for downward hops

If a downward hop (d == 1) would produce a prime below the walk floor:

```
WALK_FLOOR ← smallest prime > 2^255
```

Then the hop is redirected upward:

```
if prev_prime(Pₐ) < WALK_FLOOR:
    P_hop ← next_prime(Pₐ)       # redirect: hop up instead
else:
    P_hop ← prev_prime(Pₐ)
```

The base b is drawn from P_hop regardless of direction. The walk log
records P_hop. This rule ensures the walk remains within the range
where Miller-Rabin primality testing is well-characterised.

---

## 4. Reversal

### 4.1 What the receiver needs

The receiver requires:

1. The seed prime P₀ (or the seed verse, from which P₀ is derived)
2. The twisted token stream
3. The twist-map (base used per position, as in the standard schedule)

The prime walk is NOT required in the artifact. It is fully
reconstructable from P₀ and the token count.

### 4.2 Reversal procedure

The receiver replays the walk identically to the encoder:

```
Pₐ ← P₀
pos ← 0

for each twisted token T_twisted at position pos:
    d ← digits(Pₐ)[pos mod len(digits(Pₐ))]

    if d == 0:
        P_hop ← next_prime(Pₐ)
        b ← twist_map[pos]         # verify: should match digits(P_hop)[pos mod ...]
        T_plain ← untwist(T_twisted, b)
        Pₐ ← P_hop

    elif d == 1:
        P_hop ← prev_prime_or_redirect(Pₐ)
        b ← twist_map[pos]
        T_plain ← untwist(T_twisted, b)
        Pₐ ← P_hop

    else:
        b ← twist_map[pos]         # verify: should equal d (or 10 if fallback)
        T_plain ← untwist(T_twisted, b)
        # Pₐ unchanged

    pos ← pos + 1
```

The twist-map provides the actual base used (after feasibility
fallback). The walk provides the expected base (before fallback).
A receiver MAY verify that the twist-map base matches the expected
base from the walk, modulo the fallback rule. A receiver MUST NOT
fail if a fallback was applied — the fallback is a normal condition.

### 4.3 Walk verification (OPTIONAL)

An implementation MAY log the prime walk during encoding and include
it as an optional RSRC field for debugging. A receiver that receives
a walk log MAY verify it matches the reconstructed walk. This field
is advisory only and MUST NOT be required for reversal.

---

## 5. RSRC block

The prime-chain schedule is declared in the artifact RSRC block as:

```
RSRC: BEGIN
  TYPE:         ccl-prime-twist
  VERSION:      1
  SCHEDULE:     prime-chain/1
  SEED-PRIME:   <P₀ — decimal string>
  TWIST-MAP:    <pos:base pos:base ...>
  WIDTH:        5
  TOKENS:       <count>
  CRC32:        <hex>
RSRC: END
```

**SCHEDULE: prime-chain/1** — identifies this schedule variant. A
receiver encountering an unrecognised schedule identifier MUST NOT
attempt to decode the CCL layer and MUST surface the version mismatch
to the operator (per Structural Principle 14).

**SEED-PRIME** — the decimal string of P₀. Sufficient for the
receiver to reconstruct the full walk. The verse that generated P₀
is NOT included — it is the operator's secret.

**TWIST-MAP** — identical format to the standard schedule. Records
the actual base used at each position after feasibility fallback.
Positions using base 10 (fallback) are recorded as base 10.

---

## 6. Properties

### 6.1 Completeness

Every digit in the key schedule drives real work. Digits 0 and 1,
previously dead weight producing base-10 fallthrough, now trigger
prime hops and draw bases from the destination prime. No position
in the schedule is wasted.

### 6.2 Non-periodicity

The standard schedule repeats with period len(P₀.digits) ≈ 77. The
prime-chain schedule has no fixed period — the active prime changes
at each hop, and the hop frequency and direction are determined by
the digit distribution of each prime visited. In practice, for any
message longer than a few hundred tokens, the walk will have visited
multiple distinct primes and the schedule will not repeat.

### 6.3 Walk opacity

The twist-map records the base used at each position but not which
prime was active. An observer with the twist-map but not the seed
prime cannot reconstruct the walk. At hop positions, the base is
drawn from the destination prime — indistinguishable in the
twist-map from an in-place twist of the same base. The hop positions
are not marked.

### 6.4 Determinism

The walk is fully deterministic from P₀ and the token count. Two
implementations given the same P₀ MUST produce identical walks and
identical twisted output. This property is verified by the canonical
test vector (§8).

### 6.5 Composability

The prime-chain schedule is composable with stacking. Each pass in
a CCL stack may independently use the standard schedule or the
prime-chain schedule. The RSRC block for each pass declares its
own schedule. Mixed stacks (e.g. pass 1 standard, pass 2
prime-chain, pass 3 standard) are valid and SHOULD be supported
by conformant implementations.

---

## 7. Implementation notes

### 7.1 prev_prime efficiency

`next_prime(n)` is well-characterised: increment by 2 (for odd n)
and test primality. `prev_prime(n)` is symmetric: decrement by 2
and test. For 77-digit primes, the prime gap is at most a few
thousand, so both operations complete in milliseconds on any
modern device. Primality testing uses the same Miller-Rabin witness
set as the standard construction.

### 7.2 Walk state

The encoder and decoder maintain a single state variable: the active
prime Pₐ. No additional state is required. The walk is a pure
function of P₀ and the sequence of digits encountered.

### 7.3 Digit indexing across primes

When the active prime changes (on a hop), the digit index resets to
`pos mod len(new_prime.digits)`. This means the digit drawn from the
destination prime at a hop position is:

```
digits(P_hop)[pos mod len(digits(P_hop))]
```

not `digits(P_hop)[0]`. The walk does not restart the digit sequence
on each hop — it uses the current global position modulo the new
prime's length. This ensures that the base drawn at a hop position
is a function of both the destination prime and the input position,
not just the destination prime.

### 7.4 Relationship to standard schedule

The prime-chain schedule is a strict superset of the standard
schedule. A prime P₀ with no digits 0 or 1 would produce an
identical output under both schedules. In practice this does not
occur — all sufficiently large primes contain both digits — but
the relationship is useful for understanding the construction.

---

## 8. Canonical test vector

*To be generated after implementation.*

The canonical test vector for the prime-chain schedule uses:

```
Seed verse:  "Factoring primes in the hot sun,
              I fought Entropy — and Entropy won."
P₀:          11527664883411634260504727650961908130612748343418385764879292322648049456943
Schedule:    prime-chain/1
Input:       archive/second-law-blues.txt (UCS-DEC encoded)
```

Expected output: to be committed to `archive/` after implementation.
The canonical test vector MUST verify:

1. The walk visits the expected sequence of primes
2. The twist-map matches the expected base-per-position sequence
3. Reversal recovers the original token stream exactly
4. CRC32 of the recovered stream matches the declared value

---

## 9. Open questions

**Q1: Walk log as optional RSRC field**
Should implementations be encouraged to include the walk log as an
optional RSRC field for debugging? The log is potentially large (one
prime per hop, ~15 hops per 77 digits ≈ several kilobytes for long
messages). Recommendation: optional, advisory, MUST NOT be required
for reversal.

**Q2: Hop frequency tuning**
The hop frequency is determined by the frequency of digits 0 and 1
in the active prime's digit sequence — approximately 20% of positions.
Is this the right frequency? Could a variant reserve additional digits
as hop triggers (e.g. digits 0, 1, and one other) to increase walk
complexity? Deferred pending empirical analysis.

**Q3: Multi-hop per position**
Could a single position trigger multiple hops (e.g. if the
destination prime's digit at that position is also 0 or 1)? The
current construction applies at most one hop per position. Multi-hop
would increase walk complexity but also complexity of the reversal
procedure. Deferred.

**Q4: Named prime chains**
Should the spec define named prime chains — e.g. a chain seeded
from K1 together with a specific walk length — as named constants
analogous to the mathematical constants in `docs/constants/`? This
would allow interoperability without sharing the seed verse.
Deferred pending use case analysis.

---

## 10. Relationship to existing constructions

| Property | Standard schedule | Prime-chain schedule |
|----------|-----------------|---------------------|
| Key material | Single prime P₀ | Single prime P₀ |
| Schedule period | len(P₀.digits) ≈ 77 | No fixed period |
| Dead positions | ~20% (digits 0, 1) | Zero |
| Walk opacity | N/A | Hop positions invisible in twist-map |
| Reversal requirement | Twist-map only | Seed prime + twist-map |
| Composable with stacking | Yes | Yes |
| Composable with Gloss layer | Yes | Yes |
| Implementation complexity | Low | Medium |
| Spec complexity | Low | Medium |

The prime-chain schedule adds meaningful complexity in the right
places: the key schedule is harder to characterise statistically,
hop positions are invisible in the output, and no digit is wasted.
The reversal procedure is only marginally more complex than the
standard schedule.

CCL provides no cryptographic confidentiality regardless of schedule.
The prime-chain schedule raises the cost of passive schedule
reconstruction, not the cost of active decryption with the seed.

---

*Pre-normative. Subject to revision.*
*Proper Tools SRL — propertools.be*
*TLP:CLEAR*
