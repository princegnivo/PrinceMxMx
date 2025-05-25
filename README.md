# Telegram Multi-Account Group Member Manager

Script Python ultra-sûr et interactif pour gérer l'ajout de membres entre groupes Telegram en utilisant plusieurs comptes.

---

## Fonctionnalités

- Gestion multi-comptes Telegram (ajout, mise à jour, reconnexion, correction erreurs)
- Affichage de l'état des comptes (connexion, erreurs, nombre d'ajouts)
- Choix interactif des groupes source et cible parmi tous les groupes accessibles d’un compte
- Ajout des membres actifs récents (7 derniers jours)
- Rotation sécurisée entre comptes (10 membres max par compte, pauses longues aléatoires)
- Envoi automatique d'un lien d'invitation si le compte ne peut pas ajouter directement les membres (pas admin)
- Interface console simple et intuitive avec menu numéroté

---

## Prérequis

- Python 3.7+
- [Telethon](https://docs.telethon.dev/en/stable/) (`pip install telethon`)
- Création préalable de comptes Telegram avec `api_id` et `api_hash` (obtenus sur https://my.telegram.org)
- Être membre (ou admin) des groupes source et cible

---

## Installation

1. Cloner ce dépôt ou télécharger le fichier `telegram_group_multiaccount_manager.py`.
2. Installer Telethon (si ce n’est pas déjà fait) :
   ```
   pip install telethon
   ```
   
#####   Utilisation

Lancer le script :

```
python telegram_group_multiaccount_manager.py
```
Utiliser le menu pour :

Ajouter ou mettre à jour des comptes Telegram (api_id, api_hash, numéro)
Afficher l’état des comptes (statistiques, erreurs)
Choisir les groupes source et cible parmi ceux dont vous êtes membre
Mettre à jour et actualiser les comptes (connexion)
Lancer l’ajout des membres actifs récents du groupe source vers le groupe cible
Quitter proprement le programme
Suivre les instructions en console.

