# DotQuality — Documentation fonctionnelle

**Un Système de Management de la Qualité (SMQ) numérique, pensé pour devenir une
plateforme configurable multi-secteurs.**

*Document destiné à la présentation du produit auprès d'un expert qualité /
décideur métier — support de préparation de pitch.*

---

## Résumé exécutif

DotQuality digitalise le Système de Management de la Qualité d'une entreprise :
maîtrise documentaire, non-conformités, actions correctives, audits internes,
organisation et référentiels de certification, pilotés depuis un tableau de bord
unique. Ce n'est pas une maquette : c'est un **prototype fonctionnel, testé (63 tests
automatisés), qui tourne réellement**, avec un vrai workflow documentaire, une vraie
boucle qualité, et une architecture pensée depuis le premier jour pour devenir une
plateforme adaptable à plusieurs secteurs d'activité et plusieurs entreprises.

**Où on en est** : les fondations métiers les plus structurantes d'ISO 9001
(maîtrise documentaire, non-conformités/actions/audits, contexte et périmètre de
l'organisme, référentiels et matrice de conformité) sont construites et
opérationnelles. Les briques encore en construction (risques, objectifs, revue de
direction, compétences, fournisseurs, réclamations) sont identifiées précisément et
chiffrées — ce document présente les deux : ce qui existe, et ce qui vient.

---

## Sommaire

1. [Le problème que DotQuality résout](#1-le-problème-que-dotquality-résout)
2. [Couverture ISO 9001 — où en est le produit aujourd'hui](#2-couverture-iso-9001--où-en-est-le-produit-aujourdhui)
3. [Les grandes fonctionnalités, racontées](#3-les-grandes-fonctionnalités-racontées)
4. [Ce qui reste à construire](#4-ce-qui-reste-à-construire)
5. [La vision : une seule plateforme, tous les secteurs](#5-la-vision--une-seule-plateforme-tous-les-secteurs)
6. [Feuille de route commerciale](#6-feuille-de-route-commerciale)
7. [Messages clés à retenir](#7-messages-clés-à-retenir)

---

## 1. Le problème que DotQuality résout

Un Responsable Qualité gère aujourd'hui son SMQ à travers des outils dispersés :
tableurs pour les indicateurs, dossiers partagés pour les documents, échanges d'e-mail
pour les non-conformités, préparation manuelle de chaque audit et de chaque revue de
direction. Résultat : une charge de travail administrative lourde, une traçabilité
fragile, et un risque réel en audit de certification si un document, une preuve ou une
décision n'est pas retrouvée au bon moment.

DotQuality répond à ce problème avec **un seul système, structuré autour de la norme
ISO 9001 elle-même** plutôt qu'autour d'un outil générique de gestion de tâches : les
processus, les documents, les non-conformités, les audits et les référentiels sont
des objets métier à part entière, reliés entre eux, avec une traçabilité et des droits
d'accès qui suivent le cycle de vie réel d'un SMQ.

---

## 2. Couverture ISO 9001 — où en est le produit aujourd'hui

C'est la vue la plus importante pour un expert qualité : où en est le produit,
clause par clause, par rapport à la structure d'ISO 9001:2015.

| Clause ISO 9001 | Exigence | Couverture DotQuality |
|---|---|---|
| 4.2 | Besoins et attentes des parties intéressées | ✅ **Couvert** — module Parties intéressées (catégorie, attentes, niveau d'influence) |
| 4.3 | Périmètre du système de management de la qualité | ✅ **Couvert** — module Périmètre du SMQ (sites, activités, processus couverts) |
| 4.4 | Le SMQ et ses processus | ✅ **Couvert** — module Processus + chaîne qualité visuelle sur le tableau de bord |
| 5.2 | Politique qualité | ✅ **Couvert** — document maîtrisé de type "Politique", avec workflow d'approbation |
| 5.3 | Rôles, responsabilités et autorités | ✅ **Couvert** — 6 rôles hiérarchiques avec droits distincts (rédaction, vérification, validation, publication) |
| 6.1 | Risques et opportunités | 🕓 **À venir** — voir feuille de route |
| 6.2 | Objectifs qualité et planification | 🕓 **À venir** |
| 6.3 | Planification des modifications | 🕓 **À venir** (Gestion des changements) |
| 7.2 | Compétences | 🕓 **À venir** — un module de compétences RH existe déjà dans la plateforme, non encore relié au SMQ |
| 7.5 | Informations documentées | ✅ **Couvert** — workflow documentaire complet (brouillon → validation → approbation → publication → en vigueur → obsolète) |
| 8.4 | Maîtrise des prestataires externes (fournisseurs) | 🕓 **À venir** |
| 9.1 | Surveillance, mesure, analyse et évaluation | ⚠️ **Partiel** — indicateurs opérationnels réels sur le tableau de bord (documents, non-conformités, actions, audits), pas encore de fiche indicateur formalisée par objectif |
| 9.2 | Audit interne | ✅ **Couvert** — module Audits internes, checklist, constats, liens vers non-conformités |
| 9.3 | Revue de direction | 🕓 **À venir** — un moteur existe déjà dans la plateforme technique, en cours d'intégration |
| 10.2 | Non-conformité et action corrective | ✅ **Couvert** — workflow complet avec analyse de cause, actions, vérification d'efficacité |
| 10.3 | Amélioration continue | ⚠️ **Partiel** — visible via la tendance des non-conformités et des actions, pas encore de module dédié |

**Lecture honnête** : 8 exigences sur 16 sont pleinement couvertes aujourd'hui,
notamment les plus lourdes à mettre en œuvre (maîtrise documentaire, boucle
non-conformité/action, audit interne). Les exigences encore en construction sont
identifiées une à une, avec un chiffrage précis (section 6).

---

## 3. Les grandes fonctionnalités, racontées

### 3.1 La maîtrise documentaire

Chaque document qualité (politique, manuel, procédure, instruction, formulaire...)
suit un cycle de vie contrôlé : un rédacteur crée un brouillon, le soumet à
validation, un vérificateur l'approuve ou le rejette avec un motif obligatoire, un
responsable qualité le publie puis le met en vigueur à une date donnée — ce qui rend
automatiquement obsolète la version précédente. Impossible de valider sans pièce
jointe, impossible de modifier un document après sa mise en validation, impossible de
créer une nouvelle version sans justifier le motif du changement. Ce n'est pas un
partage de fichiers : c'est un contrôle documentaire réel.

### 3.2 La boucle qualité : non-conformité → action → audit

Une non-conformité déclarée passe par une analyse de cause (méthode 5 pourquoi ou
Ishikawa), déclenche une ou plusieurs actions correctives, et ne peut être clôturée
que si l'efficacité de chaque action a été vérifiée. Les audits internes s'appuient
sur des checklists et peuvent faire naître directement des non-conformités. Tout est
relié au processus concerné et aux documents associés.

### 3.3 Organisation et périmètre

Avant même de parler de risques ou d'objectifs, un SMQ doit définir *sur quoi* il
porte. DotQuality permet de décrire les sites, les activités de l'entreprise, les
parties intéressées (clients, autorités, actionnaires...) et d'assembler tout cela
dans un périmètre de certification explicite — la première question que pose tout
auditeur ISO 9001 (clause 4.3).

### 3.4 Référentiels et matrice de conformité

Plutôt que de coder "ISO 9001" en dur, DotQuality modélise un référentiel comme une
donnée : n'importe quelle norme (ISO 14001, ISO 45001, un référentiel client...) peut
être ajoutée avec ses propres exigences, organisées par clause. Chaque exigence peut
ensuite être évaluée face à un ou plusieurs processus, avec un état de conformité, des
preuves documentaires et un écart constaté si besoin — c'est la matrice de conformité,
l'outil de préparation d'audit par excellence.

### 3.5 Le tableau de bord

Un seul écran donne : un score de santé qualité global, les indicateurs clés avec leur
tendance sur 30 jours, les priorités du moment (documents à valider, échéances,
non-conformités critiques), les tâches personnelles selon le rôle de chacun, et la
tendance des non-conformités sur 6 mois. Aucun chiffre n'y est inventé : ce qui n'est
pas encore mesurable est explicitement marqué "à venir" plutôt que remplacé par une
fausse donnée.

---

## 4. Ce qui reste à construire

Présenté ici du point de vue métier — le chiffrage détaillé est en section 6.

| Fonctionnalité | Pourquoi c'est important | État |
|---|---|---|
| **Risques & opportunités** | Cœur de l'approche par les risques introduite par ISO 9001:2015 (clause 6.1) — l'une des premières choses qu'un auditeur demande à voir | Non construit |
| **Objectifs qualité & indicateurs** | Sans objectifs formalisés avec cible/échéance/responsable, impossible de démontrer le pilotage exigé en clause 6.2 | Non construit |
| **Revue de direction** | Rendez-vous obligatoire de la clause 9.3 — synthèse de la performance du SMQ devant la direction | Moteur technique déjà disponible, intégration en cours |
| **Compétences & formations** | Démonstration de la maîtrise des compétences requises par poste (clause 7.2) | Brique technique déjà disponible, à relier au SMQ |
| **Fournisseurs & partenaires** | Évaluation et qualification des prestataires externes (clause 8.4) | Non construit |
| **Réclamations clients** | Pas une clause isolée, mais le scénario que tout dirigeant teste spontanément en démonstration | Non construit |
| **Gestion des changements** | Traçabilité des modifications ayant un impact sur le SMQ (clause 6.3) | Non construit |
| **Amélioration continue formalisée** | Aujourd'hui démontrable via les briques existantes (tendance NC + actions), mais sans module dédié | Partiel |

---

## 5. La vision : une seule plateforme, tous les secteurs

L'ambition de DotQuality n'est pas de livrer *un* logiciel qualité, mais *une
plateforme* : le même socle, configuré différemment selon l'entreprise qui l'utilise.

```
Entreprise A → Secteur Industrie   → ISO 9001  → Modules industriels activés
Entreprise B → Secteur Formation   → ISO 21001 → Modules pédagogiques activés
                    ↓
        Les deux sur la même plateforme, sans duplication de code
```

Concrètement, une entreprise pourra définir :
- son secteur d'activité, ses sites, ses départements, ses activités ;
- son périmètre de certification et le ou les référentiels applicables ;
- les objectifs, risques, indicateurs et workflows propres à son contexte ;
- les rôles et responsabilités adaptés à son organisation ;

puis activer uniquement les modules pertinents pour elle — un centre de formation
n'a pas besoin des mêmes modules qu'un site industriel, mais tous deux s'appuient sur
le même moteur SMQ.

**Où en est cette vision aujourd'hui** : les fondations de données (organisation,
périmètre, référentiels — section 2) sont posées. La pièce qui manque est le **moteur
de configuration** : le mécanisme qui active/désactive réellement des modules et
adapte l'interface par entreprise, plutôt qu'une navigation identique pour tout le
monde. C'est le principal chantier de la phase suivante.

---

## 6. Feuille de route commerciale

| Palier | Ce qu'il débloque commercialement | Effort estimé* |
|---|---|---|
| **Palier 1 — MVP pilote** | Vendre à un premier client, secteur unique : comble les clauses ISO 9001 encore vides (risques, objectifs, compétences, fournisseurs, revue de direction, réclamations) | ≈ 5-6 semaines |
| **Palier 2 — Produit complet** | Vendre en série à plusieurs clients d'un même secteur : ajoute gestion des changements, amélioration continue, durcissement sécurité, documentation utilisateur, anglais | ≈ 15-18 semaines |
| **Palier 3 — Plateforme multi-secteurs** | Vendre la plateforme elle-même, adaptable à n'importe quel secteur : moteur de configuration, catalogue de modules sectoriels | ≈ 24-39 semaines |

*Effort avec développement assisté par IA sous supervision humaine continue (revue
d'architecture, arbitrages métier, tests) — le détail complet, y compris l'équivalent
en développement manuel classique, est disponible dans la note de chiffrage dédiée.

---

## 7. Messages clés à retenir

- DotQuality n'est pas une maquette : c'est un **prototype fonctionnel et testé**,
  avec un vrai workflow documentaire et une vraie boucle qualité.
- **8 exigences ISO 9001 sur 16** sont déjà pleinement couvertes, dont les plus
  lourdes à mettre en œuvre (maîtrise documentaire, non-conformités/actions, audits).
- Les manques sont **identifiés clause par clause**, pas découverts au hasard — et
  chiffrés précisément.
- L'architecture est pensée **depuis le premier jour** pour devenir une plateforme
  multi-secteurs, pas juste un logiciel pour un client unique.
- La prochaine étape critique n'est pas une fonctionnalité isolée, mais le **moteur
  de configuration** qui transforme un bon produit qualité en véritable plateforme.
