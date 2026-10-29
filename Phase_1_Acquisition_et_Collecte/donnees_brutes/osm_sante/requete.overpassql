[out:json][timeout:240];
(
  nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy)$"](32.2987,-9.0592,33.8319,-6.7613);
  nwr["healthcare"](32.2987,-9.0592,33.8319,-6.7613);
);
out center tags;