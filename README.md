# Gestionnaire Telegram Multi-Comptes Ultra-Sûr et Optimisé

Ce gestionnaire Telegram multi-comptes est un script Python conçu pour automatiser la gestion des groupes Telegram avec une approche ultra-sûre, ultra-optimisée et robuste grâce à une interface console colorée. Il est compatible avec Python 3.7+ et utilise la bibliothèque Telethon pour les interactions avec Telegram.

---

## Fonctionnalités

- **Gestion multi-comptes** avec reconnexion et rotation automatique.
- **Correction complète** de la gestion du `datetime` en UTC, compatible Python 3.12+.
- **Interface console colorée ANSI** avec effacement de l’écran entre menus.
- **Choix interactif des groupes source et cible** parmi vos groupes Telegram.
- **Ajout des membres actifs récents** (derniers 7 jours) dans le groupe cible.
- **Rotation sécurisée des comptes** avec pauses aléatoires optimisées pour réduire les risques de blocage.
- **Envoi de lien d’invitation** si absence de droits d’admin dans le groupe cible.
- **Gestion avancée des erreurs** courantes (FloodWait, restrictions de confidentialité).
- **Sauvegarde automatique** des sessions et comptes localement.
- **Caches des membres** pour éviter les appels Telegram redondants.
- **Retrait d’un compte Telegram** du gestionnaire.
- **Envoi de messages en masse** vers un groupe sélectionné.
- **Retrait automatique des membres inactifs** au-delà de 2 mois.
- **Option d’actualisation et correction du script**.

---

## Prérequis

- Python 3.7 ou supérieur
- Module [`Telethon`](https://github.com/LonamiWebs/Telethon)

---

## Installation

1. Clonez ou téléchargez ce script.
2. Installez Telethon si ce n’est pas déjà fait :

   ```bash
   pip install telethon
