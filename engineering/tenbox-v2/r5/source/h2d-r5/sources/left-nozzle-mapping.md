# H2D saved reach and left-nozzle assignment (R4/R5)

## Saved printer limits

The unchanged personal H2D template defines logical extruder area 0 as X0–325, Y0–320, height 320, and area 1 as X25–350, Y0–320, height 325. Their common intersection is X25–325, Y0–320. The wrapping exclusion is X145–256, Y310–326.

A 317 ×290 ×5 mm roof fits flat at **X4–321, Y10–300, Z0–5** in the left-nozzle area. It clears the rear exclusion by 10 mm. There is 4 mm of part clearance at each X edge and at least 10 mm in Y. No brim is configured. An optional 2 mm brim with the saved 0.1 mm object gap would still fit, with X1.9–323.1, Y7.9–302.1.

Rotating the roof 90° creates a 290 ×317 mm rectangle, but it cannot be placed in the common area without crossing the rear exclusion. Therefore a common-area layout pass would be a false claim. The new roof project uses a left-nozzle-specific geometric check, while the generic helper is used for its mesh/package structural validation only.

## Existing assignment and plate-level lock

The template contains `filament_map = [1,1]`, `filament_nozzle_map = [0,0]`, `physical_extruder_map = [1,0]`, and `filament_map_mode = Auto For Flush`.

The official source defines the filament-map values as logical assignments: 1 is left and 2 is right. The physical ID is obtained by subtracting 1 and looking up `physical_extruder_map`; this is a separate indexing system from the printable-area array. Object `extruder=1` selects filament slot 1, not by itself a physical nozzle.

The roof and R5 common-floor plates preserve the existing map values and all global configuration bytes. Each adds supported plate-level metadata:

```xml
<metadata key="filament_map_mode" value="Manual" />
<metadata key="filament_maps" value="1 1" />
```

This fixes the existing left assignment for this plate instead of allowing automatic regrouping. No printer area, height, hardware profile, filament profile, physical-extruder map, or machine code is changed. The actual Studio slice remains unverified in this environment.

## Primary-source evidence

Pinned official BambuStudio source commit: `4c2c19a4bf698edf153555dfe28fd4f81d6550be`.

- [PartPlate.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/slic3r/GUI/PartPlate.cpp): `get_physical_extruder_by_filament_id` documents left/right logical map values and applies the separate physical map. `get_real_filament_maps` and `get_real_filament_map_mode` give plate overrides priority over global configuration.
- [bbs_3mf.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/libslic3r/Format/bbs_3mf.cpp): the model-settings importer recognizes `filament_map_mode` and `filament_maps`; the exporter writes the map as space-separated integer values.
- [PrintConfig.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/libslic3r/PrintConfig.cpp): the serialized value `Manual` maps exactly to `fmmManual`.
- [Extruder.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/libslic3r/Extruder.cpp): logical extruder selection derives from the 1-based filament map; nozzle-list indices are a different field.

The local template and generated project are the direct evidence for dimensions and saved settings. The source links support their interpretation and the plate metadata format.
