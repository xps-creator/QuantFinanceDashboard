/* Requêtes d'analyse sur la base data/processed/marches.db (SQLite) */

/* 1. Performance annuelle de chaque actif (rendement composé par année) */
SELECT a.nom,
       d.annee,
       ROUND((EXP(SUM(LN(1 + p.rendement))) - 1) * 100, 1) AS rendement_annuel_pct
FROM fait_prix p
JOIN dim_actif a ON a.ticker = p.ticker
JOIN dim_date  d ON d.date = p.date
WHERE p.rendement IS NOT NULL
GROUP BY a.nom, d.annee
ORDER BY d.annee, rendement_annuel_pct DESC;

/* 2. Volatilité annualisée par secteur (écart type des rendements journaliers) */
WITH stats AS (
    SELECT a.secteur,
           AVG(p.rendement) AS moyenne,
           AVG(p.rendement * p.rendement) AS moyenne_carres,
           COUNT(*) AS n
    FROM fait_prix p
    JOIN dim_actif a ON a.ticker = p.ticker
    WHERE p.rendement IS NOT NULL
    GROUP BY a.secteur
)
SELECT secteur,
       ROUND(SQRT((moyenne_carres - moyenne * moyenne) * n / (n - 1)) * SQRT(252) * 100, 1) AS volatilite_pct
FROM stats
ORDER BY volatilite_pct DESC;

/* 3. Les 10 pires journées du portefeuille équipondéré */
SELECT date, ROUND(rendement * 100, 2) AS rendement_pct
FROM fait_portefeuille
WHERE strategie = 'Équipondéré'
ORDER BY rendement ASC
LIMIT 10;

/* 4. Rendement mensuel de chaque stratégie, avec la meilleure stratégie du mois */
WITH mensuel AS (
    SELECT strftime('%Y-%m', date) AS mois,
           strategie,
           EXP(SUM(LN(1 + rendement))) - 1 AS rendement
    FROM fait_portefeuille
    GROUP BY mois, strategie
),
classement AS (
    SELECT *, RANK() OVER (PARTITION BY mois ORDER BY rendement DESC) AS rang
    FROM mensuel
)
SELECT mois, strategie, ROUND(rendement * 100, 2) AS rendement_pct
FROM classement
WHERE rang = 1
ORDER BY mois;

/* 5. Poids moyen de chaque actif par stratégie */
SELECT f.strategie, a.nom, ROUND(AVG(f.poids) * 100, 1) AS poids_moyen_pct
FROM fait_poids f
JOIN dim_actif a ON a.ticker = f.ticker
GROUP BY f.strategie, a.nom
ORDER BY f.strategie, poids_moyen_pct DESC;
