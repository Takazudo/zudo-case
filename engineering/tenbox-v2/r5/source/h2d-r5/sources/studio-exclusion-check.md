# Studio exclusion check used for the R5 diagonal floor

The floor is validated against its projected convex hull, not only its XY
bounding rectangle. Its bounding rectangle overlaps the rear exclusion, while
the actual hull is clear. This is compatible with the shape-based checks in
the official Bambu Studio source pinned to commit
`4c2c19a4bf698edf153555dfe28fd4f81d6550be`.

- [PartPlate.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/slic3r/GUI/PartPlate.cpp),
  `PartPlate::check_outside`, lines 2980–3014: first tests the object bounds
  against the whole plate, then intersects `instance->convex_hull_2d()` with
  each exclusion polygon. The old bbox-intersection expression is commented
  out. A bounding rectangle crossing an exclusion is not by itself rejection.
- [BedExcludeChecker.cpp](https://github.com/bambulab/BambuStudio/blob/4c2c19a4bf698edf153555dfe28fd4f81d6550be/src/libslic3r/GCode/BedExcludeChecker.cpp),
  `toolpath_intersects_bed_exclude_area_2d`: checks actual extrusion segments
  against exclusion polygons, with point containment and segment intersections.
  Its comment explicitly includes wrapping exclusions on or beyond the bed
  edge; it does not reject solely because the total toolpath bbox overlaps.

The saved template has a wrapping exclusion at X145–256, Y310–326 mm. The R5
floor has no brim or supports, and its conservative projected convex hull
is more than 21 mm from this rectangle. All of its mesh is within the locked
left nozzle's X0–325, Y0–320 mm area.

This source review supports the geometric check; it does not substitute for
opening and slicing the supplied project in the user's installed Studio.
The package remains explicitly unsliced. No g-code or printer operation is
generated or performed.
