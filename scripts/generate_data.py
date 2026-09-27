"""Generate a realistic, seeded claims dataset for ClaimLens.

The dataset models nine months of motor and health claims at a mid-sized
general insurer operating in Hyderabad / Telangana. Most claims are genuine.
Hidden inside them are four organised fraud patterns that are *invisible when
you look at one claim at a time* and only appear across history:

  R1  Garage + surveyor collusion (Sri Balaji Auto Works + surveyor K. Venkat Rao)
      inflated "hit from behind by unknown vehicle" repairs, shared phone numbers
      and payee accounts across "unrelated" claimants.
  R2  Hospital admission ring (Lifeline Multispeciality, Kukatpally)
      1-2 day weekend admissions for gastroenteritis / viral fever on freshly
      bought policies sold by the same agent, bills just under room-rent limits.
  R3  Early-claim intermediary (agent AGT-2290)
      old vehicles insured and then declared stolen / total loss within weeks,
      claimants living in the same apartment block.
  R4  Recycled damage
      the same vehicle claims the same damage twice under different owners.

Two decoys make the problem honest:
  D1  Lakshmi Hyundai, Kondapur - an authorised dealer with *very high* claim
      volume that is completely clean (volume alone is not fraud).
  D2  Genuine claims at Sri Balaji Auto Works handled by other surveyors
      (the garage alone is not fraud; the garage+surveyor pair is).

Output: data/claims.json  (sorted by intimation date)

Run:  python scripts/generate_data.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 20260927
rng = random.Random(SEED)

START = date(2026, 1, 5)
SEED_CUTOFF = date(2026, 8, 31)   # claims up to here form the "history" memory
END = date(2026, 9, 26)           # September claims form the live review queue

OUT = Path(__file__).resolve().parents[1] / "data" / "claims.json"

# --------------------------------------------------------------------------- #
# Reference data                                                               #
# --------------------------------------------------------------------------- #

FIRST = [
    "Srinivas", "Lakshmi", "Venkatesh", "Padma", "Ramesh", "Sravani", "Anil", "Kavya",
    "Mahesh", "Swathi", "Praveen", "Divya", "Naresh", "Harika", "Kiran", "Bhavana",
    "Suresh", "Anusha", "Raju", "Keerthi", "Vamshi", "Sowmya", "Ravi", "Pooja",
    "Sai Krishna", "Meghana", "Arjun", "Nikhila", "Chaitanya", "Madhavi", "Imran",
    "Ayesha", "Farhan", "Sana", "Joseph", "Priya", "Rahul", "Sneha", "Vikram", "Deepika",
    "Abhishek", "Tejaswini", "Gopal", "Rekha", "Santosh", "Hema", "Yashwanth", "Mounika",
]
LAST = [
    "Reddy", "Rao", "Goud", "Naidu", "Sharma", "Varma", "Chowdary", "Yadav", "Kumar",
    "Khan", "Patel", "Iyer", "Pillai", "Murthy", "Prasad", "Shaik", "Mohammed", "Joshi",
    "Agarwal", "Rathod", "Nayak", "Babu", "Achari", "Deshmukh",
]
AREAS = [
    "Kukatpally", "Miyapur", "Madhapur", "Gachibowli", "Kondapur", "Ameerpet", "Begumpet",
    "Secunderabad", "LB Nagar", "Dilsukhnagar", "Uppal", "Kompally", "Nizampet", "Manikonda",
    "Tolichowki", "Mehdipatnam", "Attapur", "Banjara Hills", "Jubilee Hills", "Chandanagar",
    "Bachupally", "Moosapet", "Habsiguda", "Nacharam", "Alwal", "Malkajgiri", "Kothapet",
]
STREETS = [
    "Road No. {n}", "{n}th Cross", "Lane {n}", "Street No. {n}", "Main Road", "Colony Road",
]
BUILDINGS = [
    "Sri Sai Residency", "Green Valley Apartments", "Vasavi Nilayam", "Ganga Towers",
    "Lotus Enclave", "Shanti Nagar Colony", "Pragathi Nagar", "Rainbow Vistas",
    "Aditya Homes", "Sunshine Apartments", "Mythri Nagar", "Jayabheri Enclave",
]

MOTOR_MODELS = [
    ("Maruti Suzuki Swift", 650000), ("Maruti Suzuki Baleno", 720000), ("Hyundai i20", 780000),
    ("Hyundai Creta", 1350000), ("Tata Nexon", 1050000), ("Kia Seltos", 1400000),
    ("Honda City", 1250000), ("Mahindra XUV700", 1900000), ("Toyota Innova Crysta", 2100000),
    ("Maruti Suzuki Dzire", 700000), ("Tata Punch", 680000), ("Hyundai Venue", 950000),
    ("Honda Activa 6G", 78000), ("Royal Enfield Classic 350", 195000), ("TVS Jupiter", 76000),
    ("Bajaj Pulsar 150", 115000), ("Maruti Suzuki Ertiga", 980000), ("Renault Kwid", 420000),
]

# id, name, area, kind
GARAGES = [
    ("G01", "Lakshmi Hyundai (Authorised), Kondapur", "Kondapur", "dealer"),  # decoy D1
    ("G02", "Varun Motors Maruti Arena, Ameerpet", "Ameerpet", "dealer"),
    ("G03", "Harsha Toyota Service, Begumpet", "Begumpet", "dealer"),
    ("G04", "Kun Hyundai Workshop, LB Nagar", "LB Nagar", "dealer"),
    ("G05", "Sai Ram Car Care, Uppal", "Uppal", "multibrand"),
    ("G06", "Speed Wheels Garage, Kompally", "Kompally", "multibrand"),
    ("G07", "Sri Balaji Auto Works, Moosapet", "Moosapet", "multibrand"),      # R1 garage
    ("G08", "Royal Bikes Service Point, Dilsukhnagar", "Dilsukhnagar", "bike"),
    ("G09", "Tata Motors Service - Concorde, Madhapur", "Madhapur", "dealer"),
    ("G10", "Friends Auto Garage, Tolichowki", "Tolichowki", "multibrand"),
    ("G11", "Mahindra Service - Sireesh Auto, Kukatpally", "Kukatpally", "dealer"),
    ("G12", "Honda Bikes - Jayabheri Service, Secunderabad", "Secunderabad", "bike"),
]
SURVEYORS = [
    ("SV03", "P. Anjaneyulu"), ("SV05", "M. Farooq Ali"), ("SV07", "R. Sudhakar"),
    ("SV09", "T. Lavanya"), ("SV11", "G. Narsimha"), ("SV12", "K. Venkat Rao"),  # SV12 = R1
    ("SV14", "S. Deepthi"), ("SV15", "B. Ramakrishna"),
]
HOSPITALS = [
    ("H01", "Sunrise Care Hospitals, Madhapur", "Madhapur"),
    ("H02", "Nizampet Medicentre", "Nizampet"),
    ("H03", "Lifeline Multispeciality Hospital, Kukatpally", "Kukatpally"),  # R2
    ("H04", "Aarogya Superspeciality, Secunderabad", "Secunderabad"),
    ("H05", "Deccan Heart & Multispeciality, Banjara Hills", "Banjara Hills"),
    ("H06", "CarePoint Hospital, LB Nagar", "LB Nagar"),
    ("H07", "Rainbow Mother & Child, Kondapur", "Kondapur"),
    ("H08", "Sree Venkateswara Nursing Home, Uppal", "Uppal"),
]
DOCTORS = {
    "H01": ["Dr. A. Kiran Kumar", "Dr. Sunitha Rao", "Dr. Faheem Ahmed"],
    "H02": ["Dr. P. Srikanth", "Dr. Rajitha M."],
    "H03": ["Dr. S. Prakash", "Dr. N. Vijaya"],
    "H04": ["Dr. V. Madhusudhan", "Dr. Anitha Reddy", "Dr. K. Rohit"],
    "H05": ["Dr. Harsha Vardhan", "Dr. Shalini Iyer"],
    "H06": ["Dr. B. Naveen", "Dr. Swapna Latha"],
    "H07": ["Dr. Keerthana S.", "Dr. Arvind Menon"],
    "H08": ["Dr. Y. Chandrasekhar"],
}
AGENTS = [
    ("AGT-1102", "Sridevi Insurance Point"), ("AGT-1587", "Secure Life Advisors"),
    ("AGT-2290", "Ravi Teja Insurance Services"),   # R3
    ("AGT-3015", "Direct - Online"), ("AGT-3016", "Direct - Branch Ameerpet"),
    ("AGT-3890", "Kotha Financial Services"), ("AGT-4471", "Mahesh Goud (Individual Agent)"),  # R2
    ("AGT-5120", "PolicyHub Brokers"),
]
POLICE_STATIONS = [
    "Kukatpally PS", "KPHB PS", "Madhapur PS", "Gachibowli PS", "Raidurgam PS",
    "Miyapur PS", "Chandanagar PS", "LB Nagar PS", "Uppal PS", "Begumpet PS",
    "Moosapet (Sanathnagar) PS", "Alwal PS",
]
TPAS = ["MediAssist TPA", "Paramount TPA", "In-house Health Claims", "Vidal Health TPA"]

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

_used_phones: set[str] = set()


def phone() -> str:
    while True:
        p = f"{rng.choice('6789')}{rng.randint(100000000, 999999999)}"
        if p not in _used_phones:
            _used_phones.add(p)
            return f"+91 {p[:5]} {p[5:]}"


def person() -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def address(area: str | None = None) -> str:
    area = area or rng.choice(AREAS)
    street = rng.choice(STREETS).format(n=rng.randint(1, 14))
    return f"Flat {rng.randint(101, 804)}, {rng.choice(BUILDINGS)}, {street}, {area}, Hyderabad"


BANK_IFSC = ["SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "UBIN", "CNRB", "BARB"]


def acct() -> str:
    """Payee bank account as an SIU analyst sees it: IFSC + masked number."""
    return f"{rng.choice(BANK_IFSC)}0{rng.randint(10000, 99999)} / XXXXXX{rng.randint(1000, 9999)}"


def reg(state: str = "TS") -> str:
    rto = rng.choice(["07", "08", "09", "10", "11", "12", "13", "15"])
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(2))
    return f"{state}{rto}{letters}{rng.randint(1000, 9999)}"


def rand_date(a: date, b: date) -> date:
    return a + timedelta(days=rng.randint(0, (b - a).days))


def money(x: float) -> int:
    return int(round(x / 50.0) * 50)


def iso(d: date) -> str:
    return d.isoformat()


_seq = 0


def claim_id(d: date) -> str:
    global _seq
    _seq += 1
    return f"CLM-{d.year}-{_seq:05d}"


def policy_no(line: str) -> str:
    prefix = "MOT" if line == "motor" else "HLT"
    return f"{prefix}/{rng.randint(2400, 2699)}/{rng.randint(100000, 999999)}"


# --------------------------------------------------------------------------- #
# Narrative banks                                                              #
# --------------------------------------------------------------------------- #

MOTOR_GENUINE = {
    "rear_end_known": [
        "While waiting at the {junction} signal around {time}, a {other} rammed into the rear of my car. The driver stopped, we exchanged details ({other_reg}) and he admitted fault. Rear bumper, boot lid and tail lamp damaged.",
        "Slow-moving traffic on {road} near {junction}. The car behind ({other_reg}) could not brake in time and hit my rear bumper. Photos of both vehicles taken at the spot. No injuries.",
    ],
    "front_collision": [
        "I was driving towards {junction} at about {time}. A two-wheeler suddenly cut across from the left and I braked hard; my car hit the divider. Front bumper, left headlamp and bonnet damaged.",
        "Hit a stationary water tanker while reversing out of the parking lot at {place}. Front grille and bumper cracked, radiator support bent.",
        "During heavy rain on {road}, visibility was poor and I hit the vehicle in front at low speed. Front bumper and number plate damaged. The other party did not claim.",
    ],
    "side_scrape": [
        "Car was parked outside {place}. On return found deep scratches and a dent on the right side doors. Probably a passing vehicle. CCTV at the shop was not working.",
        "While taking a U-turn at {junction} an RTC bus brushed the left side of the car. Both left doors and the ORVM damaged.",
    ],
    "flood": [
        "Heavy overnight rain in {area}; the basement parking of our apartment flooded to about 3 feet. Engine would not start in the morning. Vehicle towed to workshop, water found in engine and electricals.",
    ],
    "bike_skid": [
        "Bike skidded on loose gravel near {junction} while turning at low speed. Right side crash guard, indicator, brake lever and side panel damaged. Minor bruises, no hospitalisation.",
        "A car opened its door suddenly on {road}; I hit the door and fell. Front fork bent, headlamp broken, mudguard cracked.",
    ],
    "windshield": [
        "A stone thrown up by a truck on the ORR near {junction} cracked the windshield. No other damage.",
    ],
    "theft_genuine": [
        "Bike was parked outside my house in {area} overnight and was missing in the morning. Complaint lodged at {ps}, FIR {fir}. Neighbour's CCTV shows two persons taking it at 3:10 AM.",
    ],
}

# R1: templated, near-identical phrasing (the tell only history reveals)
R1_NARRATIVES = [
    "I was returning home late night on the ORR service road near {junction} when an unknown vehicle hit my car from behind and fled the spot. It was dark so I could not note the number. Rear bumper, boot, both tail lamps and rear chassis member damaged.",
    "Around {time} near {junction} an unknown vehicle hit my car from behind and fled from the spot. Due to darkness the number could not be noted. Rear bumper, dicky, tail lamps and rear chassis damaged.",
    "Late night while returning home near {junction}, one unknown vehicle hit from behind and fled the spot. Number not noted due to darkness. Rear bumper, boot door, tail lamps and rear floor panel damaged.",
    "Unknown vehicle hit my car from behind near {junction} at night and fled the spot immediately. Could not see the number as it was dark. Damage to rear bumper, dicky, both tail lamps and chassis.",
]

HEALTH_GENUINE = [
    ("Dengue fever with thrombocytopenia", 4, 7, "Admitted with high-grade fever for 5 days, platelet count 38,000. Managed with IV fluids and platelet monitoring. Discharged after platelets recovered to 1.2 lakh."),
    ("Acute appendicitis", 2, 4, "Presented with right lower abdominal pain and vomiting. USG confirmed appendicitis. Laparoscopic appendectomy done. Uneventful recovery."),
    ("Fracture - distal radius (right)", 1, 3, "Fall from two-wheeler. X-ray showed displaced distal radius fracture. Open reduction and internal fixation with plate. Discharged with cast."),
    ("Cholelithiasis", 2, 3, "Recurrent biliary colic. Elective laparoscopic cholecystectomy performed."),
    ("Community acquired pneumonia", 4, 6, "Fever, cough and breathlessness. Chest X-ray right lower lobe consolidation. IV antibiotics, oxygen support for 2 days."),
    ("Cataract - left eye", 1, 1, "Day-care phacoemulsification with IOL implantation under local anaesthesia."),
    ("Normal delivery", 2, 3, "Full-term normal vaginal delivery. Mother and baby stable."),
    ("Lower segment caesarean section", 3, 5, "Elective LSCS for breech presentation. Healthy baby, mother recovered well."),
    ("Renal calculus", 1, 3, "Severe left flank pain. CT KUB showed 7mm left ureteric calculus. Ureteroscopy with DJ stenting."),
    ("Typhoid fever", 3, 5, "Persistent fever, Widal and blood culture positive for S. typhi. IV ceftriaxone."),
    ("Acute myocardial infarction", 5, 8, "Chest pain radiating to left arm. ECG ST elevation. Primary angioplasty with one stent to LAD."),
    ("Knee replacement - right", 5, 7, "Advanced osteoarthritis right knee. Total knee replacement done. Physiotherapy started day 1."),
    ("Acute gastroenteritis with dehydration", 1, 3, "Loose stools and vomiting since previous day after eating outside food. Moderate dehydration, IV fluids and antiemetics."),
    ("Viral fever with dehydration", 1, 3, "High-grade fever with body pains for 3 days, NS1 and malaria negative. IV fluids and antipyretics."),
]

R2_DIAGNOSES = [
    ("Acute gastroenteritis with dehydration", "Complaints of loose motions and vomiting since morning. Admitted for IV fluids and observation. Symptoms settled. Discharged in stable condition."),
    ("Viral fever with dehydration", "Complaints of fever and body pains since 2 days. Admitted for IV fluids and observation. Symptoms settled. Discharged in stable condition."),
    ("Acute febrile illness", "Complaints of fever and weakness since 2 days. Admitted for IV fluids, antibiotics and observation. Symptoms settled. Discharged in stable condition."),
]

JUNCTIONS = [
    "Kukatpally Y junction", "JNTU junction", "Miyapur X roads", "Biodiversity junction",
    "Mehdipatnam flyover", "Punjagutta", "Paradise circle", "LB Nagar ring road",
    "Uppal ring road", "Kondapur Botanical Garden junction", "Gachibowli flyover",
    "Nanakramguda ORR exit", "Narsingi ORR exit", "Kompally Suchitra junction",
    "Moosapet junction", "Balanagar flyover",
]
ROADS = ["NH-65", "Old Mumbai Highway", "Madhapur main road", "ORR service road", "Sagar Road", "Rajiv Rahadari"]
PLACES = ["Inorbit Mall", "Sarath City Capital Mall", "Ratnadeep supermarket", "my office in HITEC City", "Ameerpet metro station", "KPHB 4th phase market"]
OTHERS = ["private bus", "Innova cab", "DCM van", "Ola cab", "tipper lorry", "Swift Dzire taxi"]

# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class Party:
    name: str
    phone: str
    address: str
    payee_account: str


def new_party(area: str | None = None) -> Party:
    return Party(person(), phone(), address(area), acct())


def fmt(t: str, area: str) -> str:
    return t.format(
        junction=rng.choice(JUNCTIONS), time=f"{rng.randint(7, 10)}:{rng.choice(['05','15','30','40','50'])} {rng.choice(['AM','PM'])}",
        other=rng.choice(OTHERS), other_reg=reg(), road=rng.choice(ROADS), place=rng.choice(PLACES),
        area=area, ps=rng.choice(POLICE_STATIONS), fir=f"{rng.randint(100, 999)}/2026",
    )


def base_claim(line: str, intimation: date, party: Party, agent: tuple[str, str],
               policy_start: date) -> dict:
    return {
        "claim_id": claim_id(intimation),
        "line": line,
        "policy_no": policy_no(line),
        "policy_start": iso(policy_start),
        "intimation_date": iso(intimation),
        "claimant": {
            "name": party.name,
            "phone": party.phone,
            "address": party.address,
        },
        "payee_account": party.payee_account,
        "intermediary": {"agent_code": agent[0], "agent_name": agent[1]},
    }


def motor_claim(*, intimation: date, party: Party, agent, garage, surveyor, model, reg_no,
                incident: date, kind: str, narrative: str, amount: int, policy_start: date,
                fir: dict | None, truth: dict) -> dict:
    c = base_claim("motor", intimation, party, agent, policy_start)
    name, idv = model
    c.update({
        "incident_date": iso(incident),
        "vehicle": {"registration": reg_no, "make_model": name, "idv": idv,
                    "year": rng.randint(2012, 2024) if kind not in ("theft_r3", "total_loss_r3") else rng.randint(2011, 2015)},
        "incident_type": kind.replace("_r3", "").replace("_r1", ""),
        "garage": {"id": garage[0], "name": garage[1]},
        "surveyor": {"id": surveyor[0], "name": surveyor[1]} if surveyor else None,
        "police_report": fir,
        "narrative": narrative,
        "claimed_amount": amount,
        "_truth": truth,
    })
    return c


def health_claim(*, intimation: date, party: Party, agent, hospital, doctor, diagnosis: str,
                 admit: date, los: int, narrative: str, amount: int, sum_insured: int,
                 policy_start: date, truth: dict) -> dict:
    c = base_claim("health", intimation, party, agent, policy_start)
    c.update({
        "incident_date": iso(admit),
        "hospital": {"id": hospital[0], "name": hospital[1]},
        "treating_doctor": doctor,
        "diagnosis": diagnosis,
        "admission_date": iso(admit),
        "discharge_date": iso(admit + timedelta(days=los)),
        "length_of_stay_days": los,
        "sum_insured": sum_insured,
        "tpa": rng.choice(TPAS),
        "narrative": narrative,
        "claimed_amount": amount,
        "_truth": truth,
    })
    return c


GENUINE = {"label": "legit", "ring": None, "pattern": None}

# --------------------------------------------------------------------------- #
# Generation                                                                   #
# --------------------------------------------------------------------------- #

claims: list[dict] = []
non_r1_garages = [g for g in GARAGES if g[0] not in ("G07",)]
bike_garages = [g for g in GARAGES if g[3] == "bike"]
car_garages = [g for g in GARAGES if g[3] != "bike" and g[0] != "G07"]
clean_surveyors = [s for s in SURVEYORS if s[0] != "SV12"]
normal_agents = [a for a in AGENTS if a[0] not in ("AGT-2290", "AGT-4471")]


def genuine_motor(intimation: date, garage=None, surveyor=None):
    model = rng.choice(MOTOR_MODELS)
    is_bike = model[1] < 250000
    if garage is None:
        garage = rng.choice(bike_garages if is_bike else car_garages)
    kinds = ["bike_skid"] if is_bike else ["rear_end_known", "front_collision", "side_scrape",
                                         "front_collision", "side_scrape", "windshield", "flood"]
    if is_bike and rng.random() < 0.15:
        kinds = ["theft_genuine"]
    kind = rng.choice(kinds)
    area = rng.choice(AREAS)
    party = new_party(area)
    incident = intimation - timedelta(days=rng.randint(0, 3))
    policy_start = incident - timedelta(days=rng.randint(60, 340))
    if kind == "theft_genuine":
        amount = model[1] * rng.uniform(0.7, 0.85)
        fir = {"station": rng.choice(POLICE_STATIONS), "fir_no": f"{rng.randint(100, 999)}/2026"}
    else:
        base = {"rear_end_known": (18000, 55000), "front_collision": (25000, 90000),
                "side_scrape": (12000, 40000), "flood": (90000, 240000), "bike_skid": (4000, 16000),
                "windshield": (9000, 22000)}[kind]
        amount = rng.uniform(*base) * (1.25 if model[1] > 1300000 else 1.0)
        fir = None
        if kind == "front_collision" and rng.random() < 0.3:
            fir = {"station": rng.choice(POLICE_STATIONS), "fir_no": f"{rng.randint(100, 999)}/2026"}
    narrative = fmt(rng.choice(MOTOR_GENUINE[kind]), area)
    return motor_claim(
        intimation=intimation, party=party, agent=rng.choice(normal_agents), garage=garage,
        surveyor=surveyor or rng.choice(clean_surveyors), model=model, reg_no=reg(), incident=incident,
        kind=kind, narrative=narrative, amount=money(amount), policy_start=policy_start, fir=fir,
        truth=GENUINE,
    )


def genuine_health(intimation: date):
    hosp = rng.choice([h for h in HOSPITALS if h[0] != "H03"] + [HOSPITALS[2]] * 0)
    if rng.random() < 0.08:  # a few genuine Lifeline claims (hospital alone is not fraud)
        hosp = HOSPITALS[2]
    diag, lo, hi, story = rng.choice(HEALTH_GENUINE)
    los = rng.randint(lo, hi)
    admit = intimation - timedelta(days=rng.randint(0, 2))
    si = rng.choice([300000, 500000, 500000, 1000000, 1500000])
    per_day = rng.uniform(14000, 32000)
    heavy = {"Acute myocardial infarction": 3.2, "Knee replacement - right": 3.0,
             "Lower segment caesarean section": 1.5}.get(diag, 1.0)
    amount = min(si * 0.95, per_day * max(los, 1) * heavy + rng.uniform(8000, 45000))
    party = new_party(hosp[2] if rng.random() < 0.5 else None)
    return health_claim(
        intimation=intimation, party=party, agent=rng.choice(normal_agents), hospital=hosp,
        doctor=rng.choice(DOCTORS[hosp[0]]), diagnosis=diag, admit=admit, los=los,
        narrative=story, amount=money(amount), sum_insured=si,
        policy_start=admit - timedelta(days=rng.randint(120, 1400)), truth=GENUINE,
    )


# --- baseline genuine flow: ~5 claims/week -----------------------------------
d = START
while d <= END:
    for _ in range(rng.choice([3, 4, 4, 5, 5, 6])):
        day = d + timedelta(days=rng.randint(0, 6))
        if day > END:
            continue
        claims.append(genuine_motor(day) if rng.random() < 0.62 else genuine_health(day))
    d += timedelta(days=7)

# --- D1 decoy: very high volume, clean authorised dealer ----------------------
for _ in range(16):
    claims.append(genuine_motor(rand_date(START, END), garage=GARAGES[0]))

# --- D2 decoy: genuine claims at the R1 garage with *other* surveyors ---------
for _ in range(6):
    claims.append(genuine_motor(rand_date(START, END), garage=GARAGES[6],
                                surveyor=rng.choice(clean_surveyors)))

# --- R1: garage + surveyor collusion ------------------------------------------
# Shared contact details across "unrelated" claimants. This is the link a
# per-claim reviewer never sees.
r1_shared_phone = phone()
r1_shared_acct = acct()
r1_dates = sorted(rand_date(date(2026, 3, 2), date(2026, 8, 25)) for _ in range(10))
r1_dates += [date(2026, 9, 8), date(2026, 9, 17), date(2026, 9, 23)]  # live queue
for i, day in enumerate(r1_dates):
    area = rng.choice(["Moosapet", "Kukatpally", "Bachupally", "Nizampet", "Miyapur"])
    p = new_party(area)
    if i % 3 == 1:
        p.phone = r1_shared_phone
    if i % 4 == 2:
        p.payee_account = r1_shared_acct
    model = rng.choice([m for m in MOTOR_MODELS if m[1] > 600000 and m[1] < 1500000])
    incident = day - timedelta(days=rng.randint(1, 4))
    fir = None if i % 2 == 0 else {"station": "Moosapet (Sanathnagar) PS", "fir_no": f"{rng.randint(100, 999)}/2026"}
    narrative = fmt(R1_NARRATIVES[i % len(R1_NARRATIVES)], area)
    amount = money(rng.uniform(1.7, 2.3) * rng.uniform(40000, 60000))
    claims.append(motor_claim(
        intimation=day, party=p, agent=rng.choice(normal_agents), garage=GARAGES[6], surveyor=SURVEYORS[5],
        model=model, reg_no=reg(), incident=incident, kind="rear_end_unknown_r1", narrative=narrative,
        amount=amount, policy_start=incident - timedelta(days=rng.randint(90, 300)), fir=fir,
        truth={"label": "fraud", "ring": "R1", "pattern": "Garage-surveyor collusion: staged 'unknown vehicle hit from behind' at night, inflated rear-end repairs at Sri Balaji Auto Works surveyed by K. Venkat Rao; shared phone/payee accounts across claimants."},
    ))

# --- R2: hospital admission ring --------------------------------------------
r2_dates = sorted(rand_date(date(2026, 2, 16), date(2026, 8, 28)) for _ in range(9))
r2_dates += [date(2026, 9, 12), date(2026, 9, 20)]
r2_referrer_phone = phone()
for i, day in enumerate(r2_dates):
    # weekend admissions
    admit = day - timedelta(days=(day.weekday() - 5) % 7)
    if admit > day:
        admit -= timedelta(days=7)
    diag, story = R2_DIAGNOSES[i % len(R2_DIAGNOSES)]
    si = rng.choice([200000, 300000])
    los = rng.choice([1, 2, 2])
    room_cap = si * 0.01  # 1% of SI per day room rent limit
    amount = money(rng.uniform(0.86, 0.97) * (si * 0.18))  # just under typical sub-limit
    p = new_party(rng.choice(["Kukatpally", "KPHB", "Moosapet", "Balanagar", "Kukatpally"]))
    if i in (2, 6, 9):
        p.phone = r2_referrer_phone
    claims.append(health_claim(
        intimation=admit + timedelta(days=los + rng.randint(0, 1)), party=p, agent=AGENTS[6],
        hospital=HOSPITALS[2], doctor="Dr. S. Prakash", diagnosis=diag, admit=admit, los=los,
        narrative=story + f" Room rent charged at Rs {int(room_cap)} per day.",
        amount=amount, sum_insured=si, policy_start=admit - timedelta(days=rng.randint(32, 55)),
        truth={"label": "fraud", "ring": "R2", "pattern": "Hospital admission ring: short weekend admissions for vague febrile/GI illness at Lifeline Multispeciality, Dr. S. Prakash, policies sold 30-55 days earlier by agent AGT-4471, bills just under sub-limits."},
    ))

# --- R3: early-claim intermediary ------------------------------------------
r3_building = "Plot 42, Sai Enclave, Miyapur"
r3_dates = sorted(rand_date(date(2026, 4, 6), date(2026, 8, 20)) for _ in range(6))
r3_dates += [date(2026, 9, 15)]
for i, day in enumerate(r3_dates):
    p = new_party("Miyapur")
    p.address = f"Flat {rng.randint(101, 502)}, {r3_building}, Hyderabad"
    model = rng.choice([("Maruti Suzuki Swift", 650000), ("Hyundai i20", 780000), ("Honda City", 1250000), ("Maruti Suzuki Ertiga", 980000)])
    incident = day - timedelta(days=rng.randint(0, 2))
    policy_start = incident - timedelta(days=rng.randint(9, 24))
    theft = i % 2 == 0
    if theft:
        narrative = (f"Car parked on the road outside the apartment in Miyapur was found missing in the morning. "
                     f"Searched nearby areas. Complaint given at Miyapur PS. Original keys available.")
        kind = "theft_r3"
        amount = money(model[1] * rng.uniform(0.92, 1.0))
        fir = {"station": "Miyapur PS", "fir_no": f"{rng.randint(100, 999)}/2026"}
    else:
        narrative = (f"Car caught fire while driving on the Miyapur - Bachupally road late evening. "
                     f"Managed to get out, vehicle completely burnt before fire services arrived.")
        kind = "total_loss_r3"
        amount = money(model[1] * rng.uniform(0.9, 1.0))
        fir = {"station": "Bachupally PS", "fir_no": f"{rng.randint(100, 999)}/2026"}
    claims.append(motor_claim(
        intimation=day, party=p, agent=AGENTS[2], garage=rng.choice(car_garages),
        surveyor=rng.choice(clean_surveyors), model=model, reg_no=reg(), incident=incident,
        kind=kind, narrative=narrative, amount=amount, policy_start=policy_start, fir=fir,
        truth={"label": "fraud", "ring": "R3", "pattern": "Early-claim intermediary: older cars insured at high IDV via agent AGT-2290, declared stolen/burnt within 3 weeks of inception; claimants share one apartment block (Sai Enclave, Miyapur)."},
    ))

# --- R4: recycled damage -----------------------------------------------------
recycled_reg = "TS08FK4521"
r4_story = "Front bumper, left headlamp assembly, left fender and bonnet damaged after hitting a road divider near {junction} at night."
for i, day in enumerate([date(2026, 2, 23), date(2026, 6, 18), date(2026, 9, 10)]):
    p = new_party()
    model = ("Hyundai Creta", 1350000)
    incident = day - timedelta(days=1)
    claims.append(motor_claim(
        intimation=day, party=p, agent=rng.choice(normal_agents),
        garage=[GARAGES[9], GARAGES[4], GARAGES[5]][i], surveyor=rng.choice(clean_surveyors),
        model=model, reg_no=recycled_reg, incident=incident, kind="front_collision",
        narrative=fmt(r4_story, "Tolichowki"), amount=money(rng.uniform(88000, 102000)),
        policy_start=incident - timedelta(days=rng.randint(20, 60)), fir=None,
        truth={"label": "fraud" if i > 0 else "legit", "ring": "R4" if i > 0 else None,
               "pattern": "Recycled damage: same vehicle TS08FK4521 claims the identical front-left damage again under a new owner and a new policy, repaired at a different garage." if i > 0 else None},
    ))

# --- Live-queue decoys: genuine September claims that *look* risky ----------
# A busy-but-clean dealer, and the R1 garage with an honest surveyor. The
# agent should not flag either: memory says these entities were cleared.
claims.append(genuine_motor(date(2026, 9, 19), garage=GARAGES[0]))
claims.append(genuine_motor(date(2026, 9, 24), garage=GARAGES[6], surveyor=SURVEYORS[3]))

# --------------------------------------------------------------------------- #
# Investigator verdicts (what really happened historically)                    #
# --------------------------------------------------------------------------- #

claims.sort(key=lambda c: (c["intimation_date"], c["claim_id"]))
# renumber in chronological order so IDs look like a real claims system
for n, c in enumerate(claims, start=1):
    c["claim_id"] = f"CLM-2026-{10400 + n:05d}"

ring_seen: dict[str, int] = {}
for c in claims:
    t = c["_truth"]
    idate = date.fromisoformat(c["intimation_date"])
    closed = idate + timedelta(days=rng.randint(12, 40))
    if idate > SEED_CUTOFF:
        c["status"] = "open"
        c["verdict"] = None
        continue
    c["status"] = "closed"
    if t["label"] == "legit":
        paid = c["claimed_amount"] * rng.uniform(0.82, 1.0)
        c["verdict"] = {"decision": "approved", "paid_amount": money(paid), "closed_on": iso(closed),
                        "investigator": None, "notes": rng.choice([
                            "Documents in order. Surveyor assessment accepted.",
                            "Approved after standard verification.",
                            "Minor deductions for depreciation and non-payables. Approved.",
                            "Approved. Cashless settlement with network provider.",
                        ])}
        continue
    ring = t["ring"]
    ring_seen[ring] = ring_seen.get(ring, 0) + 1
    k = ring_seen[ring]
    # Early ring claims slipped through - that is exactly how real rings grow.
    caught_after = {"R1": 5, "R2": 5, "R3": 3, "R4": 1}[ring]
    if k <= caught_after:
        c["verdict"] = {"decision": "approved", "paid_amount": money(c["claimed_amount"] * rng.uniform(0.9, 1.0)),
                        "closed_on": iso(closed), "investigator": None,
                        "notes": "Approved after standard verification."}
    else:
        notes = {
            "R1": "SIU visit: rear damage inconsistent with a single impact; paint transfer absent. Surveyor K. Venkat Rao approved estimate without photos of chassis. Claimant could not explain route. Phone number matches earlier claimant. Repudiated.",
            "R2": "Hospital visit: indoor case papers incomplete, no nursing chart for night. Patient admitted Saturday, discharged Sunday. Policy sold 5 weeks earlier by AGT-4471. Pattern matches earlier Lifeline claims. Repudiated.",
            "R3": "Vehicle insured 2-3 weeks before loss at IDV above market value. Neighbours in Sai Enclave report car sold months ago. Agent AGT-2290 sourced this and prior similar policies. Repudiated and reported to IIB.",
            "R4": "Vehicle TS08FK4521 had identical front-left damage claimed in Feb 2026 under previous owner; repair invoice then was never fully executed. Repudiated.",
        }[ring]
        c["verdict"] = {"decision": "fraud_confirmed", "paid_amount": 0, "closed_on": iso(closed),
                        "investigator": rng.choice(["A. Srilatha (SIU)", "Mohd. Irfan (SIU)", "V. Karthik (SIU)"]),
                        "notes": notes}

meta = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "seed": SEED,
    "seed_cutoff": iso(SEED_CUTOFF),
    "description": "Synthetic Hyderabad motor + health claims. Fields starting with '_' are ground truth for evaluation only and are never shown to the agent.",
    "counts": {
        "total": len(claims),
        "history": sum(c["status"] == "closed" for c in claims),
        "open_queue": sum(c["status"] == "open" for c in claims),
        "fraud": sum(c["_truth"]["label"] == "fraud" for c in claims),
    },
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"meta": meta, "claims": claims}, indent=2, ensure_ascii=False))
print(json.dumps(meta["counts"], indent=2))
print(f"wrote {OUT}")
