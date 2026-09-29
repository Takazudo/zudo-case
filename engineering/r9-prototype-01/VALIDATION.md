# R9-PROTOTYPE-01 検証集約

**状態:** passed_with_flags / 製作承認: なし

**集計:** pass 156 / flag 14 / fail 0
**対象:** 7u40 / mm / R9候補データ

## 確認結果

- 本体平板: 5枚、蓋板: 1枚。
- 穴テーブル: 46件 (長穴 36、丸穴 10)。
- R9生成STL: 56件をSTEP再取込形状と照合。
- STEP: 64件、DXF: 17件を再取込。
- パラメーター変更: 2ケースを一時コピーで再生成。
- R6元レールSTLはR9生成物ではないため、R9 STLの閉じたメッシュ検査から除外。

## フラグ

- stl:out/hardware-envelopes/7u40-r9-hw-case-mount-bolt-qty10-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-hw-foot-qty4-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-hw-inner-spacer-qty10-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-hw-panel-joint-bolt-qty36-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-hw-rail-end-bolt-qty12-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-hw-washer-1mm-qty46-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- stl:out/hardware-envelopes/7u40-r9-pcb-fixer-qty2-mm.stl: Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth.
- hardware-envelope-stl-scope: Hardware-envelope and source-derived PCB STLs are assembly/display references, not manufacturing candidates; each is still listed and checked against its STEP geometry.
- source-rail-stl-exclusion: The 40HP rail mesh is saved R6 source geometry, not an R9-made STL; source identity is checked separately.
- s2-slot-bearing-coverage: The provisional 10 mm washer does not meet nominal bearing overlap at current wall slots; larger OD remains a candidate.
- s4b-static-interference-coverage: Assembly collision coverage is partial; untested pair classes remain.
- s4b-lift-path-coverage: Lift-path checks cover limited BREP and envelope classes, not all actual assembly solids.
- s4b-physical-fastener-access: M3/M5 driver access and physical washer fit are not validated.
- s4b-band-contact-and-deflection: Straps are schematic; plate-only contact and deflection remain unresolved.

## 参照メッシュの詳細

- 参照包絡STLのSTEP境界との差は最大 0.001862 mm。厳密照合値は 0.0001 mm、STL書出しの弦誤差許容値は 0.01 mm。
  - out/hardware-envelopes/7u40-r9-hw-case-mount-bolt-qty10-mm.stl: 0.001400 mm
  - out/hardware-envelopes/7u40-r9-hw-foot-qty4-mm.stl: 0.001556 mm
  - out/hardware-envelopes/7u40-r9-hw-inner-spacer-qty10-mm.stl: 0.001561 mm
  - out/hardware-envelopes/7u40-r9-hw-panel-joint-bolt-qty36-mm.stl: 0.001862 mm
  - out/hardware-envelopes/7u40-r9-hw-rail-end-bolt-qty12-mm.stl: 0.001405 mm
  - out/hardware-envelopes/7u40-r9-hw-washer-1mm-qty46-mm.stl: 0.001561 mm
- out/hardware-envelopes/7u40-r9-pcb-fixer-qty2-mm.stl: 閉じたメッシュではありません。辺出現数 {"1": 20, "2": 18950, "6": 4}。R6由来輪郭を用いた表示用包絡で、製作用PCBデータとして扱いません。

## 未検証

- FEA, load capacity, or strength under service loads.
- Fit with real materials and manufacturing tolerances.
- Guard adhesion, retention, and pull-off strength.
- The effect of anodizing thickness on fit.
- Drop resistance and fatigue life.
- Band tension, strap load strength, and lid deflection during transport.
- Actual module knob heights and cable clearance (G05).
- Actual hardware, fastener, washer, and driver fit (G06).
- Physical assembly and transport trial (G11).
- Body plate and internal part solid-pair collision coverage: body plate STEP patterns are local and most repeated hardware has only instance AABBs; intentional fastener contacts need pair-specific exclusions.
- Lift path exact solids against body, PCB, rail, brackets, hardware and actual module knobs; locator AABBs against available component AABBs are a conservative 1 mm lift-step screen, not exact solids.
- M3 driver cone/tool access: eight plate/frame bores are modeled, but driver and screw heads are not specified.
- M5 physical tool access and washer fit; S2 exterior envelope is nominal only.
- Adhesive retention, physical fit, strap load strength, module knob/cable envelope and transport testing.

CAD再取込・メッシュ検査・名目配置チェックは、現物の嵌合、材料、強度、接着、運搬の結果を示しません。
すべての詳細は同じフォルダーの out/validation.json を参照してください。
