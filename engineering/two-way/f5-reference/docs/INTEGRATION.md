# Handoff / later repository integration

This package is a standalone F5 study. Neither `Takazudo/zudo-case` nor `zudolab/zzmod` was edited.

Keep the source rail assets and existing R6/R9 manufacturing candidates unchanged. If publishing this study in zudo-case, add it as a **new unapproved preview**, with its own source directory, provenance, documentation route and asset-manifest entries. Do not replace the existing R9 candidate HTML or CAD. Follow that checkout's AGENTS.md and asset/build checks.

The viewer can be copied to a new path under `public/previews/`; its embedded data needs no network. Any website integration still requires the repository's own checks; those were not run by this standalone validation.

Before exact-CAD integration, use the original KiCad polygon contours instead of the simplified rounded cutout curves baked into this display. Retain the rail vertices/indices and source placement datums. The authoritative paths and hashes are in `reference/PROVENANCE.md`. Do not mistake the derivative PCB's `sourceBlobSHA` for a hash of its generated viewing mesh.

Key migration facts: B is two stock 3U assemblies with a 1 mm gap and a 290 mm shell dimension. C's full 7U frame needs the revised 70 mm lid. The collar now has a 7.1 mm inward extent at default inputs, not 12.1 mm. Exterior fastener-cover allowances change the closed width. Old F4 setup JSONs are rejected to avoid silently applying the old frame assumptions.

Open gates: original-PCB-to-actual-fastener fit; lid back and frame tolerance; narrower support land strength; full casing/tool interference; protective cap design; module/power fit; fixed-length leads; stand and transport tests. No fabrication/order release exists here.
