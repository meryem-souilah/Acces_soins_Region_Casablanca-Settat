[out:json][timeout:180];
    (
      nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy)$"](31.9,-9.4,33.95,-6.4);
      nwr["healthcare"](31.9,-9.4,33.95,-6.4);
    );
    out center tags;