// Units: mm. Diameter values are provisional R6 geometry, not measured hardware.
height = 8;
outer_diameter = 10;
bore_diameter = 5.5;
$fn = 128;
assert(height > 0 && outer_diameter > bore_diameter && bore_diameter > 0);
difference() {
    cylinder(h = height, d = outer_diameter);
    translate([0, 0, -0.1]) cylinder(h = height + 0.2, d = bore_diameter);
}
