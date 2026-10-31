"""Ajoute des clients synthétiques directement dans la base MySQL d'un Magento 1.9.

    python scripts/magento_seed_customers.py -n 5000
    python scripts/magento_seed_customers.py --delete              # retire ceux ajoutés par ce script
    python scripts/magento_seed_customers.py -n 100 --dry-run      # écrit le SQL sans l'exécuter

Chaque client a un prénom et un nom vraisemblables (Maroc, France, Belgique, Royaume-Uni,
Allemagne, Pays-Bas), une date de naissance, un sexe, une date d'inscription sur les trois
dernières années et une adresse par défaut (facturation et livraison) dans son pays.

- Les e-mails sont sur example.com / example.net / example.org, domaines réservés (RFC 2606) :
  aucun message ne peut partir vers une vraie personne.
- Tous ont le même mot de passe (--password), haché comme Magento 1.9.4 :
  sha256(sel + mot de passe):sel, avec un sel aléatoire de 32 caractères par client.
- `increment_id` vaut « synth-<n> » : c'est la marque qu'utilise --delete ; les clients
  réels ne sont jamais touchés. Les adresses et attributs suivent par les clés étrangères.
- La liste des comptes (e-mail, mot de passe, nom, pays) est écrite dans --out, pour le test
  de charge (scripts/magento_load_test.py).

Passe par le client en ligne de commande `mysql` (WampServer : bin/mysql/mysql5.7.x/bin).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import random
import string
import subprocess
import sys
import unicodedata
from pathlib import Path

MARK = "synth-"
DOMAINS = ["example.com", "example.net", "example.org"]

# Attributs du client et de l'adresse dans une installation Magento 1.9 standard ; relus dans
# eav_attribute au lancement pour ne pas dépendre de ces numéros.
CUSTOMER_ATTRS = ["created_in", "firstname", "lastname", "password_hash", "dob", "gender",
                  "default_billing", "default_shipping", "password_created_at"]
ADDRESS_ATTRS = ["firstname", "lastname", "street", "city", "country_id", "postcode", "telephone"]

LOCALES = {
    # pays: (part, prénoms masculins, prénoms féminins, noms, [(ville, code postal)], rues, indicatif, format du numéro)
    "MA": (0.45,
           "Mohamed Youssef Amine Hamza Omar Mehdi Anas Ayoub Karim Rachid Hicham Said Nabil Othmane Ilyas Adam Zakaria Soufiane Khalid Reda",
           "Fatima Khadija Salma Imane Sara Meryem Hajar Nadia Zineb Houda Asmae Yasmine Ghita Loubna Samira Aya Malak Kenza Hiba Nora",
           "Alaoui Benali Bennani Tazi Idrissi Berrada Chraibi El Amrani Fassi Lahlou Benjelloun Ouazzani Kettani Bouzid Naciri Saidi "
           "Mansouri Haddad Ziani Rami Ait Taleb Belkadi Cherkaoui El Khatib Amrani Tahiri Bakkali Zerouali Hilali Sebti",
           [("Casablanca", "20250"), ("Rabat", "10000"), ("Marrakech", "40000"), ("Fès", "30050"), ("Tanger", "90000"),
            ("Agadir", "80000"), ("Meknès", "50000"), ("Oujda", "60000"), ("Kénitra", "14000"), ("Tétouan", "93000")],
           ["Rue {n} Hay Riad", "{n}, Boulevard Mohammed V", "Avenue Hassan II, n° {n}", "Résidence Al Amal, Imm. {n}",
            "{n}, Rue Ibn Sina", "Lotissement Al Wifaq, n° {n}"],
           "+212", "6########"),
    "FR": (0.30,
           "Lucas Hugo Louis Gabriel Arthur Jules Adam Raphaël Léo Nathan Thomas Antoine Maxime Paul Victor Théo Nicolas Julien Pierre Mathis",
           "Emma Jade Louise Alice Chloé Lina Léa Manon Camille Sarah Inès Julie Clara Marie Anaïs Lucie Zoé Laura Pauline Juliette",
           "Martin Bernard Dubois Thomas Robert Richard Petit Durand Leroy Moreau Simon Laurent Lefebvre Michel Garcia David Bertrand "
           "Roux Vincent Fournier Morel Girard André Mercier Dupont Lambert Bonnet François Fontaine Rousseau",
           [("Paris", "75011"), ("Lyon", "69003"), ("Marseille", "13006"), ("Toulouse", "31000"), ("Nantes", "44000"),
            ("Bordeaux", "33000"), ("Lille", "59000"), ("Strasbourg", "67000"), ("Montpellier", "34000"), ("Rennes", "35000")],
           ["{n} rue de la République", "{n} avenue Jean Jaurès", "{n} boulevard Victor Hugo", "{n} rue Pasteur",
            "{n} place de la Gare", "{n} allée des Tilleuls"],
           "+33", "6 ## ## ## ##"),
    "BE": (0.08,
           "Noah Liam Louis Arthur Lucas Jules Adam Victor Mathis Tom", "Olivia Emma Louise Mila Alice Elena Juliette Lina Nora Léa",
           "Peeters Janssens Maes Jacobs Mertens Willems Claes Goossens Wouters De Smet Dubois Lambert Dupont Martin Simon",
           [("Bruxelles", "1000"), ("Liège", "4000"), ("Namur", "5000"), ("Charleroi", "6000"), ("Anvers", "2000"), ("Gand", "9000")],
           ["Rue Neuve {n}", "Chaussée de Louvain {n}", "Avenue Louise {n}", "Rue Royale {n}"],
           "+32", "4## ## ## ##"),
    "GB": (0.07,
           "Oliver George Harry Jack Charlie Thomas James William Daniel Samuel", "Olivia Amelia Isla Ava Emily Sophie Grace Lily Freya Ella",
           "Smith Jones Taylor Brown Williams Wilson Johnson Davies Patel Wright Evans Walker Thompson Roberts Khan",
           [("London", "E1 6AN"), ("Manchester", "M1 1AE"), ("Birmingham", "B1 1BB"), ("Leeds", "LS1 4AP"), ("Bristol", "BS1 4DJ")],
           ["{n} High Street", "{n} Station Road", "{n} Church Lane", "{n} Victoria Road"],
           "+44", "7### ######"),
    "DE": (0.05,
           "Ben Paul Leon Finn Elias Jonas Luis Noah Felix Lukas", "Mia Emma Hannah Sofia Anna Emilia Lina Marie Lea Clara",
           "Müller Schmidt Schneider Fischer Weber Meyer Wagner Becker Schulz Hoffmann Koch Richter Klein Wolf",
           [("Berlin", "10115"), ("Hamburg", "20095"), ("München", "80331"), ("Köln", "50667"), ("Frankfurt am Main", "60311")],
           ["Hauptstraße {n}", "Bahnhofstraße {n}", "Gartenstraße {n}", "Schulstraße {n}"],
           "+49", "15# #######"),
    "NL": (0.05,
           "Daan Sem Lucas Levi Finn Milan Bram Jesse Thijs Ruben", "Emma Julia Mila Tess Sophie Zoë Sara Nora Eva Anna",
           "de Jong Jansen de Vries van den Berg van Dijk Bakker Visser Smit Meijer de Boer Mulder de Groot",
           [("Amsterdam", "1012 AB"), ("Rotterdam", "3011 AA"), ("Utrecht", "3511 AB"), ("Den Haag", "2511 AA"), ("Eindhoven", "5611 AA")],
           ["Kerkstraat {n}", "Dorpsstraat {n}", "Molenweg {n}", "Stationsweg {n}"],
           "+31", "6 ########"),
}
# Noms composés : « El Amrani », « de Jong » restent d'un seul tenant.
COMPOUND = {"MA": ["El Amrani", "Ait Taleb", "El Khatib"], "BE": ["De Smet"],
            "NL": ["de Jong", "de Vries", "van den Berg", "van Dijk", "de Boer", "de Groot"]}


def names(country: str, text: str) -> list[str]:
    out, rest = [], text
    for c in COMPOUND.get(country, []):
        if c in rest:
            out.append(c)
            rest = rest.replace(c, " ")
    return out + rest.split()


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def phone(rng: random.Random, prefix: str, fmt: str) -> str:
    return f"{prefix} " + "".join(str(rng.randint(0, 9)) if ch == "#" else ch for ch in fmt)


def password_hash(rng: random.Random, password: str) -> str:
    salt = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(32))
    return hashlib.sha256((salt + password).encode()).hexdigest() + ":" + salt


def make_customers(n: int, seed: int, password: str, start: int) -> list[dict]:
    rng = random.Random(seed)
    countries = list(LOCALES)
    weights = [LOCALES[c][0] for c in countries]
    now = dt.datetime.now().replace(microsecond=0)
    used: set[str] = set()
    out = []
    for i in range(n):
        c = rng.choices(countries, weights)[0]
        _, men, women, last, cities, streets, prefix, fmt = LOCALES[c]
        gender = rng.choice((1, 2))                                        # options Male / Female
        first = rng.choice(names(c, men if gender == 1 else women))
        lastname = rng.choice(names(c, last))
        base = rng.choice([f"{ascii_slug(first)}.{ascii_slug(lastname)}", f"{ascii_slug(first)}{ascii_slug(lastname)}",
                           f"{ascii_slug(first)[0]}{ascii_slug(lastname)}", f"{ascii_slug(first)}_{ascii_slug(lastname)}"])
        email = f"{base}@{rng.choice(DOMAINS)}"
        while email in used:
            email = f"{base}{rng.randint(1, 9999)}@{email.split('@')[1]}"
        used.add(email)
        city, postcode = rng.choice(cities)
        created = now - dt.timedelta(seconds=rng.randint(0, 3 * 365 * 86400))
        dob = dt.date(rng.randint(1955, 2006), rng.randint(1, 12), rng.randint(1, 28))
        out.append({"n": start + i, "email": email, "firstname": first, "lastname": lastname, "gender": gender,
                    "dob": f"{dob} 00:00:00", "created": created, "country": c, "city": city, "postcode": postcode,
                    "street": rng.choice(streets).format(n=rng.randint(1, 180)), "telephone": phone(rng, prefix, fmt),
                    "password_hash": password_hash(rng, password)})
    return out


# --- MySQL ----------------------------------------------------------------------------------

class MySQL:
    def __init__(self, exe: str, db: str, user: str, password: str, host: str):
        self.base = [exe, f"-h{host}", f"-u{user}", "--default-character-set=utf8"] + ([f"-p{password}"] if password else [])
        self.db = db

    def run(self, sql: str) -> str:
        r = subprocess.run(self.base + ["-N", "-B", self.db], input=sql, capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise SystemExit(f"mysql : {r.stderr.strip()}")
        return r.stdout

    def scalar(self, sql: str) -> str:
        return self.run(sql).strip()


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def rows_sql(table: str, cols: list[str], rows: list[tuple], chunk: int = 1000) -> list[str]:
    return [f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n" +
            ",\n".join("(" + ", ".join(map(q, r)) + ")" for r in rows[i:i + chunk]) + ";"
            for i in range(0, len(rows), chunk)]


def build_sql(customers: list[dict], attrs: dict, first_customer: int, first_address: int) -> str:
    ca, aa = attrs["customer"], attrs["customer_address"]
    ent, addr = [], []
    values = {"varchar": [], "int": [], "datetime": [], "text": []}
    for k, c in enumerate(customers):
        cid, aid = first_customer + k, first_address + k
        created = c["created"].strftime("%Y-%m-%d %H:%M:%S")
        ent.append((cid, 1, 1, 1, c["email"], 1, f"{MARK}{c['n']}", 1, created, created, 1, 0))
        addr.append((aid, 2, 2, cid, created, created, 1))
        for code, val in (("created_in", "Default Store View"), ("firstname", c["firstname"]), ("lastname", c["lastname"]),
                          ("password_hash", c["password_hash"])):
            values["varchar"].append(("customer_entity_varchar", 1, ca[code], cid, val))
        values["datetime"].append(("customer_entity_datetime", 1, ca["dob"], cid, c["dob"]))
        for code, val in (("gender", c["gender"]), ("default_billing", aid), ("default_shipping", aid),
                          ("password_created_at", int(c["created"].timestamp()))):
            values["int"].append(("customer_entity_int", 1, ca[code], cid, val))
        for code, val in (("firstname", c["firstname"]), ("lastname", c["lastname"]), ("city", c["city"]),
                          ("country_id", c["country"]), ("postcode", c["postcode"]), ("telephone", c["telephone"])):
            values["varchar"].append(("customer_address_entity_varchar", 2, aa[code], aid, val))
        values["text"].append(("customer_address_entity_text", 2, aa["street"], aid, c["street"]))

    sql = ["SET NAMES utf8;", "START TRANSACTION;"]
    sql += rows_sql("customer_entity", ["entity_id", "entity_type_id", "attribute_set_id", "website_id", "email", "group_id",
                                        "increment_id", "store_id", "created_at", "updated_at", "is_active",
                                        "disable_auto_group_change"], ent)
    sql += rows_sql("customer_address_entity", ["entity_id", "entity_type_id", "attribute_set_id", "parent_id",
                                                "created_at", "updated_at", "is_active"], addr)
    for kind in values:
        by_table: dict[str, list[tuple]] = {}
        for table, *row in values[kind]:
            by_table.setdefault(table, []).append(tuple(row))
        for table, rows in by_table.items():
            sql += rows_sql(table, ["entity_type_id", "attribute_id", "entity_id", "value"], rows)
    sql.append("COMMIT;")
    return "\n".join(sql)


def load_attrs(db: MySQL) -> dict:
    out = {"customer": {}, "customer_address": {}}
    rows = db.run("SELECT t.entity_type_code, a.attribute_code, a.attribute_id FROM eav_attribute a "
                  "JOIN eav_entity_type t ON t.entity_type_id = a.entity_type_id "
                  "WHERE t.entity_type_code IN ('customer', 'customer_address');")
    for line in rows.splitlines():
        etype, code, aid = line.split("\t")
        out[etype][code] = int(aid)
    missing = [a for a in CUSTOMER_ATTRS if a not in out["customer"]] + \
              [f"address.{a}" for a in ADDRESS_ATTRS if a not in out["customer_address"]]
    if missing:
        raise SystemExit(f"attributs absents de eav_attribute : {', '.join(missing)} (Magento 1.9 attendu)")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("-n", "--count", type=int, default=5000, help="nombre de clients à ajouter")
    p.add_argument("--password", default="Test1234!", help="mot de passe commun des comptes")
    p.add_argument("--seed", type=int, default=7, help="graine : mêmes noms d'une exécution à l'autre")
    p.add_argument("--out", default="data/magento_customers.csv", help="liste des comptes pour le test de charge")
    p.add_argument("--delete", action="store_true", help="retirer les clients ajoutés par ce script, puis quitter")
    p.add_argument("--dry-run", metavar="FICHIER_SQL", help="écrire le SQL dans ce fichier sans rien exécuter")
    p.add_argument("--backup", metavar="FICHIER_SQL", help="sauvegarder les tables clients (mysqldump) avant d'écrire")
    p.add_argument("--mysql", default="C:/wamp64/bin/mysql/mysql5.7.26/bin/mysql.exe")
    p.add_argument("--db", default="magento")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--user", default="root")
    p.add_argument("--db-password", default="")
    a = p.parse_args()
    db = MySQL(a.mysql, a.db, a.user, a.db_password, a.host)

    if a.backup:
        dump = str(Path(a.mysql).with_name("mysqldump" + Path(a.mysql).suffix))
        tables = db.run("SHOW TABLES LIKE 'customer\\_%';").split()
        Path(a.backup).parent.mkdir(parents=True, exist_ok=True)
        with open(a.backup, "w", encoding="utf-8") as f:
            r = subprocess.run([dump, *db.base[1:], a.db, *tables], stdout=f, stderr=subprocess.PIPE, text=True)
        if r.returncode:
            raise SystemExit(f"mysqldump : {r.stderr.strip()}")
        print(f"sauvegarde : {a.backup} ({len(tables)} tables)")

    if a.delete:
        n = db.scalar(f"SELECT COUNT(*) FROM customer_entity WHERE increment_id LIKE '{MARK}%';")
        db.run(f"DELETE FROM customer_entity WHERE increment_id LIKE '{MARK}%';")
        print(f"{n} clients synthétiques retirés")
        return 0

    attrs = load_attrs(db)
    start = int(db.scalar(f"SELECT COALESCE(MAX(CAST(SUBSTRING(increment_id, {len(MARK) + 1}) AS UNSIGNED)), 0) + 1 "
                          f"FROM customer_entity WHERE increment_id LIKE '{MARK}%';"))
    first_customer = int(db.scalar("SELECT COALESCE(MAX(entity_id), 0) + 1 FROM customer_entity;"))
    first_address = int(db.scalar("SELECT COALESCE(MAX(entity_id), 0) + 1 FROM customer_address_entity;"))
    customers = make_customers(a.count, a.seed + start, a.password, start)
    taken = set(db.run("SELECT email FROM customer_entity WHERE website_id = 1;").split())
    for c in customers:      # un e-mail déjà pris (relance du script) reçoit un suffixe
        while c["email"] in taken:
            user, dom = c["email"].split("@")
            c["email"] = f"{user}{random.Random(c['n']).randint(10, 99999)}@{dom}"
        taken.add(c["email"])
    sql = build_sql(customers, attrs, first_customer, first_address)

    if a.dry_run:
        Path(a.dry_run).write_text(sql, encoding="utf-8")
        print(f"SQL écrit dans {a.dry_run} ({len(customers)} clients), rien n'est exécuté")
        return 0
    db.run(sql)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists() or start == 1
    with out.open("w" if new else "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["email", "password", "firstname", "lastname", "country", "city"])
        w.writerows([c["email"], a.password, c["firstname"], c["lastname"], c["country"], c["city"]] for c in customers)
    total = db.scalar(f"SELECT COUNT(*) FROM customer_entity WHERE increment_id LIKE '{MARK}%';")
    by_country = db.run(f"SELECT v.value, COUNT(*) FROM customer_address_entity_varchar v "
                        f"JOIN customer_address_entity ad ON ad.entity_id = v.entity_id "
                        f"JOIN customer_entity c ON c.entity_id = ad.parent_id "
                        f"WHERE v.attribute_id = {attrs['customer_address']['country_id']} AND c.increment_id LIKE '{MARK}%' "
                        f"GROUP BY v.value ORDER BY 2 DESC;").replace("\t", " ").splitlines()
    print(f"{len(customers)} clients ajoutés (ids {first_customer} à {first_customer + len(customers) - 1}), "
          f"{total} clients synthétiques en tout ; pays : {', '.join(by_country)}")
    print(f"comptes pour le test de charge : {out} (mot de passe : {a.password})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
