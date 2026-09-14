# Lightweight offline geo-lookup for the GIS risk map.
# Maps district -> (lat, lon). Falls back to state centroid when a district
# is not in the table, so any user-entered district still plots on the map.

STATE_CENTROIDS = {
    'Andhra Pradesh': (15.9129, 79.7400), 'Arunachal Pradesh': (28.2180, 94.7278),
    'Assam': (26.2006, 92.9376), 'Bihar': (25.0961, 85.3131), 'Chhattisgarh': (21.2787, 81.8661),
    'Goa': (15.2993, 74.1240), 'Gujarat': (22.2587, 71.1924), 'Haryana': (29.0588, 76.0856),
    'Himachal Pradesh': (31.1048, 77.1734), 'Jharkhand': (23.6102, 85.2799),
    'Karnataka': (15.3173, 75.7139), 'Kerala': (10.8505, 76.2711), 'Madhya Pradesh': (22.9734, 78.6569),
    'Maharashtra': (19.7515, 75.7139), 'Manipur': (24.6637, 93.9063), 'Meghalaya': (25.4670, 91.3662),
    'Mizoram': (23.1645, 92.9376), 'Nagaland': (26.1584, 94.5624), 'Odisha': (20.9517, 85.0985),
    'Punjab': (31.1471, 75.3412), 'Rajasthan': (27.0238, 74.2179), 'Sikkim': (27.5330, 88.5122),
    'Tamil Nadu': (11.1271, 78.6569), 'Telangana': (18.1124, 79.0193), 'Tripura': (23.9408, 91.9882),
    'Uttar Pradesh': (26.8467, 80.9462), 'Uttarakhand': (30.0668, 79.0193), 'West Bengal': (22.9868, 87.8550),
    'Delhi': (28.7041, 77.1025), 'Jammu and Kashmir': (33.7782, 76.5762), 'Ladakh': (34.1526, 77.5771),
    'Puducherry': (11.9416, 79.8083), 'Chandigarh': (30.7333, 76.7794),
}

DISTRICT_COORDS = {
    # Maharashtra
    'nagpur': (21.1458, 79.0882), 'pune': (18.5204, 73.8567), 'solapur': (17.6599, 75.9064),
    'kolhapur': (16.7050, 74.2433), 'mumbai': (19.0760, 72.8777), 'nashik': (19.9975, 73.7898),
    'aurangabad': (19.8762, 75.3433), 'amravati': (20.9374, 77.7796), 'thane': (19.2183, 72.9781),
    'nanded': (19.1383, 77.3210),
    # Telangana
    'hyderabad': (17.3850, 78.4867), 'warangal': (17.9689, 79.5941), 'karimnagar': (18.4386, 79.1288),
    'nizamabad': (18.6725, 78.0941), 'khammam': (17.2473, 80.1514), 'rangareddy': (17.3406, 78.2960),
    'medchal': (17.6294, 78.4808),
    # Karnataka
    'bengaluru': (12.9716, 77.5946), 'bangalore': (12.9716, 77.5946), 'mysuru': (12.2958, 76.6394),
    'belagavi': (15.8497, 74.4977), 'hubballi': (15.3647, 75.1240),
    # Tamil Nadu
    'chennai': (13.0827, 80.2707), 'coimbatore': (11.0168, 76.9558), 'madurai': (9.9252, 78.1198),
    'salem': (11.6643, 78.1460), 'tiruchirappalli': (10.7905, 78.7047),
    # Gujarat
    'ahmedabad': (23.0225, 72.5714), 'surat': (21.1702, 72.8311), 'vadodara': (22.3072, 73.1812),
    'rajkot': (22.3039, 70.8022),
    # Rajasthan
    'jaipur': (26.9124, 75.7873), 'jodhpur': (26.2389, 73.0243), 'udaipur': (24.5854, 73.7125),
    'kota': (25.2138, 75.8648),
    # Uttar Pradesh
    'lucknow': (26.8467, 80.9462), 'kanpur': (26.4499, 80.3319), 'varanasi': (25.3176, 82.9739),
    'noida': (28.5355, 77.3910), 'agra': (27.1767, 78.0081), 'ghaziabad': (28.6692, 77.4538),
    'prayagraj': (25.4358, 81.8463),
    # Madhya Pradesh
    'bhopal': (23.2599, 77.4126), 'indore': (22.7196, 75.8577), 'jabalpur': (23.1815, 79.9864),
    'gwalior': (26.2183, 78.1828),
    # Bihar
    'patna': (25.5941, 85.1376), 'gaya': (24.7955, 84.9994), 'muzaffarpur': (26.1225, 85.3906),
    # West Bengal
    'kolkata': (22.5726, 88.3639), 'howrah': (22.5958, 88.2636), 'durgapur': (23.5204, 87.3119),
    # Odisha
    'bhubaneswar': (20.2961, 85.8245), 'cuttack': (20.4625, 85.8830),
    # Punjab / Haryana
    'ludhiana': (30.9010, 75.8573), 'amritsar': (31.6340, 74.8723), 'gurugram': (28.4595, 77.0266),
    'faridabad': (28.4089, 77.3178),
    # Kerala
    'kochi': (9.9312, 76.2673), 'thiruvananthapuram': (8.5241, 76.9366), 'kozhikode': (11.2588, 75.7804),
    # Andhra Pradesh
    'visakhapatnam': (17.6868, 83.2185), 'vijayawada': (16.5062, 80.6480), 'guntur': (16.3067, 80.4365),
    # Others
    'bhilai': (21.1938, 81.3509), 'raipur': (21.2514, 81.6296), 'ranchi': (23.3441, 85.3096),
    'jamshedpur': (22.8046, 86.2029), 'guwahati': (26.1445, 91.7362), 'dehradun': (30.3165, 78.0322),
    'shimla': (31.1048, 77.1734), 'panaji': (15.4909, 73.8278), 'chandigarh': (30.7333, 76.7794),
    'new delhi': (28.6139, 77.2090),
}


def locate(state, district):
    """Return (lat, lon) for a district, falling back to state centroid, then India centroid."""
    key = (district or '').strip().lower()
    if key in DISTRICT_COORDS:
        return DISTRICT_COORDS[key]
    s = (state or '').strip()
    if s in STATE_CENTROIDS:
        return STATE_CENTROIDS[s]
    for name, coords in STATE_CENTROIDS.items():
        if name.lower() == s.lower():
            return coords
    return (22.9734, 78.6569)  # India centroid fallback
