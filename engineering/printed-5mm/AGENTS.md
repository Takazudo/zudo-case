# Printed 5mm family

This is the independent 7U40 home-print family. The current revision is P6-PRINTED-5MM-LID-SLOTS (`project/current-selection.json`); P5-PRINTED-5MM-TAB-JOINTS-J3, P4-PRINTED-5MM-UNIFORM-VENTS and P3-PRINTED-5MM-7U-RAILS are superseded, and their reader pages live in `src/content/docs/archive/printed-5mm/`. Keep metal-family geometry, packages and order records (including the current 7U40 R11 candidate and archived R10 records) unchanged. Keep the 2WAY family independent. The accepted P3 reference and user decisions outrank schematic descriptions. Regenerate from the locked Python 3.13/CadQuery 2.8 environment; never use a cached P2 scene as the authoritative full build. New prints are ASA case parts, not rail, PCB or metal hardware replacements. No manufacture or physical validation is implied by software checks.

## P5 tab-joint scope

P5-PRINTED-5MM-TAB-JOINTS-J3 adopts integral tabs and closed receivers only for the independent home-printed 7U40 family. The root prohibition of old thick-panel interlocking tabs remains in force for the metal family. Preserve P3/P4 sources, payloads, previews/downloads (original URLs and bytes) and P4 H2D projects. Generate P5 from maintained source and original rail/PCB inputs; received J3 STEP files are acceptance fixtures only. Brim is zero for P5; P4's 5mm allowance is historical. Six body pieces change together; six lid pieces and three optional types do not. Never promote software verification to physical validation or production approval.

Japanese docs follow src/content/docs/development/maintenance.mdx. The five current printed-5mm pages describe P6 only; do not add historical P5/P4/P3 rows, settings (such as the 5mm brim or P4 envelope) or reading-order links to them. Link the archive once from the family index.

## P6 lid-slot scope

Only `lid-top-1` and `lid-top-2` change: four 10.5 × 5.5 mm capsule slots per plate, X axes for left/right edges and Y for front/back. Preserve centers, roof outline, thickness and print orientation. `p6-lid-slots/` contains pinned P5 STEP inputs and editable parametric cutters; all 13 other part types reuse byte-identical P5 sources/outputs/projects. Preserve every P5 download and preview at its original URL and bytes. P6 full packages substitute only the two roofs and identify the inherited parts; the replacement package contains two roofs only. Keep saved H2D/PLA/0.6 mm settings, unsliced state and production_approved=false.
