/* Schéma en étoile : deux dimensions, trois tables de faits */

CREATE TABLE dim_actif (
    ticker   TEXT PRIMARY KEY,
    nom      TEXT NOT NULL,
    secteur  TEXT NOT NULL,
    pays     TEXT NOT NULL
);

CREATE TABLE dim_date (
    date          TEXT PRIMARY KEY,
    annee         INTEGER NOT NULL,
    trimestre     INTEGER NOT NULL,
    mois          INTEGER NOT NULL,
    jour_semaine  INTEGER NOT NULL
);

CREATE TABLE fait_prix (
    date       TEXT NOT NULL REFERENCES dim_date(date),
    ticker     TEXT NOT NULL REFERENCES dim_actif(ticker),
    cloture    REAL NOT NULL,
    rendement  REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE fait_portefeuille (
    date       TEXT NOT NULL REFERENCES dim_date(date),
    strategie  TEXT NOT NULL,
    rendement  REAL NOT NULL,
    PRIMARY KEY (date, strategie)
);

CREATE TABLE fait_poids (
    date       TEXT NOT NULL,
    ticker     TEXT NOT NULL REFERENCES dim_actif(ticker),
    poids      REAL NOT NULL,
    strategie  TEXT NOT NULL,
    PRIMARY KEY (date, ticker, strategie)
);

CREATE INDEX idx_prix_ticker ON fait_prix(ticker);
CREATE INDEX idx_portefeuille_strategie ON fait_portefeuille(strategie);
