# PRD — Budget Tracker

## 1. Executive Summary

Budget Tracker est une application web personnelle de suivi budgétaire pour Arnaud, qui vit sous curatelle avec ~1350€/mois (AAH + chômage + APL). L'app importe les relevés de compte BoursoBank (PDF), parse automatiquement les transactions, les catégorise, et affiche un dashboard avec graphes et alertes budgétaires.

Le père d'Arnaud (Erick) doit pouvoir consulter un résumé mensuel via un lien partagé, sans compte ni mot de passe.

**MVP Goal** : Importer un PDF BoursoBank, extraire les transactions, les catégoriser automatiquement, afficher un dashboard mensuel avec enveloppes budgétaires et alertes, et partager un résumé avec le père.

## 2. Mission

**Rendre les finances visibles et maîtrisables, simplement.**

Principes :
1. **Zéro friction** — upload un PDF, tout le reste est automatique
2. **Clarté** — savoir en un coup d'œil où en est le budget
3. **Alertes proactives** — prévenir avant de dépasser, pas après
4. **Partage familial** — le père peut suivre sans setup technique
5. **Privacy-first** — données locales, pas de cloud bancaire tiers

## 3. Target Users

### Arnaud (utilisateur principal)
- Dev senior, 40 ans, sous curatelle
- Compte unique BoursoBank
- Revenus gérés par curateur (virements réguliers entrants)
- Besoin : visualiser ses dépenses, respecter des enveloppes, anticiper les fins de mois
- Confort technique : 5/5

### Erick (père, lecteur)
- Accès lecture seule via lien partagé
- Besoin : voir un résumé mensuel des dépenses d'Arnaud
- Confort technique : basique (navigateur web)

## 4. MVP Scope

### In Scope

**Import & Parsing**
- ✅ Upload PDF BoursoBank via interface web
- ✅ Parsing automatique des transactions (pdftotext -layout + regex)
- ✅ Gestion des lignes multi (virements avec nom + ref sur 2-3 lignes)
- ✅ Détection doublons (même PDF importé 2 fois)
- ✅ Historique des imports

**Catégorisation**
- ✅ Auto-catégorisation par patterns regex (courses, bar/tabac, abonnements, etc.)
- ✅ Correction manuelle (clic pour changer la catégorie d'une transaction)
- ✅ Apprentissage : une correction manuelle crée un nouveau pattern pour le futur
- ✅ Catégorie "Transfert interne" pour les virements entre comptes

**Dashboard**
- ✅ Vue mensuelle : dépenses par catégorie (donut Chart.js)
- ✅ Évolution du solde sur le mois (ligne Chart.js)
- ✅ Top dépenses du mois
- ✅ Comparaison mois précédent (delta par catégorie)

**Enveloppes & Alertes**
- ✅ Définir un budget max par catégorie (ex : Bar/Tabac = 100€/mois)
- ✅ Barre de progression par enveloppe (vert → orange → rouge)
- ✅ Alerte visuelle quand une enveloppe dépasse 80% puis 100%
- ✅ Notification Discord (webhook) quand un seuil est dépassé

**Partage père**
- ✅ Page résumé accessible via URL avec token unique (pas de login)
- ✅ Résumé mensuel : total dépenses, répartition catégories, solde
- ✅ Pas de détail transaction (respect vie privée)

**Déploiement**
- ✅ LXC Proxmox (Debian 12, IP statique)
- ✅ Tunnel Cloudflare (budget.nanoserveur.fr)
- ✅ Service systemd

### Out of Scope

- ❌ Connexion bancaire automatique (API BoursoBank / scraping)
- ❌ Multi-comptes / multi-banques
- ❌ Export CSV BoursoBank (PDF uniquement pour le MVP)
- ❌ App mobile native
- ❌ OCR avancé (on utilise pdftotext, pas de scan photo)
- ❌ Prévisions IA / machine learning
- ❌ Authentification utilisateur (usage perso, token partage pour le père)

## 5. User Stories

1. **En tant qu'Arnaud**, je veux uploader mon relevé BoursoBank PDF, pour que mes transactions soient automatiquement extraites et catégorisées.
   > *Ex : drop du fichier "Releve-compte-27-02-2026.pdf" → 30 transactions parsées en 2 secondes*

2. **En tant qu'Arnaud**, je veux voir un dashboard mensuel avec mes dépenses par catégorie, pour savoir où part mon argent.
   > *Ex : donut montrant Courses 35%, Bar/Tabac 25%, Abonnements 20%, Shopping 15%, Divers 5%*

3. **En tant qu'Arnaud**, je veux définir des enveloppes budgétaires par catégorie, pour me fixer des limites.
   > *Ex : Bar/Tabac = 80€/mois, Courses = 300€/mois, Abonnements tech = 300€/mois*

4. **En tant qu'Arnaud**, je veux être alerté quand je dépasse 80% d'une enveloppe, pour freiner avant qu'il soit trop tard.
   > *Ex : notification Discord "⚠️ Bar/Tabac : 65€/80€ (81%) — attention !"*

5. **En tant qu'Arnaud**, je veux corriger la catégorie d'une transaction et que l'app apprenne, pour améliorer l'auto-catégorisation.
   > *Ex : "LA MAISON DU PERO" catégorisé "Divers" → je corrige en "Bar/Tabac" → pattern sauvé*

6. **En tant qu'Arnaud**, je veux comparer mes dépenses mois par mois, pour voir si je m'améliore.
   > *Ex : "Bar/Tabac : 120€ en janvier → 85€ en février (-29%)"*

7. **En tant qu'Erick (père)**, je veux accéder à un résumé mensuel via un lien, pour suivre les finances d'Arnaud sans lui demander.
   > *Ex : budget.nanoserveur.fr/partage/abc123 → résumé février : 1050€ dépensés, solde 107€*

## 6. Core Architecture & Patterns

### Architecture

```
[Browser] → [aiohttp server :8080] → [SQLite DB]
                    ↓
            [pdftotext -layout]  (subprocess, parsing PDF)
                    ↓
            [regex parser]  (extraction transactions)
                    ↓
            [auto-categorizer]  (pattern matching)
```

### Structure du projet

```
budget-tracker/
├── app.py                  # Point d'entrée aiohttp
├── parser.py               # Parsing PDF BoursoBank (pdftotext + regex)
├── categorizer.py          # Auto-catégorisation + apprentissage
├── db.py                   # SQLite init + requêtes
├── notifications.py        # Alertes Discord webhook
├── static/
│   ├── css/style.css       # Dark theme
│   ├── js/app.js           # Chart.js + interactions
│   └── js/charts.js        # Config graphes
├── templates/
│   ├── index.html          # Dashboard principal
│   ├── transactions.html   # Liste transactions
│   ├── budgets.html        # Gestion enveloppes
│   ├── import.html         # Upload PDF
│   └── share.html          # Résumé partagé (père)
├── uploads/                # PDFs uploadés (gitignored)
├── data/
│   └── budget.db           # SQLite
├── requirements.txt
└── README.md
```

### Patterns

- **Backend** : aiohttp avec templates Jinja2 (pas de SPA, server-rendered)
- **DB** : SQLite avec requêtes directes (pas d'ORM, c'est du CRUD simple)
- **Parsing** : subprocess `pdftotext -layout` → regex Python sur le texte
- **Catégorisation** : table `category_patterns` avec regex, match top-down, fallback "Divers"
- **Alertes** : check enveloppes après chaque import, webhook Discord si dépassement
- **Partage** : token UUID généré une fois, URL stable pour le père

## 7. Features

### 7.1 Import PDF

- Zone de drop/upload sur la page d'import
- Validation : fichier PDF, < 5 Mo
- Feedback : nombre de transactions extraites, période détectée, erreurs éventuelles
- Détection doublons : hash SHA256 du PDF, refus si déjà importé
- Stockage du PDF original dans `uploads/`

### 7.2 Parser BoursoBank

Le parser extrait les transactions depuis le texte `pdftotext -layout` :

```python
# Ligne type :
# 02/02/2026 CARTE 30/01/26 AGENALINE        CB*0403   02/02/2026     11,50
# Colonnes à positions fixes (approximatives) :
# [0:10]   date_operation
# [11:80]  libellé
# [80:92]  date_valeur
# [92:108] débit
# [108:]   crédit
```

Gestion des cas spéciaux :
- Lignes multi (virement avec nom + ref) : rattachées à la transaction parente
- "SOLDE AU :" : extraction solde initial
- "Nouveau solde" : extraction solde final
- "AVOIR" : montant en crédit (remboursement)
- Montants au format français (virgule décimale) → conversion float

### 7.3 Catégorisation automatique

Catégories par défaut avec patterns :

| Catégorie | Icon | Patterns |
|-----------|------|----------|
| Courses | 🛒 | `INTERMARCHE`, `AGENALINE`, `LECLERC`, `CARREFOUR`, `LIDL`, `ALDI` |
| Bar / Tabac | ☕ | `LE BALTO`, `TABAC`, `BAR `, `CAFE`, `MAISON DU PERO` |
| Abonnements tech | 🤖 | `CLAUDE.AI`, `PROTON`, `GOOGLE.*CLOUD`, `Google Play`, `GANDI` |
| Téléphone | 📱 | `FREE MOBILE`, `SFR`, `ORANGE`, `BOUYGUES` |
| Internet | 📡 | `FREE\b(?!.*MOBILE)` |
| Shopping | 📦 | `AMAZON`, `PAYPAL` |
| Famille | 👨‍👩‍👧 | `LARRIEU ERICK`, `ELISA`, `CASTAING MARTINE` |
| Transfert interne | 🔄 | `VIR INST M LARRIEU ARNAUD` (en crédit) |
| Remboursement | ↩️ | `AVOIR` |
| Divers | 📌 | fallback |

### 7.4 Enveloppes budgétaires

- CRUD : créer/modifier/supprimer des enveloppes
- Champs : catégorie, montant max mensuel
- Barre de progression colorée : vert (< 60%), orange (60-80%), rouge (> 80%)
- Reset automatique chaque mois

### 7.5 Alertes Discord

```
⚠️ Budget Tracker — Alerte enveloppe
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
☕ Bar / Tabac : 68€ / 80€ (85%)
Tu approches de ta limite !
```

Envoi via webhook Discord (variable `DISCORD_WEBHOOK_BUDGET` dans .env).

### 7.6 Page de partage (père)

- URL : `budget.nanoserveur.fr/share/<token>`
- Contenu : mois en cours, total dépenses, répartition catégories (donut), solde actuel
- **Pas de détail** des transactions individuelles (vie privée)
- Design simple, lisible sur mobile
- Token généré à la première config, stable dans le temps

## 8. Technology Stack

| Composant | Technologie | Justification |
|-----------|-------------|---------------|
| Backend | Python 3.11+ / aiohttp | Même stack que Mood Tracker, Dashboard |
| Templates | Jinja2 (aiohttp_jinja2) | Server-rendered, simple |
| DB | SQLite | Léger, pas besoin de serveur DB, pattern rodé |
| Graphes | Chart.js 4 | Même lib que les autres dashboards |
| CSS | Custom (dark theme) | Cohérent avec l'écosystème nanoserveur |
| PDF parsing | pdftotext (poppler-utils) | Testé et validé sur relevé BoursoBank |
| Notifications | Discord webhook | Déjà en place sur mon-assistant |
| Tunnel | Cloudflare (cloudflared) | Pattern standard nanoserveur |

### Dépendances Python

```
aiohttp>=3.9
aiohttp-jinja2>=1.6
aiofiles>=23.0
```

### Dépendances système

```
poppler-utils   # pdftotext
```

## 9. Security & Configuration

### Configuration (.env)

```env
# Server
PORT=8080
DATA_DIR=/opt/budget-tracker/data

# Discord alerts
DISCORD_WEBHOOK_BUDGET=https://discord.com/api/webhooks/...

# Share token (generated once)
SHARE_TOKEN=<uuid4>
```

### Sécurité

- **In scope** : token de partage pour le père, validation upload (type + taille)
- **Out of scope** : authentification utilisateur (usage perso, réseau local + tunnel)
- Les PDFs uploadés restent sur le serveur (pas de cloud)
- Pas de données bancaires sensibles stockées au-delà des transactions (pas de RIB, IBAN dans la DB)

## 10. API Specification

### Pages (server-rendered)

| Route | Méthode | Description |
|-------|---------|-------------|
| `GET /` | GET | Dashboard mensuel |
| `GET /transactions` | GET | Liste des transactions (filtrable) |
| `GET /import` | GET | Page d'upload PDF |
| `POST /import` | POST | Upload + parsing PDF |
| `GET /budgets` | GET | Gestion enveloppes |
| `POST /budgets` | POST | Créer/modifier enveloppe |
| `GET /share/<token>` | GET | Résumé partagé (père) |

### API JSON (pour les graphes)

| Route | Méthode | Description |
|-------|---------|-------------|
| `GET /api/dashboard?month=YYYY-MM` | GET | Données dashboard (catégories, solde, enveloppes) |
| `POST /api/transactions/<id>/category` | POST | Changer catégorie d'une transaction |
| `GET /api/months` | GET | Liste des mois disponibles |

## 11. Success Criteria

### MVP réussi si :

- ✅ Un PDF BoursoBank uploadé est parsé en < 3 secondes
- ✅ 90%+ des transactions sont correctement catégorisées automatiquement
- ✅ Le dashboard affiche les graphes mensuels (donut + ligne de solde)
- ✅ Les enveloppes budgétaires fonctionnent avec barres de progression
- ✅ Les alertes Discord partent quand un seuil est dépassé
- ✅ Le père peut voir le résumé via le lien partagé
- ✅ L'app tourne sur une LXC Proxmox accessible via budget.nanoserveur.fr

### Qualité

- Dark theme cohérent avec l'écosystème (Mood Tracker, Dashboard)
- Mobile-friendly (responsive)
- Temps de chargement < 1s
- Aucun crash sur PDF mal formé (fallback graceful)

## 12. Implementation Phases

### Phase 1 — Foundation + Parser (backend)

**Goal** : Parser PDF fonctionnel + DB + import

- ✅ Setup projet (aiohttp, SQLite, structure fichiers)
- ✅ Schema DB (transactions, categories, budgets, imports)
- ✅ Parser BoursoBank (pdftotext -layout + regex)
- ✅ Tests parser sur le relevé réel
- ✅ API upload PDF + stockage + parsing
- ✅ Auto-catégorisation (patterns par défaut)
- ✅ Page d'import basique (upload + feedback)

**Validation** : uploader le PDF test → voir les transactions en DB

### Phase 2 — Dashboard + Transactions

**Goal** : Interface de visualisation complète

- ✅ Dashboard mensuel (donut catégories, ligne solde, stats)
- ✅ Liste transactions avec filtres (date, catégorie, recherche)
- ✅ Correction manuelle de catégorie (clic → select → save)
- ✅ Apprentissage patterns (correction → nouveau pattern)
- ✅ Navigation entre les mois
- ✅ Dark theme CSS

**Validation** : naviguer le dashboard, corriger une catégorie, vérifier la persistence

### Phase 3 — Enveloppes + Alertes + Partage

**Goal** : Budget actif + partage familial

- ✅ CRUD enveloppes budgétaires
- ✅ Barres de progression colorées
- ✅ Alertes Discord (webhook) sur dépassement
- ✅ Page de partage avec token (résumé mensuel pour le père)
- ✅ Comparaison mois/mois (delta par catégorie)

**Validation** : créer une enveloppe, déclencher une alerte, ouvrir le lien de partage

### Phase 4 — Déploiement + Polish

**Goal** : Production sur Proxmox

- ✅ Script setup LXC (`scripts/setup-budget-lxc.sh`)
- ✅ Service systemd + Cloudflare tunnel
- ✅ PWA manifest (installable sur phone)
- ✅ Tests E2E (agent-browser)
- ✅ Documentation

**Validation** : app accessible sur budget.nanoserveur.fr, E2E screenshots OK

## 13. Future Considerations

- **Export CSV BoursoBank** : parser alternatif si BoursoBank propose le CSV
- **Multi-banques** : parser générique avec plugins par banque
- **Résumé WhatsApp** : envoyer le résumé mensuel au père par WhatsApp (en plus du lien)
- **Prévisions** : "à ce rythme, tu finiras le mois à X€"
- **Graphe annuel** : vue 12 mois pour les tendances longues
- **Objectifs d'épargne** : mettre de côté X€/mois

## 14. Risks & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Format PDF BoursoBank change | Parser cassé | Regex modulaires, tests unitaires sur samples, fallback pdfplumber |
| Catégorisation incorrecte | Données faussées | Correction manuelle facile + apprentissage, review après import |
| Doublons de transactions | Totaux faux | Hash PDF + check période déjà importée |
| Vie privée (lien partage) | Données exposées | Token UUID, pas de détail transactions, HTTPS only |
| poppler non installé sur LXC | Import échoue | Ajout dans script setup LXC (apt install poppler-utils) |

## 15. Appendix

### Relevé BoursoBank analysé

- Fichier : `Releve-compte-27-02-2026.pdf`
- Période : 31/01/2026 → 27/02/2026
- ~30 transactions sur 2 pages
- Extraction validée avec `pdftotext -layout`

### Infra cible

- **LXC** : Proxmox (Debian 12, 512 MB RAM, 1 CPU)
- **IP** : à attribuer (prochaine dispo dans la plage 192.168.1.x)
- **Tunnel** : budget.nanoserveur.fr
- **Accès Proxmox** : `ssh root@100.83.143.68`

### Liens

- Repo : https://github.com/Wessonano/budget-tracker
- Projet Obsidian : `memory/projects/budget-tracker.md`
- Relevé test : `~/Téléchargements/Releve-compte-27-02-2026.pdf` (Dell)
