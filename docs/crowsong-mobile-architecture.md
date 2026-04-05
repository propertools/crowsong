# Crowsong Mobile — Architecture Sketch

*Offline UCS-DEC + CCL decoder for Android and iOS*

**Version:** 0.1 (pre-normative)
**Status:** Architecture sketch for developer handoff.
**Classification:** TLP:CLEAR

---

## What this app does

A person photographs printed pages of a UCS-DEC+CCL artifact — a VPN
profile, a firmware image, a document, a key shard — using the device
camera. The app:

1. Extracts the decimal token stream via on-device OCR
2. Validates token shape and verifies CRC32 against the declared value
3. Accepts a key from the user (verse, melody, image, or named constant)
4. Derives the prime, unstacks the CCL layers
5. Saves the decoded payload to local storage
6. Installs directly if the payload is a recognised type (MDM profile, etc.)

**No network connection required at any step.**

The app that provisions a secure network connection requires no network
connection to operate. This is a feature.

---

## Target scenario

```
Pawn shop handset, no SIM, wifi off
  ↓
APK sideloaded from USB / F-Droid / local network
  ↓
Open camera → photograph printed pages
  ↓
On-device OCR extracts token stream
  ↓
App validates: token shape + CRC32
  "531 VALUES · CRC32:E8DC9BF3 — VERIFIED"
  ↓
User enters key:
  verse typed / spoken       → prime P₁
  melody intervals hummed    → prime P₂
  logo images tapped         → prime P₃ (binary seed)
  ↓
App derives prime, unstacks CCL
  ↓
Decoded payload saved locally
  ↓
If MDM profile: install directly
If firmware: export via OTG
If document: open in local reader
If key shard: store in secure enclave
```

---

## Platform choices

### Android (primary)

**Language:** Kotlin
**Minimum SDK:** API 24 (Android 7.0, 2016) — covers ~95% of active devices
**Distribution:** APK sideload + F-Droid. No Google Play required.

**Key platform APIs:**
- OCR: ML Kit Text Recognition v2 (`com.google.mlkit:text-recognition`)
  — fully offline, no network call, models bundled at install
- Camera: CameraX (`androidx.camera`)
- Storage: internal app storage (`Context.filesDir`) — no permissions needed
- MDM install: `DevicePolicyManager` + `ACTION_PROVISION_MANAGED_PROFILE`
- Secure key storage: Android Keystore (for derived primes, never raw key)

**Why Android first:**
- Sideloading is trivial (enable unknown sources, install APK)
- F-Droid distribution requires no Google account
- Older hardware is cheap and widely available globally
- Used handsets are available in pawn shops worldwide

### iOS (secondary)

**Language:** Swift
**Minimum iOS:** 15.0 (2021) — covers ~90% of active devices
**Distribution:** AltStore / sideloading (7-day re-sign cycle without
developer account) or TestFlight. App Store submission possible but not
required for the use case.

**Key platform APIs:**
- OCR: Vision framework (`VNRecognizeTextRequest`) — offline, on-device
- Camera: AVFoundation / VisionKit (`DataScannerViewController` on iOS 16+)
- Storage: app sandbox Documents directory
- MDM install: `UIApplication.openURL` with `.mobileconfig` payload
  triggers system install dialog — no MDM enrollment required for
  simple VPN profiles

**Limitation:** iOS sideloading requires either a developer account
($99/year) or the 7-day re-sign cycle via AltStore. For the target
scenario (pawn shop handset), Android is strongly preferred.

---

## Core logic — platform-independent

The following algorithms are pure arithmetic with no platform
dependencies. ~130 lines total. Port once, test exhaustively.

### 1. Token validation

```kotlin
// Kotlin
val TOKEN_RE = Regex("""^\d{5}$""")  // WIDTH/5
fun isValidToken(s: String) = TOKEN_RE.matches(s)
```

```swift
// Swift
let tokenRE = /^\d{5}$/
func isValidToken(_ s: String) -> Bool { s.wholeMatch(of: tokenRE) != nil }
```

### 2. CRC32 verification

```kotlin
// Kotlin (java.util.zip.CRC32)
fun crc32hex(payload: String): String {
    val crc = CRC32()
    crc.update(payload.toByteArray(Charsets.UTF_8))
    return "%08X".format(crc.value)
}
```

```swift
// Swift (zlib via Foundation)
import zlib
func crc32hex(_ payload: String) -> String {
    let data = Data(payload.utf8)
    let value = data.withUnsafeBytes { ptr in
        zlib.crc32(0, ptr.bindMemory(to: UInt8.self).baseAddress, uInt(data.count))
    }
    return String(format: "%08X", value)
}
```

### 3. Base conversion

```kotlin
// Kotlin — from_base (parse token in given base to Int)
fun fromBase(token: String, base: Int): Int =
    if (base == 10) token.toInt() else token.toInt(base)

// to_base (format Int in given base, zero-padded to width)
fun toBase(n: Int, base: Int, width: Int): String =
    if (base == 10) n.toString().padStart(width, '0')
    else n.toString(base).padStart(width, '0')
```

### 4. Twist-map decode

```kotlin
// Kotlin — parse sparse "pos:base,pos:base,..." string
fun decodeTwistMap(encoded: String, tokenCount: Int): IntArray {
    val map = IntArray(tokenCount) { 10 }  // default: base 10
    if (encoded.isBlank()) return map
    encoded.split(",").forEach { pair ->
        val parts = pair.trim().split(":")
        if (parts.size == 2) {
            val pos = parts[0].trim().toIntOrNull() ?: return@forEach
            val base = parts[1].trim().toIntOrNull() ?: return@forEach
            if (pos in 0 until tokenCount) map[pos] = base
        }
    }
    return map
}
```

### 5. CCL untwist (single pass)

```kotlin
// Kotlin
fun untwist(tokens: List<String>, twistMap: IntArray, width: Int): List<String> =
    tokens.mapIndexed { i, tok ->
        val n = fromBase(tok, twistMap[i])
        n.toString().padStart(width, '0')
    }
```

### 6. Miller-Rabin primality

```kotlin
// Kotlin — BigInteger-based for 77-digit primes
import java.math.BigInteger

val WITNESSES = listOf(2,3,5,7,11,13,17,19,23,29,31,37).map { it.toBigInteger() }

fun isPrime(n: BigInteger): Boolean {
    if (n < 2.toBigInteger()) return false
    for (p in WITNESSES) {
        if (n == p) return true
        if (n.mod(p) == BigInteger.ZERO) return false
    }
    var d = n - BigInteger.ONE; var r = 0
    while (d.mod(2.toBigInteger()) == BigInteger.ZERO) { d /= 2.toBigInteger(); r++ }
    outer@ for (a in WITNESSES) {
        if (a >= n) continue
        var x = a.modPow(d, n)
        if (x == BigInteger.ONE || x == n - BigInteger.ONE) continue
        repeat(r - 1) {
            x = x.modPow(2.toBigInteger(), n)
            if (x == n - BigInteger.ONE) return@outer
        }
        return false
    }
    return true
}

fun nextPrime(n: BigInteger): BigInteger {
    var candidate = if (n <= 2.toBigInteger()) 2.toBigInteger()
                    else if (n.mod(2.toBigInteger()) == BigInteger.ZERO) n + BigInteger.ONE
                    else n
    while (!isPrime(candidate)) candidate += 2.toBigInteger()
    return candidate
}
```

### 7. Verse → prime

```kotlin
// Kotlin
import java.security.MessageDigest
import java.text.Normalizer

fun derivePrimeFromVerse(verse: String): BigInteger {
    // NFC normalise + strip
    val normalised = Normalizer.normalize(verse.trim(), Normalizer.Form.NFC)
    // UCS-DEC encode
    val tokens = normalised.codePoints().toArray()
        .joinToString(" ") { "%05d".format(it) }
    // SHA256
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(tokens.toByteArray(Charsets.UTF_8))
    // Interpret as BigInteger N
    val N = BigInteger(1, digest)
    return nextPrime(N)
}
```

### 8. Binary seed → prime

```kotlin
// Kotlin — any byte array (image, audio, document)
fun derivePrimeFromBytes(data: ByteArray): BigInteger {
    val digest = MessageDigest.getInstance("SHA-256").digest(data)
    return nextPrime(BigInteger(1, digest))
}
```

### 9. Melody (interval sequence) → prime

```kotlin
// Kotlin
fun derivePrimeFromIntervals(intervals: List<Int>): BigInteger {
    val canonical = intervals
        .map { it.coerceIn(-24, 24) }
        .joinToString(" ") { "%+03d".format(it) }
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(canonical.toByteArray(Charsets.UTF_8))
    return nextPrime(BigInteger(1, digest))
}
```

---

## OCR pipeline

### Android (ML Kit)

```kotlin
val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

fun extractTokens(bitmap: Bitmap, onResult: (List<String>) -> Unit) {
    val image = InputImage.fromBitmap(bitmap, 0)
    recognizer.process(image)
        .addOnSuccessListener { result ->
            val tokens = result.text
                .split(Regex("\\s+"))
                .filter { it.matches(Regex("\\d{3,7}")) }
            onResult(tokens)
        }
}
```

### iOS (Vision)

```swift
func extractTokens(from image: UIImage, completion: @escaping ([String]) -> Void) {
    guard let cgImage = image.cgImage else { return completion([]) }
    let request = VNRecognizeTextRequest { req, _ in
        let tokens = (req.results as? [VNRecognizedTextObservation] ?? [])
            .compactMap { $0.topCandidates(1).first?.string }
            .flatMap { $0.split(separator: " ").map(String.init) }
            .filter { $0.range(of: #"^\d{3,7}$"#, options: .regularExpression) != nil }
        completion(tokens)
    }
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false  // critical: numbers only
    try? VNImageRequestHandler(cgImage: cgImage).perform([request])
}
```

**Critical setting:** `usesLanguageCorrection = false` on iOS,
`setPreferredLanguage` on Android. OCR engines will "correct" digit
sequences if language correction is enabled. Disable it.

---

## Artifact parser

The app must parse two formats from the OCR output:

### Format A — bare FDS-FRAME (single-page artifact)

```
ENC: UCS · DEC · COL/6 · PAD/00000 · WIDTH/5
<token stream>
531 VALUES · CRC32:E8DC9BF3
IF COUNT FAILS: DESTROY IMMEDIATELY
```

Parser extracts: WIDTH, COL, PAD from ENC line; tokens from body;
declared count and CRC32 from trailer.

### Format B — CCL stack file (multi-pass artifact)

```
=== CCL STACK BEGIN · DEPTH/3 · REF/ref ===
[pass 1 artifact — full FDS-FRAME]
=== CCL STACK PASS 2/3 ===
[pass 2 artifact]
=== CCL STACK PASS 3/3 ===
[pass 3 artifact]
=== CCL STACK END · REF/ref ===
```

Parser splits on `=== CCL STACK` delimiter lines, extracts each pass
artifact, parses RSRC block per pass for TWIST-MAP, WIDTH, SCHEDULE.
Applies untwist in reverse order (pass 3 → pass 2 → pass 1).

---

## Key input UI

Three input modes, selectable by the user:

### Mode 1 — Verse (text input)

Simple text field. Multi-line. The user types or dictates the verse.
App derives prime via `derivePrimeFromVerse()`.

Display the first 8 digits of the derived prime so the user can verify
against a known value if they have one: `P: 11105665...`

### Mode 2 — Melody (interval input)

A simple piano keyboard or interval picker. User hums the tune and
taps: up (+), down (-), same (0), by semitone count.

Alternatively: accept Parsons code string (`*UDUDDR...`) typed directly.

App derives prime via `derivePrimeFromIntervals()`.

### Mode 3 — Binary seed (image selection)

User selects an image from camera roll or taps to photograph.
App derives prime via `derivePrimeFromBytes(imageData)`.

**Important UI note:** display the file size and first 8 hex bytes of
the SHA256 so the user can confirm they selected the correct file.
Two very similar images (different resolutions of the same logo) will
produce different primes.

---

## Verification UI

Before proceeding to key input, display clearly:

```
┌─────────────────────────────────────┐
│  Artifact: SI-2084-FP-001           │
│  Tokens:   534 (531 non-padding)    │
│  CRC32:    E8DC9BF3 ✓ VERIFIED      │
│  CCL:      3 passes                 │
│  Width:    5                        │
│                                     │
│  [Enter key to decode]              │
│  [Destroy / discard]                │
└─────────────────────────────────────┘
```

If verification fails:

```
┌─────────────────────────────────────┐
│  ⚠ VERIFICATION FAILED              │
│                                     │
│  Declared: 531 values               │
│  Actual:   528 values               │
│  CRC32:    MISMATCH                 │
│                                     │
│  IF COUNT FAILS: DESTROY            │
│  IMMEDIATELY                        │
│                                     │
│  [Discard artifact]                 │
└─────────────────────────────────────┘
```

The DESTROY path wipes the extracted token stream from memory.
No key input is offered if verification fails.

---

## Payload dispatch

After successful decode, inspect the first bytes of the payload:

| Signature | Type | Action |
|-----------|------|--------|
| `<?xml` or `<!DOCTYPE plist` | MDM / mobileconfig | Offer to install |
| `PK\x03\x04` | ZIP / APK | Save to Downloads |
| `\x7fELF` | ELF binary (firmware) | Save + offer OTG export |
| `BEGIN PGP` | PGP-encrypted payload | Save to secure storage |
| UTF-8 text | Document / key shard | Display + save |

MDM profile installation:

```kotlin
// Android — trigger managed profile provisioning
val intent = Intent(DevicePolicyManager.ACTION_PROVISION_MANAGED_PROFILE)
intent.putExtra(DevicePolicyManager.EXTRA_PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME, adminComponent)
startActivityForResult(intent, REQUEST_CODE)
```

```swift
// iOS — open .mobileconfig triggers system install dialog
let url = URL(fileURLWithPath: savedProfilePath)
UIApplication.shared.open(url)
```

---

## Security model

**What the app protects:**
- Derived primes are held in memory only; never written to disk
- Decrypted payloads written to app-private storage (not accessible
  to other apps without root)
- Token stream wiped from memory after decode or on DESTROY

**What the app does not protect:**
- Screen capture (OS-level; use `FLAG_SECURE` on Android)
- Physical observation of the screen
- Device compromise (rooted device, malware)
- Coercion of the user after decode

**The app makes no network connections.** This should be verified by
the user via a network monitor or firewall app before use in a
sensitive context. Declare `android:networkSecurityConfig` with no
permitted domains, and disable background network access.

---

## Implementation notes for the mobile developer

**CCL is ~130 lines of pure integer arithmetic.** It has no
dependencies beyond BigInteger (for the 77-digit prime arithmetic)
and SHA256 (stdlib everywhere). Port the Python reference
implementation in `tools/mnemonic/` directly — the logic is
straightforward and the test vectors are in the repo.

**The canonical test vector is your integration test.** After
implementing the full pipeline, decode `archive/flash-paper-SI-2084-FP-001-payload.txt`
and verify you get the poem. CRC32 must be `E8DC9BF3`. First three
tokens must decode to 桜稲荷. This is the pass/fail criterion.

**OCR tuning matters more than CCL.** The hard part is not the
mathematics — it's getting clean digit sequences out of photographs
of printed pages under variable lighting. Invest in:
- Forced monochrome mode before OCR
- Page boundary detection (crop to the printed area)
- Confidence thresholding (reject low-confidence character recognitions)
- A manual correction UI for ambiguous characters
- Test with photographs taken under bad lighting, at an angle, with glare

**The CRC32 check saves the user from OCR errors.** If the CRC32
fails, tell the user to rephotograph the affected pages. The token
count in the trailer tells them how many tokens were expected; they
can identify which page has the gap.

**Start with Android.** Sideloading is trivial, the ML Kit OCR is
excellent, and BigInteger is available in the standard library.
iOS can follow once the core logic is validated.

---

## Estimated scope

| Component | Effort |
|-----------|--------|
| Core CCL logic (port from Python) | 2–3 days |
| FDS-FRAME parser | 1 day |
| CCL stack file parser | 1 day |
| OCR integration + tuning | 3–5 days |
| Key input UI (all three modes) | 2–3 days |
| Verification UI | 1 day |
| Payload dispatch | 1–2 days |
| MDM profile install | 1 day |
| Security hardening | 1–2 days |
| Testing against canonical test vectors | 1 day |
| **Total** | **~2–3 weeks** |

One developer. No backend. No cloud. No dependencies beyond the
platform SDK and ML Kit / Vision.

---

## Reference implementation

All core logic is in `tools/mnemonic/` and `tools/ucs-dec/`:

| File | Port target |
|------|-------------|
| `tools/mnemonic/mnemonic.py` | Core prime derivation |
| `tools/mnemonic/prime_twist.py` | CCL unstack |
| `tools/ucs-dec/ucs_dec_tool.py` | FDS decode + CRC32 verify |

The canonical test vector for integration testing:
```
archive/flash-paper-SI-2084-FP-001-payload.txt
archive/flash-paper-SI-2084-FP-001-framed.txt
```

Expected decode: the poem *Second Law Blues*.
Expected CRC32: `E8DC9BF3`.
Expected first three tokens: `26716 31282 33655` → 桜稲荷

Run `bash tests/roundtrip/run_tests.sh` to verify the Python
reference implementation before porting.

---

*The app that provisions a secure network connection*
*requires no network connection to operate.*
*This is a feature.*

*531 VALUES · CRC32:E8DC9BF3 · SIGNAL SURVIVES*
